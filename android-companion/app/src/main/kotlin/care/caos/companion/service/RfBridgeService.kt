package care.caos.companion.service

import android.app.Notification
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.lifecycle.LifecycleService
import androidx.lifecycle.lifecycleScope
import care.caos.companion.CompanionApp
import care.caos.companion.MainActivity
import care.caos.companion.R
import care.caos.companion.data.SettingsStore
import care.caos.companion.rtl433.Rtl433Bridge
import care.caos.companion.usb.RtlSdrUsb
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/**
 * The forever-running heart of this app.
 *
 *   1) Reads provisioned settings (apiUrl, kioskId, rfSecret)
 *   2) Acquires the Nooelec via USB host
 *   3) Hands the USB descriptor to Rtl433Bridge for native decode
 *   4) Forwards every decoded fingerprint to /api/rf/event via BridgeApi
 *
 * Promoted to foreground with a persistent notification so Android won't
 * kill it when the screen sleeps. Self-restart on boot via BootReceiver.
 */
class RfBridgeService : LifecycleService() {

    private lateinit var store: SettingsStore
    private lateinit var api: BridgeApi
    private val rtl = Rtl433Bridge()
    private var workJob: Job? = null

    override fun onCreate() {
        super.onCreate()
        store = SettingsStore(this)
        api = BridgeApi(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForegroundCompat()
        if (workJob?.isActive == true) return START_STICKY
        workJob = lifecycleScope.launch {
            val settings = store.peek() ?: return@launch
            api.configure(settings)

            val sdr = RtlSdrUsb(this@RfBridgeService)
            val device = sdr.acquire() ?: run {
                // No SDR plugged in. Service stays alive — when the user attaches
                // one, the USB_DEVICE_ATTACHED intent re-launches MainActivity which
                // calls startService again. We just exit this loop.
                return@launch
            }
            rtl.start(device.fileDescriptor) { fingerprint ->
                lifecycleScope.launch { api.postEvent(fingerprint) }
            }
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent): IBinder? {
        super.onBind(intent)
        return null
    }

    override fun onDestroy() {
        rtl.stop()
        workJob?.cancel()
        super.onDestroy()
    }

    private fun startForegroundCompat() {
        val openApp = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE,
        )
        val n: Notification = NotificationCompat.Builder(this, CompanionApp.NOTIF_CHANNEL)
            .setContentTitle("CAOS Care RF Bridge")
            .setContentText("Listening for pendant presses")
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setOngoing(true)
            .setContentIntent(openApp)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(NOTIF_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(NOTIF_ID, n)
        }
    }

    companion object { const val NOTIF_ID = 4242 }
}
