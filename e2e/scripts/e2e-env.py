#!/usr/bin/env python3
"""Resolve the e2e environment and the links to test. Stdlib only.

Reads scripts/e2e-env.json (the one table of hosts, slugs and backend URLs) and the run's choices
from the environment:

  LINKTRAIL_ENV                 dev | prod (empty = the file's default_environment; test = dev)
  E2E_CUSTOM_LINK               \\
  E2E_SUBDOMAIN_LINK             | each a full URL (https://<host>/<slug>) or a bare slug;
  E2E_CUSTOM_PROBLISTIC_LINK     | empty = the slot's default slug on the environment's host
  E2E_SUBDOMAIN_PROBLISTIC_LINK /
  E2E_LINK_TYPES                link-type matrix: all (default), none, or a comma list (general,partner)
  E2E_EXPECT_PRODUCT            product name the click-token flows must show (empty = any product)
  E2E_EXPECT_VOUCHER            voucher code they must show (empty = the file's default)

and prints the resolved values, one per line:

  resolve --format shell   KEY='value' lines for `eval` (scripts/e2e-maestro.sh)
  resolve --format env     KEY=value lines for $GITHUB_ENV / $GITHUB_OUTPUT

Link types (scripts/e2e-env.json link_types: type -> environment -> {host, slug}): E2E_LINK_TYPES_RUN
lists the selected types that have a link in this environment (E2E_LINK_TYPE_<TYPE> is its URL);
E2E_LINK_TYPES_SKIPPED the selected types that have none here (prod until its links exist): skipped
with a notice, not an error. E2E_LT_* is link_type_expect (what the allow runs must show) and
E2E_MATRIX_FLOWS the flows marked link_type_matrix in scripts/e2e-flows.json: each runs once more
per type, as <flow>__<type>; E2E_MATRIX_ONLY_FLOWS those of them also marked link_type_only (no
plain row, only the <flow>__<type> rows). E2E_REWARDED_LINK_TYPES is rewarded_link_types: the types
whose rows must show the backend's reward earned on allow and nothing on deny.
E2E_REWARD_LINK_PER_EVENT / _REV_SHARE are the reward_links of this environment (empty: none, the
deferred_event_* / deferred_revshare_* rows are skipped), E2E_REVENUE_MINOR / E2E_OTHER_EVENT the
reward_events those flows send; E2E_REWARD_LINK_TYPE_<MODEL> the link type of each reward link.
E2E_CHECK_EVENTS / E2E_CHECK_DEVICE_LOOKUP are the environment's backend_checks (1 deployed, 0 not
yet: that check is recorded as skipped, never pass or fail).

  prepare-flow --flow F --out O --link-type T --source S --consent allow|deny
                           writes the flow for one link-type run: allow adds the meta-linkType /
                           meta-source assertions; deny is unchanged (its check is the backend's)

A link whose host is not the environment's host for that slot, an unknown environment or a bad
voucher fails fast: exit 2 with one clear "ERROR: …" line on stderr (a ::error annotation in CI).
Resolving is idempotent: feeding the output back in gives the same output.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
import urllib.parse
from pathlib import Path

CONFIG = Path(__file__).with_name("e2e-env.json")
FLOWS = Path(__file__).with_name("e2e-flows.json")
SLOTS = ("custom_link", "subdomain_link", "custom_problistic_link", "subdomain_problistic_link")
HOST_FIELDS = ("subdomain_host", "custom_host")
_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._~-]{0,127}")
_VOUCHER = re.compile(r"[A-Za-z0-9_-]{1,64}")
_TYPE = re.compile(r"[a-z][a-z0-9_]{0,31}")
_EVENT = re.compile(r"[A-Za-z0-9_.:-]{1,64}")
# The event-based reward models with a dedicated e2e link (reward_links): the reward flows send events.
REWARD_MODELS = ("per_event", "rev_share")
# The newer verify-endpoint checks, deployed per environment (backend_checks): a false one is recorded
# as skipped ("not on <env> backend yet"), never pass or fail.
BACKEND_CHECKS = ("events", "device_lookup")
_HOST = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+")
# Java regex metacharacters (Maestro matches text selectors as Java regexes).
_REGEX_META = set("\\^$.|?*+()[]{}")


class TargetError(ValueError):
    """A choice that can't be resolved. The message is shown to the person who started the run."""


