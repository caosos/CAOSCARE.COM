package care.caos.companion.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Logout
import androidx.compose.material.icons.filled.Radio
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import care.caos.companion.data.CompanionSettings

/**
 * Post-provision dashboard. Shows current status, the kiosk it's bound to,
 * and a "forget this device" button (for re-pairing if you swap tablets).
 */
@Composable
fun DashboardScreen(settings: CompanionSettings, onClear: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("CAOS Care Companion", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)

        Card {
            Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    Icon(Icons.Default.Radio, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("RF Bridge running", style = MaterialTheme.typography.titleMedium)
                }
                Text("Bound to kiosk: ${settings.kioskId}", style = MaterialTheme.typography.bodySmall)
                Text("API: ${settings.apiUrl}", style = MaterialTheme.typography.bodySmall)
                Text(
                    "Secret: " + settings.rfSecret.take(6) + "…" + settings.rfSecret.takeLast(4),
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }

        Card {
            Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("What to do next", style = MaterialTheme.typography.titleMedium)
                Text("• Plug in the Nooelec NESDR via the USB-OTG hub.")
                Text("• When you press a paired pendant, the alert will appear in the staff dashboard within a second.")
                Text("• To pair a new pendant, open the admin web UI → RF Pendants → Add new pendant.")
            }
        }

        Spacer(Modifier.weight(1f))

        OutlinedButton(onClick = onClear) {
            Icon(Icons.Default.Logout, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("Forget this kiosk")
        }
    }
}
