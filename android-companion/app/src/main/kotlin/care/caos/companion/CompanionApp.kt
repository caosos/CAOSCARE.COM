package care.caos.companion

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build

/**
 * Application entry point. The only thing it does at process start is
 * register the foreground-service notification channel — required on Oreo+.
 */
class CompanionApp : Application() {
    override fun onCreate() {
        super.onCreate()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(NotificationManager::class.java)
            nm?.createNotificationChannel(
                NotificationChannel(
                    NOTIF_CHANNEL,
                    "CAOS RF Bridge",
                    NotificationManager.IMPORTANCE_LOW,
                ).apply {
                    description = "Background service that listens for pendant button presses."
                }
            )
        }
    }

    companion object {
        const val NOTIF_CHANNEL = "caos_rf_bridge"
    }
}
