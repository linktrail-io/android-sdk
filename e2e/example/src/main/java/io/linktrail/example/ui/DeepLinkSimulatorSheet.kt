package io.linktrail.example.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.linktrail.example.sdk.AttributionCoordinator
import io.linktrail.example.ui.theme.KickFlipColors
import kotlinx.coroutines.launch

/**
 * A small dev panel that fires each of the four deferred deep-link scenarios so you can see where
 * the app lands, without a real click + install round-trip. Mirrors `DeepLinkSimulatorView` on iOS:
 * picking a row hides the sheet first and routes once it is gone.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalComposeUiApi::class)
@Composable
fun DeepLinkSimulatorSheet(
    scenarios: List<AttributionCoordinator.Scenario>,
    onDismiss: () -> Unit,
    onSelect: (AttributionCoordinator.Scenario) -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val scope = rememberCoroutineScope()
    fun hideThen(action: () -> Unit) {
        scope.launch { sheetState.hide() }.invokeOnCompletion { action() }
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = KickFlipColors.GroupedBackground,
    ) {
        // The sheet is its own window, so it needs its own testTag → resource-id mapping for Maestro.
        Column(
            Modifier
                .fillMaxWidth()
                .semantics { testTagsAsResourceId = true }
                .navigationBarsPadding()
                .padding(bottom = 16.dp),
        ) {
            Box(Modifier.fillMaxWidth().padding(horizontal = 8.dp)) {
                Text(
                    "Simulate a Link",
                    fontSize = 17.sp,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.align(Alignment.Center),
                )
                TextButton(
                    onClick = { hideThen(onDismiss) },
                    modifier = Modifier.align(Alignment.CenterEnd).testTag("simulator-close"),
                ) {
                    Text("Close", fontSize = 17.sp, color = KickFlipColors.Tint)
                }
            }

            Text(
                "DEFERRED DEEP LINK SCENARIOS",
                fontSize = 13.sp,
                color = KickFlipColors.SecondaryLabel,
                modifier = Modifier.padding(start = 36.dp, end = 36.dp, top = 16.dp, bottom = 6.dp),
            )
            Column(
                Modifier
                    .padding(horizontal = 16.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(KickFlipColors.SystemBackground),
            ) {
                scenarios.forEachIndexed { index, scenario ->
                    if (index > 0) HorizontalDivider(Modifier.padding(start = 20.dp), color = KickFlipColors.Separator)
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .clickable { hideThen { onSelect(scenario) } }
                            .padding(horizontal = 20.dp, vertical = 12.dp)
                            .testTag(scenario.testTag),
                        verticalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        Text(scenario.title, fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
                        Text(scenario.detail, fontSize = 15.sp, color = KickFlipColors.SecondaryLabel)
                        Text(scenario.pathLabel, fontSize = 12.sp, fontFamily = FontFamily.Monospace, color = KickFlipColors.Tint)
                    }
                }
            }
            Text(
                "Simulates a fresh install landing via the SDK's deferred deep link. The link's path and " +
                    "meta decide where you land — the same thing your real onLink handler routes on.",
                fontSize = 13.sp,
                color = KickFlipColors.SecondaryLabel,
                modifier = Modifier.padding(start = 36.dp, end = 36.dp, top = 6.dp),
            )
        }
    }
}
