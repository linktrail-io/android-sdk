package io.linktrail.example.sdk

import android.annotation.SuppressLint
import android.content.Context
import android.net.Uri
import android.util.Log
import io.linktrail.LinkTrail
import io.linktrail.LinkTrailError
import io.linktrail.LinkTrailLogLevel
import io.linktrail.LinkTrailOptions
import io.linktrail.example.BuildConfig
import io.linktrail.example.Store
import io.linktrail.model.LinkTrailDeepLink
import io.linktrail.model.LinkTrailLinkSource
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * Bridges the demo UI to the LinkTrail SDK: configures it, forwards real deferred + re-engagement
 * links into [Store.route], records the consent decision, and can *simulate* the four deferred
 * scenarios locally so you can see each one without a real click → install round-trip.
 * Mirrors `AttributionCoordinator.swift` in the iOS example.
 *
 * Android difference: the deferred click token comes from the **Play Install Referrer** (read by the
 * SDK itself), not the clipboard, so there is no paste button and no clipboard prompt.
 */
class AttributionCoordinator(
    context: Context,
    private val store: Store,
    private val consent: ConsentPrefs = ConsentPrefs(context),
    /** Records the decision in the SDK. A seam so tests can check it without a configured SDK. */
    private val sdkConsent: (Boolean) -> Unit = { LinkTrail.shared?.setConsent(it) },
    /** Sends one event through the SDK (the debug e2e event hook). A seam for tests. */
    private val sdkEvent: suspend (E2eEvent) -> Boolean? = { e ->
        LinkTrail.shared?.trackEventAsync(e.name, e.value, e.currency)?.attributed
    },
    /** Debug builds only: the e2e event hook is off in release builds. */
    private val debugBuild: Boolean = BuildConfig.DEBUG,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Main),
) {
    /** One of the demo's deferred-deep-link scenarios. */
    data class Scenario(val id: String, val title: String, val detail: String, val link: LinkTrailDeepLink) {
        /** The Maestro / accessibility id of the scenario row (same as iOS). */
        val testTag: String get() = "scenario-$id"

        /** `/products/aj1  ·  meta: voucher=SUMMER25, 25%` */
        val pathLabel: String
            get() {
                var label = link.path
                val voucher = link.customData?.get("voucher") ?: return label
                label += "  ·  meta: voucher=$voucher"
                link.customData?.get("discountPercent")?.let { label += ", $it%" }
                return label
            }
    }

    /** The four scenarios from the brief, each expressed as a real [LinkTrailDeepLink]. */
    val scenarios: List<Scenario> = SCENARIOS

    /** `true` until the user has answered the consent gate (persisted, so it is asked once). */
    val needsConsentDecision: Boolean get() = !consent.decided

    /**
     * Records the user's tracking choice, which releases the install the SDK has been holding.
     *
     * `requireConsent` is on (the SDK default) and `autoTrackInstall` is on, so `configure` asked for
     * the install but the SDK held it. `setConsent` sends it exactly once, carrying the real answer:
     * **Allow** sends a counted, attributed install; **Not now** sends one uncounted `consent: false`
     * install that still resolves the deferred link. No extra `trackInstall()` call is needed.
     */
    fun answerConsent(granted: Boolean) {
        consent.markDecided()
        sdkConsent(granted)
    }

    /** The ONE piece of real wiring: route deferred (first launch) + re-engagement links. */
    val onLink: (LinkTrailDeepLink, LinkTrailLinkSource) -> Unit = { link, source -> store.route(link, source) }

    /**
     * Configures the SDK and wires its callbacks. Call once, from `Application.onCreate`.
     * [rawKey] is the build's key (empty when none was set); it is never logged. [logEnabled] defaults
     * to the build's setting (see [sdkOptions]); tests turn it on to check what the SDK logs in any variant.
     */
    fun configureSdk(
        context: Context,
        rawKey: String = BuildConfig.LINKTRAIL_API_KEY,
        simulatedE2e: Boolean = simulatedE2e(BuildConfig.DEBUG, systemProperty(SIMULATED_E2E_PROPERTY)),
        logEnabled: Boolean = logsEnabled(BuildConfig.DEBUG, BuildConfig.LINKTRAIL_LOGS, BuildConfig.LINKTRAIL_RELEASE_LOGS),
    ) {
        val key = resolveApiKey(rawKey)
        if (key == PLACEHOLDER_API_KEY) {
            Log.w(TAG, "No LinkTrail API key set: using the placeholder, which the backend rejects. " +
                "Set linktrail.apiKey in local.properties (see example/README.md). The simulator still works.")
        }
        if (simulatedE2e) Log.i(TAG, SIMULATED_E2E_LOG)
        val options = sdkOptions(logEnabled = logEnabled, autoTrackInstall = !simulatedE2e)
        val sdk = try {
            LinkTrail.configure(context, key, options)
        } catch (e: LinkTrailError) {
            Log.e(TAG, "LinkTrail configuration failed: ${e.message}")
            return
        }

        // Surface backend failures, most importantly a rejected API key.
        sdk.onError { error ->
            if (error is LinkTrailError.InvalidApiKey) {
                Log.w(TAG, "LinkTrail: API key rejected by the server. Check your lt_live_… key.")
            } else {
                Log.w(TAG, "LinkTrail error: ${error.message}")
            }
        }
        sdk.onAttribution { attribution ->
            Log.i(TAG, "LinkTrail attribution: attributed=${attribution.attributed}")
        }

        sdk.onLink(onLink)
    }

    /**
     * Sends [event] through the SDK and logs the outcome under [TAG] (`E2E event hook: '<name>' done,
     * attributed=<true|false|null>` or `… failed: <error>`); `scripts/e2e-maestro.sh` waits for these
     * lines. Without consent the SDK drops the event itself (and logs that), so nothing is sent.
     */
    fun sendE2eEvent(event: E2eEvent) = scope.launch {
        try {
            val attributed = sdkEvent(event)
            Log.i(TAG, "$E2E_EVENT_LOG '${event.name}' done, attributed=$attributed")
        } catch (e: Exception) {
            Log.w(TAG, "$E2E_EVENT_LOG '${event.name}' failed: ${e.message}")
        }
    }

    /** Simulate a fresh install arriving via a deferred deep link (no backend needed). */
    fun simulate(scenario: Scenario) = store.route(scenario.link, LinkTrailLinkSource.DEFERRED)

    /**
     * Forward an incoming URI (App Link or `kickflip://` scheme) to the SDK, and also route our own
     * scheme locally so manual testing works while the app is installed, e.g.
     * `adb shell am start -a android.intent.action.VIEW -d "kickflip://products/aj1?voucher=SUMMER25&discountPercent=25"`.
     */
    fun handleIncomingUri(uri: Uri) {
        if (LinkTrail.shared?.handleDeepLink(uri) == true) return
        val event = e2eEvent(
            debug = debugBuild,
            scheme = uri.scheme,
            host = uri.host,
            pathSegments = uri.pathSegments.orEmpty(),
            query = uri.queryParameterNames.associateWith { uri.getQueryParameter(it) },
        )
        if (event != null) {
            sendE2eEvent(event)
            return
        }
        val link = customSchemeLink(
            scheme = uri.scheme,
            host = uri.host,
            pathSegments = uri.pathSegments.orEmpty(),
            query = uri.queryParameterNames.associateWith { uri.getQueryParameter(it) },
        ) ?: return
        store.route(link, LinkTrailLinkSource.REENGAGEMENT)
    }

    companion object {
        const val TAG = "KickFlip"
        const val SCHEME = "kickflip"

        /** Committed fallback key. The backend rejects it (surfaced via `onError`). */
        const val PLACEHOLDER_API_KEY = "lt_live_REPLACE_WITH_YOUR_KEY"

        /**
         * The options the example configures the SDK with.
         * - linkDomains: only our own link hosts' App Links (the link host and the custom domain) are LinkTrail
         *   links (kickflip:// is routed locally).
         * - requireConsent: hold everything until the consent gate is answered (the SDK default, spelled out).
         * - autoTrackInstall: the SDK asks for the install itself; `setConsent` releases it. Off only in
         *   the simulated e2e mode (see [simulatedE2e]), where no install is ever sent.
         * - logEnabled: debug builds print what the SDK is doing (install, consent value, routing),
         *   unless built with linktrail.logs=false. Release builds log only when built with
         *   linktrail.releaseLogs=true (the Play Store e2e build, which asserts on logcat).
         */
        fun sdkOptions(
            linkHost: String = BuildConfig.LINKTRAIL_LINK_HOST,
            customLinkHost: String = BuildConfig.LINKTRAIL_CUSTOM_LINK_HOST,
            logEnabled: Boolean = logsEnabled(BuildConfig.DEBUG, BuildConfig.LINKTRAIL_LOGS, BuildConfig.LINKTRAIL_RELEASE_LOGS),
            autoTrackInstall: Boolean = true,
        ) =
            LinkTrailOptions(
                logEnabled = logEnabled,
                logLevel = LinkTrailLogLevel.DEBUG,
                linkDomains = listOf(linkHost, customLinkHost).filter { it.isNotBlank() }.distinct(),
                autoTrackInstall = autoTrackInstall,
                requireConsent = true,
            )

        /** SDK logging: debug builds unless `logs` is off; release builds only with `releaseLogs`. */
        fun logsEnabled(debug: Boolean, logs: Boolean, releaseLogs: Boolean): Boolean = logs && (debug || releaseLogs)

        /**
         * Debug-only e2e switch, set by `scripts/e2e-maestro.sh` around the simulated suite only
         * (`adb shell setprop debug.kickflip.simulated 1`). Those flows drive the in-app simulator and
         * `kickflip://` links and need no backend, but with the install on, an **Allow** sent a real
         * install from the CI runners' shared public IP, which the backend's probabilistic matcher could
         * attribute to a click another e2e run had just made, routing a real deferred link over the
         * simulated screen. In this mode the SDK is still configured (the consent gate
         * still calls `setConsent`), but `autoTrackInstall` is off, so no install is sent for either
         * answer and nothing can be attributed. The real flows never set it.
         */
        const val SIMULATED_E2E_PROPERTY = "debug.kickflip.simulated"

        /** Logged under [TAG] when [simulatedE2e] is on; the e2e script asserts it (and no install). */
        const val SIMULATED_E2E_LOG = "E2E simulated mode ($SIMULATED_E2E_PROPERTY=1): install tracking off, no install is sent"

        /** On only in a debug build with [SIMULATED_E2E_PROPERTY] set to exactly `1`. */
        fun simulatedE2e(debug: Boolean, propertyValue: String?): Boolean = debug && propertyValue?.trim() == "1"

        /** Reads an Android system property (`android.os.SystemProperties` is hidden API); `null` on error. */
        @SuppressLint("PrivateApi")
        fun systemProperty(name: String): String? = try {
            Class.forName("android.os.SystemProperties").getMethod("get", String::class.java).invoke(null, name) as? String
        } catch (_: Throwable) {
            null
        }

        /** Prefix of the e2e event hook's log lines (see [sendE2eEvent]). */
        const val E2E_EVENT_LOG = "E2E event hook:"

        /**
         * Debug-only e2e hook: `kickflip://e2e/event?name=<event>[&value=<major units>&currency=<ISO>]`
         * sends that event through the SDK instead of routing. The e2e reward flows use it to send the
         * reward's events after the counted install (`scripts/e2e-maestro.sh`). `null` in release
         * builds, for any other link, without a valid name, or with a value that isn't a finite number.
         */
        fun e2eEvent(
            debug: Boolean,
            scheme: String?,
            host: String?,
            pathSegments: List<String>,
            query: Map<String, String?>,
        ): E2eEvent? {
            if (!debug || !scheme.equals(SCHEME, ignoreCase = true) || host != "e2e" || pathSegments != listOf("event")) return null
            val name = query["name"]?.trim()?.takeIf { E2E_EVENT_NAME.matches(it) } ?: return null
            val rawValue = query["value"]?.trim()?.takeIf { it.isNotEmpty() }
            val value = rawValue?.let { it.toDoubleOrNull()?.takeIf { v -> v.isFinite() } ?: return null }
            val currency = query["currency"]?.trim()?.uppercase()?.takeIf { it.isNotEmpty() }
            if (currency != null && !E2E_CURRENCY.matches(currency)) return null
            return E2eEvent(name, value, currency)
        }

        private val E2E_EVENT_NAME = Regex("[A-Za-z0-9_.:-]{1,64}")
        private val E2E_CURRENCY = Regex("[A-Z]{3}")

        /** The build's key, or [PLACEHOLDER_API_KEY] when none was set. */
        fun resolveApiKey(raw: String?): String = raw?.trim()?.takeIf { it.isNotEmpty() } ?: PLACEHOLDER_API_KEY

        /**
         * Builds a link from a `kickflip://` URI: the host and path segments form the destination
         * (`kickflip://products/aj1` → `/products/aj1`) and the query becomes `customData`.
         * Returns `null` for any other scheme.
         */
        fun customSchemeLink(
            scheme: String?,
            host: String?,
            pathSegments: List<String>,
            query: Map<String, String?>,
        ): LinkTrailDeepLink? {
            if (!scheme.equals(SCHEME, ignoreCase = true)) return null
            val segments = listOfNotNull(host?.takeIf { it.isNotEmpty() }) + pathSegments.filter { it.isNotEmpty() }
            val meta = query.mapNotNull { (k, v) -> v?.let { k to it } }.toMap()
            return LinkTrailDeepLink(
                deepLinkPath = "/" + segments.joinToString("/"),
                customData = meta.ifEmpty { null },
            )
        }

        val SCENARIOS: List<Scenario> = listOf(
            Scenario(
                id = "home",
                title = "Home",
                detail = "User just lands on the storefront",
                link = LinkTrailDeepLink(deepLinkPath = "/", campaign = "brand-awareness"),
            ),
            Scenario(
                id = "category",
                title = "Home · Running selected",
                detail = "Lands on home with a category pre-selected",
                link = LinkTrailDeepLink(deepLinkPath = "/category/running", campaign = "running-sale"),
            ),
            Scenario(
                id = "product",
                title = "Product · Air Jordan 1",
                detail = "Lands directly on a product page",
                link = LinkTrailDeepLink(deepLinkPath = "/products/aj1", campaign = "aj1-launch"),
            ),
            Scenario(
                id = "voucher",
                title = "Product · Air Jordan 1 + voucher",
                detail = "Product page with a voucher from the link meta",
                link = LinkTrailDeepLink(
                    deepLinkPath = "/products/aj1",
                    campaign = "vip-loyalty",
                    customData = mapOf("voucher" to "SUMMER25", "discountPercent" to "25"),
                ),
            ),
        )
    }
}

/** One event for the debug e2e event hook (see [AttributionCoordinator.e2eEvent]). */
data class E2eEvent(val name: String, val value: Double? = null, val currency: String? = null)

/**
 * Remembers that the consent gate was answered, so it is shown once per install. The SDK persists
 * the decision itself (via `setConsent`); this flag only drives the UI.
 */
class ConsentPrefs(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    val decided: Boolean get() = prefs.getBoolean(KEY_DECIDED, false)

    fun markDecided() {
        prefs.edit().putBoolean(KEY_DECIDED, true).apply()
    }

    private companion object {
        const val PREFS = "kickflip_consent"
        const val KEY_DECIDED = "decided"
    }
}
