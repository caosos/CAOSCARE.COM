package care.caos.companion.usb

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbDeviceConnection
import android.hardware.usb.UsbManager
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

/**
 * Claims the Nooelec NESDR (or any RTL2832U-based SDR) over USB host and
 * exposes a file descriptor that native code can read directly.
 *
 * Real RTL-SDR libs (rtl_sdr / Martin Marinov's rtl-sdr-android) do quite a
 * bit more — they speak vendor-specific control transfers, configure the
 * tuner, set sample rate, etc. The Rtl433Bridge native layer wraps that.
 * This class is just the Android-side USB plumbing.
 */
class RtlSdrUsb(private val ctx: Context) {

    data class Acquired(val device: UsbDevice, val connection: UsbDeviceConnection, val fileDescriptor: Int)

    private val ACTION_PERMISSION = "care.caos.companion.USB_PERMISSION"

    suspend fun acquire(): Acquired? {
        val mgr = ctx.getSystemService(Context.USB_SERVICE) as UsbManager
        val device = mgr.deviceList.values.firstOrNull(::looksLikeRtlSdr) ?: return null
        if (!mgr.hasPermission(device)) askPermission(mgr, device)
        if (!mgr.hasPermission(device)) return null
        val conn = mgr.openDevice(device) ?: return null
        return Acquired(device, conn, conn.fileDescriptor)
    }

    private fun looksLikeRtlSdr(d: UsbDevice): Boolean {
        // Realtek RTL2832U is vendor id 0x0bda. Most RTL-SDRs.
        return d.vendorId == 0x0bda
    }

    private suspend fun askPermission(mgr: UsbManager, device: UsbDevice) =
        suspendCancellableCoroutine<Unit> { cont ->
            val pi = PendingIntent.getBroadcast(
                ctx, 0, Intent(ACTION_PERMISSION).setPackage(ctx.packageName),
                PendingIntent.FLAG_MUTABLE,
            )
            val rcv = object : BroadcastReceiver() {
                override fun onReceive(c: Context?, i: Intent?) {
                    runCatching { ctx.unregisterReceiver(this) }
                    if (cont.isActive) cont.resume(Unit)
                }
            }
            ctx.registerReceiver(
                rcv,
                IntentFilter(ACTION_PERMISSION),
                Context.RECEIVER_NOT_EXPORTED,
            )
            mgr.requestPermission(device, pi)
        }
}
