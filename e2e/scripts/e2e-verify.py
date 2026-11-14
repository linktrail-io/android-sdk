#!/usr/bin/env python3
"""Checks one response of the e2e verify endpoint GET /v1/e2e/clicks/<token> (needs E2E_TOKEN).
Stdlib only. Called by scripts/e2e-maestro.sh while
it polls the endpoint for a flow's own click token.

  check --mode M --body F [--link-type T] [--rewarded a,b] [--baseline F]

prints three lines: the status, the report step, and the detail (one line, what the backend said;
it goes to report.json's backend_detail):

  ok        the response matches the mode
  bad       it does not (yet): the script keeps polling (allow) or fails at once (deny)
  fail      it does not and won't (fraud, a wrong link type): fails at once
  missing   the backend lacks a field this check needs (it predates the contract): fails at once,
            never skipped, with a clear "backend has no <field> field" message

Modes:
  allow         installRecorded, attributed, matchType == click_token, installCount == 1
  deny          installRecorded false, installCount 0
  reopen_allow  re-engagement App Link open on the installed app (--baseline: the response read after
                the install): openCount == baseline + 1, installCount and earning unchanged
  reopen_deny   the same open without consent records nothing: openCount, installCount and earning
                unchanged
  events_allow  the reward flows, after the counted install and the events (--model, --revenue-minor,
                --baseline: the install's response, whose earning must be 0, as no event was sent yet):
                per_event earning.amountMinor == 2 × reward.amountMinor (the other event adds nothing),
                rev_share earning.amountMinor == floor(revenue_minor × reward.rateBps / 10000) (the
                revenue event in another currency adds nothing)
  events_deny   the same flows without consent: no install counted, earning 0 (baseline too)

  plan-events --model M --body F --revenue-minor N --other-event E

prints the status and detail lines, then the kickflip://e2e/event links the flow opens to send the
events (the example app's debug event hook): the reward's eventName twice plus E once (per_event), or
one revenue event of N minor units in the reward's currency plus one in another currency (rev_share).

Every allow install (click token) is also checked for fraud: earning.excludedAsFraud false and
fraudReasons [] ('fail', final: the message names the rule, e.g. ip_velocity). The events modes
check linkType == --link-type (reward_links.<model>.<env>.link_type) and, with --events-check on
(backend_checks.events), the click's events: per_event allow byName[eventName] == 2, other == 1,
count 3; rev_share allow revenue has the reward currency and the other one at --revenue-minor;
deny count 0. Off: that check is recorded as skipped ("not on <env> backend yet").

After the three lines, each newer check this response reached prints one more line,
CHECK<TAB>name<TAB>pass|fail|skipped<TAB>detail, which the report shows as its own row.

  check-device --mode allow|deny --body F --slug S [--since EPOCH]

the *_problistic flows' GET /v1/e2e/devices/:deviceId response (same output): allow installCount >= 1
with the newest install attributed, matchType probabilistic, linkSlug S and not fraud; deny
installCount 0.

  device-id [--dump F] [--log F]

prints 'id <id>' (from the app's debug label: a uiautomator dump, else its logcat line), 'none' (the
label shows none: the SDK has no device id) or 'unread' (the label couldn't be read).

With --link-type (the link-type rows) allow / deny also check the reward (rewarded types: --rewarded):
  rewarded type, allow   reward set, earning.counted true, earning.amountMinor == what the response's
                         reward pays one install (per_install only: reward.amountMinor; any other
                         model is bad here, the contract defines only per_install on these rows)
  rewarded type, deny    earning.counted false, earning.amountMinor 0
  other types            reward null, earning.counted false, earning.amountMinor 0
and linkType must be the row's type.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

MODES = ("allow", "deny", "reopen_allow", "reopen_deny", "events_allow", "events_deny")
# The reward flows (deferred_event_* / deferred_revshare_*): per_event sends the reward's event this
# many times (plus one other event, which earns nothing); rev_share sends one revenue event.
REWARD_EVENTS = 2
# The rev_share flow's revenue event name (plan-events sends two of it, one per currency).
REVENUE_EVENT = "e2e_revenue"
# Minor-unit exponents that aren't 2 (ISO 4217), to send revenue_minor as a major-unit value.
_EXPONENT = {"BHD": 3, "CLP": 0, "IQD": 3, "ISK": 0, "JOD": 3, "JPY": 0, "KRW": 0, "KWD": 3, "LYD": 3,
             "OMR": 3, "PYG": 0, "TND": 3, "UGX": 0, "VND": 0, "XAF": 0, "XOF": 0}
INSTALL_STEP = "backend install check"
REWARD_STEP = "backend reward check"
REOPEN_STEP = "backend re-engagement check"
EVENTS_STEP = "backend event earning check"
FRAUD_STEP = "backend fraud check"
LINK_TYPE_STEP = "backend link type check"
EVENT_COUNT_STEP = "backend events check"
DEVICE_STEP = "backend device lookup check"
CONTRACT = "the e2e verify endpoint's current version"
# What a backend fraud rule means for an e2e run, so a failure names its likely cause.
FRAUD_RULES = {
    "ip_velocity": "more than 20 installs from one IP in an hour: the e2e runners share one public IP, "
                   "so too many runs in the hour trip it",
    "device_repeat": "the same device installed again: a device id from an earlier run",
    "ctit_too_short": "the install came under 10 s after its click (MIN_CTIT_WAIT)",
}
# A device lookup install counts for this attempt when it was created at most this long before the
# attempt started (clock skew between the runner and the backend).
DEVICE_SKEW_S = 120
_DEVICE_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}")
DEVICE_LABEL = "e2e-device-id"
DEVICE_LOG = "E2E device id:"


def _j(value) -> str:
    """A value as the backend wrote it (true / false / null), for the detail line."""
    return json.dumps(value, ensure_ascii=False)


def _money(obj) -> str:
    if not isinstance(obj, dict):
        return _j(obj)
    amount, currency = obj.get("amountMinor"), obj.get("currency")
    return f"{_j(amount)}{' ' + str(currency) if currency else ''}"


def describe(d: dict) -> str:
    """The response, one line, e.g. 'installRecorded=true … earning=counted 50 GBP'."""
    parts = [f"{k}={_j(d.get(k))}" for k in ("installRecorded", "attributed", "matchType", "installCount", "openCount")]
    if "linkType" in d:
        parts.append(f"linkType={d.get('linkType')}")
    if "reward" in d:
        r = d.get("reward")
        parts.append("reward=" + (f"{r.get('model')} {_money(r)}" if isinstance(r, dict) else _j(r)))
    if "earning" in d:
        e = d.get("earning")
        if isinstance(e, dict):
            # fraudReasons names the backend rule that flagged the install (ip_velocity, device_repeat, …).
            reasons = d.get("fraudReasons") or []
            fraud = f" (excluded as fraud: {', '.join(map(str, reasons))})" if reasons else " (excluded as fraud)"
            parts.append(f"earning={'counted' if e.get('counted') is True else 'not counted'} {_money(e)}"
                         + (fraud if e.get("excludedAsFraud") is True else ""))
        else:
            parts.append(f"earning={_j(e)}")
    return " ".join(parts)


def _missing(field: str) -> str:
    return (f"backend has no {field} field in GET /v1/e2e/clicks/:token: the backend predates {CONTRACT} "
            f"(deploy the change that adds linkType, reward and earning)")


def _amount(obj):
    """amountMinor of a reward / earning object, or None when absent / not an integer."""
    if not isinstance(obj, dict):
        return None
    v = obj.get("amountMinor")
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def expected_install_earning(reward: dict):
    """What one counted install earns on an install-only rewarded row: per_install → reward.amountMinor.
    None for every other model (flat, per_event, rev_share): the contract defines only per_install there."""
    return _amount(reward) if reward.get("model") == "per_install" else None


def install_problems(mode: str, d: dict) -> list[str]:
    if mode == "allow":
        want = {"installRecorded": True, "attributed": True, "matchType": "click_token", "installCount": 1}
    else:
        want = {"installRecorded": False, "installCount": 0}
    return [f"{k} {_j(d.get(k))} (want {_j(v)})" for k, v in want.items()
            if d.get(k) != v or type(d.get(k)) is not type(v)]


def reward_check(mode: str, d: dict, link_type: str, rewarded) -> tuple[str, list[str]]:
    """→ ('missing', [msg]) | ('bad', problems) | ('ok', [])."""
    for field in ("earning", "reward", "linkType"):
        if field not in d:
            return "missing", [_missing(field)]
    problems = []
    if d.get("linkType") != link_type:
        problems.append(f"linkType {_j(d.get('linkType'))} (want {_j(link_type)}: the row's link has the wrong type)")
    reward, earning = d.get("reward"), d.get("earning")
    if not isinstance(earning, dict):
        return "bad", problems + [f"earning {_j(earning)} (want an object)"]
    counted, amount = earning.get("counted"), _amount(earning)
    if link_type in rewarded:
        if not isinstance(reward, dict) or _amount(reward) is None:
            problems.append(f"reward {_j(reward)} (want the {link_type} link's reward terms with amountMinor)")
        elif mode == "allow":
            # The amount always comes from the response's own reward, never a hardcoded one.
            want = expected_install_earning(reward)
            if want is None:
                problems.append(f"reward.model {_j(reward.get('model'))} (want per_install: the contract defines only per_install on an install-only row)")
            else:
                if counted is not True:
                    problems.append(f"earning.counted {_j(counted)} (want true: the counted install earns the reward)")
                if amount != want:
                    problems.append(f"earning.amountMinor {_j(earning.get('amountMinor'))} (want {want}: "
                                    "reward.amountMinor)")
        if mode == "deny":
            if counted is not False:
                problems.append(f"earning.counted {_j(counted)} (want false: a denied install earns nothing)")
            if amount != 0:
                problems.append(f"earning.amountMinor {_j(earning.get('amountMinor'))} (want 0: a denied install earns nothing)")
    else:
        if reward is not None:
            problems.append(f"reward {_j(reward)} (want null: {link_type} links carry no reward)")
        if counted is not False:
            problems.append(f"earning.counted {_j(counted)} (want false: no reward)")
        if amount != 0:
            problems.append(f"earning.amountMinor {_j(earning.get('amountMinor'))} (want 0: no reward)")
    return ("bad" if problems else "ok"), problems


def reopen_check(mode: str, d: dict, base: dict) -> tuple[str, list[str], str]:
    """→ (status, problems, 'openCount 0→1 installCount 1→1 earning 50→50 GBP')."""
    for field in ("openCount", "installCount"):
        if field not in d or field not in base:
            return "missing", [f"backend has no {field} field in GET /v1/e2e/clicks/:token ({CONTRACT})"], ""
    if "earning" not in d or "earning" not in base:
        return "missing", [_missing("earning")], ""
    opens, base_opens = d.get("openCount"), base.get("openCount")
    e, be = d.get("earning"), base.get("earning")
    delta = f"openCount {_j(base_opens)}→{_j(opens)} installCount {_j(base.get('installCount'))}→{_j(d.get('installCount'))} " \
            f"earning {_money(be)}→{_money(e)}"
    problems = []
    if not isinstance(base_opens, int) or isinstance(base_opens, bool):
        problems.append(f"baseline openCount {_j(base_opens)} (want a number)")
    else:
        want = base_opens + 1 if mode == "reopen_allow" else base_opens
        if opens != want:
            why = ("the App Link open must be recorded once for this click" if mode == "reopen_allow"
                   else "an open without consent records nothing")
            problems.append(f"openCount {_j(opens)} (want {want}: {why})")
    if d.get("installCount") != base.get("installCount"):
        problems.append(f"installCount {_j(d.get('installCount'))} (want {_j(base.get('installCount'))}: "
                        "re-engagement must not record a second install)")
    # The whole earning object must be as after the install: amount, counted, currency, excludedAsFraud.
    if e != be:
        changed = sorted(k for k in set(e or {}) | set(be or {})
                         if not isinstance(e, dict) or not isinstance(be, dict) or e.get(k) != be.get(k))
        problems.append(f"earning {_j(e)} (want {_j(be)} as after the install, changed: {', '.join(changed)}: "
                        "no second reward)")
    return ("bad" if problems else "ok"), problems, delta


def event_reward(d: dict, model: str) -> tuple[str, str, dict | None]:
    """The response's reward for a reward flow → (status, problem, reward). It must be there and be of
    the flow's model (per_event with eventName, rev_share with rateBps)."""
    if "reward" not in d:
        return "missing", _missing("reward"), None
    r = d.get("reward")
    if not isinstance(r, dict):
        return "bad", f"reward {_j(r)} (want the link's {model} reward)", None
    if r.get("model") != model:
        return "bad", f"reward.model {_j(r.get('model'))} (want {_j(model)}: the link is set up with another model)", None
    if model == "per_event" and (_amount(r) is None or not isinstance(r.get("eventName"), str) or not r["eventName"]):
        return "bad", f"reward {_j(r)} (want amountMinor and eventName for per_event)", None
    rate = r.get("rateBps")
    if model == "rev_share" and (not isinstance(rate, int) or isinstance(rate, bool) or not r.get("currency")):
        return "bad", f"reward {_j(r)} (want rateBps and currency for rev_share)", None
    return "ok", "", r