def env_var(slot: str) -> str:
    return "E2E_" + slot.upper()


def load_config(path=CONFIG) -> dict:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    envs = cfg.get("environments")
    if not isinstance(envs, dict) or not envs:
        raise TargetError(f"{path}: 'environments' must be a non-empty object")
    for name, e in envs.items():
        for key in ("backend_url", "key_secret", *HOST_FIELDS):
            if not isinstance(e.get(key), str) or not e[key]:
                raise TargetError(f"{path}: environment '{name}' is missing '{key}'")
        if not isinstance(e.get("override_backend"), bool):
            raise TargetError(f"{path}: environment '{name}' needs a boolean 'override_backend'")
        if not e["backend_url"].startswith("https://"):
            raise TargetError(f"{path}: environment '{name}' backend_url must be https")
        checks = e.get("backend_checks")
        if not isinstance(checks, dict) or set(checks) != set(BACKEND_CHECKS) \
                or any(not isinstance(checks[c], bool) for c in BACKEND_CHECKS):
            raise TargetError(f"{path}: environment '{name}' needs backend_checks with a boolean "
                              f"{', '.join(BACKEND_CHECKS)} (and nothing else)")
    if cfg.get("default_environment") not in envs:
        raise TargetError(f"{path}: default_environment must be one of {sorted(envs)}")
    for alias, target in (cfg.get("aliases") or {}).items():
        if target not in envs:
            raise TargetError(f"{path}: alias '{alias}' points at unknown environment '{target}'")
    links = cfg.get("links") or {}
    if set(links) != set(SLOTS):
        raise TargetError(f"{path}: 'links' must define exactly {list(SLOTS)}")
    for slot, link in links.items():
        if link.get("host") not in HOST_FIELDS or not _SLUG.fullmatch(link.get("slug") or ""):
            raise TargetError(f"{path}: link '{slot}' needs host in {list(HOST_FIELDS)} and a valid slug")
    lt = cfg.get("link_types")
    if not isinstance(lt, dict):
        raise TargetError(f"{path}: 'link_types' must be an object (type -> environment -> link)")
    for t, per_env in lt.items():
        if t.startswith("_"):
            continue
        if not _TYPE.fullmatch(t) or not isinstance(per_env, dict):
            raise TargetError(f"{path}: link_types: type '{t}' needs a lower-case name and an object per environment")
        for env_name, link in per_env.items():
            if env_name not in envs:
                raise TargetError(f"{path}: link_types.{t}: unknown environment '{env_name}'")
            if not isinstance(link, dict) or link.get("host") not in HOST_FIELDS or not _SLUG.fullmatch(link.get("slug") or ""):
                raise TargetError(f"{path}: link_types.{t}.{env_name} needs host in {list(HOST_FIELDS)} and a valid slug")
    if any(not t.startswith("_") for t in lt):
        lte = cfg.get("link_type_expect")
        if not isinstance(lte, dict):
            raise TargetError(f"{path}: link_type_expect must be an object with product, voucher and source")
        if not _VOUCHER.fullmatch(lte.get("voucher") or ""):
            raise TargetError(f"{path}: link_type_expect.voucher must be a voucher code")
        if not _VOUCHER.fullmatch(lte.get("source") or ""):
            raise TargetError(f"{path}: link_type_expect.source must be letters, digits, '-' or '_'")
        product = lte.get("product")
        if not isinstance(product, str) or not product.strip() or len(product) > 100 \
                or any(c in product for c in "\r\n\t") or "${" in product:
            raise TargetError(f"{path}: link_type_expect.product must be the product name (one line, at most 100 characters)")
    rewarded = cfg.get("rewarded_link_types", [])
    known = [t for t in lt if not t.startswith("_")]
    if not isinstance(rewarded, list) or any(not isinstance(t, str) or t not in known for t in rewarded) \
            or len(set(rewarded)) != len(rewarded):
        raise TargetError(f"{path}: rewarded_link_types must be a list of distinct link types from link_types ({', '.join(known) or 'none'})")
    rl = cfg.get("reward_links", {})
    if not isinstance(rl, dict) or set(rl) - set(REWARD_MODELS):
        raise TargetError(f"{path}: reward_links must be an object with keys from {list(REWARD_MODELS)}")
    for model, per_env in rl.items():
        if not isinstance(per_env, dict):
            raise TargetError(f"{path}: reward_links.{model} must be an object per environment")
        for env_name, link in per_env.items():
            if env_name not in envs or not isinstance(link, dict) or link.get("host") not in HOST_FIELDS \
                    or not _SLUG.fullmatch(link.get("slug") or ""):
                raise TargetError(f"{path}: reward_links.{model}.{env_name} needs a known environment, "
                                  f"host in {list(HOST_FIELDS)} and a valid slug")
            if link.get("link_type") not in known:
                raise TargetError(f"{path}: reward_links.{model}.{env_name} needs link_type, one of the "
                                  f"link_types ({', '.join(known) or 'none'}): the type the events check expects")
    if rl:
        rev = cfg.get("reward_events")
        if not isinstance(rev, dict) or not isinstance(rev.get("revenue_minor"), int) \
                or isinstance(rev.get("revenue_minor"), bool) or not 0 < rev["revenue_minor"] <= 10**9 \
                or not _EVENT.fullmatch(rev.get("other_event") or ""):
            raise TargetError(f"{path}: reward_events needs revenue_minor (a positive integer) and other_event (an event name)")
    if not _VOUCHER.fullmatch((cfg.get("expect") or {}).get("voucher") or ""):
        raise TargetError(f"{path}: expect.voucher must be a voucher code")
    return cfg


