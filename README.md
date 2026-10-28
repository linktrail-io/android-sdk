# LinkTrail Android SDK

Mobile **attribution** and **deferred deep linking** for Android. Distributed as a **binary AAR** —
package `io.linktrail`, entry point `LinkTrail`. The counterpart of the
[LinkTrail iOS SDK](https://github.com/linktrail-io/ios-sdk).

- **Artifact:** `io.linktrail:sdk:0.1.0` (Maven Central) · **Min SDK:** 26
- **Docs:** [docs.linktrail.io](https://docs.linktrail.io) ·
  **Release notes:** [GitHub releases](https://github.com/linktrail-io/android-sdk/releases)

## Install

The SDK is published to **Maven Central**, so no custom repository is needed — just add the
dependency:

```kotlin
// app/build.gradle.kts
dependencies {
    implementation("io.linktrail:sdk:0.1.0")
}
```

`mavenCentral()` is already in the default repositories of every Android project, which also
resolves the SDK's transitive dependencies (coroutines, Play Install Referrer, App Set ID). Keep
`google()` alongside it.

Upgrading from 0.0.5 or earlier? Read [Upgrading to 0.1.0](#upgrading-to-010) first: 0.1.0 has
breaking changes.

## Quick start

```kotlin
import io.linktrail.LinkTrail
import io.linktrail.LinkTrailOptions

// In Application.onCreate(). The API key is required — a blank key throws.
LinkTrail.configure(context = this, apiKey = "lt_live_…")

// One hook handles both first-launch (deferred) AND re-engagement links:
LinkTrail.shared?.onLink { link, source ->
    router.route(link.path, link.customData)   // e.g. "/products/aj1" + { voucher: SUMMER25 }
}

// Observe failures if you want:
LinkTrail.shared?.onError { error -> /* e.g. LinkTrailError.InvalidApiKey (401) */ }
```

The install is tracked automatically by `configure` (held until the user's consent decision, see
below). Forward incoming links from your Activity:

```kotlin
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    route(intent?.data)
}
override fun onNewIntent(intent: Intent) {
    super.onNewIntent(intent)
    route(intent.data)
}

private fun route(uri: Uri?) {
    if (LinkTrail.shared?.handleDeepLink(uri) == true) return   // a LinkTrail link: onLink fires
    // Not a LinkTrail link (your own myapp:// links, OAuth callbacks, ...): handle it yourself.
}
```

Every callback API also has a coroutine `suspend` twin (`trackInstallAsync`, `handleDeepLinkAsync`,
`trackEventAsync`). Callbacks are delivered on the main thread.

### `configure` is a singleton

- A repeat call with the **same key and equal options** is a no-op that returns the existing
  instance.
- A call with a **different key or options** shuts the previous instance down (its pending work,
  queue flushes and callbacks are dropped) and returns a new one. **Re-register** `onLink`,
  `onAttribution` and `onError` on the new instance (`LinkTrail.shared`).
- Don't keep a reference to an old instance: calls on a replaced instance are ignored (no request,
  no callback; `handleDeepLink` returns `false`).
- Persisted state (install flags, consent, device id) is untouched by a reconfigure.
- Configure the SDK in **one process only** (normally your main process).

## Consent gating

Consent gating is **on by default** (`requireConsent = true`), for GDPR / ePrivacy. The SDK **holds
until the user decides**:

- **Before `setConsent`:** nothing is sent. The install is held (not lost), and events are dropped.
- **`setConsent(true)`:** the install is sent with `consent = true`. It is **counted and attributed**,
  the deferred link is **routed** through `onLink`, and queued events are flushed.
- **`setConsent(false)`:** **one uncounted install** is sent with `consent = false` and **no device
  id**. The backend resolves the deferred link so the user still lands on the right screen, and
  records nothing. Events are dropped. The denial isn't re-sent on later launches.

```kotlin
LinkTrail.configure(context, "lt_live_…")           // install held until a decision
// … once your consent UI resolves:
LinkTrail.shared?.setConsent(granted = true)         // counted + attributed install, routes, flushes events
// LinkTrail.shared?.setConsent(granted = false)     // one uncounted install, no device id; still routes
```

Granting after a denial, on the same launch or a later one, sends the counted install then and routes
the deferred link if the denial couldn't. A deferred link is routed **at most once**, so a user who
already reached their screen is never re-routed. Re-engagement links always route; without consent
they use a non-recording resolve. The decision persists across launches (on this device, see
[Data and privacy](#data-and-privacy)).

To attribute at init without waiting for an answer, opt out: `LinkTrailOptions(requireConsent =
false)`; an explicit `setConsent(false)` still wins. (Separately, `autoTrackInstall = false` lets you
send the install yourself via `trackInstall()`; it is still held until `setConsent`, and `force`
never skips the hold.)

## Deferred deep links

Android gets deferred linking the **deterministic** way: the Play Install Referrer supplies a click
token on first launch, which the SDK sends with the install. You can register `onLink` whenever your
app is ready to route, for example after a splash or login screen. The deferred link is delivered
**at least once**:

- When the install response carries a link, the SDK saves it to disk straight away.
- If `onLink` is already set, the link is delivered at once. Otherwise it is delivered (on the main
  thread, with `source = DEFERRED`) as soon as `onLink` is set, in the same launch or a later one,
  even if the app was killed in between.
- The link is marked routed only after your handler has been called. If your handler crashes, the
  link may be delivered once more on the next launch, so make routing idempotent.
- A saved link that hasn't been delivered within **7 days** is dropped.
- The install is never re-sent for this; only the delivery is retried.

## Data and privacy

The SDK keeps its state on the device only: the install and deferred-link flags, the consent answer,
the device id, the cached attribution and the offline event queue. It is one small file in the app's
[`noBackupFilesDir`](https://developer.android.com/reference/android/content/Context#getNoBackupFilesDir()).
Android Auto Backup and device-to-device transfer never copy that folder, so:

- **A reinstall restored from backup, or a new phone, starts fresh.** The install is sent again and
  its deferred link is routed; the new device gets its own device id.
- **Consent stays with the device.** After a restore the consent answer is gone too, so the SDK holds
  the install again. Show your consent UI whenever the SDK has no answer, not only on the very first
  launch.
- **No setup is needed.** You don't need `fullBackupContent` or `dataExtractionRules` rules for the
  SDK, and your `android:allowBackup` setting doesn't affect it. If you keep your own copy of the
  consent answer in backed-up storage, exclude it too, or it will disagree with the SDK after a
  restore.

## More

```kotlin
// Custom post-install events:
LinkTrail.shared?.trackEvent("purchase", value = 59.99, currency = "USD")

// Cached results:
val attribution = LinkTrail.shared?.lastAttribution
val lastLink = LinkTrail.shared?.lastDeepLink

// Attribution stream (fires when an install is attributed):
LinkTrail.shared?.onAttribution { attribution -> /* … */ }
```

`LinkTrailOptions` also takes `logEnabled`, `logLevel`, `requestTimeoutMillis`, `retryPolicy`,
`autoTrackInstall` and `linkDomains` (see [Which links the SDK claims](#which-links-the-sdk-claims)).
Invalid values (`maxAttempts < 1`, a delay or `requestTimeoutMillis` `<= 0`) are clamped with a
WARNING, never thrown. (App Tracking Transparency / SKAdNetwork are iOS-only and have no Android
equivalent.)

Custom events that fail with a transport error, 408, 429 or 5xx are queued and retried. Any other
status (400, 401, 403, 404, 409, 422, …) is reported to `onError` and dropped.

## Deep-link setup

Declare your App Links host in the manifest:

```xml
<intent-filter android:autoVerify="true">
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data android:scheme="https" android:host="kick.linktrail.io" />
</intent-filter>
```

Android verifies it against a Digital Asset Links file at `https://<host>/.well-known/assetlinks.json`
listing your package + signing-cert SHA-256. LinkTrail hosts this file for your link domains, built
from the app you register in the dashboard.

A custom scheme (`myapp://…`) is your own routing: the SDK only claims `https` LinkTrail links, so
handle custom-scheme intents yourself. To open a LinkTrail link in the app, use its `https` URL.

Links opening the browser or Play Store instead of your installed app? That's almost always App
Links verification — see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for the diagnosis commands,
signing-certificate pitfalls, and the two caches involved.

### Which links the SDK claims

`handleDeepLink` returns `true` only for a LinkTrail link, which needs all three:

1. the scheme is `https` (`http` is accepted in debuggable builds only);
2. the host (case, port and a trailing dot ignored; internationalised names compared in punycode) is
   `linktrail.io` or a subdomain of it, or a `linkDomains` entry or a subdomain of it. A URL whose
   authority contains `\`, `%`, whitespace or a control character, has a bad port, or whose host
   isn't a valid host name, is never claimed;
3. the path has a slug (`https://kick.linktrail.io/` alone is not a link).

Anything else, such as `mailto:`, `file:`, your own `myapp://settings` or an OAuth callback like
`https://accounts.example.com/cb?code=…`, returns `false` (`handleDeepLinkAsync` throws
`LinkTrailError.NotALinkTrailUrl`). No request is sent and `onError` is not called. An empty
`linkDomains` (the default) means only `*.linktrail.io` links are claimed, **not** every link.

If your links use a **custom domain**, list it at configure, or its links won't be claimed:

```kotlin
LinkTrail.configure(context, "lt_live_…", LinkTrailOptions(linkDomains = listOf("go.example.com")))
```

Entries are normalised (`"https://Go.Example.com:443/x"` becomes `"go.example.com"`); empty or
invalid ones are ignored with a warning. Order and duplicates don't matter.

## Upgrading to 0.1.0

0.1.0 has breaking changes (a `0.x` minor bump). Check each one against your integration:

1. **Custom link domains must be listed in `linkDomains`.** `handleDeepLink` now claims only `https`
   links on `linktrail.io` (or a subdomain) or on a `linkDomains` entry (or a subdomain). Before, an
   empty `linkDomains` meant "handle every link". Links on `*.linktrail.io` need no change; for a
   custom domain:

   ```kotlin
   // 0.0.5: LinkTrailOptions()  (empty linkDomains handled every link)
   // 0.1.0:
   LinkTrailOptions(linkDomains = listOf("go.example.com"))
   ```

   Other URLs (`mailto:`, OAuth callbacks, your own `myapp://` links) now return `false`, so route
   them yourself.
2. **A denied install carries no device identifier** and is sent exactly once. `setConsent(false)`
   wins even with `requireConsent = false`.
3. **`trackInstall(force = true)` no longer bypasses the consent hold.**
4. **`configure` is a singleton.** Re-register callbacks after a reconfigure. See
   [`configure` is a singleton](#configure-is-a-singleton).
5. **Log format.** Lines read `[LinkTrail] [LEVEL] <message>` (`WARNING`, not `WARN`), with no query
   strings and a redacted referrer token. Update any Logcat filters.
6. **SDK state is no longer backed up.** It moves to device-only storage on the first `configure`
   (in-place updates keep their state). A restored or new phone starts fresh and must ask for
   consent again. See [Data and privacy](#data-and-privacy).
7. **Invalid options are clamped, not thrown**, and only retryable event failures (transport, 408,
   429, 5xx) are queued.

Full notes: [v0.1.0 release](https://github.com/linktrail-io/android-sdk/releases/tag/v0.1.0).

## Testing

Reset the SDK in a debug build to replay a first launch:

```kotlin
// In Application.onCreate(), before LinkTrail.configure:
if (BuildConfig.DEBUG) {
    LinkTrail.resetForTesting(this)   // clears install flags, cached attribution, saved deferred link, queue, consent and device id
}
LinkTrail.configure(this, "lt_live_…")
// The reset cleared the consent answer: call setConsent again, or the install stays held.
```

Then create a link in the LinkTrail dashboard, open it once on the device (registers a click), and
launch the app: `onLink` should fire with `source = DEFERRED` and that link's path. Turn on
`LinkTrailOptions(logEnabled = true)` and watch `adb logcat -s LinkTrail`.

Or clear the whole app: `adb shell pm clear <applicationId>`.

**Faking the Play Install Referrer (debuggable builds only).** An `adb install` has no Play Install
Referrer, so the deterministic deferred path can't run on an emulator. A debuggable app can stand in
a referrer string instead; the SDK parses it like Play's:

```bash
adb shell setprop debug.linktrail.referrer "lt_click=<32-hex token>"   # before the app's first launch
adb shell setprop debug.linktrail.referrer ""                          # off again (Play is asked as usual)
```

- Read only for the install (the first launch after install, `pm clear` or `resetForTesting`).
- A value without a valid `lt_click` (32 lowercase hex) gives no token, like an organic referrer.
- Logged as a WARNING with the token redacted. A `<meta-data android:name="LINKTRAIL_REFERRER">`
  entry in a debug-only manifest works too; the system property wins.

**Not configurable in release builds.** Release builds never read the referrer override and always
talk to LinkTrail's production backend; there is no base-URL option.

More: [docs.linktrail.io](https://docs.linktrail.io) and [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Example app

[`example/`](example/) is **KickFlip**, a small Jetpack Compose storefront that shows deferred
deep linking end to end — it consumes this exact AAR, the same way your app would. A debug panel
fires the four scenarios (home · category · product · product + voucher):

```bash
cd example && ./gradlew :app:installDebug
```

Add your key to `example/local.properties` (`linktrail.apiKey=lt_live_…`) to run against the live
backend; without one it routes the simulator's links locally. See [example/README.md](example/README.md).

## Issues & feedback

Hit a bug, or something not behaving as documented? **Everyone is encouraged to
[open an issue](https://github.com/linktrail-io/android-sdk/issues/new/choose)** — no problem is too
small, and a quick report helps us make the SDK better for everyone. Picking a template walks you
through the details we need. For App Links / deep-linking problems, the
[troubleshooting guide](TROUBLESHOOTING.md) is often the fastest fix.

## Auto-merge

Put `auto-merge` anywhere in a PR title (any case, e.g. `[auto-merge] Fix typo`) and the
`Auto-merge` workflow (`.github/workflows/auto-merge.yml`) turns on GitHub auto-merge for it.
GitHub then merges it with a merge commit (never squash, so stacked PRs keep working) once the
required checks and approvals pass. Drafts are skipped: auto-merge turns on when the PR is marked
ready for review. Remove the word from the title, or convert the PR back to draft, to turn it off.
PRs from forks are ignored. Until the `AUTOMERGE_TOKEN` org secret exists, the merge is made with
`GITHUB_TOKEN`, which does not trigger the push workflows on the base branch.

This repo's `main` ruleset requires an approving review, so auto-merge completes only after the PR is approved.

## License

Apache License 2.0. See [LICENSE](LICENSE).
