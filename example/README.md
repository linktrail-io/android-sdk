# KickFlip — LinkTrail Android demo

A small Jetpack Compose storefront that shows how the **LinkTrail** SDK's deferred deep linking
drives where a user lands after installing. It consumes the SDK's **binary AAR** from this repo's
Maven layout (`../m2`, artifact `linktrail.io:sdk:0.0.3`) — the same way an external app would.

## Run it

Requires JDK 17 and an Android device/emulator on API 26+ (Android Studio optional — the Gradle
wrapper is included).

### 1. Add your API key

Create (or edit) the untracked [`local.properties`](local.properties) in this folder and add your
workspace SDK key (`lt_live_…`, from the LinkTrail dashboard):

```properties
# example/local.properties — never commit a real key
linktrail.apiKey=lt_live_REPLACE_WITH_YOUR_KEY
```

The key is injected at build time as `BuildConfig.LINKTRAIL_API_KEY` and read in
[`KickFlipApp`](app/src/main/java/io/linktrail/example/KickFlipApp.kt). Without a key the SDK is
left unconfigured and the **deep-link simulator still works** — it fabricates links locally — so
you can explore the UI first and add the key only when you want the real install/open calls to
authenticate.

### 2. Build and run

```bash
cd example && ./gradlew :app:installDebug   # then launch KickFlip on the device/emulator
```

## The app

Two screens, nothing more:

- **Home** — a category bar on top (All · Basketball · Running · Lifestyle · Skate) and a grid of products.
- **Product** — one product. If a voucher was delivered in the deep link, it shows the voucher badge, the discounted price, and how much you saved.

## The four deferred deep-link scenarios

Tap the **🧪 Simulate deep link** button (bottom-right) to open the simulator and fire any of
these. Each is a real `LinkTrailDeepLink` — the same object your `onLink` handler receives from a
real install.

| Scenario | Deep link | Where you land |
|---|---|---|
| 1 · Just the store | `deepLinkPath: "/"` | Home |
| 2 · Category selected | `deepLinkPath: "/category/running"` | Home with **Running** pre-selected |
| 3 · A product | `deepLinkPath: "/products/aj1"` | The Air Jordan 1 product page |
| 4 · Product + voucher | `deepLinkPath: "/products/aj1"`, `customData: {voucher: "SUMMER25", discountPercent: "25"}` | Product page with **SUMMER25 −25%** applied |

The simulator fabricates the deferred link locally so you don't need a real click → install
round-trip. In production these arrive from the SDK — no code changes in the app.

## How it maps to the SDK

The entire integration is one method —
[`Store.route(link, source)`](app/src/main/java/io/linktrail/example/Store.kt) — which reads
`link.path` and `link.customData` and decides the screen. It's wired up once:

```kotlin
LinkTrail.shared?.onLink { link, source ->
    store.route(link, source)   // deferred (first launch) AND re-engagement
}
```

| SDK touchpoint | Where |
|---|---|
| `LinkTrail.configure(context, apiKey, options)` in `Application.onCreate()` | [`KickFlipApp`](app/src/main/java/io/linktrail/example/KickFlipApp.kt) |
| `onLink { link, source -> … }` — the one routing hook | [`MainActivity`](app/src/main/java/io/linktrail/example/MainActivity.kt) → [`Store`](app/src/main/java/io/linktrail/example/Store.kt) |
| `handleDeepLink(uri)` for the already-installed path | [`MainActivity`](app/src/main/java/io/linktrail/example/MainActivity.kt), forwarded from `onCreate`/`onNewIntent` |
| App Links (`https://kick.linktrail.io`) + `kickflip://` custom scheme | [`AndroidManifest.xml`](app/src/main/AndroidManifest.xml) |

## Test from the terminal

While the app is installed, the custom scheme routes the same way:

```bash
adb shell am start -a android.intent.action.VIEW \
  -d "kickflip://products/aj1?voucher=SUMMER25&discountPercent=25"
```

With the SDK configured the link is resolved server-side via `handleDeepLink` → `onLink`; without
a key the demo routes the raw URI locally so the flow is still visible offline.
