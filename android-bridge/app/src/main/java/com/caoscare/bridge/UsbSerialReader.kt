package com.caoscare.bridge

import android.content.Context
import android.hardware.usb.UsbManager
import com.hoho.android.usbserial.driver.UsbSerialDriver
import com.hoho.android.usbserial.driver.UsbSerialPort
import com.hoho.android.usbserial.driver.UsbSerialProber
import java.io.ByteArrayOutputStream
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Opens the first available USB-serial device, reads bytes, frames them into newline-delimited lines,
 * and invokes [onLine] for each parsed line. Runs until [stop] is called.
 *
 * Expected firmware output: one JSON object per line, terminated with \n.
 */
class UsbSerialReader(
    private val ctx: Context,
    private val onLine: (String) -> Unit,
    private val onStatus: (String) -> Unit,
) {
    private val running = AtomicBoolean(false)
    private var port: UsbSerialPort? = null

    fun run() {
        running.set(true)
        val manager = ctx.getSystemService(Context.USB_SERVICE) as UsbManager
        val drivers: List<UsbSerialDriver> = UsbSerialProber.getDefaultProber().findAllDrivers(manager)
        if (drivers.isEmpty()) {
            onStatus("No USB-serial device detected.")
            running.set(false)
            return
        }
        val driver = drivers.first()
        val connection = manager.openDevice(driver.device) ?: run {
            onStatus("USB permission not granted.")
            running.set(false)
            return
        }
        port = driver.ports.first().apply {
            open(connection)
            // 115200-8-N-1 is standard for Arduino USB-CDC
            setParameters(115200, 8, UsbSerialPort.STOPBITS_1, UsbSerialPort.PARITY_NONE)
        }
        onStatus("Listening on ${driver.device.deviceName}")

        val buf = ByteArray(4096)
        val acc = ByteArrayOutputStream()
        try {
            while (running.get()) {
                val n = port?.read(buf, 500) ?: 0
                if (n > 0) {
                    for (i in 0 until n) {
                        val b = buf[i]
                        if (b == '\n'.code.toByte() || b == '\r'.code.toByte()) {
                            if (acc.size() > 0) {
                                val line = acc.toString(Charsets.UTF_8.name()).trim()
                                acc.reset()
                                if (line.isNotEmpty()) onLine(line)
                            }
                        } else {
                            acc.write(b.toInt())
                        }
                    }
                }
            }
        } catch (e: Exception) {
            onStatus("Serial error: ${e.message}")
        } finally {
            try { port?.close() } catch (_: Exception) {}
            port = null
            onStatus("Stopped.")
        }
    }

    fun stop() { running.set(false) }
}
