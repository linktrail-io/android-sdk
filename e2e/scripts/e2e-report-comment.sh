#!/usr/bin/env bash
# Create or update the ONE sticky e2e report comment on a pull request.
#
# The comment is found by the marker (default <!-- linktrail-e2e-report -->, or $MARKER) at the start of its body (written
# by scripts/e2e-report.py) and by its author (the workflow token's bot), then edited in place, so a
# PR never collects more than one report comment.
#
# Usage: GH_TOKEN=… bash scripts/e2e-report-comment.sh <owner/repo> <pr number> <report.md>
# Needs: curl + python3 , and a token with
# pull-requests: write. The token reaches curl through a stdin config, so it is never in argv / `ps`.
# GITHUB_API_URL (set by Actions) picks the API host.
set -euo pipefail

REPO="${1:?owner/repo}"; PR="${2:?pr number}"; BODY="${3:?report.md}"
MARKER="${MARKER:-<!-- linktrail-e2e-report -->}"
AUTHOR="${COMMENT_AUTHOR:-github-actions[bot]}"
API="${GITHUB_API_URL:-https://api.github.com}"

[[ -s "$BODY" ]] || { echo "No report body at $BODY; nothing to comment."; exit 0; }
head -1 "$BODY" | grep -qF "$MARKER" || { echo "ERROR: $BODY does not start with $MARKER" >&2; exit 1; }
[[ "$PR" =~ ^[0-9]+$ ]] || { echo "ERROR: PR number must be numeric (got '$PR')" >&2; exit 2; }
[[ "$REPO" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { echo "ERROR: repo must be owner/name (got '$REPO')" >&2; exit 2; }
[[ -n "${GH_TOKEN:-}" ]] || { echo "ERROR: GH_TOKEN is not set" >&2; exit 1; }

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# api <method> <url> [payload file] → prints the HTTP status; the response body is in $work/resp.
api() {
  local data=()
  [[ -n "${3:-}" ]] && data=(--data-binary "@$3")
  printf 'header = "Authorization: Bearer %s"\n' "$GH_TOKEN" \
    | curl -sS -o "$work/resp" -w '%{http_code}' --max-time 30 --config - -X "$1" \
        -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28" \
        ${data[@]+"${data[@]}"} "$2" || true
}

python3 -I -c 'import json, sys; json.dump({"body": open(sys.argv[1], encoding="utf-8", errors="replace").read()}, open(sys.argv[2], "w"))' \
  "$BODY" "$work/payload"

# Our comment: the first one by $AUTHOR whose body starts with the marker, across every page.
# A failed lookup falls through to creating a comment (which reports its own error).
id="" page=1
while :; do
  code="$(api GET "$API/repos/$REPO/issues/$PR/comments?per_page=100&page=$page")"
  if [[ "$code" != 200 ]]; then echo "warning: listing PR comments failed (HTTP $code); creating a new one" >&2; break; fi
  read -r id count < <(python3 -I -c '
import json, sys
items = json.load(open(sys.argv[1]))
hit = next((c["id"] for c in items if (c.get("user") or {}).get("login") == sys.argv[2]
            and (c.get("body") or "").startswith(sys.argv[3])), "")
print(hit or "-", len(items))' "$work/resp" "$AUTHOR" "$MARKER")
  [[ "$id" == "-" ]] && id=""
  if [[ -n "$id" || "$count" -lt 100 ]]; then break; fi
  page=$((page + 1))
done

if [[ -n "$id" ]]; then
  code="$(api PATCH "$API/repos/$REPO/issues/comments/$id" "$work/payload")"
  [[ "$code" == 200 ]] || { echo "ERROR: updating comment $id failed (HTTP $code)" >&2; exit 1; }
else
  code="$(api POST "$API/repos/$REPO/issues/$PR/comments" "$work/payload")"
  [[ "$code" == 201 ]] || { echo "ERROR: creating the comment failed (HTTP $code)" >&2; exit 1; }
fi
python3 -I -c 'import json, sys; print(json.load(open(sys.argv[1])).get("html_url", ""))' "$work/resp" 2>/dev/null || true
