# Changelog

All notable changes to the LinkTrail Android SDK (`io.linktrail:sdk`).

## [0.2.0] - 2026-11-12

### Added
- **`onLink(null)` removes the link handler**, for example in `onDestroy`. Links that resolve while
  no handler is set are kept and delivered once to the next handler.

### Fixed
- **The device id is now a random per-install UUID**, not the Play App Set ID, so installs of
  several apps from the same developer, and reinstalls, are each recorded correctly. The
  `play-services-appset` dependency is removed. Ids saved by an older SDK are kept once the install
  has been counted.
- **A re-engagement link that resolves before `onLink` is set is no longer dropped.** The latest
  one is held for this launch and delivered once, with `source = REENGAGEMENT`, when `onLink` is
  registered. If a deferred link is waiting too, the deferred link is delivered first.
- **The Play Install Referrer `lt_click` token is matched as a whole parameter** (exactly 32
  lowercase hex characters), including in a percent-encoded referrer.
- **`trackEvent` validates its arguments before sending.** A blank name, a `value` that is NaN,
  infinite or negative, or a `currency` that isn't 3 letters is reported as
  `LinkTrailError.InvalidEvent(reason)`, and nothing is sent.
- **A consent denial made just before an install, open or event is sent now always wins.** The
  install goes out as the denied install, and no open or event is sent (links still route).

## [0.1.0] - 2026-10-27

### Changed
- **Breaking: `handleDeepLink` only claims LinkTrail links.** A URL is claimed only if it is `https`
  (or `http` in a debuggable app), its host is `linktrail.io` or a subdomain, or a `linkDomains`
  host or a subdomain, and its path has a slug. Anything else (`mailto:`, OAuth callbacks, your own
  `myapp://` links) returns `false` (`handleDeepLinkAsync` throws `NotALinkTrailUrl`) with no
  request and no `onError`. Previously an empty `linkDomains` meant "handle every link".
  **Migration:** if your links use a custom domain, list it, e.g.
  `LinkTrailOptions(linkDomains = listOf("go.example.com"))`. Links on `*.linktrail.io` need nothing.
- **`linkDomains` entries are normalised** (`"https://Go.Example.com:443/x"` becomes
  `"go.example.com"`, internationalised names become punycode). Empty or invalid entries are
  ignored with a WARNING.
- **Privacy: a denied install carries no device identifier**, and is sent exactly once.
- **`trackInstall(force = true)` no longer bypasses the consent hold.**
- **Manual install path (`autoTrackInstall = false`):** a `trackInstall()` made before the consent
  decision is held and released by `setConsent`, on this launch or a later one.
- **Log lines** now read `[LinkTrail] [LEVEL] <message>` at the matching Logcat priority, and log
  less personal data (no query strings, redacted referrer token). Update any Logcat filters.

### Fixed
- **A deferred link is delivered at least once, even if `onLink` is set late** (after a splash or
  login screen, or on a later launch). Saved links expire after 7 days.
- **The deferred deep link is no longer lost when consent is granted after a denial.**
- **A consent change while the install is in flight is no longer lost.**
- **An event in flight when consent is denied is no longer queued and sent later.**
- **SDK state is no longer backed up or restored.** It lives in device-only storage, so a restore or
  a new phone starts fresh (and the consent question is asked again). In-place updates keep their
  state.
- `configure` is a safe singleton: same key and options reuse the instance; different ones replace it.
- Invalid options (`retryPolicy`, `requestTimeoutMillis`) are clamped with a WARNING instead of throwing.
- A huge or negative `Retry-After` no longer causes an immediate retry.
- Only retryable event failures (transport error, 408, 429, 5xx) are queued.

### Added
- Every request sends `X-LinkTrail-SDK: android/<version>`.

### Consent model (unchanged since 0.0.5)
Hold until a decision: nothing is sent before `setConsent`. Grant means counted, attributed and
routed. Deny means one uncounted install with no device id that still routes the user. Re-engagement
links always route.
