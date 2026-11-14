package io.linktrail.example.ui

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

/**
 * Release twin of the debug-only SDK device id label (`src/debug`, used by the e2e device lookup):
 * nothing is shown and the SDK's state file is never read in a release build.
 */
object E2eDeviceId {
    /** No label in release builds. */
    const val ENABLED = false
}

/** No-op in release builds. */
@Suppress("UNUSED_PARAMETER")
@Composable
fun E2eDeviceIdLabel(modifier: Modifier = Modifier) = Unit