def resolve_environment(cfg: dict, requested: str) -> tuple[str, str]:
    """→ (canonical name, the name as requested). Empty = default; aliases map (test → dev)."""
    req = (requested or "").strip().lower()
    name = req or cfg["default_environment"]
    name = (cfg.get("aliases") or {}).get(name, name)
    if name not in cfg["environments"]:
        choices = sorted(set(cfg["environments"]) | set(cfg.get("aliases") or {}))
        raise TargetError(f"unknown e2e environment '{requested}': use one of {', '.join(choices)}")
    return name, req or name


def resolve_link(cfg: dict, env_name: str, slot: str, value: str) -> str:
    """A slot's input (empty, bare slug or full URL) → the https URL to test, validated."""
    env = cfg["environments"][env_name]
    host_field = cfg["links"][slot]["host"]
    host = env[host_field].lower()
    raw = (value or "").strip()
    where = f"{env_var(slot)} / {slot}"
    if not raw:
        return f"https://{host}/{cfg['links'][slot]['slug']}"
    if "://" not in raw:
        if "/" in raw or not _SLUG.fullmatch(raw):
            raise TargetError(f"{where}: '{raw}' is neither a slug nor a full URL "
                              f"(use a bare slug like 'summer-sale' or https://{host}/<slug>)")
        return f"https://{host}/{raw}"
    try:
        u = urllib.parse.urlsplit(raw)
        port = u.port
    except ValueError as exc:
        raise TargetError(f"{where}: '{raw}' is not a valid URL ({exc})") from None
    if u.scheme != "https":
        raise TargetError(f"{where}: '{raw}' must use https")
    if u.username or u.password or port is not None or u.query or u.fragment:
        raise TargetError(f"{where}: '{raw}' must be https://<host>/<slug> (no credentials, port, query or fragment)")
    got = (u.hostname or "").lower()
    if got != host:
        allowed = ", ".join(sorted({e[host_field] for e in cfg["environments"].values()}))
        raise TargetError(f"{where}: host '{got or '<none>'}' is not the {env_name} "
                          f"{host_field.replace('_', ' ')} '{host}' (known for this slot: {allowed}). "
                          f"Pick the matching environment or a {env_name} link.")
    slug = u.path[1:] if u.path.startswith("/") else ""
    if not _SLUG.fullmatch(slug):
        raise TargetError(f"{where}: '{raw}' needs exactly one path segment, the slug (https://{host}/<slug>)")
    return f"https://{host}/{slug}"


