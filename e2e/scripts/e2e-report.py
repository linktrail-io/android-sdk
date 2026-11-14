#!/usr/bin/env python3
"""E2E results report for the LinkTrail Android SDK (Maestro flows).

Two subcommands, stdlib only:

  record  appends one JSON line per flow to a results file. Called by scripts/e2e-maestro.sh after
          each flow (pass, fail or skipped).
  render  turns the results + scripts/e2e-flows.json (the single source of Link / Match / Consent /
          Expected per flow) into report.md (GitHub step summary and sticky PR comment),
          report.json and report.html.

Same layout as the iOS SDK's scripts/e2e-report.py (headline, context line, columns, symbols,
"Failed flows" sections), so both platforms' reports read alike; only the platform's own values
(Link / Match / Expected) differ.

Everything rendered is redacted: SDK keys (lt_live_… / lt_test_…) become "[redacted API key]", the
values of LINKTRAIL_KEY and E2E_TOKEN and X-API-Key / X-E2E-Token header values
become "[redacted]"; click tokens show as the first 4 chars plus "…".
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
from pathlib import Path

MARKER = "<!-- linktrail-e2e-report -->"
COLUMNS = ["Flow", "Link", "Link type", "Match", "Consent", "Expected", "Result", "Attempts",
           "Backend install recorded", "Duration"]
SECRET_ENV = ("LINKTRAIL_KEY", "E2E_TOKEN")
LOG_TAIL = 30
# GitHub rejects comments over 65536 characters; keep a margin for the marker and the note.
MAX_MARKDOWN = 60000

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_SDK_KEY = re.compile(r"\blt_(live|test)_[A-Za-z0-9_\-]+")
_API_KEY_HEADER = re.compile(r"(?i)(x-api-key|x-e2e-token)(\s*[:=]\s*)[^\s,;)[\]'\"]+")
_TOKEN = re.compile(r"(?<![0-9a-fA-F])([0-9a-f]{4})[0-9a-f]{28}(?![0-9a-fA-F])")
_CLICK_PARAM = re.compile(r"(lt_click=)([A-Za-z0-9_\-]{4})[A-Za-z0-9_\-]+")
PLATFORM = "Android SDK e2e"


# ── Redaction ────────────────────────────────────────────────────────────────────────────────

def secret_values(env=None) -> list[str]:
    env = os.environ if env is None else env
    return [v for v in (env.get(k, "") for k in SECRET_ENV) if len(v) >= 6]


def redact(text, secrets=()) -> str:
    """Hide secrets and shorten click tokens. Safe on None and non-strings."""
    if text is None:
        return ""
    s = str(text)
    for value in sorted(secrets, key=len, reverse=True):
        s = s.replace(value, "[redacted]")
    s = _API_KEY_HEADER.sub(lambda m: f"{m.group(1)}{m.group(2)}[redacted]", s)
    s = _SDK_KEY.sub("[redacted API key]", s)
    s = _CLICK_PARAM.sub(lambda m: f"{m.group(1)}{m.group(2)}…", s)
    s = _TOKEN.sub(lambda m: f"{m.group(1)}…", s)
    return s


def short_token(token) -> str:
    token = (token or "").strip()
    return f"{token[:4]}…" if token else ""


# ── record ───────────────────────────────────────────────────────────────────────────────────

def failed_step(maestro_output: str) -> str:
    """The Maestro command that failed, e.g. 'Assert that "X" is visible', from its CLI output."""
    last = ""
    for raw in maestro_output.splitlines():
        line = _ANSI.sub("", raw).strip()
        if line.endswith("FAILED") and len(line) > len("FAILED"):
            last = line
    if not last:
        return ""
    last = re.sub(r"[.\s]*FAILED$", "", last)
    return re.sub(r"^[^\w\"']+\s*", "", last).strip()


CHECK_RESULTS = ("pass", "fail", "skipped")
CHECK_ICON = {"pass": "✅", "fail": "❌", "skipped": "⏭️ skipped"}
CHECK_DETAIL_MAX = 400


def load_checks(path) -> list[dict]:
    """The row's per-check results (scripts/e2e-maestro.sh: name<TAB>pass|fail|skipped<TAB>detail per
    line) → [{name, result, detail}]; a bad line is dropped, a missing file is no checks."""
    p = Path(path) if path else None
    if not p or not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t", 2)
        if len(parts) >= 2 and parts[0].strip() and parts[1] in CHECK_RESULTS:
            out.append({"name": parts[0].strip(), "result": parts[1],
                        "detail": parts[2].strip() if len(parts) > 2 else ""})
    return out


def cmd_record(a) -> int:
    step = a.step or ""
    if a.maestro_out and Path(a.maestro_out).is_file():
        step = failed_step(Path(a.maestro_out).read_text(errors="replace")) or step
    row = {
        "flow": a.flow,
        "suite": a.suite,
        "result": a.result,
        "attempts": a.attempts,
        "duration_s": round(a.duration, 1),
        "backend": a.backend,
        "failed_step": step if a.result == "fail" else "",
        "error": a.error if a.result == "fail" else "",
        # What the backend check saw (install, reward, earning, opens), on pass and on fail.
        "backend_detail": a.backend_detail,
        "log": a.log or "",
        "debug_dir": a.debug_dir or "",
        "click": short_token(a.token),
        "version_code": a.version_code or "",
        "link_url": (a.link or "").strip(),
        "link_type": (a.link_type or "").strip(),
        "note": a.error if a.result == "skipped" else "",
        # The newer backend checks one by one (fraud, link type, events / revenue, device lookup).
        "checks": load_checks(a.checks_file),
    }
    path = Path(a.results)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return 0


# ── render ───────────────────────────────────────────────────────────────────────────────────

def load_results(path) -> list[dict]:
    p = Path(path) if path else None
    if not p or not p.is_file():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def load_flows(path) -> dict:
    """scripts/e2e-flows.json (a 'flows' list, as on iOS) → {flow name: entry}."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    flows = data.get("flows") if isinstance(data, dict) else None
    if not isinstance(flows, list) or not flows:
        raise ValueError(f"{path}: expected a non-empty 'flows' list")
    for f in flows:
        for key in ("flow", "suite", "link", "match", "consent", "expected"):
            if not isinstance(f.get(key), str) or not f[key]:
                raise ValueError(f"{path}: flow entry {f.get('flow')!r} is missing '{key}'")
    return {f["flow"]: f for f in flows}


