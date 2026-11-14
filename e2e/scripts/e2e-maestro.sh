#!/usr/bin/env bash
# End-to-end tests for the PUBLISHED LinkTrail Android SDK (io.linktrail:sdk from Maven Central, version in
# gradle/libs.versions.toml), driven by Maestro against the KickFlip example in example/.
#
# Android note: unlike iOS (clipboard/paste), Android deferred deep linking uses the Play Install
# Referrer, which only exists for real Play-Store installs — it can't be staged in an emulator/CI.
# So these flows exercise the SAME outcomes via (a) the in-app Deep Link Simulator (deferred
# scenarios) and (b) real re-engagement links (openLink), across consent allow/deny.
#
# Two kinds of flow:
#   scripts/*.yaml       12 SIMULATED flows — in-app Deep Link Simulator + kickflip:// links. Need no
#                        backend or key; always run. They run with `debug.kickflip.simulated=1`, so the
#                        debug app sends no install: an Allow there used to send a real one from the
#                        runners' shared IP, which the backend's probabilistic matcher could attribute to
#                        another run's click and route over the simulated screen.
#                        Each passing attempt is also checked in logcat: the app's simulated-mode line
#                        is there and the SDK's "Sending install event" line is not.
#   scripts/real/*.yaml  16 REAL flows — the SDK's network path end to end, on the same links as the iOS
#                        suite (scripts/e2e-env.json; nothing here names a host or slug). Run only when LINKTRAIL_KEY is set, otherwise skipped with a note. For
#                        each deferred flow the script makes a real click (Android Chrome UA), takes
#                        lt_click from the Play Store redirect, polls GET /v1/events/click/<token> until
#                        the backend knows it and reinstalls the app. Click-token flows then stage the
#                        token via the debug fake referrer (setprop debug.linktrail.referrer);
#                        *_problistic flows stage nothing, so only the backend's IP + platform match can
#                        attribute the install (the click comes from this host, which shares the
#                        emulator's public IP). Each flow then checks logcat for its install log line.
#                        The App Link flows open the subdomain link (E2E_SUBDOMAIN_LINK).
#   LINK-TYPE matrix     the click-token deferred flows marked link_type_matrix in scripts/e2e-flows.json
#                        (deferred_custom_allow / _deny) run once more per link type (link_types in
#                        scripts/e2e-env.json), on that type's link, as <flow>__<type>. Allow asserts the
#                        product + voucher of link_type_expect, the debug meta row (meta-linkType == the
#                        type, meta-source) and the backend install check (recorded + attributed); deny
#                        asserts nothing was recorded. A type with no link in the environment (prod until
#                        its links exist) is skipped with a notice. Link-type allow / deny rows also check the
#                        reward (scripts/e2e-verify.py): on rewarded_link_types (scripts/e2e-env.json) allow
#                        earns reward.amountMinor and deny earns 0; the other types have reward == null. A
#                        backend without the earning field fails the row ("backend has no earning field").
#   RE-ENGAGEMENT rows   reengagement_applink_type_{allow,deny}__<type> (link_type_only: no plain row). The
#                        app is installed first through the type's link (real click + fake referrer +
#                        real/deferred_custom_<consent>.yaml) and the backend baseline for that click read;
#                        then the flow opens the same link as an App Link on the installed app and asserts
#                        the product + voucher, and the backend: openCount +1 (allow) / unchanged (deny),
#                        installCount and earning unchanged (no second reward).
#   REWARD flows         deferred_event_{allow,deny} / deferred_revshare_{allow,deny} on reward_links
#                        (scripts/e2e-env.json; prod has e2e-revshare, no per_event link yet: those rows are skipped). As
#                        deferred_custom_*, then the backend install check, then the events: the reward's
#                        eventName twice + reward_events.other_event once (per_event) or one revenue event of
#                        revenue_minor in the reward's currency + one in another currency (rev_share), sent
#                        through the example app's debug hook kickflip://e2e/event (allow: each must come
#                        back attributed=true). The install's response is the baseline: earning 0. Allow expects earning 2 × reward.amountMinor /
#                        floor(revenue_minor × rateBps / 10000); deny sends the same, the SDK drops them,
#                        earning 0. A link that doesn't exist yet fails with "<env> link <slug> not created".
#   PROBABILISTIC rows   *_problistic have no click token: the install is checked by the SDK device id the
#                        example app shows on its debug label (e2e-device-id; uiautomator dump, else its
#                        logcat line) with GET /v1/e2e/devices/<id>: allow installCount >= 1, the newest
#                        install (from this attempt: createdAt) attributed, matchType probabilistic, on the
#                        flow's link; deny installCount 0. A label showing none (a denied install mints no
#                        device id) is not checkable: skipped. A label that can't be read fails. Gated by
#                        backend_checks.device_lookup (scripts/e2e-env.json).
#   NO SILENT PASSES     a row passes only when every backend check ran: no E2E_TOKEN, a backend_checks
#                        toggle off, a backend without fraudReasons, no device id → the row is skipped,
#                        with the reason.
#   FRAUD                every counted allow install (click token or device lookup) must have
#                        earning.excludedAsFraud false and fraudReasons [] (the failure names the rule, e.g.
#                        ip_velocity: more than 20 installs per IP per hour).
#   EVENTS               the reward flows also check the click's linkType (reward_links link_type) and, with
#                        backend_checks.events on, its events: byName / count (per_event), revenue (rev_share),
#                        count 0 (deny). Off: recorded as skipped ("not on <env> backend yet").
#   backend_detail       every backend check writes what the backend said (install, reward, earning, opens)
#                        to the row's backend_detail in report.json, on pass and on fail. The newer checks
#                        (fraud, link type, events / revenue, device lookup) are also recorded one by one
#                        (report.json "checks", the report's "Backend checks" table).
#
# Usage:
#   bash scripts/e2e-maestro.sh            # build, install, run all flows on a booted emulator/device
#   bash scripts/e2e-maestro.sh <flow>     # one flow (bare name or filename; real flows by name too;
#                                          # a matrix flow also runs its link-type rows;
#                                          # <flow>__<type> for one link-type row only)
#
# Env:
#   LINKTRAIL_KEY   SDK key for the selected environment's workspace. Baked into the debug build
#                   (BuildConfig) and enables the real flows. Never printed.
#   LINKTRAIL_ENV   an environment in scripts/e2e-env.json (default and only one here: prod) — the backend +
#                   link hosts of the real flows.
#   E2E_CUSTOM_LINK, E2E_SUBDOMAIN_LINK, E2E_CUSTOM_PROBLISTIC_LINK, E2E_SUBDOMAIN_PROBLISTIC_LINK
#                   the links to test: a full URL (https://<host>/<slug>) or a bare slug (the
#                   environment's host); empty = the default. A host that isn't the environment's host
#                   for that slot fails before anything runs (scripts/e2e-env.py).
#   E2E_LINK_TYPES  link-type matrix: all (default) | none | comma list, e.g. general,partner
#   E2E_EXPECT_PRODUCT  product name the click-token + App Link flows must show (default: any product)
#   E2E_EXPECT_VOUCHER  voucher code they must show (default in scripts/e2e-env.json)
#   RETRIES         attempts per flow (default 3)
#   CLICK_WAIT      seconds to poll /v1/events/click for a fresh token (default 60)
#   E2E_TOKEN       secret for the private backend check GET /v1/e2e/clicks/<token> (X-E2E-Token).
#                   When set, each real deferred flow also asserts the backend recorded (allow) or
#                   did not record (deny) the install for its own click. Never printed.
#   VERIFY_WAIT     seconds to poll that endpoint (default 15)
#   LOG_WAIT        seconds to wait for each expected SDK / app logcat line (default 15, polled every second)
#   E2E_LOG_DIR     where failed attempts dump `adb logcat -s LinkTrail KickFlip`
#                   (default build/e2e-logs; CI uploads it as an artifact on failure)
#   E2E_RESULTS     JSON-lines file, one row per flow, for scripts/e2e-report.py (default
#                   $E2E_LOG_DIR/results.jsonl). CI renders it into the step summary / PR comment.
#   ANDROID_SERIAL  the emulator / device to use (adb and Maestro); unset = the only one attached
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

