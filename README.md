# LinkTrail Android SDK

Mobile **attribution** and **deferred deep linking** for Android. Distributed as a **binary AAR** —
package `io.linktrail`, entry point `LinkTrail`. The counterpart of the
[LinkTrail iOS SDK](https://github.com/linktrail-io/ios-sdk).

- **Artifact:** `linktrail.io:sdk:0.0.3` (Maven Central) · **Min SDK:** 26

## Install

The SDK is published to **Maven Central**, so no custom repository is needed — just add the
dependency:

```kotlin
// app/build.gradle.kts
dependencies {
    implementation("linktrail.io:sdk:0.0.3")
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

## More

```kotlin
// Custom post-install events:
LinkTrail.shared?.trackEvent("purchase", value = 59.99, currency = "USD")

// Cached results:
val attribution = LinkTrail.shared?.lastAttribution
val lastLink = LinkTrail.shared?.lastDeepLink

// Attribution stream (fires when an install is attributed):
LinkTrail.shared?.onAttribution { attribution -> /* … */ }

// Consent-gated install (defer configure's auto-track, then call manually):
LinkTrail.configure(context = this, apiKey = "lt_live_…",
    options = LinkTrailOptions(autoTrackInstall = false))
LinkTrail.shared?.trackInstall()
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

## Example app

[`example/`](example/) is **KickFlip**, a small Jetpack Compose storefront that shows deferred
deep linking end to end — it consumes this exact AAR, the same way your app would. A debug panel
fires the four scenarios (home · category · product · product + voucher):

```bash
cd example && ./gradlew :app:installDebug
```

Add your key to `example/local.properties` (`linktrail.apiKey=lt_live_…`) to run against the live
backend; without one it routes the simulator's links locally. See [example/README.md](example/README.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).