def known_link_types(cfg: dict) -> list[str]:
    """Every link type in the file, in file order."""
    return [t for t in cfg["link_types"] if not t.startswith("_")]


def resolve_link_types(cfg: dict, env_name: str, value: str) -> dict:
    """E2E_LINK_TYPES (all | none | comma list) → the selection, the runnable ones, their URLs and
    what their allow runs must show (link_type_expect)."""
    known = known_link_types(cfg)
    raw = (value or "").strip().lower()
    if raw in ("", "all"):
        selected = list(known)
    elif raw == "none":
        selected = []
    else:
        wanted = [x.strip() for x in raw.split(",") if x.strip()]
        unknown = [t for t in wanted if t not in known]
        if unknown:
            raise TargetError(f"E2E_LINK_TYPES / link_types: unknown link type '{','.join(unknown)}' "
                              f"(use all, none or a comma list of {', '.join(known) or 'no known types'})")
        if not wanted:
            raise TargetError("E2E_LINK_TYPES / link_types: empty list (use all, none or a comma list)")
        selected = [t for t in known if t in wanted]   # file order, no duplicates
    env = cfg["environments"][env_name]
    run = [t for t in selected if cfg["link_types"][t].get(env_name)]
    lte = cfg.get("link_type_expect") or {}
    out = {
        "E2E_LINK_TYPES": ",".join(selected) if selected else "none",
        "E2E_LINK_TYPES_RUN": ",".join(run),
        "E2E_LINK_TYPES_SKIPPED": ",".join(t for t in selected if t not in run),
        # What a link-type allow run must show: the product page of /products/aj1, the voucher, and the
        # debug meta row's source (next to linkType == the type).
        "E2E_LT_PRODUCT": lte.get("product", ""),
        "E2E_LT_PRODUCT_RE": java_regex_literal(lte.get("product", "")) if lte.get("product") else ".*",
        "E2E_LT_VOUCHER": lte.get("voucher", ""),
        "E2E_LT_SOURCE": lte.get("source", ""),
        # The types whose links carry a reward: their rows check the backend's earning (scripts/e2e-verify.py).
        "E2E_REWARDED_LINK_TYPES": ",".join(cfg.get("rewarded_link_types") or []),
    }
    for t in run:
        link = cfg["link_types"][t][env_name]
        out["E2E_LINK_TYPE_" + t.upper()] = f"https://{env[link['host']].lower()}/{link['slug']}"
    return out


def resolve_reward_links(cfg: dict, env_name: str) -> dict:
    """reward_links + reward_events → E2E_REWARD_LINK_<MODEL> (the URL; empty when this environment
    has none, so its rows are skipped), E2E_REWARD_SLUG_<MODEL> (for the "not created" message),
    E2E_REWARD_LINK_TYPE_<MODEL> (its link type), E2E_REVENUE_MINOR and E2E_OTHER_EVENT."""
    env = cfg["environments"][env_name]
    out = {}
    for model in REWARD_MODELS:
        link = (cfg.get("reward_links") or {}).get(model, {}).get(env_name)
        out["E2E_REWARD_LINK_" + model.upper()] = f"https://{env[link['host']].lower()}/{link['slug']}" if link else ""
        out["E2E_REWARD_SLUG_" + model.upper()] = link["slug"] if link else ""
        # The link's type: the events check expects it as the click's linkType.
        out["E2E_REWARD_LINK_TYPE_" + model.upper()] = link["link_type"] if link else ""
    rev = cfg.get("reward_events") or {}
    out["E2E_REVENUE_MINOR"] = str(rev.get("revenue_minor", ""))
    out["E2E_OTHER_EVENT"] = rev.get("other_event", "")
    return out


