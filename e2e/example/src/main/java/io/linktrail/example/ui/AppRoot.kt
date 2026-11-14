package io.linktrail.example.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.linktrail.example.R
import io.linktrail.example.Store
import io.linktrail.example.sdk.AttributionCoordinator
import io.linktrail.example.ui.theme.KickFlipColors
import io.linktrail.example.ui.theme.KickFlipTheme
import io.linktrail.model.LinkTrailLinkSource
import kotlinx.coroutines.delay

/** How long the "arrived via link" banner stays up (same as iOS). */
private const val BANNER_MILLIS = 3_500L

/**
 * Consent gate first, then the storefront: home → product navigation, plus the deep-link simulator
 * and the "arrived via link" banner. Mirrors `RootView` in the iOS example. [showE2eDeviceId] (debug
 * builds only: `src/debug`; a no-op in release) shows the SDK device id on every storefront screen for the e2e
 * device lookup (`E2eDeviceIdLabel`).
 */
@OptIn(ExperimentalComposeUiApi::class)
@Composable
fun AppRoot(store: Store, coordinator: AttributionCoordinator, showE2eDeviceId: Boolean = E2eDeviceId.ENABLED) {
    KickFlipTheme {
        // Expose Compose testTags as resource-ids so Maestro can target them by `id:`.
        Box(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }) {
            var showConsentGate by remember { mutableStateOf(coordinator.needsConsentDecision) }
            if (showConsentGate) {
                ConsentGateScreen { granted ->
                    coordinator.answerConsent(granted)
                    showConsentGate = false
                }
            } else {
                Storefront(store, coordinator, showE2eDeviceId)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun Storefront(store: Store, coordinator: AttributionCoordinator, showE2eDeviceId: Boolean) {
    var showSimulator by rememberSaveable { mutableStateOf(false) }
    val product = store.path.lastOrNull()

    BackHandler(enabled = product != null) { store.pop() }

    Box(Modifier.fillMaxSize()) {
        Scaffold(
            containerColor = KickFlipColors.GroupedBackground,
            topBar = {
                TopAppBar(
                    title = {
                        if (product == null) Text("KickFlip", fontWeight = FontWeight.Bold, fontSize = 28.sp)
                    },
                    navigationIcon = {
                        if (product != null) {
                            IconButton(onClick = { store.pop() }, modifier = Modifier.testTag("back")) {
                                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                            }
                        }
                    },
                    actions = {
                        // Like iOS, the simulator lives in the home screen's toolbar.
                        if (product == null) {
                            IconButton(onClick = { showSimulator = true }, modifier = Modifier.testTag("simulate-link")) {
                                Icon(painterResource(R.drawable.ic_link), contentDescription = "Simulate a link")
                            }
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = KickFlipColors.GroupedBackground,
                        navigationIconContentColor = KickFlipColors.Tint,
                        actionIconContentColor = KickFlipColors.Tint,
                    ),
                )
            },
        ) { padding ->
            Box(Modifier.fillMaxSize().padding(padding)) {
                if (product == null) HomeScreen(store) else ProductScreen(product, store.voucher(product), store.linkMeta(product))
            }
        }

        // Every storefront screen: an attributed probabilistic install routes straight to a product
        // page, and the e2e reads the label wherever the app lands.
        if (E2eDeviceId.ENABLED && showE2eDeviceId) {
            E2eDeviceIdLabel(Modifier.align(Alignment.BottomCenter).navigationBarsPadding().padding(bottom = 4.dp))
        }
        LandingBannerOverlay(store)
    }

    if (showSimulator) {
        DeepLinkSimulatorSheet(
            scenarios = coordinator.scenarios,
            onDismiss = { showSimulator = false },
            // Called after the sheet has animated away, so the route lands on the visible storefront.
            onSelect = { scenario ->
                showSimulator = false
                coordinator.simulate(scenario)
            },
        )
    }
}

/** The transient banner shown when a deep link (deferred or re-engagement) lands. */
@Composable
private fun LandingBannerOverlay(store: Store) {
    val banner = store.banner
    // Keep the last banner around while it animates out.
    var shown by remember { mutableStateOf(banner) }
    if (banner != null) shown = banner

    banner?.let { current ->
        LaunchedEffect(current.id) {
            delay(BANNER_MILLIS)
            store.dismissBanner(current.id)
        }
    }

    AnimatedVisibility(
        visible = banner != null,
        enter = slideInVertically { -it } + fadeIn(),
        exit = slideOutVertically { -it } + fadeOut(),
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
    ) {
        val b = shown ?: return@AnimatedVisibility
        Surface(
            shape = RoundedCornerShape(14.dp),
            color = MaterialTheme.colorScheme.surface.copy(alpha = 0.97f),
            shadowElevation = 8.dp,
            modifier = Modifier
                .fillMaxWidth()
                .border(1.dp, KickFlipColors.Separator.copy(alpha = 0.4f), RoundedCornerShape(14.dp))
                .testTag("landing-banner"),
        ) {
            Row(
                Modifier.padding(12.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(if (b.source == LinkTrailLinkSource.DEFERRED) "✨" else "↩️", fontSize = 20.sp)
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(b.title, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                    Text(b.subtitle, fontSize = 12.sp, color = KickFlipColors.SecondaryLabel)
                }
            }
        }
    }
}
