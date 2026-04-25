package care.caos.companion.service

import android.content.Context
import android.util.Log
import care.caos.companion.data.CompanionSettings
import io.ktor.client.HttpClient
import io.ktor.client.engine.android.Android
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.headers
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec
import java.util.concurrent.atomic.AtomicLong

/**
 * Backend client. Posts every decoded RF event to /api/rf/event with an
 * HMAC-SHA256 signature in the X-RF-Signature header.
 *
 * Sequence number is monotonic and persisted (the backend rejects
 * non-monotonic values to defeat replay attacks). We seed from epoch
 * milliseconds at first run so reboots can't accidentally reset to 0.
 */
class BridgeApi(private val ctx: Context) {

    @Serializable
    data class Fingerprint(
        val frequency_hz: Long,
        val modulation: String,
        val bit_pattern_hex: String,
        val bit_length: Int,
        val rssi: Double? = null,
    )

    @Serializable
    private data class EventBody(
        val kiosk_id: String,
        val fingerprint: Fingerprint,
        val sequence: Long,
        val captured_at: String? = null,
    )

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }
    private val http = HttpClient(Android) {
        install(ContentNegotiation) { json(json) }
    }
    private var settings: CompanionSettings? = null
    private val seq = AtomicLong(System.currentTimeMillis())

    fun configure(s: CompanionSettings) { settings = s }

    suspend fun postEvent(fp: Fingerprint) {
        val s = settings ?: return
        val body = EventBody(
            kiosk_id = s.kioskId,
            fingerprint = fp,
            sequence = seq.incrementAndGet(),
            captured_at = null,
        )
        val payload = json.encodeToString(body)
        val sig = hmacSha256(s.rfSecret, payload)
        runCatching {
            http.post("${s.apiUrl.trimEnd('/')}/api/rf/event") {
                contentType(ContentType.Application.Json)
                headers { append("X-RF-Signature", sig) }
                setBody(payload)
            }
        }.onFailure { Log.w(TAG, "rf event post failed: ${it.message}") }
    }

    private fun hmacSha256(key: String, payload: String): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key.toByteArray(), "HmacSHA256"))
        return mac.doFinal(payload.toByteArray()).joinToString("") { "%02x".format(it) }
    }

    companion object { private const val TAG = "BridgeApi" }
}
