package io.linktrail.example.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

/** iOS light-mode system colours, so the demo reads the same on both platforms. */
object KickFlipColors {
    val Tint = Color(0xFF007AFF) // systemBlue, the iOS default accent
    val Label = Color(0xFF000000)
    val SecondaryLabel = Color(0x993C3C43)
    val TertiaryLabel = Color(0x4D3C3C43)
    val SystemBackground = Color(0xFFFFFFFF)
    val GroupedBackground = Color(0xFFF2F2F7)
    val SecondaryBackground = Color(0xFFF2F2F7)
    val Separator = Color(0x493C3C43)
    val Green = Color(0xFF34C759)
}

private val ColorScheme = lightColorScheme(
    primary = KickFlipColors.Tint,
    onPrimary = Color.White,
    background = KickFlipColors.GroupedBackground,
    onBackground = KickFlipColors.Label,
    surface = KickFlipColors.SystemBackground,
    onSurface = KickFlipColors.Label,
    surfaceVariant = KickFlipColors.SecondaryBackground,
    onSurfaceVariant = KickFlipColors.SecondaryLabel,
)

@Composable
fun KickFlipTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = ColorScheme, content = content)
}