APP_ID="io.linktrail.demo.store"
FLOW_DIR="scripts"
APK="example/build/outputs/apk/debug/example-debug.apk"
LOG_DIR="${E2E_LOG_DIR:-$ROOT/build/e2e-logs}"

command -v maestro >/dev/null 2>&1 || { echo "ERROR: maestro not found. Install: curl -Ls https://get.maestro.mobile.dev | bash"; exit 1; }
command -v adb >/dev/null 2>&1 || { echo "ERROR: adb not found (Android platform-tools)."; exit 1; }

# Require a booted device/emulator.
if ! adb get-state 1>/dev/null 2>&1; then
  echo "ERROR: no booted Android device/emulator (check 'adb devices')."; exit 1
fi

# Environment + links (scripts/e2e-env.json). Sets LINKTRAIL_ENV (canonical), BACKEND_URL, BASE_OVERRIDE,
# SUBDOMAIN_HOST, CUSTOM_HOST, E2E_<SLOT> (full URLs), E2E_PRODUCT_RE and E2E_EXPECT_VOUCHER; a bad choice
# fails here, before the build.
targets="$(python3 -I scripts/e2e-env.py resolve --format shell)" || exit 1
eval "$targets"
REAL_DIR="$FLOW_DIR/real"
CLICK_WAIT="${CLICK_WAIT:-60}"
VERIFY_WAIT="${VERIFY_WAIT:-15}"
# The backend flags an install under 10 s after its click as click injection (CTIT_TOO_SHORT), and on
# Growth/Scale a flagged install earns nothing, so a fast flow would fail its reward check. No real
# user installs that fast: the app is launched only once this long has passed since the click.
MIN_CTIT_WAIT="${MIN_CTIT_WAIT:-15}"
# Android Chrome UA: the redirect sends Android clicks to androidUrl (Play Store) + &referrer=lt_click=<token>.
ANDROID_UA="Mozilla/5.0 (Linux; Android 15; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"

HAVE_KEY=0
[[ -n "${LINKTRAIL_KEY:-}" ]] && HAVE_KEY=1

# The SDK under test: the published artifact, version from gradle/libs.versions.toml (linktrailSdk).
SDK_VERSION="$(sed -nE 's/^linktrailSdk[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' gradle/libs.versions.toml)"
echo "==> Building the example APK against io.linktrail:sdk:${SDK_VERSION:-?} from Maven Central (environment: $LINKTRAIL_ENV, backend: $BACKEND_URL, link host: $SUBDOMAIN_HOST)"
# Built once. LINKTRAIL_KEY comes from the environment (never echoed); the link host drives the App
# Links intent filter + linkDomains (the custom host too: the re-engagement link-type rows open its links);
# LINKTRAIL_BASE is set only for an environment with override_backend (none here: prod is the SDK default).
LINKTRAIL_LINK_HOST="$SUBDOMAIN_HOST" LINKTRAIL_CUSTOM_LINK_HOST="$CUSTOM_HOST" LINKTRAIL_BASE="$BASE_OVERRIDE" ./gradlew :example:assembleDebug -q

echo "==> Installing $APK"
# Uninstall first: a cached emulator image can hold a copy signed with another debug key, and
# `install -r` then fails with INSTALL_FAILED_UPDATE_INCOMPATIBLE. Fails harmlessly if not installed.
adb uninstall "$APP_ID" >/dev/null 2>&1 || true
adb install -r -t "$APK" >/dev/null

# link_for <flow name> → the link slot's resolved URL (scripts/e2e-env.py; same slots as the iOS suite).
link_for() {
  case "$1" in
    deferred_event_*)    echo "$E2E_REWARD_LINK_PER_EVENT" ;;
    deferred_revshare_*) echo "$E2E_REWARD_LINK_REV_SHARE" ;;
    *custom*problistic*) echo "$E2E_CUSTOM_PROBLISTIC_LINK" ;;
    *custom*)            echo "$E2E_CUSTOM_LINK" ;;
    *problistic*)        echo "$E2E_SUBDOMAIN_PROBLISTIC_LINK" ;;
    *)                   echo "$E2E_SUBDOMAIN_LINK" ;;
  esac
}

