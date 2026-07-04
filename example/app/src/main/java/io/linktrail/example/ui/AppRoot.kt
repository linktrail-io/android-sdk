package io.linktrail.example.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import io.linktrail.example.Screen
import io.linktrail.example.Store
import io.linktrail.example.ui.theme.KickFlipTheme

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppRoot(store: Store) {
    KickFlipTheme {
        var showSimulator by remember { mutableStateOf(false) }
        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text("KickFlip", fontWeight = FontWeight.Black) },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.primary,
                        titleContentColor = MaterialTheme.colorScheme.onPrimary,
                    ),
                )
            },
            floatingActionButton = {
                ExtendedFloatingActionButton(onClick = { showSimulator = true }) {
                    Text("🧪  Simulate deep link")
                }
            },
        ) { padding ->
            Box(Modifier.fillMaxSize().padding(padding)) {
                when (val screen = store.screen) {
                    Screen.Home -> HomeScreen(store)
                    is Screen.ProductDetail -> ProductScreen(
                        product = screen.product,
                        voucher = screen.voucher,
                        source = store.lastSource,
                        onBack = store::goHome,
                    )
                }
            }
        }

        if (showSimulator) {
            SimulatorPanel(
                onDismiss = { showSimulator = false },
                onFire = { scenario ->
                    store.simulate(scenario)
                    showSimulator = false
                },
            )
        }
    }
}