def expected_event_earning(reward: dict, revenue_minor: int) -> int:
    """The contract's formula for what the flow's events earn."""
    if reward["model"] == "per_event":
        return REWARD_EVENTS * _amount(reward)
    return (revenue_minor * reward["rateBps"]) // 10000


def major_units(minor: int, currency: str) -> str:
    """1999 GBP → '19.99', 1999 JPY → '1999', exactly (no float)."""
    exp = _EXPONENT.get(currency.upper(), 2)
    if exp == 0:
        return str(minor)
    sign, minor = ("-" if minor < 0 else ""), abs(minor)
    return f"{sign}{minor // 10 ** exp}.{minor % 10 ** exp:0{exp}d}"


def other_currency(currency: str) -> str:
    """A currency that isn't the workspace's: USD, or EUR when the workspace's is USD."""
    return "EUR" if currency.upper() == "USD" else "USD"


def plan_events(model: str, d, revenue_minor: int, other_event: str) -> tuple[str, str, list[str]]:
    """→ (status, detail, the kickflip://e2e/event links to open, in order)."""
    if not isinstance(d, dict):
        return "bad", f"response is not a JSON object: {_j(d)[:200]}", []
    status, problem, r = event_reward(d, model)
    if status != "ok":
        return status, problem, []
    from urllib.parse import urlencode
    if model == "per_event":
        if r["eventName"] == other_event:
            return "bad", f"reward.eventName {_j(other_event)} is the other event's name (reward_events.other_event)", []
        names = [r["eventName"]] * REWARD_EVENTS + [other_event]
        links = ["kickflip://e2e/event?" + urlencode({"name": n}) for n in names]
        detail = f"per_event: {REWARD_EVENTS} × {r['eventName']} + 1 × {other_event}"
    else:
        value = major_units(revenue_minor, r["currency"])
        # The same amount in another currency must add nothing (contract: other currencies are ignored).
        other = other_currency(r["currency"])
        other_value = major_units(revenue_minor, other)
        links = ["kickflip://e2e/event?" + urlencode({"name": REVENUE_EVENT, "value": value, "currency": r["currency"]}),
                 "kickflip://e2e/event?" + urlencode({"name": REVENUE_EVENT, "value": other_value, "currency": other})]
        detail = (f"rev_share: 1 revenue event of {revenue_minor} minor ({value} {r['currency']}) at {r['rateBps']} bps "
                  f"+ 1 in another currency ({other_value} {other}, adds nothing)")
    return "ok", detail, links