# Which flows to run. Real flows are "<yaml>|<row name>|<link>|<link type>" jobs. Every selected flow
# marked link_type_matrix (E2E_MATRIX_FLOWS) runs once more per type in E2E_LINK_TYPES_RUN, as
# <flow>__<type> on that type's link (as on iOS).
IFS=',' read -r -a LINK_TYPES_RUN <<< "$E2E_LINK_TYPES_RUN"
IFS=',' read -r -a LINK_TYPES_SKIPPED <<< "$E2E_LINK_TYPES_SKIPPED"
IFS=',' read -r -a LINK_TYPE_FLOWS <<< "$E2E_MATRIX_FLOWS"
IFS=',' read -r -a LINK_TYPE_ONLY <<< "${E2E_MATRIX_ONLY_FLOWS:-}"
# link_type_url <type> → its resolved URL (E2E_LINK_TYPE_<TYPE> from scripts/e2e-env.py).
link_type_url() { local var; var="E2E_LINK_TYPE_$(printf '%s' "$1" | tr '[:lower:]' '[:upper:]')"; printf '%s' "${!var:-}"; }
is_matrix_flow() { local f; for f in ${LINK_TYPE_FLOWS[@]+"${LINK_TYPE_FLOWS[@]}"}; do [[ "$f" == "$1" ]] && return 0; done; return 1; }
# is_type_only <flow> → 0 for the matrix flows with no plain row (link_type_only in scripts/e2e-flows.json).
is_type_only() { local f; for f in ${LINK_TYPE_ONLY[@]+"${LINK_TYPE_ONLY[@]}"}; do [[ "$f" == "$1" ]] && return 0; done; return 1; }
REAL_FLOWS=()
MATRIX_SELECTED=()   # matrix flows picked this run: their skipped link types get a row each
add_real() { # add_real <flow name> [only link type]: the flow itself (no type), then its link-type rows
  local t
  if [[ -z "${2:-}" ]] && ! is_type_only "$1"; then REAL_FLOWS+=("$REAL_DIR/$1.yaml|$1|$(link_for "$1")|"); fi
  is_matrix_flow "$1" || return 0
  [[ -n "${2:-}" ]] || MATRIX_SELECTED+=("$1")
  for t in ${LINK_TYPES_RUN[@]+"${LINK_TYPES_RUN[@]}"}; do
    [[ -n "${2:-}" && "$t" != "$2" ]] && continue
    REAL_FLOWS+=("$REAL_DIR/$1.yaml|$1__$t|$(link_type_url "$t")|$t")
  done
}
if [[ $# -ge 1 ]]; then
  name="${1%.yaml}"; name="${name#real/}"
  if [[ "$name" == *__* ]]; then
    base="${name%%__*}"; lt="${name#*__}"
    is_matrix_flow "$base" || { echo "ERROR: '$base' has no link-type rows (link_type_matrix in scripts/e2e-flows.json: ${E2E_MATRIX_FLOWS:-none})."; exit 1; }
    FLOWS=(); add_real "$base" "$lt"
    [[ ${#REAL_FLOWS[@]} -gt 0 ]] || { echo "ERROR: link type '$lt' has no $LINKTRAIL_ENV link or isn't selected (E2E_LINK_TYPES)."; exit 1; }
  elif [[ -f "$REAL_DIR/$name.yaml" ]]; then FLOWS=(); add_real "$name"
  else FLOWS=("$FLOW_DIR/$name.yaml"); fi
else
  FLOWS=("$FLOW_DIR"/*.yaml)
  for flow in "$REAL_DIR"/*.yaml; do add_real "$(basename "$flow" .yaml)"; done
fi
# Link-type rows go after the plain flows, type by type (as the report lists them).
plain=(); matrix=()
for job in ${REAL_FLOWS[@]+"${REAL_FLOWS[@]}"}; do
  IFS='|' read -r _ _ _ jt <<< "$job"; if [[ -n "$jt" ]]; then matrix+=("$job"); else plain+=("$job"); fi
done
REAL_FLOWS=(${plain[@]+"${plain[@]}"})
for t in ${LINK_TYPES_RUN[@]+"${LINK_TYPES_RUN[@]}"}; do
  for job in ${matrix[@]+"${matrix[@]}"}; do
    IFS='|' read -r _ _ _ jt <<< "$job"; [[ "$jt" == "$t" ]] && REAL_FLOWS+=("$job")
  done
done
PREPARED_DIR="$(mktemp -d)"
VERIFY_LAST="$PREPARED_DIR/verify-last.json"
# The current row's per-check results (name<TAB>pass|fail|skipped<TAB>detail), for the report.
ROW_CHECKS="$PREPARED_DIR/checks.tsv"
: > "$ROW_CHECKS"
# skipped_check_reason → "<check>: <detail>" of the row's first skipped check, or nothing.
skipped_check_reason() { awk -F'\t' '$2 == "skipped" { print $1 ": " $3; exit }' "$ROW_CHECKS"; }
add_check() { printf '%s\t%s\t%s\n' "$1" "$2" "$(printf '%s' "$3" | tr '\t\n' '  ')" >> "$ROW_CHECKS"; }

# Simulated-suite isolation (see the header). The example app reads the property once, at launch, in
# debug builds only; the real flows run with it cleared.
SIM_PROP="debug.kickflip.simulated"
SIM_MODE_LOG="E2E simulated mode ($SIM_PROP=1): install tracking off, no install is sent"
SIM_INSTALL_LOG="Sending install event"
set_simulated() { # set_simulated on|off
  if [[ "$1" == on ]]; then adb shell setprop "$SIM_PROP" 1 >/dev/null 2>&1 || true
  else adb shell setprop "$SIM_PROP" "''" >/dev/null 2>&1 || true; fi
}
trap 'set_simulated off; rm -rf "$PREPARED_DIR"' EXIT

# Clear stale Maestro state (a leftover process / adb port-forward / on-device driver from an
# interrupted run makes the next run die with "DeviceServerDied … UNAVAILABLE"). Reinstalling the
# driver is cheap and Maestro re-pushes it on demand.
reset_maestro() {
  adb forward --remove-all >/dev/null 2>&1 || true
  adb uninstall dev.mobile.maestro      >/dev/null 2>&1 || true
  adb uninstall dev.mobile.maestro.test >/dev/null 2>&1 || true
}

# Slow CI emulators often raise "System UI isn't responding" over the app, which hides the consent
# gate. Suppress ANR/crash dialogs and close any system
# dialog before each flow.
settle_device() {
  adb shell settings put global hide_error_dialogs 1 >/dev/null 2>&1 || true
  adb shell am broadcast -a android.intent.action.CLOSE_SYSTEM_DIALOGS >/dev/null 2>&1 || true
  if adb shell dumpsys window 2>/dev/null | grep -q "Application Not Responding"; then
    adb shell input keyevent KEYCODE_BACK >/dev/null 2>&1 || true
  fi
}

# Diagnostics: each failed attempt saves the SDK + example app logcat to $LOG_DIR/<label>.log, so the
# SDK's install / resolve line (e.g. "Install tracking failed: Server returned status 404: …") is in
# the CI artifact. The emulator is gone after the job step, so the dump has to happen here.
mkdir -p "$LOG_DIR"
dump_logcat() {
  adb logcat -d -s LinkTrail KickFlip > "$LOG_DIR/$1.log" 2>&1 || true
  echo "   logcat saved: $LOG_DIR/$1.log"
}

# Results for the e2e report (scripts/e2e-report.py). A failed record never fails the run.
RESULTS="${E2E_RESULTS:-$LOG_DIR/results.jsonl}"
: > "$RESULTS"
record() { python3 -I scripts/e2e-report.py record --results "$RESULTS" "$@" || echo "   (could not record the result)" >&2; }

# run_maestro <label> <maestro args…> → Maestro with its debug output and screenshots directly in
# $LOG_DIR/<label>/ (flattened: without it Maestro nests them under a hidden .maestro/tests/<time>/,
# which upload-artifact skips) and its console output in $LOG_DIR/<label>.maestro.txt (the report
# reads the failed step from it). Both are removed again when the attempt passes.
# ANDROID_SERIAL (when set) pins adb to one
# emulator; pin Maestro to it too, or with a second device attached it may pick the other one.
MAESTRO=(maestro)
[[ -n "${ANDROID_SERIAL:-}" ]] && MAESTRO+=(--device "$ANDROID_SERIAL")
run_maestro() {
  local label="$1"; shift
  if "${MAESTRO[@]}" test --debug-output "$LOG_DIR/$label" --flatten-debug-output --test-output-dir "$LOG_DIR/$label" \
      "$@" 2>&1 | tee "$LOG_DIR/$label.maestro.txt"; then
    rm -rf "${LOG_DIR:?}/$label" "$LOG_DIR/$label.maestro.txt"
    return 0
  fi
  return 1
}

RETRIES="${RETRIES:-3}"
# Seconds to wait for an expected SDK / app log line to appear in logcat (polled every second).
LOG_WAIT="${LOG_WAIT:-15}"
reset_maestro   # start clean
settle_device

# sim_isolated → 0 when this attempt's logcat shows the app in simulated mode and no install sent.
# Sets SIM_ERROR otherwise.
sim_isolated() {
  local out waited=0
  SIM_ERROR=""
  # The mode line can land after the flow: poll for it (LOG_WAIT), then check what came with it.
  while :; do
    out="$(adb logcat -d -s LinkTrail:V KickFlip:V 2>/dev/null || true)"
    grep -qF "$SIM_MODE_LOG" <<< "$out" && break
    (( waited >= LOG_WAIT )) && break
    sleep 1; waited=$((waited + 1))
  done
  if ! grep -qF "$SIM_MODE_LOG" <<< "$out"; then
    SIM_ERROR="the app did not log simulated mode ($SIM_PROP not honoured: not a debug build, or an older APK)"
  elif grep -qF "$SIM_INSTALL_LOG" <<< "$out"; then
    SIM_ERROR="the SDK sent an install during a simulated flow (it must send none)"
  fi
  [[ -z "$SIM_ERROR" ]]
}

fail=0
[[ ${#FLOWS[@]} -gt 0 ]] && set_simulated on
for flow in ${FLOWS[@]+"${FLOWS[@]}"}; do
  ok=0; name="$(basename "$flow" .yaml)"; started=$SECONDS
  for attempt in $(seq 1 "$RETRIES"); do
    echo "==> maestro test $flow (attempt $attempt/$RETRIES)"
    settle_device
    adb logcat -c >/dev/null 2>&1 || true
    label="$name-attempt$attempt"; SIM_STEP=""; SIM_ERROR=""
    if run_maestro "$label" "$flow"; then
      if sim_isolated; then ok=1; break; fi
      echo "   simulated isolation check failed: $SIM_ERROR" >&2
      SIM_STEP="simulated isolation check"
    fi
    dump_logcat "$label"
    echo "   attempt failed — resetting the Maestro driver and retrying…"
    reset_maestro; sleep 3
  done
  if [[ $ok -eq 1 ]]; then
    record --flow "$name" --suite simulated --result pass --attempts "$attempt" --duration $((SECONDS - started))
  elif [[ -n "$SIM_STEP" ]]; then
    echo "!! FAILED after $RETRIES attempts: $flow"; fail=1
    record --flow "$name" --suite simulated --result fail --attempts "$RETRIES" --duration $((SECONDS - started)) \
      --log "$LOG_DIR/$label.log" --step "$SIM_STEP" --error "$SIM_ERROR"
  else
    echo "!! FAILED after $RETRIES attempts: $flow"; fail=1
    record --flow "$name" --suite simulated --result fail --attempts "$RETRIES" --duration $((SECONDS - started)) \
      --maestro-out "$LOG_DIR/$label.maestro.txt" --log "$LOG_DIR/$label.log" --debug-dir "$label" \
      --step "maestro test failed (see the job log)"
  fi
done
set_simulated off

# ── Real flows ───────────────────────────────────────────────────────────────────────────────

reset_props() {
  adb shell setprop debug.linktrail.referrer "''" >/dev/null 2>&1 || true
  adb shell setprop debug.linktrail.base "''" >/dev/null 2>&1 || true
  set_simulated off   # the real flows must send their install
}


# real_click <url> → prints the 32-hex lt_click token from the Play Store redirect.
real_click() {
  local redirect token
  redirect="$(curl -sS -o /dev/null -A "$ANDROID_UA" -w '%{redirect_url}' "$1")" || return 1
  token="$(printf '%s' "$redirect" | grep -oE 'lt_click(%3D|=)[0-9a-f]{32}' | head -1 | grep -oE '[0-9a-f]{32}$')" || true
  [[ -n "$token" ]] || { echo "   no lt_click in the redirect for $1 (got: ${redirect:-<none>})" >&2; return 1; }
  printf '%s' "$token"
}

# wait_ctit <click time in $SECONDS> → returns once MIN_CTIT_WAIT has passed since the click; no click, no wait.
wait_ctit() {
  [[ -n "$1" ]] || return 0
  local left=$((MIN_CTIT_WAIT - (SECONDS - $1)))
  if (( left > 0 )); then sleep "$left"; fi
}

# wait_click <token> → 0 once GET /v1/events/click/<token> answers 200 for this workspace's key.
wait_click() {
  local code waited=0
  while (( waited < CLICK_WAIT )); do
    code="$(curl -sS -o /dev/null -w '%{http_code}' -H "X-API-Key: $LINKTRAIL_KEY" "$BACKEND_URL/v1/events/click/$1" || true)"
    [[ "$code" == "200" ]] && return 0
    sleep 2; waited=$((waited + 2))
  done
  echo "   click token not visible to this key after ${CLICK_WAIT}s (last status: ${code:-none})" >&2
  return 1
}

# verify_backend <mode> <token> [link type] [baseline file] [reward model] → checks the private e2e endpoint for this
# click only; scripts/e2e-verify.py has the rules for each mode:
#   allow / deny               the install (recorded + attributed, or nothing), plus on link-type rows the
#                              reward and earning (rewarded_link_types in scripts/e2e-env.json)
#   reopen_allow / reopen_deny an App Link open on the installed app against the baseline response read
#                              after the install: openCount +1 / unchanged, installCount + earning unchanged
#   events_allow / events_deny the reward flows after their events: the earning of the contract formula
# allow modes poll until the check matches; deny modes hold the whole window, so a late install / open
# shows. A backend without a field the check needs (e.g. earning) fails at once, never skipped.
# Sets BACKEND_RESULT, BACKEND_DETAIL (always: report.json's backend_detail) and, on failure, FAIL_STEP
# and FAIL_ERROR; the last 200 body is kept in $VERIFY_LAST (the next step's baseline).
verify_backend() {
  local mode="$1" token="$2" link_type="${3:-}" baseline="${4:-}" model="${5:-}" body code waited=0 out status="" step="" detail="" checks=""
  if [[ -z "${E2E_TOKEN:-}" ]]; then
    # Not checkable: the row ends skipped with this reason, never a pass.
    BACKEND_RESULT=n/a; BACKEND_DETAIL="not checked: E2E_TOKEN not set"; ROW_UNCHECKED="not checked: E2E_TOKEN not set"
    echo "   backend check skipped: E2E_TOKEN not set"; return 0
  fi
  body="$(mktemp)"; rm -f "$VERIFY_LAST"
  while (( waited <= VERIFY_WAIT )); do
    # Header passed through stdin config, so the secret never appears in argv or the log.
    code="$(printf 'header = "X-E2E-Token: %s"\n' "$E2E_TOKEN" | curl -sS -K - -o "$body" -w '%{http_code}' "$BACKEND_URL/v1/e2e/clicks/$token" || true)"
    if [[ "$code" == "404" ]]; then
      rm -f "$body"
      BACKEND_RESULT=fail; FAIL_STEP="backend install check"; BACKEND_DETAIL="$mode: e2e verify endpoint not enabled (404)"
      FAIL_ERROR="e2e verify endpoint not enabled (404)"
      echo "   e2e verify endpoint not enabled — set E2E_ENDPOINTS_ENABLED=true and E2E_TOKEN on the backend" >&2
      return 1
    fi
    if [[ "$code" == "200" ]]; then
      out="$(python3 -I scripts/e2e-verify.py check --mode "$mode" --body "$body" --link-type "$link_type" \
        --rewarded "${E2E_REWARDED_LINK_TYPES:-}" --baseline "$baseline" --model "$model" \
        --revenue-minor "${E2E_REVENUE_MINOR:-0}" --other-event "${E2E_OTHER_EVENT:-e2e_other}" \
        --events-check "$([[ "${E2E_CHECK_EVENTS:-1}" == 1 ]] && echo on || echo off)" --env "$LINKTRAIL_ENV")" \
        || out=$'bad\nbackend install check\nscripts/e2e-verify.py failed'
      { read -r status; read -r step; IFS= read -r detail; } <<< "$out" || true
      checks="$(grep '^CHECK' <<< "$out" | cut -f2- || true)"
      cp "$body" "$VERIFY_LAST"
      # missing: the field won't appear; fail: a flagged install or a wrong link type won't change.
      [[ "$status" == missing || "$status" == fail ]] && break
      if [[ "$mode" == *allow && "$status" == ok ]]; then break; fi
      if [[ "$mode" == *deny && "$status" != ok ]]; then break; fi
    fi
    sleep 3; waited=$((waited + 3))
  done
  rm -f "$body"
  # The last response's per-check rows (fraud, link type, events / revenue) go to the report.
  [[ -n "$checks" ]] && printf '%s\n' "$checks" >> "$ROW_CHECKS"
  # For the report: BACKEND_RESULT ok (check matched) / fail (did not); n/a when not reached.
  if [[ "$status" == ok ]]; then BACKEND_RESULT=ok; BACKEND_DETAIL="$mode: $detail"; echo "   backend ok ($mode): $detail"; return 0; fi
  BACKEND_RESULT=fail
  if [[ -n "$status" ]]; then
    echo "   backend check failed ($mode): $detail" >&2
    FAIL_STEP="${step:-backend install check}"; BACKEND_DETAIL="$mode: $detail"
    # A missing field (or a fraud flag / wrong link type) is the clearest message there is: the row's error too.
    [[ "$status" == missing || "$status" == fail ]] && FAIL_ERROR="${detail%%;*}"
  else
    echo "   backend check failed ($mode): no 200 within ${VERIFY_WAIT}s (last status: ${code:-none})" >&2
    FAIL_STEP="backend install check"
    BACKEND_DETAIL="$mode: no 200 within ${VERIFY_WAIT}s (last status: ${code:-none})"
  fi
  return 1
}

# read_device_id → "id <id>" from the example app's debug label (e2e-device-id: a uiautomator dump of the
# screen, else the label's logcat line "E2E device id: <id>"), "none" (the label shows none: the SDK has
# no device id) or "unread" (the label couldn't be read).
read_device_id() {
  local dump="$PREPARED_DIR/ui.xml" log="$PREPARED_DIR/device-log.txt"
  : > "$dump"
  adb shell uiautomator dump /sdcard/e2e-ui.xml >/dev/null 2>&1 && adb exec-out cat /sdcard/e2e-ui.xml > "$dump" 2>/dev/null || true
  adb logcat -d -s KickFlip:V > "$log" 2>/dev/null || true
  python3 -I scripts/e2e-verify.py device-id --dump "$dump" --log "$log" 2>/dev/null || echo unread
}

# verify_device <consent> <link url> <attempt start, epoch s> → the *_problistic install by SDK device id:
# GET /v1/e2e/devices/<id> (scripts/e2e-verify.py check-device). Not checkable without E2E_TOKEN, when
# backend_checks.device_lookup is false, or when the label shows no device id: a skipped check row, and
# ROW_UNCHECKED, so the row ends skipped (never a pass). A label that can't be read fails. Sets BACKEND_RESULT,
# BACKEND_DETAIL and, on failure, FAIL_STEP / FAIL_ERROR.
DEVICE_STEP="backend device lookup check"
verify_device() {
  local consent="$1" url="$2" since="$3" id state body code waited=0 out status="" step="" detail="" checks="" why
  [[ -n "$since" ]] || { BACKEND_RESULT=fail; FAIL_STEP="$DEVICE_STEP"; FAIL_ERROR="no attempt start for the device lookup"; return 1; }
  why=""
  [[ -z "${E2E_TOKEN:-}" ]] && why="not checked: E2E_TOKEN not set"
  [[ -z "$why" && "${E2E_CHECK_DEVICE_LOOKUP:-1}" != 1 ]] && \
    why="not on $LINKTRAIL_ENV backend yet (backend_checks.device_lookup is false in scripts/e2e-env.json)"
  if [[ -n "$why" ]]; then
    BACKEND_RESULT=n/a; BACKEND_DETAIL="device lookup $why"; ROW_UNCHECKED="device lookup $why"
    add_check "device lookup" skipped "$why"; echo "   device lookup skipped: $why"; return 0
  fi
  state="$(read_device_id)"; id=""
  [[ "$state" == "id "* ]] && id="${state#id }"
  if [[ "$state" == none ]]; then
    # The label was read and shows none: the SDK has no device id (a denied install mints none), so
    # there is nothing to look up. Not checkable: skipped, never a pass.
    why="not checkable (no SDK device id)"
    BACKEND_RESULT=n/a; BACKEND_DETAIL="device_$consent: $why"; ROW_UNCHECKED="device lookup $why"
    add_check "device lookup" skipped "$why: the e2e-device-id label shows none"
    echo "   device lookup skipped: $why"; return 0
  fi
  if [[ -z "$id" ]]; then
    BACKEND_RESULT=fail; FAIL_STEP="$DEVICE_STEP"; FAIL_ERROR="could not read the app's debug label (e2e-device-id): no uiautomator dump and no 'E2E device id' log line"
    BACKEND_DETAIL="device_$consent: $FAIL_ERROR"; add_check "device lookup" fail "$FAIL_ERROR"
    echo "   $FAIL_ERROR" >&2; return 1
  fi
  body="$(mktemp)"
  while (( waited <= VERIFY_WAIT )); do
    code="$(printf 'header = "X-E2E-Token: %s"\n' "$E2E_TOKEN" | curl -sS -K - -o "$body" -w '%{http_code}' "$BACKEND_URL/v1/e2e/devices/$id" || true)"
    if [[ "$code" == "404" ]]; then
      rm -f "$body"
      BACKEND_RESULT=fail; FAIL_STEP="$DEVICE_STEP"; FAIL_ERROR="e2e device lookup not enabled (404)"
      BACKEND_DETAIL="device_$consent: $FAIL_ERROR"; add_check "device lookup" fail "$FAIL_ERROR"
      echo "   e2e device lookup not enabled: deploy GET /v1/e2e/devices/:deviceId, E2E_ENDPOINTS_ENABLED=true and E2E_TOKEN" >&2
      return 1
    fi
    if [[ "$code" == "200" ]]; then
      out="$(python3 -I scripts/e2e-verify.py check-device --mode "$consent" --body "$body" --slug "${url##*/}" --since "$since")" \
        || out=$'bad\nbackend device lookup check\nscripts/e2e-verify.py failed'
      { read -r status; read -r step; IFS= read -r detail; } <<< "$out" || true
      checks="$(grep '^CHECK' <<< "$out" | cut -f2- || true)"
      [[ "$status" == fail ]] && break
      if [[ "$consent" == allow && "$status" == ok ]]; then break; fi
      if [[ "$consent" == deny && "$status" != ok ]]; then break; fi
    fi
    sleep 3; waited=$((waited + 3))
  done
  rm -f "$body"
  [[ -n "$checks" ]] && printf '%s\n' "$checks" >> "$ROW_CHECKS"
  if [[ "$status" == ok ]]; then
    BACKEND_RESULT=ok; BACKEND_DETAIL="device_$consent: device ${id:0:8}… $detail"; echo "   backend ok (device_$consent): $detail"; return 0
  fi
  BACKEND_RESULT=fail; FAIL_STEP="${step:-$DEVICE_STEP}"
  if [[ -n "$status" ]]; then
    BACKEND_DETAIL="device_$consent: device ${id:0:8}… $detail"
    [[ "$status" == fail ]] && FAIL_ERROR="${detail%%;*}"
  else
    BACKEND_DETAIL="device_$consent: no 200 within ${VERIFY_WAIT}s (last status: ${code:-none})"
    add_check "device lookup" fail "no 200 within ${VERIFY_WAIT}s (last status: ${code:-none})"
  fi
  echo "   backend check failed (device_$consent): ${BACKEND_DETAIL#*: }" >&2
  return 1
}

# reward_link_type <flow name> → the reward link's type (reward_links link_type), empty otherwise.
reward_link_type() {
  case "$1" in
    deferred_event_*)    echo "${E2E_REWARD_LINK_TYPE_PER_EVENT:-}" ;;
    deferred_revshare_*) echo "${E2E_REWARD_LINK_TYPE_REV_SHARE:-}" ;;
  esac
}

# reward_model <flow name> → per_event / rev_share for the reward flows, empty otherwise.
reward_model() {
  case "$1" in
    deferred_event_*)    echo per_event ;;
    deferred_revshare_*) echo rev_share ;;
  esac
}
EVENT_WAIT="${EVENT_WAIT:-20}"
EVENT_HOOK_LOG="E2E event hook:"

