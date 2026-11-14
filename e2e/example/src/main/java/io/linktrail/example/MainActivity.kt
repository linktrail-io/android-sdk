package io.linktrail.example

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import io.linktrail.example.ui.AppRoot

class MainActivity : ComponentActivity() {

    private val app: KickFlipApp get() = application as KickFlipApp

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // A recreated activity (rotation, process restore) must not re-handle the launch link.
        if (savedInstanceState == null) handleIntent(intent)
        setContent { AppRoot(app.store, app.coordinator) }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleIntent(intent)
    }

    /** App Links (https://<link host>/…) and the kickflip:// scheme both arrive as VIEW intents. */
    private fun handleIntent(intent: Intent?) {
        val uri = intent?.takeIf { it.action == Intent.ACTION_VIEW }?.data ?: return
        app.coordinator.handleIncomingUri(uri)
    }
}
