package io.linktrail.example

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import io.linktrail.LinkTrail
import io.linktrail.example.ui.AppRoot

class MainActivity : ComponentActivity() {

    private val store: Store by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // The one routing hook — fires for deferred (first launch) AND re-engagement links.
        LinkTrail.shared?.onLink { link, source -> store.route(link, source) }

        handleIntent(intent)
        setContent { AppRoot(store) }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(intent: Intent?) {
        val uri = intent?.data ?: return
        val sdk = LinkTrail.shared
        if (sdk != null) {
            sdk.handleDeepLink(uri) // resolves server-side → onLink (re-engagement)
        } else {
            store.routeUri(uri) // offline demo: route the raw link locally
        }
    }
}