# send_reward_events <flow name> <consent> → plans the events from the install check's response
# ($VERIFY_LAST; scripts/e2e-verify.py plan-events), opens each kickflip://e2e/event link on the app and
# waits for the app's hook line per event (deny: also the SDK's "dropped" line). Sets EVENTS_DETAIL;
# FAIL_STEP / FAIL_ERROR (and BACKEND_RESULT for a bad reward) on failure.
send_reward_events() {
  local name="$1" consent="$2" model out status detail links=() link n waited=0 logs done_n dropped_n
  model="$(reward_model "$name")"
  out="$(python3 -I scripts/e2e-verify.py plan-events --model "$model" --body "$VERIFY_LAST" \
    --revenue-minor "${E2E_REVENUE_MINOR:-0}" --other-event "${E2E_OTHER_EVENT:-e2e_other}")" || out=$'bad\nscripts/e2e-verify.py failed'
  { read -r status; IFS= read -r detail; } <<< "$out" || true
  while IFS= read -r link; do [[ -n "$link" ]] && links+=("$link"); done < <(tail -n +3 <<< "$out")
  EVENTS_DETAIL="$detail"
  if [[ "$status" != ok || ${#links[@]} -eq 0 ]]; then
    echo "   reward events not planned: $detail" >&2
    BACKEND_RESULT=fail; FAIL_STEP="backend event earning check"; FAIL_ERROR="$detail"
    return 1
  fi
  echo "   sending $detail"
  adb logcat -c >/dev/null 2>&1 || true
  for link in "${links[@]}"; do
    # One string for the device shell, so the query's & stays inside the quotes.
    adb shell "am start -W -a android.intent.action.VIEW -d '$link' $APP_ID" >/dev/null 2>&1 || true
    sleep 1
  done
  n=${#links[@]}
  while (( waited <= EVENT_WAIT )); do
    logs="$(adb logcat -d -s KickFlip:V LinkTrail:V 2>/dev/null || true)"
    if grep -qF "$EVENT_HOOK_LOG" <<< "$logs" && grep -F "$EVENT_HOOK_LOG" <<< "$logs" | grep -q "' failed:"; then
      FAIL_STEP="send reward events"; FAIL_ERROR="$(grep -F "$EVENT_HOOK_LOG" <<< "$logs" | grep "' failed:" | head -1 | sed 's/.*E2E event hook: //')"
      echo "   reward event failed: $FAIL_ERROR" >&2
      return 1
    fi
    # With consent every event must come back attributed to this install; false / null names the event.
    if [[ "$consent" == allow ]] && grep -F "$EVENT_HOOK_LOG" <<< "$logs" | grep "' done" | grep -qv "attributed=true[[:space:]]*$"; then
      FAIL_STEP="send reward events"
      FAIL_ERROR="$(grep -F "$EVENT_HOOK_LOG" <<< "$logs" | grep "' done" | grep -v "attributed=true[[:space:]]*$" | head -1 \
        | sed -E "s/.*E2E event hook: '([^']*)' done, (attributed=.*)/event '\\1' not attributed (\\2)/")"
      echo "   reward event not attributed: $FAIL_ERROR" >&2
      return 1
    fi
    done_n="$(grep -F "$EVENT_HOOK_LOG" <<< "$logs" | grep -c "' done" || true)"
    dropped_n="$(grep -c "dropped — consent not granted" <<< "$logs" || true)"
    if (( done_n >= n )) && { [[ "$consent" == allow ]] || (( dropped_n >= n )); }; then
      if [[ "$consent" == deny ]]; then echo "   reward events done: $done_n/$n (dropped by the SDK: $dropped_n)"
      else echo "   reward events done: $done_n/$n"; fi
      return 0
    fi
    sleep 2; waited=$((waited + 2))
  done
  FAIL_STEP="send reward events"
  FAIL_ERROR="the app's event hook logged ${done_n:-0}/$n events within ${EVENT_WAIT}s"
  [[ "$consent" == deny ]] && FAIL_ERROR+=" (SDK dropped ${dropped_n:-0}/$n without consent)"
  echo "   $FAIL_ERROR" >&2
  return 1
}

# expected_log <flow name> (a link-type row passes its flow's name) → the SDK log line that proves the network path ran (an extended regex for
# the probabilistic flows, a fixed string otherwise; see log_has).
expected_log() {
  case "$1" in
    # A real install response, whatever the backend's IP match decides (it has none yet: organic).
    deferred_*_allow_problistic) echo "Install attributed|Organic install \(no attribution match\)" ;;
    deferred_*_deny_problistic)  echo "Install not counted \(no consent\)" ;;
    deferred_*_allow)       echo "Install attributed (deterministic click token)" ;;
    deferred_*_deny)        echo "Install not counted (no consent) — routing the deferred link only" ;;
    reengagement_*_allow)   echo "Deep link resolved → path:" ;;
    reengagement_*_deny)    echo "Re-engagement resolved route-only — consent not granted (not recorded)" ;;
  esac
}

