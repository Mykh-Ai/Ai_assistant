package sk.zevsflow.officeflow.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val OfficeFlowColors = lightColorScheme(
    primary = Color(0xFF175CD3),
    onPrimary = Color.White,
    secondary = Color(0xFF344054),
    background = Color(0xFFF7F8FA),
    surface = Color.White,
    error = Color(0xFFB42318),
)

@Composable
fun OfficeFlowTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = OfficeFlowColors, content = content)
}