def fraud_reason_text(reasons) -> str:
    """'ip_velocity (more than 20 installs …)' per reason, joined; 'no reason recorded' when empty."""
    if not reasons:
        return "no reason recorded"
    return ", ".join(f"{r} ({FRAUD_RULES[r]})" if r in FRAUD_RULES else str(r) for r in reasons)


def fraud_check(obj: dict) -> tuple[str, str]:
    """A counted allow install must not be fraud: earning.excludedAsFraud false (absent = false, as on
    a link without a reward) and fraudReasons [] (obj is the click response or one device lookup
    install). → ('ok' | 'fail' | 'skipped', detail); 'fail' names the rule (e.g. ip_velocity).
    Without a fraudReasons field the check can't be made: skipped (and the row with it), unless
    the install is excluded as fraud anyway (fail)."""
    e = obj.get("earning")
    excluded = e.get("excludedAsFraud") if isinstance(e, dict) else None
    reasons = obj.get("fraudReasons")
    problems = []
    if "fraudReasons" in obj and not isinstance(reasons, list):
        problems.append(f"fraudReasons {_j(reasons)} (want a list)")
        reasons = []
    reasons = reasons or []
    if excluded is True:
        problems.append(f"earning.excludedAsFraud true (want false): {fraud_reason_text(reasons)}")
    elif excluded not in (False, None):
        problems.append(f"earning.excludedAsFraud {_j(excluded)} (want false)")
    if reasons and excluded is not True:
        problems.append(f"fraudReasons {_j(reasons)} (want []): {fraud_reason_text(reasons)}")
    if problems:
        return "fail", "; ".join(problems)
    if "fraudReasons" not in obj:
        return "skipped", "not checkable: backend reports no fraudReasons field"
    return "ok", "excludedAsFraud false, fraudReasons []"


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def events_shape(ev) -> str:
    """'' when the events field has the contract's shape (count int, byName {str: int}, revenue
    [{currency: str, amountMinor: int}] with each currency once), else what is wrong. Booleans and
    floats (3.0) are not integers here."""
    if not isinstance(ev, dict):
        return f"events {_j(ev)} (want an object)"
    if not _is_int(ev.get("count")):
        return f"events.count {_j(ev.get('count'))} (want an integer)"
    by_name = ev.get("byName")
    if not isinstance(by_name, dict) or any(not _is_int(n) for n in by_name.values()):
        return f"events.byName {_j(by_name)} (want an object of integer counts)"
    revenue = ev.get("revenue")
    if not isinstance(revenue, list):
        return f"events.revenue {_j(revenue)} (want a list)"
    seen = set()
    for r in revenue:
        if not isinstance(r, dict) or not isinstance(r.get("currency"), str) or not r["currency"] \
                or not _is_int(r.get("amountMinor")):
            return f"events.revenue entry {_j(r)} (want {{currency, amountMinor}} with an integer amountMinor)"
        cur = r["currency"].upper()
        if cur in seen:
            return f"events.revenue lists {cur} twice (want each currency once, summed)"
        seen.add(cur)
    return ""


