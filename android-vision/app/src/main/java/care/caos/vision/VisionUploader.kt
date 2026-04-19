package care.caos.vision

import android.util.Base64
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/** Posts camera frames to the CAOS Care backend and returns the AI reply + TTS audio. */
class VisionUploader(
    private val baseUrl: String,
    private val deviceToken: String,
) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    data class Result(val reply: String, val audioBase64: String?)

    fun describe(jpegBytes: ByteArray, question: String? = null): Result {
        val body = JSONObject().apply {
            put("image_base64", Base64.encodeToString(jpegBytes, Base64.NO_WRAP))
            question?.let { put("question", it) }
            put("speak", true)
        }.toString().toRequestBody("application/json".toMediaType())

        val path = if (question != null) "/api/vision/frame" else "/api/vision/describe"
        val req = Request.Builder()
            .url("$baseUrl$path")
            .post(body)
            .apply {
                if (deviceToken.isNotBlank()) addHeader("X-Device-Token", deviceToken)
            }
            .build()

        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) throw RuntimeException("vision http ${resp.code}")
            val json = JSONObject(resp.body!!.string())
            return Result(
                reply = json.optString("reply", ""),
                audioBase64 = json.optString("audio_base64").ifBlank { null }
            )
        }
    }
}