# sdk_log → the SDK's logcat so far. Read whole before grepping: with pipefail, `adb … | grep -q` fails
# when grep exits on the first match while adb is still writing (SIGPIPE), a false "line not found".
sdk_log() { adb logcat -d -s LinkTrail:V 2>/dev/null || true; }

# log_has <flow name> <expected> → 0 once the SDK logcat shows the expected line. Polled every second for
# up to LOG_WAIT seconds: the SDK can write the line after the Maestro flow has finished (a deny install's
# "Install not counted (no consent)" could come too late for a single read).
log_has() {
  local out waited=0
  while :; do
    out="$(sdk_log)"
    if [[ "$1" == *_problistic ]]; then grep -qE "$2" <<< "$out" && return 0
    else grep -qF "$2" <<< "$out" && return 0; fi
    (( waited >= LOG_WAIT )) && return 1
    sleep 1; waited=$((waited + 1))
  done
}

# click_flow <flow name> → 0 for flows that start with a real click (the deferred ones, and the
# re-engagement link-type rows, which install through a click first).
click_flow() { [[ "$1" == deferred_* || "$1" == reengagement_applink_type_* ]]; }
# reopen_flow <flow name> → 0 for the re-engagement link-type rows: install first, then the App Link open.
reopen_flow() { [[ "$1" == reengagement_applink_type_* ]]; }

