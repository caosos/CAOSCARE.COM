package com.caoscare.bridge

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.lifecycle.LifecycleService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import androidx.lifecycle.lifecycleScope

/**
 * Foreground service. Holds the USB-serial reader alive, POSTs each received JSON line to
 * the CAOS Care backend, updates a persistent notification so Android doesn't kill it.
 */
class BridgeService : LifecycleService() {

    private lateinit var reader: UsbSerialReader
    private lateinit var api: CaosApi
    private lateinit var settings: Settings

    @Volatile private var lastStatus: String = "Starting…"
    @Volatile private var lastEventAt: String = "—"

    override fun onCreate() {
        super.onCreate()
        settings = Settings(this)
        api = CaosApi(settings)

        ensureChannel()
        startForeground(NOTIFY_ID, buildNotification())

        reader = UsbSerialReader(
            ctx = this,
            onLine = { line -> onLineReceived(line) },
            onStatus = { status ->
                lastStatus = status
                updateNotification()
            },
        )

        lifecycleScope.launch(Dispatchers.IO) { reader.run() }
    }

    private fun onLineReceived(line: String) {
        val ts = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.US)
            .format(java.util.Date())
        lastEventAt = ts
        lifecycleScope.launch(Dispatchers.IO) {
            val (ok, detail) = api.postPendantEvent(line)
            lastStatus = if (ok) "POST ok at $ts" else "POST failed: $detail"
            updateNotification()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        reader.stop()
    }

    override fun onBind(intent: Intent): IBinder? { super.onBind(intent); return null }

    private fun ensureChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(NotificationManager::class.java)
            if (nm.getNotificationChannel(CHANNEL) == null) {
                nm.createNotificationChannel(
                    NotificationChannel(CHANNEL, "CAOS Bridge", NotificationManager.IMPORTANCE_LOW)
                )
            }
        }
    }

    private fun buildNotification(): Notification =
        NotificationCompat.Builder(this, CHANNEL)
            .setContentTitle("CAOS Bridge — ${settings.zone.ifBlank { "no zone set" }}")
            .setContentText("$lastStatus · last event $lastEventAt")
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
            .setOngoing(true)
            .build()

    private fun updateNotification() {
        val nm = getSystemService(NotificationManager::class.java)
        nm.notify(NOTIFY_ID, buildNotification())
    }

    companion object {
        private const val NOTIFY_ID = 1
        private const val CHANNEL = "caos_bridge"
    }
}
