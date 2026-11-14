# E2E: the published SDK

Maestro end-to-end tests for the **published** LinkTrail Android SDK. The KickFlip demo in
[`example/`](example) depends on `io.linktrail:sdk` from **Maven Central**, the same way any app
does. CI runs it on GitHub-hosted runners (`.github/workflows/e2e.yml`).

The SDK version is set in one place, `linktrailSdk` in
[`gradle/libs.versions.toml`](gradle/libs.versions.toml). Bump it there after a release.

## Flows

| Suite | Files | Needs |
|---|---|---|
| Simulated (12) | `scripts/*.yaml`: the in-app Deep Link Simulator (home, category, product, voucher) and `kickflip://` re-engagement links, consent allow and deny | nothing |
| Real (16) | `scripts/real/*.yaml`: real clicks on the custom-domain and subdomain links, probabilistic installs, App Link re-engagement, `rev_share` and `per_event` reward links | `LINKTRAIL_KEY` |
| Link-type matrix | `deferred_custom_{allow,deny}` and `reengagement_applink_type_{allow,deny}` once per link type (general, campaign, influencer, partner). `per_install` reward checks run on the rewarded types | `LINKTRAIL_KEY` |

Hosts, slugs and the backend are set only in [`scripts/e2e-env.json`](scripts/e2e-env.json). A link
type or reward link that has no entry for the environment is skipped with a notice. For example,
prod has no `per_event` link, so the `deferred_event_*` rows are skipped. The expected result of each
row is listed in [`scripts/e2e-flows.json`](scripts/e2e-flows.json).

Backend checks (install recorded or not, reward, earning, opens) need `E2E_TOKEN`. Without it, a
row whose purpose is that check is reported as skipped. It is never reported as passed.

## Run locally

You need JDK 17, a booted emulator or device (API 26+), `adb` and
[Maestro](https://maestro.mobile.dev).

```bash
cd e2e
bash scripts/e2e-maestro.sh                         # simulated flows only (no key)
LINKTRAIL_KEY=lt_live_… bash scripts/e2e-maestro.sh # plus the real flows
bash scripts/e2e-maestro.sh deferred_voucher_allow  # one flow
```

The script builds `example` (`./gradlew :example:assembleDebug`), installs it and runs the flows.
Results go to `build/e2e-logs/results.jsonl`, and the logcat of each failed attempt is saved there
too. Never commit a key. If you want a key in a file, put it in the untracked
`e2e/local.properties` as `linktrail.apiKey=…`.