# run_real <flow yaml> <attempt label> <row name> <link> [link type]. Sets FAIL_STEP / MAESTRO_FAILED /
# MAESTRO_LABEL, CLICK_TOKEN, BACKEND_RESULT and BACKEND_DETAIL for the report.
run_real() {
  local flow="$1" label="$2" row="$3" url="$4" link_type="${5:-}" token expect name consent install_expect install_detail=""
  local click_at=""
  local product_re="$E2E_PRODUCT_RE" voucher="$E2E_EXPECT_VOUCHER"
  name="${row%%__*}"   # a link-type row <flow>__<type> runs, logs and checks as its flow
  [[ "$name" == *_allow || "$name" == *_allow_* ]] && consent=allow || consent=deny
  expect="$(expected_log "$name")"
  FAIL_STEP=""; FAIL_ERROR=""; BACKEND_DETAIL=""; MAESTRO_FAILED=0; MAESTRO_LABEL="$label"; CLICK_TOKEN=""
  ROW_UNCHECKED=""   # set when the row's backend check is its point and can't run: recorded as skipped
  : > "$ROW_CHECKS"; ATTEMPT_EPOCH="$(date +%s)"
  # Cleared first, so a failed attempt's dump holds only this attempt (install + launch included).
  adb logcat -c >/dev/null 2>&1 || true
  adb uninstall "$APP_ID" >/dev/null 2>&1 || true
  reset_props
  [[ -n "$BASE_OVERRIDE" ]] && adb shell setprop debug.linktrail.base "$BASE_OVERRIDE"
  if click_flow "$name"; then
    echo "   real click: $url"
    click_at=$SECONDS
    if ! token="$(real_click "$url")"; then
      FAIL_STEP="real click"; FAIL_ERROR="no lt_click in the Play Store redirect for $url"
      # A reward link the product owner hasn't created yet answers 404: say so.
      if [[ -n "$(reward_model "$name")" ]] && \
          [[ "$(curl -sS -o /dev/null -A "$ANDROID_UA" -w '%{http_code}' "$url" || true)" == "404" ]]; then
        FAIL_ERROR="$LINKTRAIL_ENV link ${url##*/} not created"
      fi
      return 1
    fi
    CLICK_TOKEN="$token"
    wait_click "$token" || { FAIL_STEP="click registration"; FAIL_ERROR="click token not visible to this key after ${CLICK_WAIT}s"; return 1; }
    # Probabilistic flows stage no referrer: the install carries no click token.
    [[ "$name" == *_problistic ]] || adb shell setprop debug.linktrail.referrer "lt_click=$token"
  fi
  adb install -t "$APK" >/dev/null
  wait_ctit "$click_at"
  if [[ "$name" == reengagement_* ]]; then
    # Approve the link host for the app so the https link opens it, not the browser (Android 12+).
    # The link-type rows open custom-host links, so that host is approved as well.
    adb shell pm set-app-links-user-selection --user 0 --package "$APP_ID" true "$SUBDOMAIN_HOST" "$CUSTOM_HOST" >/dev/null 2>&1 || true
  fi
  if [[ -n "$(reward_model "$name")" ]]; then
    # The reward links carry the link types' customData: link_type_expect's product + voucher.
    product_re="$E2E_LT_PRODUCT_RE"; voucher="$E2E_LT_VOUCHER"
  fi
  if [[ -n "$link_type" ]]; then
    # The link-type link lands on link_type_expect's product + voucher; allow also asserts the meta row.
    product_re="$E2E_LT_PRODUCT_RE"; voucher="$E2E_LT_VOUCHER"
    if [[ ! -f "$PREPARED_DIR/$row.yaml" ]] && ! python3 -I scripts/e2e-env.py prepare-flow --flow "$flow" \
        --out "$PREPARED_DIR/$row.yaml" --link-type "$link_type" --source "$E2E_LT_SOURCE" \
        --consent "$consent"; then
      FAIL_STEP="prepare the link-type flow"; FAIL_ERROR="scripts/e2e-env.py prepare-flow failed for $flow"; return 1
    fi
    flow="$PREPARED_DIR/$row.yaml"
  fi
  if reopen_flow "$name"; then
    # Step 1, the app gets installed through the type's link: the deferred flow of the same consent
    # (counted install on allow, uncounted on deny), its install log line and backend check (reward and
    # earning included); that response is the baseline of the re-engagement check below.
    settle_device
    install_expect="$(expected_log "deferred_custom_$consent")"
    MAESTRO_LABEL="$label-install"
    run_maestro "$MAESTRO_LABEL" -e LINK_URL="$url" -e E2E_PRODUCT_RE="$product_re" -e E2E_VOUCHER="$voucher" \
      "$REAL_DIR/deferred_custom_$consent.yaml" || { MAESTRO_FAILED=1; return 1; }
    MAESTRO_LABEL="$label"
    if ! log_has "deferred_custom_$consent" "$install_expect"; then
      echo "   expected install log line not found: $install_expect" >&2
      FAIL_STEP="SDK log line check (install step)"; FAIL_ERROR="expected line not found within ${LOG_WAIT}s: $install_expect"
      return 1
    fi
    echo "   install step ok: $install_expect"
    verify_backend "$consent" "$token" "$link_type" || { BACKEND_DETAIL="install: $BACKEND_DETAIL"; return 1; }
    install_detail="install: $BACKEND_DETAIL"; BACKEND_DETAIL="$install_detail"
    # The baseline is only this attempt's matched response (no E2E_TOKEN: no backend checks at all).
    rm -f "$PREPARED_DIR/$row.baseline.json"
    if [[ "$BACKEND_RESULT" == ok ]]; then cp "$VERIFY_LAST" "$PREPARED_DIR/$row.baseline.json"; fi
    # Step 2 runs on the installed app: nothing is staged any more, and its log check sees only the open.
    adb shell setprop debug.linktrail.referrer "''" >/dev/null 2>&1 || true
    adb logcat -c >/dev/null 2>&1 || true
  fi
  settle_device
  run_maestro "$label" -e LINK_URL="$url" -e E2E_PRODUCT_RE="$product_re" -e E2E_VOUCHER="$voucher" \
    "$flow" || { MAESTRO_FAILED=1; return 1; }
  if ! log_has "$name" "$expect"; then
    echo "   expected log line not found: $expect" >&2
    FAIL_STEP="SDK log line check"; FAIL_ERROR="expected line not found within ${LOG_WAIT}s: $expect"
    return 1
  fi
  if [[ "$name" == *_problistic ]] && grep -qF "Install referrer lt_click token" <<< "$(sdk_log)"; then
    echo "   probabilistic flow read an lt_click token; the install must carry none" >&2
    FAIL_STEP="SDK log line check"; FAIL_ERROR="probabilistic flow read an lt_click token; the install must carry none"
    return 1
  fi
  echo "   logcat ok: $expect"
  # The backend check is per click token; probabilistic installs have none: device lookup (as on iOS).
  if reopen_flow "$name"; then
    if [[ -n "${E2E_TOKEN:-}" ]]; then
      verify_backend "reopen_$consent" "$token" "$link_type" "$PREPARED_DIR/$row.baseline.json"
      local rc=$?
      BACKEND_DETAIL="$install_detail; re-engagement: $BACKEND_DETAIL"
      return $rc
    fi
    # The screens passed, but the row exists for its backend check: never a pass without it.
    ROW_UNCHECKED="not checked: E2E_TOKEN not set"
  elif [[ -n "$(reward_model "$name")" ]]; then
    # Install first (recorded / nothing), then the events, then the earning of the contract formula.
    verify_backend "$consent" "$token" || { BACKEND_DETAIL="install: $BACKEND_DETAIL"; return 1; }
    if [[ "$BACKEND_RESULT" != ok ]]; then
      # No E2E_TOKEN: the reward can't be read, so no event is sent and nothing is checked.
      ROW_UNCHECKED="not checked: E2E_TOKEN not set"; return 0
    fi
    local install_detail="install: $BACKEND_DETAIL"
    # The install's response is the baseline: its earning must be 0 before any event is sent.
    cp "$VERIFY_LAST" "$PREPARED_DIR/$row.baseline.json"
    send_reward_events "$name" "$consent" || { BACKEND_DETAIL="$install_detail; events: $EVENTS_DETAIL"; return 1; }
    verify_backend "events_$consent" "$token" "$(reward_link_type "$name")" "$PREPARED_DIR/$row.baseline.json" "$(reward_model "$name")"
    local rc=$?
    BACKEND_DETAIL="$install_detail; events: $EVENTS_DETAIL; earning: $BACKEND_DETAIL"
    return $rc
  elif [[ "$name" == *_problistic ]]; then
    # No click token: checked by the SDK device id instead (as on iOS).
    verify_device "$consent" "$url" "$ATTEMPT_EPOCH" || return 1
  elif click_flow "$name"; then
    verify_backend "$consent" "$token" "$link_type" || return 1
  fi
}

