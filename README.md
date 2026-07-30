# LinkTrail Android SDK

Mobile **attribution** and **deferred deep linking** for Android. Distributed as a **binary AAR** —
package `io.linktrail`, entry point `LinkTrail`. The counterpart of the
[LinkTrail iOS SDK](https://github.com/linktrail-io/ios-sdk).

- **Artifact:** `io.linktrail:sdk:0.0.4` (Maven Central) · **Min SDK:** 26

## Install

The SDK is published to **Maven Central**, so no custom repository is needed — just add the
dependency:

```kotlin
// app/build.gradle.kts
dependencies {
    implementation("io.linktrail:sdk:0.0.4")
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

The install is tracked automatically by `configure`. Forward incoming links from your Activity:

```kotlin
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    LinkTrail.shared?.handleDeepLink(intent?.data)
}
override fun onNewIntent(intent: Intent) {
    super.onNewIntent(intent)
    LinkTrail.shared?.handleDeepLink(intent.data)
}
```

Every callback API also has a coroutine `suspend` twin (`trackInstallAsync`, `handleDeepLinkAsync`,
`trackEventAsync`). Callbacks are delivered on the main thread.

## Consent gating

Consent gating is **on by default** (`requireConsent = true`) and follows the "links work, tracking
waits" model: until the user consents, **deep links still route** — deferred and re-engagement links
reach their destination via `onLink` — but **no attribution is recorded**. The install is sent with
`consent = false`, so the backend resolves the link for routing yet stores nothing, exposes no
attribution, and drops events. Consent is **deny-by-default**: an unset flag counts as no consent.

When the user accepts your consent prompt, grant it:

```kotlin
LinkTrail.shared?.setConsent(true)   // sends the real attributed install + flushes queued events
```

This attributes the install and flushes queued events **without re-routing** a user already sent to
their screen. Revoke with `setConsent(false)` (clears the event queue). The flow:

1. `configure(...)` — links route immediately; the install is held **unattributed** (`consent = false`).
2. User accepts → `setConsent(true)` → attributed install is sent, queued events flush.
3. User declines → do nothing (or `setConsent(false)`); routing keeps working, nothing is tracked.

To attribute at init with no gate, opt out: `LinkTrailOptions(requireConsent = false)`. (Separately,
`autoTrackInstall = false` defers the install call entirely so you can send it yourself via
`trackInstall()`.)

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
`linkDomains`. (App Tracking Transparency / SKAdNetwork are iOS-only and have no Android
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

**List every link host in `linkDomains`.** When `linkDomains` is non-empty, the SDK routes
re-engagement opens (app already installed) *only* for those hosts — a link on an unlisted host
opens the app but never navigates. Deferred (install-time) links skip this check and route
regardless, so a missing host can look fine on a fresh install yet fail once the app is installed.
Leave `linkDomains` empty (the default) to handle every parseable link.

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
