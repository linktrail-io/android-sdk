# Troubleshooting — Android App Links & Deferred Deep Linking

This guide covers the most common reasons a LinkTrail deep link doesn't behave as expected on
Android, and the exact commands to diagnose each one. Package name and domain from the KickFlip
demo (`io.linktrail.example`, `kick.linktrail.io`) are used in examples — substitute your own.

## Start here: what are you seeing?

| Symptom | Likely cause | Section |
|---|---|---|
| Fresh install routes correctly, but with the app **already installed** the link opens the browser / Play Store | App Links verification failed on the device | [1](#1-link-opens-the-browser--play-store-instead-of-the-installed-app) |
| Link opens the app, but lands on the wrong screen | Path not handled by your routing code | [5](#5-app-opens-but-lands-on-the-wrong-screen) |
| First-launch (deferred) link never arrives | SDK not configured / no API key | [6](#6-deferred-deep-link-not-delivered-on-first-launch) |
| Typing the URL in Chrome's address bar opens the website, not the app | Expected Android behavior — not a bug | [4](#4-address-bar-navigation-never-opens-the-app) |

---

## 1. Link opens the browser / Play Store instead of the installed app

Android only hands an `https://` link to your app if **App Links verification** succeeded for that
domain. When verification fails, the link opens in the browser; LinkTrail's link page then
redirects to the Play Store — which is why a *failed* verification looks like "it keeps sending me
to the store even though the app is installed."

Verification succeeds only when the SHA-256 fingerprint of the certificate **your installed APK is
actually signed with** appears in `https://<your-domain>/.well-known/assetlinks.json`.

### Step 1 — check what the domain serves

```bash
curl -s https://kick.linktrail.io/.well-known/assetlinks.json | python3 -m json.tool
```

Confirm the `package_name` is right and note the fingerprint(s) listed.

### Step 2 — know which certificate your install is signed with

There are (at least) **three different signing certificates** in a typical setup, and the
fingerprint in `assetlinks.json` must match the one for *how the app got onto the device*:

| Install path | Signed with | Where to get the SHA-256 |
|---|---|---|
| Installed from Google Play | **Play app signing key** (Google re-signs your upload) | Play Console → Setup → App integrity → App signing |
| Sideloaded release build (`adb install app-release.apk`) | Your **upload/release keystore** | `keytool -list -v -keystore upload-keystore.jks -alias upload` |
| Local dev build (`./gradlew installDebug`) | The machine's **debug keystore** | `keytool -list -v -keystore ~/.android/debug.keystore -alias androiddebugkey -storepass android` |

**Recommendation:** register *all* fingerprints you install from (Play signing key, upload key, and
each developer machine's debug key) in the LinkTrail dashboard so links verify no matter how the
build was installed. `sha256_cert_fingerprints` is an array — multiple entries are fine.

You can also read the fingerprint straight off any APK:

```bash
apksigner verify --print-certs app-release.apk   # in <sdk>/build-tools/<version>/
```

### Step 3 — check Google's verifier (the cache everyone gets bitten by)

**Android 12+ devices do not fetch your `assetlinks.json` directly.** They ask Google's Digital
Asset Links service, which crawls and **caches** your file (typically for up to ~1 hour). Query
exactly what devices will see:

```bash
curl -s "https://digitalassetlinks.googleapis.com/v1/statements:list?source.web.site=https%3A%2F%2Fkick.linktrail.io&relation=delegate_permission%2Fcommon.handle_all_urls"
```

- The `sha256Fingerprint` values here are the ground truth for verification.
- `maxAge` tells you how long until Google re-crawls your file.
- **If you just fixed `assetlinks.json`, this can lag behind for up to an hour.** Fix the file
  first, then wait for this endpoint to show the new fingerprint before re-testing on a device.

### Step 4 — force the device to re-verify

Verification runs **once, at install time**, and the verdict is cached on the device. Fixing
`assetlinks.json` does **not** fix already-installed apps. After the fix (and after Google's cache
caught up), do one of:

- **Reinstall the app** — cleanest; verification re-runs at install. This is also what confirms
  new users get the correct behavior.
- **Toggle it manually** — Settings → Apps → *your app* → **Open by default** → enable
  "Open supported links" / **Add link** → check the domain. Takes effect immediately, no reinstall.
- **Via adb:**

```bash
adb shell pm verify-app-links --re-verify io.linktrail.example
# wait ~10 seconds, then:
adb shell pm get-app-links io.linktrail.example
# you want:  kick.linktrail.io ... verified
```

Remember: **every device** that installed the app while the fingerprint was wrong carries the
stale verdict and needs one of the steps above.

---

## 2. `assetlinks.json` serving requirements

Android/Google reject the file if any of these are off:

- Served at exactly `https://<domain>/.well-known/assetlinks.json` (HTTPS, valid certificate).
- HTTP `200` with **no redirects** (no `301`/`302`, no trailing-slash rewrite, no `www.` bounce).
- `Content-Type: application/json`.
- Publicly readable — no auth, no cookie/JS challenge in front of it (careful with WAF/bot
  protection; Google's crawler must fetch it).

Quick check of all of the above:

```bash
curl -s -o /dev/null -w "http: %{http_code}\nredirects: %{num_redirects}\ncontent-type: %{content_type}\n" \
  -L https://kick.linktrail.io/.well-known/assetlinks.json
```

Note for LinkTrail domains: this file is generated by the LinkTrail backend from the app's
registration in the dashboard — to change fingerprints, edit the app entry in the dashboard, not a
static file.

---

## 3. The two caches, summarized

Most "I fixed it but it still doesn't work" reports are one of these:

| Cache | Where | Lifetime | How to bust |
|---|---|---|---|
| Google Digital Asset Links crawl | Google's servers (used by Android 12+ verification) | up to ~1 h (`maxAge` in the API response) | Wait it out; re-check with the `statements:list` query above |
| Verification verdict | On each device, set at install time | until reinstall / manual re-verify | Reinstall, "Open by default" toggle, or `pm verify-app-links --re-verify` |

They stack: fix the file → wait for Google's cache → re-verify the device, **in that order**.

---

## 4. Address-bar navigation never opens the app

Typing or pasting `https://kick.linktrail.io/...` into the browser's address bar keeps you in the
browser **by design** — address-bar input is treated as browsing, not as a link tap, regardless of
verification state. This is Android/Chrome behavior, not a configuration problem.

To test like a real user, tap the link **from another app** (messaging app, email, notes), or
simulate the tap:

```bash
adb shell am start -a android.intent.action.VIEW -d "https://kick.linktrail.io/discounted-product"
```

For custom-scheme (non-verified) deep links:

```bash
adb shell am start -a android.intent.action.VIEW \
  -d "kickflip://products/aj1?voucher=SUMMER25&discountPercent=25"
```

---

## 5. App opens but lands on the wrong screen

At this point App Links are working and it's a routing question inside the app:

- Confirm your `onLink` handler covers the link's `deepLinkPath`. (In the KickFlip demo,
  `Store.route` handles `/`, `/category/<name>` and `/products/<id>` — any other path falls
  through to Home.)
- Log the incoming link to see exactly what the SDK delivered:

```kotlin
LinkTrail.shared?.onLink { link, source ->
    Log.d("MyApp", "path=${link.path} customData=${link.customData} source=$source")
    router.route(link, source)
}
```

- Make sure the Activity forwards **both** entry points to the SDK — `onCreate` *and*
  `onNewIntent` (a link tapped while the app is backgrounded arrives via `onNewIntent`).

---

## 6. Deferred deep link not delivered on first launch

- The SDK must be configured with a valid API key (`lt_live_…`) — `LinkTrail.configure` in
  `Application.onCreate()`. Without it there is no backend call, so there is nothing to defer.
  (An invalid key surfaces as `LinkTrailError.InvalidApiKey` via `onError`.)
- Register `onLink` **before** or immediately after `configure` (in the demo: in
  `MainActivity.onCreate`) so the callback isn't missed.
- Deferred matching only triggers on a genuine first launch after install. To re-test, uninstall
  the app, click a LinkTrail link, then reinstall and launch.

---

## 7. Watching the SDK logs

Enable SDK logging, then filter logcat by the SDK's tag:

```kotlin
LinkTrail.configure(this, apiKey, LinkTrailOptions(logEnabled = true))
```

```bash
adb logcat -s LinkTrail            # only the SDK's own logs (tag: LinkTrail)
adb logcat --pid=$(adb shell pidof -s io.linktrail.example)   # everything from the app's process
```

Typical debugging session:

```bash
adb logcat -c                      # clear old logs
adb shell am start -a android.intent.action.VIEW -d "https://kick.linktrail.io/discounted-product"
adb logcat -s LinkTrail            # watch the link resolve
```

Note: with no API key configured the SDK is never initialized, so `-s LinkTrail` shows nothing —
use the `--pid` variant to see general app output in that case.

---

## adb cheat sheet

```bash
# App Links verification state for the app
adb shell pm get-app-links io.linktrail.example

# Force re-verification (Android 12+)
adb shell pm verify-app-links --re-verify io.linktrail.example

# Simulate tapping an App Link / custom-scheme link
adb shell am start -a android.intent.action.VIEW -d "https://kick.linktrail.io/discounted-product"
adb shell am start -a android.intent.action.VIEW -d "kickflip://products/aj1?voucher=SUMMER25"

# SDK logs only / full app logs
adb logcat -s LinkTrail
adb logcat --pid=$(adb shell pidof -s io.linktrail.example)

# What the domain serves vs. what Google's verifier cached
curl -s https://kick.linktrail.io/.well-known/assetlinks.json | python3 -m json.tool
curl -s "https://digitalassetlinks.googleapis.com/v1/statements:list?source.web.site=https%3A%2F%2Fkick.linktrail.io&relation=delegate_permission%2Fcommon.handle_all_urls"

# Certificate fingerprints
keytool -list -v -keystore ~/.android/debug.keystore -alias androiddebugkey -storepass android   # debug key
apksigner verify --print-certs app-release.apk                                                    # any APK
```
