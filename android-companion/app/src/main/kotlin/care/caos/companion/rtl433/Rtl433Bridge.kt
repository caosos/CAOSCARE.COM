package care.caos.companion.rtl433

import care.caos.companion.service.BridgeApi
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Native rtl_433 bridge.
 *
 * **Status: STUB.** The real implementation links against rtl_433 (vendored
 * under `app/src/main/cpp/rtl_433/`) compiled by NDK, exposes a JNI
 * `nativeStart(fd, callback)` that pumps fingerprints up via the JNI env.
 *
 * This stub emits one synthetic fingerprint every 4 seconds so the rest of
 * the pipeline (USB claim → service → BridgeApi → backend → match → alert)
 * can be verified end-to-end without the native build.
 *
 * To wire the real decoder:
 *   1. `git clone --depth 1 https://github.com/merbanan/rtl_433.git app/src/main/cpp/rtl_433`
 *   2. Edit `app/src/main/cpp/CMakeLists.txt` to compile it with `add_subdirectory(rtl_433)`
 *   3. Uncomment the `externalNativeBuild` block in `app/build.gradle.kts`
 *   4. Replace `start()` below with `nativeStart(fileDescriptor, ::deliver)`
 *   5. Implement `deliver(...)` to package fingerprints into BridgeApi.Fingerprint
 */
class Rtl433Bridge {
    private var loopJob: Job? = null

    fun start(fileDescriptor: Int, onFingerprint: (BridgeApi.Fingerprint) -> Unit) {
        // TODO: System.loadLibrary("rtl433_jni"); nativeStart(fileDescriptor, onFingerprint)
        loopJob = CoroutineScope(Dispatchers.IO).launch {
            var i = 0
            while (true) {
                delay(4000)
                onFingerprint(
                    BridgeApi.Fingerprint(
                        frequency_hz = 319_000_000L,
                        modulation = "OOK",
                        bit_pattern_hex = "deadbeef%02x".format(i++ and 0xff),
                        bit_length = 40,
                        rssi = -57.0,
                    )
                )
            }
        }
    }

    fun stop() {
        // TODO: nativeStop()
        loopJob?.cancel()
        loopJob = null
    }
}