def split_matrix_name(name) -> tuple[str, str]:
    """'<flow>__<type>' (a link-type matrix row) → (flow, type); any other name → (name, '')."""
    base, sep, link_type = (name or "").partition("__")
    return (base, link_type) if sep and base and link_type else (name or "", "")


def flow_meta(flows, name) -> dict:
    """A flow's metadata; a link-type row (<flow>__<type>) uses its flow's entry, with Expected taken
    from 'link_type_expected' when the flow has one."""
    if name in flows:
        return flows[name]
    base, link_type = split_matrix_name(name)
    m = flows.get(base) if link_type else None
    if not m or not m.get("link_type_matrix"):
        return {}
    return dict(m, expected=m.get("link_type_expected") or m["expected"])


def log_tail(path, n=LOG_TAIL) -> list[str]:
    if not path or not Path(path).is_file():
        return []
    lines = [l for l in Path(path).read_text(errors="replace").splitlines() if "LinkTrail" in l]
    return lines[-n:]


def load_expect_defaults(path) -> dict:
    """expect.{product,voucher} and link_type_expect.{product,voucher,source} from scripts/e2e-env.json
    (the latter as lt_*); empty when the file is missing/bad."""
    empty = {"product": "", "voucher": "", "lt_product": "", "lt_voucher": "", "lt_source": ""}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        exp = data.get("expect") or {}
        lte = data.get("link_type_expect") or {}
        return {"product": str(exp.get("product") or ""), "voucher": str(exp.get("voucher") or ""),
                "lt_product": str(lte.get("product") or ""), "lt_voucher": str(lte.get("voucher") or ""),
                "lt_source": str(lte.get("source") or "")}
    except (OSError, ValueError, AttributeError):
        return empty