def events_check(d: dict, model: str, reward: dict, consent: str, other_event: str,
                 revenue_minor: int) -> tuple[str, str, str]:
    """The click's events field (contract "Events and revenue on the click") after a reward flow's
    events → (status, check name, detail). Exact:
      per_event allow  byName == {eventName: 2, other_event: 1}, count 3, revenue []
      rev_share allow  byName == {e2e_revenue: 2}, count 2, revenue == the reward currency and the
                       other currency each at revenue_minor, nothing else
      deny             count 0, byName {}, revenue []
    A field of the wrong shape is 'fail' (final: it won't change); wrong values are 'bad' (polled)."""
    name = "revenue" if model == "rev_share" and consent == "allow" else "events"
    if "events" not in d:
        return "missing", name, (f"backend has no events field in GET /v1/e2e/clicks/:token: the backend predates "
                                 f"{CONTRACT} 'Events and revenue on the click' (set backend_checks.events false "
                                 "for this environment until it is deployed)")
    ev = d.get("events")
    shape = events_shape(ev)
    if shape:
        return "fail", name, shape
    count, by_name, revenue = ev["count"], ev["byName"], ev["revenue"]
    amounts = {r["currency"].upper(): r["amountMinor"] for r in revenue}
    got = f"events.count {_j(count)} byName {_j(by_name)} revenue {_j(revenue)}"
    if consent == "deny":
        want_count, want_names, want_rev = 0, {}, {}
        why = "a deny run's events must not be recorded"
    elif model == "per_event":
        want_names = {reward["eventName"]: REWARD_EVENTS, other_event: 1}
        want_count, want_rev, why = sum(want_names.values()), {}, "the flow's events"
    else:
        cur = str(reward.get("currency") or "").upper()
        want_names = {REVENUE_EVENT: 2}
        want_count, want_rev = 2, {cur: revenue_minor, other_currency(cur): revenue_minor}
        why = "one revenue event per currency"
    problems = []
    if count != want_count:
        problems.append(f"events.count {count} (want {want_count}: {why})")
    if by_name != want_names:
        problems.append(f"events.byName {_j(by_name)} (want {_j(want_names)})")
    if amounts != want_rev:
        problems.append(f"events.revenue {_j(amounts)} (want {_j(want_rev)})")
    if problems:
        return "bad", name, "; ".join(problems) + "; " + got
    return "ok", name, got


