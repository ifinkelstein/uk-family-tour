package com.family.uktour.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

// Journey palette: each leg of the trip has its own accent, so color itself
// tells you where you are in the itinerary.
object Journey {
    val ink = Color(0xFF1B2432)          // midnight navy — base text
    val paper = Color(0xFFFAF7F0)        // warm paper background
    val londonRed = Color(0xFFC8102E)    // postbox red — days 2–8
    val edinburghThistle = Color(0xFF6C4AB0) // thistle purple — days 9–12
    val yorkTeal = Color(0xFF0E7C7B)     // viking teal — days 13–14
    val stampGold = Color(0xFFE8B647)    // passport stamp gold

    fun accentForDay(day: Int): Color = when {
        day <= 8 -> londonRed
        day <= 12 -> edinburghThistle
        else -> yorkTeal
    }

    fun cityForDay(day: Int): String = when {
        day <= 7 -> "London"
        day == 8 -> "Heading north"
        day <= 12 -> "Edinburgh"
        else -> "York"
    }
}

private val lightScheme = lightColorScheme(
    primary = Journey.londonRed,
    onPrimary = Color.White,
    background = Journey.paper,
    surface = Color.White,
    onBackground = Journey.ink,
    onSurface = Journey.ink,
    secondary = Journey.stampGold
)

private val darkScheme = darkColorScheme(
    primary = Color(0xFFE05A6E),
    background = Color(0xFF12161F),
    surface = Color(0xFF1B2230),
    secondary = Journey.stampGold
)

private val tourTypography = Typography(
    displaySmall = TextStyle(
        fontFamily = FontFamily.Serif,
        fontWeight = FontWeight.Bold,
        fontSize = 30.sp,
        lineHeight = 36.sp
    ),
    headlineSmall = TextStyle(
        fontFamily = FontFamily.Serif,
        fontWeight = FontWeight.Bold,
        fontSize = 22.sp,
        lineHeight = 28.sp
    ),
    titleMedium = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 17.sp
    ),
    labelSmall = TextStyle(
        fontWeight = FontWeight.Medium,
        fontSize = 11.sp,
        letterSpacing = 1.2.sp
    )
)

@Composable
fun UKTourTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) darkScheme else lightScheme,
        typography = tourTypography,
        content = content
    )
}
