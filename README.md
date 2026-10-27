# LinkTrail Android SDK

Mobile **attribution** and **deferred deep linking** for Android. Distributed as a **binary AAR** —
package `io.linktrail`, entry point `LinkTrail`. The counterpart of the
[LinkTrail iOS SDK](https://github.com/linktrail-io/ios-sdk).

- **Artifact:** `io.linktrail:sdk:0.1.0` (Maven Central) · **Min SDK:** 26

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
LinkTrail.shared?.onError { error -> /* e.g. LinkTrailError.InvalidApiKey */ }
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

`LinkTrailOptions` also takes `logEnabled`, `logLevel`, `requestTimeoutMillis`, `retryPolicy`, and
`linkDomains` (see [Which links the SDK claims](#which-links-the-sdk-claims)). (App Tracking Transparency / SKAdNetwork are iOS-only and have no Android
equivalent.)

## Deep-link setup

Declare your App Links host and (optionally) a custom scheme in the manifest:

```xml
<intent-filter android:autoVerify="true">
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data android:scheme="https" android:host="kick.linktrail.io" />
</intent-filter>
```

Then host a Digital Asset Links file at `https://<host>/.well-known/assetlinks.json` listing your
package + signing-cert SHA-256 (LinkTrail infra hosts this for your links).

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

## License

Apache License 2.0. See [LICENSE](LICENSE).