def _check_row(name: str, status: str, detail: str) -> tuple[str, str, str]:
    """One backend check for the report's per-check rows: ok → pass, skipped → skipped, else fail."""
    result = {"ok": "pass", "skipped": "skipped"}.get(status, "fail")
    return name, result, " ".join(str(detail).split())


def check(mode: str, d, link_type: str = "", rewarded=(), baseline=None, model: str = "",
          revenue_minor: int = 0, **kw) -> tuple[str, str, str]:
    """→ (status, step, detail). See the module doc."""
    return check_full(mode, d, link_type, rewarded, baseline, model, revenue_minor, **kw)[:3]


def check_full(mode: str, d, link_type: str = "", rewarded=(), baseline=None, model: str = "",
               revenue_minor: int = 0, events_enabled: bool = False, env: str = "", other_event: str = "e2e_other"):
    """→ (status, step, detail, checks): checks are the (name, pass|fail|skipped, detail) rows of the
    newer checks this response reached (fraud, link type, events / revenue), for the report."""
    checks = []
    status, step, detail = _check(mode, d, link_type, rewarded, baseline, model, revenue_minor,
                                  events_enabled, env, other_event, checks)
    return status, step, detail, checks


def _check(mode, d, link_type, rewarded, baseline, model, revenue_minor, events_enabled, env, other_event, checks):
    if mode not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}, not {mode!r}")
    if not isinstance(d, dict):
        return "bad", INSTALL_STEP, f"response is not a JSON object: {_j(d)[:200]}"
    state = describe(d)
    if mode.startswith("events_"):
        consent = mode.split("_", 1)[1]
        problems = install_problems(consent, d)
        if problems:
            return "bad", INSTALL_STEP, "; ".join(problems) + "; " + state
        status, problem, r = event_reward(d, model)
        if status != "ok":
            return status, EVENTS_STEP, problem + "; " + state
        if link_type:
            # The reward link's type (reward_links.<model>.<env>.link_type): fixed, so a wrong one is final.
            if "linkType" not in d:
                checks.append(_check_row("link type", "missing", _missing("linkType")))
                return "missing", LINK_TYPE_STEP, _missing("linkType") + "; " + state
            if d.get("linkType") != link_type:
                msg = f"linkType {_j(d.get('linkType'))} (want {_j(link_type)}: reward_links.{model} in scripts/e2e-env.json)"
                checks.append(_check_row("link type", "fail", msg))
                return "fail", LINK_TYPE_STEP, msg + "; " + state
            checks.append(_check_row("link type", "ok", f"linkType {link_type}"))
        if "earning" not in d:
            return "missing", EVENTS_STEP, _missing("earning") + "; " + state
        # Baseline: before any event, the install alone earns nothing on per_event / rev_share.
        if not isinstance(baseline, dict):
            return "bad", EVENTS_STEP, f"no baseline response from the install step; {state}"
        if "earning" not in baseline:
            return "missing", EVENTS_STEP, _missing("earning") + " (in the install's response); " + state
        be = baseline.get("earning")
        if not isinstance(be, dict) or _amount(be) != 0:
            return "bad", EVENTS_STEP, (f"install earning {_j(be)} before any event (want amountMinor 0: "
                                        f"{model} pays for events, not the install); {state}")
        e = d.get("earning")
        counted, amount = (e.get("counted"), _amount(e)) if isinstance(e, dict) else (None, None)
        if consent == "allow":
            want = expected_event_earning(r, revenue_minor)
            formula = (f"{REWARD_EVENTS} × reward.amountMinor {_amount(r)}" if model == "per_event"
                       else f"floor({revenue_minor} × rateBps {r['rateBps']} / 10000)")
            if counted is not True or amount != want:
                return "bad", EVENTS_STEP, (f"earning {_j(e)} (want counted true and amountMinor {want} = {formula}); "
                                            + state)
            ok_detail = f"earning {want} = {formula}; {state}"
        else:
            if counted is not False or amount != 0:
                return "bad", EVENTS_STEP, f"earning {_j(e)} (want counted false, amountMinor 0: deny sends no event); {state}"
            ok_detail = state
        # The click's events (contract "Events and revenue on the click"), once deployed (backend_checks.events).
        if not events_enabled:
            name = "revenue" if model == "rev_share" and consent == "allow" else "events"
            checks.append(_check_row(name, "skipped", f"not on {env or 'this'} backend yet "
                                     "(backend_checks.events is false in scripts/e2e-env.json)"))
            return "ok", EVENTS_STEP, ok_detail
        status, name, ev_detail = events_check(d, model, r, consent, other_event, revenue_minor)
        checks.append(_check_row(name, status, ev_detail))
        if status != "ok":
            return status, EVENT_COUNT_STEP, ev_detail + "; " + state
        return "ok", EVENTS_STEP, f"{ok_detail}; {name}: {ev_detail}"
    if mode.startswith("reopen_"):
        if not isinstance(baseline, dict):
            return "bad", REOPEN_STEP, f"no baseline response from the install step; {state}"
        status, problems, delta = reopen_check(mode, d, baseline)
        detail = f"{delta}; {state}" if delta else state
        if status != "ok":
            detail = "; ".join(problems) + "; " + detail
        return status, REOPEN_STEP, detail
    problems = install_problems(mode, d)
    if problems:
        return "bad", INSTALL_STEP, "; ".join(problems) + "; " + state
    if mode == "allow":
        # Every counted allow install: not excluded as fraud. A flagged install doesn't recover: final.
        status, fraud = fraud_check(d)
        checks.append(_check_row("fraud", status, fraud))
        if status == "fail":
            return "fail", FRAUD_STEP, fraud + "; " + state
    if link_type:
        status, problems = reward_check(mode, d, link_type, tuple(rewarded))
        if status != "ok":
            return status, REWARD_STEP, "; ".join(problems) + "; " + state
    return "ok", INSTALL_STEP, state


