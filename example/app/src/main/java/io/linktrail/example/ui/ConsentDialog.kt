package io.linktrail.example.ui

import android.content.Context
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import io.linktrail.LinkTrail

/**
 * Minimal consent store for the demo.
 *
 * The LinkTrail SDK persists the real consent flag itself (via [LinkTrail.setConsent]); this keeps a
 * small parallel copy only so the app knows whether to show the prompt on launch and can display the
 * current choice while you test. Consent is **deny-by-default** — [state] is `null` until the user
 * chooses, which mirrors the SDK holding the install as unattributed until consent is granted.
 */
object Consent {
    private const val PREFS = "kickflip_consent"
    private const val KEY_DECIDED = "decided"
    private const val KEY_GRANTED = "granted"

    /** `null` = the user hasn't decided yet; otherwise their choice. */
    fun state(context: Context): Boolean? {
        val p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return if (p.getBoolean(KEY_DECIDED, false)) p.getBoolean(KEY_GRANTED, false) else null
    }

    /**
     * Persist the choice and forward it to the SDK. `LinkTrail.shared?.setConsent(granted)` is the
     * single line a real app needs — granting sends the attributed install and flushes queued
     * events; revoking clears them. (`shared` is null when no API key is configured, so the demo's
     * UI still works offline.)
     */
    fun apply(context: Context, granted: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putBoolean(KEY_DECIDED, true)
            .putBoolean(KEY_GRANTED, granted)
            .apply()
        LinkTrail.shared?.setConsent(granted)
    }
}

/** The consent prompt. Accept → `setConsent(true)`, Decline → `setConsent(false)`. */
@Composable
fun ConsentDialog(current: Boolean?, onDecision: (Boolean) -> Unit, onDismiss: () -> Unit) {
    val status = when (current) {
        true -> "Currently: granted — installs are attributed."
        false -> "Currently: declined — links still work, nothing is tracked."
        null -> "Not decided yet — tracking stays off until you choose."
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Help improve KickFlip?") },
        text = {
            Text(
                "Allow LinkTrail to record which campaign brought you here so we can improve the app.\n\n" +
                    "Deep links work either way — this only controls install attribution, and you can " +
                    "change it anytime from the top bar.\n\n" + status
            )
        },
        confirmButton = { TextButton(onClick = { onDecision(true) }) { Text("Accept") } },
        dismissButton = { TextButton(onClick = { onDecision(false) }) { Text("Decline") } },
    )
}