def matrix_flows(flows_path=FLOWS) -> list[str]:
    """The flows that also run once per link type ('link_type_matrix' in scripts/e2e-flows.json)."""
    data = json.loads(Path(flows_path).read_text(encoding="utf-8"))
    return [f["flow"] for f in data.get("flows", []) if f.get("link_type_matrix") is True]


def link_type_only_flows(flows_path=FLOWS) -> list[str]:
    """Matrix flows that run ONLY as link-type rows (<flow>__<type>), with no plain row of their own
    ('link_type_only' in scripts/e2e-flows.json), e.g. the re-engagement rows on each type's link."""
    data = json.loads(Path(flows_path).read_text(encoding="utf-8"))
    return [f["flow"] for f in data.get("flows", [])
            if f.get("link_type_matrix") is True and f.get("link_type_only") is True]


def prepare_flow(src, dst, link_type: str, source: str, consent: str) -> None:
    """Write <src> to <dst> for a link-type run (<flow>__<type>). An allow run must also show the
    debug meta row with linkType == <type> and source == <source> after the product page; a deny run
    is the flow as is (its check is the backend's: nothing recorded). Raises TargetError."""
    if not _TYPE.fullmatch(link_type or ""):
        raise TargetError(f"prepare-flow: bad link type '{link_type}'")
    if not _VOUCHER.fullmatch(source or ""):
        raise TargetError(f"prepare-flow: bad source '{source}'")
    if consent not in ("allow", "deny"):
        raise TargetError(f"prepare-flow: consent must be allow or deny, not '{consent}'")
    text = Path(src).read_text(encoding="utf-8")
    if "\n---\n" not in text or 'id: "product-name"' not in text:
        raise TargetError(f"prepare-flow: {src} is not a product-page flow (no '---' or product-name assertion)")
    if "meta-linkType" in text:
        raise TargetError(f"prepare-flow: {src} already asserts the link meta")
    if consent == "allow":
        text = text.rstrip("\n") + "\n" + (
            f"# Link-type run ({link_type}): the debug meta row shows the link's customData.\n"
            f'- assertVisible: {{ id: "meta-linkType", text: "{java_regex_literal(link_type)}" }}\n'
            f'- assertVisible: {{ id: "meta-source", text: "{java_regex_literal(source)}" }}\n')
    Path(dst).write_text(text, encoding="utf-8")


def java_regex_literal(text: str) -> str:
    return "".join("\\" + c if c in _REGEX_META else c for c in text)


def resolve_expect(cfg: dict, product: str, voucher: str) -> dict:
    product = (product or "").strip()
    voucher = (voucher or "").strip() or cfg["expect"]["voucher"]
    if not _VOUCHER.fullmatch(voucher):
        raise TargetError(f"E2E_EXPECT_VOUCHER / expect_voucher: '{voucher}' must be a voucher code "
                          "(letters, digits, '-' or '_', at most 64)")
    if len(product) > 100 or any(c in product for c in "\r\n\t") or "${" in product:
        raise TargetError("E2E_EXPECT_PRODUCT / expect_product: one line of at most 100 characters, without '${'")
    product = product or (cfg["expect"].get("product") or "")
    return {
        "E2E_EXPECT_PRODUCT": product,
        # Passed to Maestro as the text selector on id product-name: any product unless one is named.
        "E2E_PRODUCT_RE": java_regex_literal(product) if product else ".*",
        "E2E_EXPECT_VOUCHER": voucher,
    }