def fill_expected(text, product="", voucher="", link_type="", source="") -> str:
    """e2e-flows.json 'expected' with {product} / {voucher} (and, on link-type rows, {type} /
    {source}) filled from the run's expectations."""
    product = f"product {product}" if product else "product"
    return (str(text).replace("{product}", product).replace("{voucher}", voucher or "the expected")
            .replace("{type}", link_type or "the type").replace("{source}", source or "the expected"))


def row_expected(m, meta, link_type="") -> str:
    """Expected for a row: link-type rows (and flows with expect_from link_type_expect) use
    link_type_expect (lt_*), the others the run's expect."""
    if link_type or m.get("expect_from") == "link_type_expect":
        return fill_expected(m.get("expected", "(no entry in scripts/e2e-flows.json)"),
                             meta.get("lt_product") or "", meta.get("lt_voucher") or "",
                             link_type, meta.get("lt_source") or "")
    return fill_expected(m.get("expected", "(no entry in scripts/e2e-flows.json)"),
                         meta.get("expect_product") or "", meta.get("expect_voucher") or "")


def link_text(kind, url) -> str:
    """The Link cell: the link kind plus the exact URL tested, when the flow used one."""
    return f"{kind}: {url}" if url else kind


def fmt_duration(seconds) -> str:
    try:
        s = int(round(float(seconds)))
    except (TypeError, ValueError):
        return "—"
    return f"{s}s" if s < 60 else f"{s // 60}m {s % 60:02d}s"


RESULT_ICON = {"pass": "✅", "fail": "❌", "skipped": "⏭️ skipped", "not_run": "⏭️ not run"}
BACKEND_ICON = {"ok": "✅", "fail": "❌"}


def result_text(f) -> str:
    """The Result cell; a skipped row with a reason says why (e.g. no prod link yet)."""
    text = RESULT_ICON.get(f["result"], f["result"])
    return f"{text} ({f['note']})" if f["result"] == "skipped" and f.get("note") else text


def backend_cell(value) -> str:
    """✅ the backend check matched, ❌ it did not, — not applicable / not reached / no E2E_TOKEN."""
    return BACKEND_ICON.get(value or "", "—")


def sdk_error(lines) -> str:
    """The SDK's last [ERROR] line without the logcat prefix, e.g. 'Install tracking failed: …'."""
    for line in reversed(lines):
        if "[ERROR]" in line:
            return line.split("[ERROR]", 1)[1].strip()
    return ""


