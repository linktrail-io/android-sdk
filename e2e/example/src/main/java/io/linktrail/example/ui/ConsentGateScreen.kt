package io.linktrail.example.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.linktrail.example.ui.theme.KickFlipColors

/**
 * First-launch consent gate. Same screen and copy as the iOS example's consent screen
 * (`TrackingConsentView`, which records the SDK consent decision; it is not the ATT prompt), minus
 * its clipboard footnote: Android reads the click token from the Play Install Referrer, so there is
 * no clipboard and no paste step.
 *
 * The SDK is deny-by-default (`requireConsent`): until a decision is recorded the install is
 * **held** and nothing is sent. This screen releases the hold:
 *  - **Allow** → `setConsent(true)` → the held install is sent, counted and attributed.
 *  - **Not now** → `setConsent(false)` → the held install is sent once with `consent: false`; the
 *    deferred link still resolves so the user lands in the right place, but nothing is recorded.
 */
@Composable
fun ConsentGateScreen(onDecision: (Boolean) -> Unit) {
    Column(
        Modifier
            .fillMaxSize()
            .background(KickFlipColors.SystemBackground)
            .systemBarsPadding()
            .padding(horizontal = 24.dp)
            .testTag("consent-gate"),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.weight(1f))

        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text("✋", fontSize = 44.sp)
            Text(
                "Allow tracking?",
                fontSize = 34.sp,
                lineHeight = 40.sp,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
            )
            Text(
                "We use this to credit the campaign you came from and to tailor your first visit. " +
                    "You can browse the whole store either way.",
                fontSize = 17.sp,
                color = KickFlipColors.SecondaryLabel,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(horizontal = 8.dp),
            )
        }

        Spacer(Modifier.weight(1f))

        Column(
            Modifier.padding(bottom = 40.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Button(
                onClick = { onDecision(true) },
                shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.buttonColors(containerColor = KickFlipColors.Tint),
                modifier = Modifier.fillMaxWidth().height(50.dp).testTag("tracking-allow"),
            ) {
                Text("Allow", fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
            }
            TextButton(onClick = { onDecision(false) }, modifier = Modifier.testTag("tracking-deny")) {
                Text("Not now", fontSize = 17.sp, fontWeight = FontWeight.Medium, color = KickFlipColors.SecondaryLabel)
            }
        }
    }
}