def resolve(environ=None, config=CONFIG, flows=FLOWS) -> dict:
    """The full set of resolved values (ordered). Raises TargetError on a bad choice."""
    environ = os.environ if environ is None else environ
    cfg = load_config(config)
    name, requested = resolve_environment(cfg, environ.get("LINKTRAIL_ENV", ""))
    env = cfg["environments"][name]
    out = {
        "LINKTRAIL_ENV": name,
        "E2E_ENV_REQUESTED": requested,
        "BACKEND_URL": env["backend_url"],
        "BASE_OVERRIDE": env["backend_url"] if env["override_backend"] else "",
        "KEY_SECRET": env["key_secret"],
        "SUBDOMAIN_HOST": env["subdomain_host"],
        "CUSTOM_HOST": env["custom_host"],
        # backend_checks: 1 = deployed on this environment's backend (required), 0 = skipped.
        "E2E_CHECK_EVENTS": "1" if env["backend_checks"]["events"] else "0",
        "E2E_CHECK_DEVICE_LOOKUP": "1" if env["backend_checks"]["device_lookup"] else "0",
    }
    for slot in SLOTS:
        out[env_var(slot)] = resolve_link(cfg, name, slot, environ.get(env_var(slot), ""))
    out.update(resolve_link_types(cfg, name, environ.get("E2E_LINK_TYPES", "")))
    out["E2E_MATRIX_FLOWS"] = ",".join(matrix_flows(flows))
    out.update(resolve_reward_links(cfg, name))
    out["E2E_MATRIX_ONLY_FLOWS"] = ",".join(link_type_only_flows(flows))
    out.update(resolve_expect(cfg, environ.get("E2E_EXPECT_PRODUCT", ""), environ.get("E2E_EXPECT_VOUCHER", "")))
    return out


def format_values(values: dict, fmt: str) -> str:
    lines = []
    for k, v in values.items():
        if "\n" in v or "\r" in v:
            raise TargetError(f"{k}: value has a line break")
        lines.append(f"{k}={shlex.quote(v)}" if fmt == "shell" else f"{k}={v}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("resolve", help="print the resolved environment + links")
    r.add_argument("--format", choices=["shell", "env"], default="shell")
    r.add_argument("--config", default=str(CONFIG))
    r.add_argument("--flows", default=str(FLOWS))
    pf = sub.add_parser("prepare-flow", help="write a flow for one link-type run (<flow>__<type>)")
    pf.add_argument("--flow", required=True)
    pf.add_argument("--out", required=True)
    pf.add_argument("--link-type", required=True)
    pf.add_argument("--source", required=True)
    pf.add_argument("--consent", required=True)
    a = p.parse_args(argv)
    if a.cmd == "prepare-flow":
        try:
            prepare_flow(a.flow, a.out, a.link_type, a.source, a.consent)
        except (TargetError, OSError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        return 0
    try:
        values = resolve(config=a.config, flows=a.flows)
        text = format_values(values, a.format)
    except (TargetError, OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title=e2e targets::{exc}", file=sys.stderr)
        return 2
    sys.stdout.write(text)
    alias = f" (requested '{values['E2E_ENV_REQUESTED']}')" if values["E2E_ENV_REQUESTED"] != values["LINKTRAIL_ENV"] else ""
    print(f"e2e targets: environment {values['LINKTRAIL_ENV']}{alias}, backend {values['BACKEND_URL']}", file=sys.stderr)
    for slot in SLOTS:
        print(f"  {slot}: {values[env_var(slot)]}", file=sys.stderr)
    if values["E2E_LINK_TYPES_RUN"]:
        print(f"  link types: {values['E2E_LINK_TYPES_RUN']}", file=sys.stderr)
    if values["E2E_LINK_TYPES_SKIPPED"]:
        print(f"NOTICE: link types skipped on {values['LINKTRAIL_ENV']} (no link in scripts/e2e-env.json): "
              f"{values['E2E_LINK_TYPES_SKIPPED']}", file=sys.stderr)
    print(f"  expect: product {values['E2E_EXPECT_PRODUCT'] or '(any)'}, voucher {values['E2E_EXPECT_VOUCHER']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