def build_report(rows, flows, meta, suites=(), secrets=(), link_types=()) -> dict:
    """Merge results with flow metadata. Flows of a listed suite with no row are 'not_run'."""
    seen, out = set(), []
    for r in rows:
        name = r.get("flow", "")
        seen.add(name)
        m = flow_meta(flows, name)
        link_type = r.get("link_type", "") or split_matrix_name(name)[1]
        result = r.get("result", "fail")
        failed = result == "fail"
        tail = [redact(l, secrets) for l in log_tail(r.get("log"))] if failed else []
        out.append({
            "flow": name,
            "suite": r.get("suite") or m.get("suite", ""),
            "link": link_text(m.get("link", "?"), redact(r.get("link_url", ""), secrets)),
            "link_url": redact(r.get("link_url", ""), secrets),
            "link_type": link_type,
            "note": redact(r.get("note", ""), secrets),
            "match": m.get("match", "?"),
            "consent": m.get("consent", "?"),
            "expected": row_expected(m, meta, link_type),
            "result": result,
            "attempts": r.get("attempts", 0),
            "backend": r.get("backend", "n/a"),
            "backend_detail": redact(r.get("backend_detail", ""), secrets),
            "duration_s": r.get("duration_s"),
            "failed_attempt": r.get("attempts") if failed else None,
            "failed_step": redact(r.get("failed_step", ""), secrets),
            "error": redact(r.get("error") or (sdk_error(tail) if failed else ""), secrets),
            "click": redact(r.get("click", ""), secrets),
            "debug_dir": r.get("debug_dir", ""),
            "version_code": r.get("version_code", ""),
            "log_tail": tail,
            "checks": [{"name": redact(c.get("name", ""), secrets), "result": c.get("result", ""),
                        "detail": redact(c.get("detail", ""), secrets)}
                       for c in (r.get("checks") or []) if isinstance(c, dict) and c.get("result") in CHECK_RESULTS],
        })
    # A link_type_only flow has no plain row: only its <flow>__<type> rows can be due.
    missing = [(name, m, "") for name, m in flows.items()
               if m.get("suite") in suites and name not in seen and not m.get("link_type_only")]
    # Link-type rows of the types that ran (<flow>__<type>), in the runner's order: type by type.
    for t in link_types:
        for base, m in flows.items():
            name = f"{base}__{t}"
            if m.get("link_type_matrix") and name not in seen:
                missing.append((name, flow_meta(flows, name), t))
    for name, m, link_type in missing:
        out.append({"flow": name, "suite": m["suite"], "link": m["link"], "link_url": "",
                    "link_type": link_type, "note": "", "match": m["match"],
                    "consent": m["consent"], "expected": row_expected(m, meta, link_type),
                    "result": "not_run",
                    "attempts": 0, "backend": "n/a", "backend_detail": "", "duration_s": None,
                    "failed_attempt": None, "failed_step": "", "error": "", "click": "",
                    "debug_dir": "", "version_code": "", "log_tail": [], "checks": []})
    counted = [f for f in out if f["result"] != "skipped"]
    passed = sum(f["result"] == "pass" for f in counted)
    failed_n = sum(f["result"] == "fail" for f in counted)
    not_run = sum(f["result"] == "not_run" for f in counted)
    status = "no_results" if not rows else ("passed" if passed == len(counted) else "failed")
    return {
        "status": status,
        "meta": {k: redact(v, secrets) for k, v in meta.items()},
        "totals": {"passed": passed, "total": len(counted), "failed": failed_n, "not_run": not_run,
                   "skipped": len(out) - len(counted)},
        "flows": out,
    }


def _cell(text) -> str:
    return str(text).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def headline(rep) -> str:
    t, title = rep["totals"], rep["meta"].get("title") or PLATFORM
    if rep["status"] == "no_results":
        return f"⚠️ {title}: no results (job failed before flows)"
    icon = "✅" if rep["status"] == "passed" else "❌"
    line = f"{icon} {title}: {t['passed']}/{t['total']} passed"
    if t["not_run"]:
        line += f", {t['not_run']} not run"
    if t["skipped"]:
        line += f", {t['skipped']} skipped"
    return line


def context_line(rep) -> str:
    m = rep["meta"]
    commit = m.get("commit") or "unknown"
    parts = [f"**Environment:** `{m.get('environment') or 'unknown'}`",
             f"**Backend:** `{m.get('backend_url') or 'unknown'}`",
             f"**Commit:** `{commit[:7] if re.fullmatch(r'[0-9a-f]{40}', commit) else commit}`",
             f"**Runner:** `{m.get('runner') or 'unknown'}`"]
    if m.get("run_url"):
        parts.append(f"[run summary]({m['run_url']})")
    return " · ".join(parts)


# Kept for the job log line printed by cmd_render.
def totals_line(rep) -> str:
    return headline(rep) + " — " + context_line(rep)