def _created_at(value):
    """An install's createdAt (ISO 8601, 'Z' or an offset) → epoch seconds, or None."""
    if not isinstance(value, str) or not value:
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError:
        return None
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).timestamp()


def describe_device(d: dict, first: dict) -> str:
    parts = [f"installCount={_j(d.get('installCount'))}"]
    if first:
        parts += [f"{k}={_j(first.get(k))}" for k in ("attributed", "matchType", "linkSlug", "createdAt")]
        if "fraudReasons" in first or isinstance(first.get("earning"), dict):
            e = first.get("earning") if isinstance(first.get("earning"), dict) else {}
            parts.append(f"excludedAsFraud={_j(e.get('excludedAsFraud'))} fraudReasons={_j(first.get('fraudReasons'))}")
    return " ".join(parts)


def check_device(mode: str, d, slug: str, since):
    """One GET /v1/e2e/devices/:deviceId response for a *_problistic flow (contract "Device lookup")
    → (status, step, detail, checks).
      allow  installCount >= 1 and the newest install, made in this attempt (createdAt present and no
             more than DEVICE_SKEW_S before `since`, the attempt's start in epoch seconds; a missing
             or unparseable createdAt can't prove that, so it is bad), is attributed with
             matchType probabilistic to the flow's link (linkSlug); then it must not be fraud
      deny   installCount == 0
    'bad' keeps the allow poll going (or ends deny's); 'fail' (fraud) is final."""
    if mode not in ("allow", "deny"):
        raise ValueError(f"device mode must be allow or deny, not {mode!r}")
    checks = []
    if not isinstance(d, dict):
        return "bad", DEVICE_STEP, f"response is not a JSON object: {_j(d)[:200]}", checks
    installs = d.get("installs") if isinstance(d.get("installs"), list) else []
    first = installs[0] if installs and isinstance(installs[0], dict) else {}
    count = d.get("installCount")
    state = describe_device(d, first)
    if not isinstance(count, int) or isinstance(count, bool):
        return "bad", DEVICE_STEP, f"installCount {_j(count)} (want a number); {state}", checks
    if mode == "deny":
        if count != 0:
            msg = f"installCount {count} (want 0: a denied install is never counted); {state}"
            checks.append(_check_row("device lookup", "bad", msg))
            return "bad", DEVICE_STEP, msg, checks
        checks.append(_check_row("device lookup", "ok", state))
        return "ok", DEVICE_STEP, state, checks
    problems = []
    if count < 1:
        problems.append(f"installCount {count} (want >= 1)")
    else:
        created = _created_at(first.get("createdAt"))
        if since is None:
            problems.append("no attempt start (--since): this attempt's install can't be told from an earlier one")
        elif created is None:
            problems.append(f"newest install createdAt {_j(first.get('createdAt'))} (want an ISO 8601 time: "
                            "it proves the install is from this attempt)")
        elif created < since - DEVICE_SKEW_S:
            problems.append(f"newest install createdAt {_j(first.get('createdAt'))} is from before this attempt "
                            "(an earlier run's install on the same device id)")
        if first.get("attributed") is not True:
            problems.append(f"attributed {_j(first.get('attributed'))} (want true)")
        if first.get("matchType") != "probabilistic":
            problems.append(f"matchType {_j(first.get('matchType'))} (want \"probabilistic\")")
        if first.get("linkSlug") != slug:
            problems.append(f"linkSlug {_j(first.get('linkSlug'))} (want {_j(slug)}: the flow's link)")
    if problems:
        msg = "; ".join(problems) + "; " + state
        checks.append(_check_row("device lookup", "bad", msg))
        return "bad", DEVICE_STEP, msg, checks
    checks.append(_check_row("device lookup", "ok", state))
    status, fraud = fraud_check(first)
    checks.append(_check_row("fraud", status, fraud))
    if status == "fail":
        return "fail", FRAUD_STEP, fraud + "; " + state, checks
    return "ok", DEVICE_STEP, state, checks


