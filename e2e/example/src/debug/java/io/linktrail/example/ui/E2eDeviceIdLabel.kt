package io.linktrail.example.ui

import android.util.Log
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.sp
import io.linktrail.example.ui.theme.KickFlipColors
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File

/**
 * Debug builds only: the SDK device id, for the e2e device lookup (`GET /v1/e2e/devices/:deviceId`). The `*_problistic` flows have no click token, so
 * `scripts/e2e-maestro.sh` reads this label (test tag [TAG]) to check their install on the backend.
 *
 * The SDK has no public getter for its device id, so this reads the SDK's state file
 * (`noBackupFilesDir/io.linktrail.state.json`, key `device_id`). Nothing in the SDK changes.
 *
 * Debug source set only: release builds compile `src/release`'s no-op instead, so neither the label
 * nor the state-file read ships in a release build.
 */
object E2eDeviceId {
    /** The label exists in this build (debug). The release twin is `false`. */
    const val ENABLED = true

    const val TAG = "e2e-device-id"

    /** Logged under `KickFlip` once the id is known: the script's fallback when it can't read the screen. */
    const val LOG = "E2E device id:"

    /** Shown while the SDK has no device id (e.g. after a denied install, which carries none). */
    const val NONE = "none"

    internal const val STATE_FILE = "io.linktrail.state.json"
    internal const val KEY = "device_id"
    internal const val POLL_MILLIS = 1_000L

    /** The SDK's device id from its state file in [noBackupDir]; `null` when there is none or it can't be read. */
    fun read(noBackupDir: File): String? = try {
        val file = File(noBackupDir, STATE_FILE)
        if (!file.isFile) null else JSONObject(file.readText()).optString(KEY).trim().takeIf { it.isNotEmpty() }
    } catch (_: Exception) {
        null
    }
}

/** The device id label. Checks the state file every second until the SDK has written an id, then logs it once. */
@Composable
fun E2eDeviceIdLabel(
    modifier: Modifier = Modifier,
    read: (File) -> String? = E2eDeviceId::read,
) {
    val dir = LocalContext.current.noBackupFilesDir
    var id by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(dir) {
        while (id == null) {
            id = withContext(Dispatchers.IO) { read(dir) }
            if (id == null) delay(E2eDeviceId.POLL_MILLIS)
        }
        Log.i("KickFlip", "${E2eDeviceId.LOG} $id")
    }
    Text(
        id ?: E2eDeviceId.NONE,
        fontSize = 10.sp,
        color = KickFlipColors.SecondaryLabel,
        modifier = modifier.testTag(E2eDeviceId.TAG),
    )
}