def screenshot_text(f, m) -> str:
    if not f.get("debug_dir"):
        return "none captured"
    name = m.get("artifact_name") or "maestro-debug"
    url = m.get("artifact_url") or (f"{m['run_url']}#artifacts" if m.get("run_url") else "")
    where = f"the [`{name}` artifact]({url})" if url else f"the `{name}` artifact"
    return f"`{f['debug_dir']}/` in {where}"


def check_rows(rep) -> list[tuple[str, dict]]:
    """(flow, check) for every per-check result, in the flows' order."""
    return [(f["flow"], c) for f in rep["flows"] for c in f.get("checks") or []]


def _short(text, n=CHECK_DETAIL_MAX) -> str:
    text = str(text)
    return text if len(text) <= n else text[:n - 1] + "…"


def checks_markdown(rep) -> list[str]:
    """The "Backend checks" table: one row per newer check of each flow (fraud, link type, events /
    revenue, device lookup), so a skipped or failed one is visible on its own."""
    rows = check_rows(rep)
    if not rows:
        return []
    out = ["### Backend checks", "", "| Flow | Check | Result | Detail |", "|---|---|---|---|"]
    for flow, c in rows:
        out.append("| " + " | ".join(_cell(x) for x in (f"`{flow}`", c["name"], CHECK_ICON.get(c["result"], c["result"]),
                                                           _short(c["detail"]) or "—")) + " |")
    return out + [""]


def render_markdown(rep) -> str:
    out = [rep["meta"].get("marker") or MARKER, "## " + headline(rep), "", context_line(rep), ""]
    if rep["status"] == "no_results":
        out += ["No flow recorded a result: the job stopped before the Maestro flows ran (the key check, "
                "the emulator, or the app build). See the job log.", ""]
        return "\n".join(out)
    out += ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    for f in rep["flows"]:
        out.append("| " + " | ".join(_cell(c) for c in (
            f"`{f['flow']}`", f["link"], f.get("link_type") or "—", f["match"], f["consent"], f["expected"],
            result_text(f), f["attempts"], backend_cell(f["backend"]),
            fmt_duration(f["duration_s"]) if f["attempts"] else "—")) + " |")
    out.append("")
    out += checks_markdown(rep)
    versions = [f"`{f['flow']}` `{f['version_code']}`" for f in rep["flows"] if f.get("version_code")]
    if versions:
        out += ["**Installed versionCode:** " + " · ".join(versions), ""]
    failed = [f for f in rep["flows"] if f["result"] == "fail"]
    if failed:
        out += ["### Failed flows", ""]
        for f in failed:
            out += [f"#### ❌ `{f['flow']}` (attempt {f.get('failed_attempt') or '?'} of {f['attempts']})", "",
                    "- **Failed step:** " + (_cell(f["failed_step"]) if f["failed_step"] else "unknown")]
            if f["error"]:
                out.append("- **Error:** " + _cell(f["error"]))
            if f["backend_detail"] and f["backend"] == "fail":
                out.append("- **Backend check:** " + _cell(f["backend_detail"]))
            out.append("- **Screenshot:** " + screenshot_text(f, rep["meta"]))
            tail = f["log_tail"]
            out += ["", f"<details><summary>Last {len(tail)} <code>[LinkTrail]</code> log lines</summary>", "",
                    "```text"]
            out += [l.replace("```", "\'\'\'") for l in tail] or ["(no [LinkTrail] lines captured)"]
            out += ["```", "", "</details>", ""]
    md = "\n".join(out)
    if len(md) > MAX_MARKDOWN:
        md = md[:MAX_MARKDOWN] + "\n\n_Report truncated; the full version is in the `e2e-report` artifact._\n"
    return md


