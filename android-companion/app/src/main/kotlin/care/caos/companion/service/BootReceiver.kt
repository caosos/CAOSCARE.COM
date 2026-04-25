package care.caos.companion.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * Re-launch the bridge service after device boot.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            context.startForegroundService(Intent(context, RfBridgeService::class.java))
        }
    }
}