def device_id(dump_text: str = "", log_text: str = "") -> tuple[str, str]:
    """The SDK device id the example app shows on its debug label (test tag e2e-device-id) →
    (state, id):
      ('id', <id>)   from a `uiautomator dump` of the screen, else the label's logcat line
                     ('E2E device id: <id>'; the label may have got its id after the dump)
      ('none', '')   the label was read and shows 'none': the SDK has no device id (a denied install
                     mints none), so the device lookup is not checkable
      ('unread', '') no label on the screen and no log line: the label could not be read"""
    label = None
    if dump_text:
        try:
            root = ET.fromstring(dump_text)
        except ET.ParseError:
            root = None
        for node in (root.iter("node") if root is not None else ()):
            rid = node.get("resource-id") or ""
            if rid == DEVICE_LABEL or rid.endswith("/" + DEVICE_LABEL):
                label = (node.get("text") or "").strip()
                break
    if label and label != "none" and _DEVICE_ID.fullmatch(label):
        return "id", label
    found = ""
    for line in (log_text or "").splitlines():
        if DEVICE_LOG in line:
            text = line.split(DEVICE_LOG, 1)[1].strip()
            found = text if _DEVICE_ID.fullmatch(text) and text != "none" else found
    if found:
        return "id", found
    if label == "none":
        return "none", ""
    return "unread", ""