def render_html(rep) -> str:
    e = html.escape
    title = rep["meta"].get("title") or PLATFORM
    rows = "".join(
        "<tr>" + "".join(f"<td>{e(str(c))}</td>" for c in (
            f["flow"], f["link"], f.get("link_type") or "—", f["match"], f["consent"], f["expected"],
            result_text(f), f["attempts"], backend_cell(f["backend"]),
            fmt_duration(f["duration_s"]) if f["attempts"] else "—")) + "</tr>"
        for f in rep["flows"])
    fails = "".join(
        f"<h3>&#10060; <code>{e(f['flow'])}</code> (attempt {e(str(f.get('failed_attempt') or '?'))} of {e(str(f['attempts']))})</h3>"
        f"<ul><li><b>Failed step:</b> {e(f['failed_step'] or 'unknown')}</li>"
        + (f"<li><b>Error:</b> {e(f['error'])}</li>" if f["error"] else "")
        + (f"<li><b>Backend check:</b> {e(f['backend_detail'])}</li>" if f["backend_detail"] and f["backend"] == "fail" else "")
        + (f"<li><b>Click:</b> <code>lt_click={e(f['click'])}</code></li>" if f["click"] else "")
        + f"<li><b>Screenshot:</b> {e(f['debug_dir'] + '/' if f['debug_dir'] else 'none captured')}</li></ul>"
        + f"<pre>{e(chr(10).join(f['log_tail']) or '(no [LinkTrail] lines captured)')}</pre>"
        for f in rep["flows"] if f["result"] == "fail")
    head = "".join(f"<th>{e(c)}</th>" for c in COLUMNS)
    crow = "".join(f"<tr><td>{e(flow)}</td><td>{e(c['name'])}</td><td>{e(CHECK_ICON.get(c['result'], c['result']))}</td>"
                   f"<td>{e(_short(c['detail']) or '—')}</td></tr>" for flow, c in check_rows(rep))
    checks = ("<h2>Backend checks</h2><table><thead><tr><th>Flow</th><th>Check</th><th>Result</th><th>Detail</th></tr>"
              f"</thead><tbody>{crow}</tbody></table>") if crow else ""
    table = (f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>" if rep["flows"]
             else "<p>No flow recorded a result: the job stopped before the Maestro flows ran.</p>")
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><title>{e(title)} report</title>"
            "<style>body{font-family:system-ui,sans-serif;margin:2rem}table{border-collapse:collapse}"
            "td,th{border:1px solid #ccc;padding:4px 8px;text-align:left;vertical-align:top}"
            "pre{background:#f6f8fa;padding:8px;overflow:auto}</style></head><body>"
            f"<h1>{e(headline(rep))}</h1>"
            f"<p>Environment <code>{e(rep['meta'].get('environment') or 'unknown')}</code> &middot; backend "
            f"<code>{e(rep['meta'].get('backend_url') or 'unknown')}</code> &middot; commit "
            f"<code>{e((rep['meta'].get('commit') or 'unknown')[:7])}</code> &middot; runner "
            f"<code>{e(rep['meta'].get('runner') or 'unknown')}</code></p>"
            + table + checks + (f"<h2>Failed flows</h2>{fails}" if fails else "") + "</body></html>\n")


def _append_summary(path, md) -> None:
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(md if md.endswith("\n") else md + "\n")


