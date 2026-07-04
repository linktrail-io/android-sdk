package io.linktrail.example

import android.app.Application
import io.linktrail.LinkTrail
import io.linktrail.LinkTrailOptions

/**
 * Configures the LinkTrail SDK once, in `Application.onCreate()`.
 *
 * The API key is read from `BuildConfig.LINKTRAIL_API_KEY`, which comes from an **untracked**
 * `local.properties` entry (`linktrail.apiKey=lt_live_…`). When it's absent the SDK is left
 * unconfigured and the demo runs entirely off the debug simulator panel.
 */
class KickFlipApp : Application() {
    override fun onCreate() {
        super.onCreate()
        val apiKey = BuildConfig.LINKTRAIL_API_KEY
        if (apiKey.isNotBlank()) {
            runCatching {
                LinkTrail.configure(this, apiKey, LinkTrailOptions(logEnabled = true))
            }
        }
    }
}