def _print_checks(checks) -> list[str]:
    return ["CHECK\t" + "\t".join(c) for c in checks]


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check one verify-endpoint response")
    c.add_argument("--mode", required=True, choices=MODES)
    c.add_argument("--body", required=True, help="the response body (JSON)")
    c.add_argument("--link-type", default="", help="the row's link type (link-type rows): also check the reward")
    c.add_argument("--rewarded", default="", help="comma list of the link types that carry a reward")
    c.add_argument("--baseline", default="", help="reopen modes: the response read after the install step")
    c.add_argument("--model", default="", choices=["", "per_event", "rev_share"], help="events modes: the link's reward model")
    c.add_argument("--revenue-minor", type=int, default=0, help="events modes: the revenue event's minor units (rev_share)")
    c.add_argument("--events-check", default="off", choices=["on", "off"],
                   help="events modes: check the click's events field (backend_checks.events)")
    c.add_argument("--env", default="", help="the environment's name (for the skipped message)")
    c.add_argument("--other-event", default="e2e_other", help="events modes: reward_events.other_event")
    cd = sub.add_parser("check-device", help="check one device lookup response (the *_problistic flows)")
    cd.add_argument("--mode", required=True, choices=["allow", "deny"])
    cd.add_argument("--body", required=True)
    cd.add_argument("--slug", required=True, help="the flow's link slug")
    cd.add_argument("--since", type=float, required=True, help="the attempt's start, epoch seconds")
    di = sub.add_parser("device-id", help="the SDK device id from the app's debug label")
    di.add_argument("--dump", default="", help="a uiautomator dump of the screen")
    di.add_argument("--log", default="", help="the app's logcat")
    pe = sub.add_parser("plan-events", help="the event links a reward flow opens")
    pe.add_argument("--model", required=True, choices=["per_event", "rev_share"])
    pe.add_argument("--body", required=True)
    pe.add_argument("--revenue-minor", type=int, required=True)
    pe.add_argument("--other-event", required=True)
    a = p.parse_args(argv)
    if a.cmd == "device-id":
        texts = []
        for path in (a.dump, a.log):
            try:
                texts.append(Path(path).read_text(encoding="utf-8", errors="replace") if path else "")
            except OSError:
                texts.append("")
        print(" ".join(device_id(*texts)).strip())
        return 0
    if a.cmd == "check-device":
        try:
            data = _load(a.body)
        except (OSError, ValueError) as exc:
            print(f"bad\n{DEVICE_STEP}\nunreadable response: {exc}")
            return 0
        status, step, detail, checks = check_device(a.mode, data, a.slug, a.since)
        print("\n".join([status, step, " ".join(detail.split()), *_print_checks(checks)]))
        return 0
    if a.cmd == "plan-events":
        try:
            data = _load(a.body)
        except (OSError, ValueError) as exc:
            print(f"bad\nunreadable response: {exc}")
            return 0
        status, detail, links = plan_events(a.model, data, a.revenue_minor, a.other_event)
        print("\n".join([status, " ".join(detail.split()), *links]))
        return 0
    rewarded = tuple(t.strip() for t in a.rewarded.split(",") if t.strip())
    step = REOPEN_STEP if a.mode.startswith("reopen_") else INSTALL_STEP
    try:
        data = _load(a.body)
    except (OSError, ValueError) as exc:
        print(f"bad\n{step}\nunreadable response: {exc}")
        return 0
    baseline = None
    if a.baseline:
        try:
            baseline = _load(a.baseline)
        except (OSError, ValueError):
            baseline = None
    status, step, detail, checks = check_full(a.mode, data, a.link_type, rewarded, baseline, a.model, a.revenue_minor,
                                              events_enabled=a.events_check == "on", env=a.env,
                                              other_event=a.other_event)
    print("\n".join([status, step, " ".join(detail.split()), *_print_checks(checks)]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