# Link types with no link in this environment (prod until its links exist): a notice + skipped rows.
if [[ ${#LINK_TYPES_SKIPPED[@]} -gt 0 && ${#MATRIX_SELECTED[@]} -gt 0 ]]; then
  msg="link types without a $LINKTRAIL_ENV link, skipped: ${E2E_LINK_TYPES_SKIPPED} (add a \"$LINKTRAIL_ENV\" entry per type to link_types in scripts/e2e-env.json)"
  echo "==> NOTE: $msg"
  [[ -n "${GITHUB_ACTIONS:-}" ]] && echo "::notice title=e2e link types::$msg"
  for t in "${LINK_TYPES_SKIPPED[@]}"; do
    for f in "${MATRIX_SELECTED[@]}"; do
      record --flow "${f}__$t" --suite real --result skipped --link-type "$t" --error "no $LINKTRAIL_ENV link yet"
    done
  done
fi

if [[ ${#REAL_FLOWS[@]} -gt 0 ]]; then
  if [[ $HAVE_KEY -eq 0 ]]; then
    echo "==> SKIPPED ${#REAL_FLOWS[@]} real flow(s): LINKTRAIL_KEY is not set (the simulated flows above still ran)."
    echo "    Set LINKTRAIL_KEY (the prod workspace's SDK key) to run them."
    for job in "${REAL_FLOWS[@]}"; do
      IFS='|' read -r flow name TESTED_LINK link_type <<< "$job"
      record --flow "$name" --suite real --result skipped --link "$TESTED_LINK" --link-type "$link_type"
    done
  else
    trap 'reset_props; rm -rf "$PREPARED_DIR"' EXIT
    for job in "${REAL_FLOWS[@]}"; do
      IFS='|' read -r flow name TESTED_LINK link_type <<< "$job"
      ok=0; started=$SECONDS
      if [[ -n "$(reward_model "$name")" && -z "$TESTED_LINK" ]]; then
        echo "==> SKIPPED $name: no $LINKTRAIL_ENV link in reward_links (scripts/e2e-env.json)"
        [[ -n "${GITHUB_ACTIONS:-}" ]] && echo "::notice title=e2e reward links::$name skipped: no $LINKTRAIL_ENV link in reward_links (scripts/e2e-env.json)"
        record --flow "$name" --suite real --result skipped --error "no $LINKTRAIL_ENV link yet"
        continue
      fi
      for attempt in $(seq 1 "$RETRIES"); do
        echo "==> real flow $name ($flow, attempt $attempt/$RETRIES)"
        label="real-$name-attempt$attempt"
        BACKEND_RESULT=n/a   # verify_backend sets ok / fail
        if run_real "$flow" "$label" "$name" "$TESTED_LINK" "$link_type"; then ok=1; break; fi
        dump_logcat "$label"
        echo "   last 30 LinkTrail log lines:"
        adb logcat -d -s LinkTrail | tail -30 | sed 's/^/     | /' || true
        echo "   attempt failed — resetting and retrying…"
        reset_maestro; sleep 3
      done
      reset_props
      # Rule: a row passes only when every backend check ran. A skipped check (events off, no
      # fraudReasons, device lookup off, …) makes the row skipped, with that check's reason.
      if [[ $ok -eq 1 && -z "$ROW_UNCHECKED" ]]; then ROW_UNCHECKED="$(skipped_check_reason)"; fi
      if [[ $ok -eq 1 && -n "$ROW_UNCHECKED" ]]; then
        echo "==> SKIPPED $name: $ROW_UNCHECKED (the screens passed; a row passes only when every backend check ran)"
        record --flow "$name" --suite real --result skipped --attempts "$attempt" --duration $((SECONDS - started)) \
          --backend "$BACKEND_RESULT" --backend-detail "$BACKEND_DETAIL" --error "$ROW_UNCHECKED" --link "$TESTED_LINK" --link-type "$link_type" \
          --checks-file "$ROW_CHECKS"
      elif [[ $ok -eq 1 ]]; then
        record --flow "$name" --suite real --result pass --attempts "$attempt" --duration $((SECONDS - started)) \
          --backend "$BACKEND_RESULT" --backend-detail "$BACKEND_DETAIL" --link "$TESTED_LINK" --link-type "$link_type" \
          --checks-file "$ROW_CHECKS"
      else
        echo "!! FAILED after $RETRIES attempts: $name"; fail=1
        maestro_out=""; [[ $MAESTRO_FAILED -eq 1 ]] && maestro_out="$LOG_DIR/$MAESTRO_LABEL.maestro.txt"
        record --flow "$name" --suite real --result fail --attempts "$RETRIES" --duration $((SECONDS - started)) \
          --backend "$BACKEND_RESULT" --maestro-out "$maestro_out" --log "$LOG_DIR/$label.log" \
          --debug-dir "$MAESTRO_LABEL" --token "$CLICK_TOKEN" --step "${FAIL_STEP:-maestro test failed (see the job log)}" \
          --error "$FAIL_ERROR" --backend-detail "$BACKEND_DETAIL" --link "$TESTED_LINK" --link-type "$link_type" \
          --checks-file "$ROW_CHECKS"
      fi
    done
    # Leave the app installed in a normal state.
    adb install -r -t "$APK" >/dev/null 2>&1 || true
  fi
fi

if [[ $fail -ne 0 ]]; then echo "==> Some E2E flows failed"; exit 1; fi
echo "==> All E2E flows passed"
