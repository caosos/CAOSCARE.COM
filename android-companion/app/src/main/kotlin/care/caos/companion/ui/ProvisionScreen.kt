package care.caos.companion.ui

import android.app.Activity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import care.caos.companion.data.CompanionSettings
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import kotlinx.serialization.json.Json

/**
 * First-run screen. Single button: "Scan provisioning code". User scans the
 * QR shown in /admin/install/{kiosk_id} on another screen, payload is parsed,
 * we hand it to MainActivity which starts the bridge service.
 */
@Composable
fun ProvisionScreen(onProvisioned: (CompanionSettings) -> Unit) {
    var status by remember { mutableStateOf<String?>(null) }
    var manualOpen by remember { mutableStateOf(false) }

    val scanner = rememberLauncherForActivityResult(ScanContract()) { result ->
        if (result.contents.isNullOrBlank()) {
            status = "No code scanned."
            return@rememberLauncherForActivityResult
        }
        runCatching {
            val payload = Json.parseToJsonElement(result.contents).let { it as kotlinx.serialization.json.JsonObject }
            CompanionSettings(
                apiUrl = payload["api_url"]?.let { it as kotlinx.serialization.json.JsonPrimitive }?.content.orEmpty(),
                kioskId = payload["kiosk_id"]?.let { it as kotlinx.serialization.json.JsonPrimitive }?.content.orEmpty(),
                rfSecret = payload["rf_secret"]?.let { it as kotlinx.serialization.json.JsonPrimitive }?.content.orEmpty(),
            )
        }.onSuccess { s ->
            if (s.isComplete) onProvisioned(s) else status = "Provisioning code is missing fields."
        }.onFailure {
            status = "Couldn't read that code: ${it.message}"
        }
    }

    Column(
        modifier = Modifier.fillMaxSize().padding(28.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text("CAOS Care Companion", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(8.dp))
        Text(
            "Pair this tablet to a CAOS Care kiosk so it can listen to RF pendants.",
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(36.dp))
        Button(onClick = {
            scanner.launch(ScanOptions().apply {
                setOrientationLocked(false)
                setBeepEnabled(true)
                setPrompt("Scan the QR shown on /admin/install")
            })
        }) {
            Icon(Icons.Default.QrCodeScanner, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("Scan provisioning code")
        }
        Spacer(Modifier.height(12.dp))
        TextButton(onClick = { manualOpen = true }) { Text("Or paste manually") }
        status?.let {
            Spacer(Modifier.height(20.dp))
            Text(it, color = MaterialTheme.colorScheme.error)
        }
    }

    if (manualOpen) ManualEntrySheet(
        onDismiss = { manualOpen = false },
        onSave = { onProvisioned(it); manualOpen = false },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ManualEntrySheet(onDismiss: () -> Unit, onSave: (CompanionSettings) -> Unit) {
    var apiUrl by remember { mutableStateOf("") }
    var kioskId by remember { mutableStateOf("") }
    var rfSecret by remember { mutableStateOf("") }
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Manual provisioning", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(value = apiUrl, onValueChange = { apiUrl = it }, label = { Text("API URL") }, singleLine = true)
            OutlinedTextField(value = kioskId, onValueChange = { kioskId = it }, label = { Text("Kiosk ID") }, singleLine = true)
            OutlinedTextField(value = rfSecret, onValueChange = { rfSecret = it }, label = { Text("RF Secret") }, singleLine = true)
            Button(
                onClick = { onSave(CompanionSettings(apiUrl.trim(), kioskId.trim(), rfSecret.trim())) },
                enabled = apiUrl.isNotBlank() && kioskId.isNotBlank() && rfSecret.isNotBlank(),
            ) { Text("Save and start") }
        }
    }
}
