package care.caos.companion.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import care.caos.companion.data.CompanionSettings

/**
 * App root — picks Provision vs Dashboard based on whether we have a complete
 * settings payload yet.
 */
@Composable
fun AppRoot(
    settings: CompanionSettings?,
    onProvisioned: (CompanionSettings) -> Unit,
    onClear: () -> Unit,
) {
    MaterialTheme {
        Surface(modifier = Modifier.fillMaxSize()) {
            when {
                settings == null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
                !settings.isComplete -> ProvisionScreen(onProvisioned = onProvisioned)
                else -> DashboardScreen(settings = settings, onClear = onClear)
            }
        }
    }
}
