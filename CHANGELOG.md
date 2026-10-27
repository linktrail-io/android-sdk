# Changelog

All notable changes to the LinkTrail Android SDK (`io.linktrail:sdk`).

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
