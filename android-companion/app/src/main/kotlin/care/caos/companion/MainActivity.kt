package care.caos.companion

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import care.caos.companion.data.SettingsStore
import care.caos.companion.service.RfBridgeService
import care.caos.companion.ui.AppRoot
import kotlinx.coroutines.launch
import androidx.lifecycle.lifecycleScope

/**
 * Single-Activity app. Compose-driven UI. Two screens:
 *   ProvisionScreen — when no kiosk_id/secret yet (QR scan landing)
 *   DashboardScreen — when provisioned (status, last events, controls)
 */
class MainActivity : ComponentActivity() {
    private val store by lazy { SettingsStore(this) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val settings by store.settings.collectAsState(initial = null)
            AppRoot(
                settings = settings,
                onProvisioned = {
                    lifecycleScope.launch { store.save(it) }
                    startService(Intent(this, RfBridgeService::class.java))
                },
                onClear = { lifecycleScope.launch { store.clear() } },
            )
        }
    }

    override fun onResume() {
        super.onResume()
        // If we're already provisioned, make sure the service is running.
        // Idempotent — Android dedupes startService calls for the same intent.
        lifecycleScope.launch {
            store.peek()?.let {
                if (it.isComplete) startService(Intent(this@MainActivity, RfBridgeService::class.java))
            }
        }
    }
}