def cmd_render(a) -> int:
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if a.skipped:
        # Same one-liner as iOS, e.g. "e2e skipped: docs-only change".
        md = f"{a.marker}\ne2e skipped: {a.skipped}\n"
        (out / "report.md").write_text(md, encoding="utf-8")
        (out / "report.json").write_text(json.dumps(
            {"status": "skipped", "reason": a.skipped, "commit": a.commit or "unknown"}, indent=2) + "\n",
            encoding="utf-8")
        _append_summary(a.summary, md)
        print(f"e2e skipped: {a.skipped}")
        return 0
    secrets = secret_values()
    defaults = load_expect_defaults(a.env_config)
    meta = {"title": a.title, "environment": a.environment, "backend_url": a.backend_url,
            "expect_product": a.expect_product or defaults["product"],
            "expect_voucher": a.expect_voucher or defaults["voucher"],
            "lt_product": defaults["lt_product"], "lt_voucher": defaults["lt_voucher"],
            "lt_source": defaults["lt_source"],
            "commit": a.commit, "runner": a.runner,
            "run_url": a.run_url, "artifact_url": a.artifact_url, "artifact_name": a.artifact_name,
            "marker": a.marker, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    suites = tuple(s for s in (a.suites or "").split(",") if s)
    link_types = tuple(t for t in (a.link_types or "").split(",") if t)
    rep = build_report(load_results(a.results), load_flows(a.flows), meta, suites, secrets, link_types)
    md = render_markdown(rep)
    (out / "report.md").write_text(md, encoding="utf-8")
    (out / "report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "report.html").write_text(render_html(rep), encoding="utf-8")
    _append_summary(a.summary, md)
    print(totals_line(rep))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("record", help="append one flow result")
    r.add_argument("--results", required=True)
    r.add_argument("--flow", required=True)
    r.add_argument("--suite", required=True, choices=["simulated", "real", "play"])
    r.add_argument("--result", required=True, choices=["pass", "fail", "skipped"])
    r.add_argument("--attempts", type=int, default=0)
    r.add_argument("--duration", type=float, default=0.0)
    r.add_argument("--backend", default="n/a", choices=["ok", "fail", "n/a"],
                   help="backend install check: ok (matched), fail (did not), n/a (not applicable / not reached / no E2E_TOKEN)")
    r.add_argument("--backend-detail", default="")
    r.add_argument("--step", default="")
    r.add_argument("--error", default="")
    r.add_argument("--maestro-out", default="")
    r.add_argument("--log", default="")
    r.add_argument("--debug-dir", default="")
    r.add_argument("--token", default="")
    r.add_argument("--version-code", default="", help="versionCode the device actually installed")
    r.add_argument("--link", default="", help="the exact link URL the flow tested")
    r.add_argument("--link-type", default="", help="link-type matrix rows (<flow>__<type>): the link type (general, campaign, …)")
    r.add_argument("--checks-file", default="",
                   help="the row's per-check results, name<TAB>pass|fail|skipped<TAB>detail per line")
    r.set_defaults(fn=cmd_record)

    g = sub.add_parser("render", help="write report.md/json/html")
    g.add_argument("--results", default="")
    g.add_argument("--flows", default=str(Path(__file__).with_name("e2e-flows.json")))
    g.add_argument("--out-dir", required=True)
    g.add_argument("--summary", default="", help="append the Markdown here (e.g. $GITHUB_STEP_SUMMARY)")
    g.add_argument("--suites", default="", help="comma list; flows of these suites without a result show as not run")
    g.add_argument("--link-types", default="", help="comma list of link types run; their rows without a result show as not run")
    g.add_argument("--title", default=PLATFORM)
    g.add_argument("--marker", default=MARKER,
                   help="first line, finds the sticky PR comment")
    g.add_argument("--skipped", default="", help="write only 'e2e skipped: <reason>' (e.g. docs-only change)")
    g.add_argument("--environment", default="")
    g.add_argument("--backend-url", default="", help="the environment's backend base URL (header line)")
    g.add_argument("--expect-product", default="", help="expect_product of the run ({product} in 'expected')")
    g.add_argument("--expect-voucher", default="", help="expect_voucher of the run (default: scripts/e2e-env.json)")
    g.add_argument("--env-config", default=str(Path(__file__).with_name("e2e-env.json")))
    g.add_argument("--commit", default="")
    g.add_argument("--runner", default="")
    g.add_argument("--run-url", default="")
    g.add_argument("--artifact-url", default="")
    g.add_argument("--artifact-name", default="maestro-debug")
    g.set_defaults(fn=cmd_render)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
