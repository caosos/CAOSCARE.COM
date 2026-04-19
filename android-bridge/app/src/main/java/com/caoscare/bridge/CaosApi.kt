package com.caoscare.bridge

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/** Tiny OkHttp client for POSTing pendant events to the CAOS Care backend. */
class CaosApi(private val settings: Settings) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    private val jsonMt = "application/json".toMediaType()

    /**
     * @param rawJson the raw JSON line we received from the receiver firmware
     * @return pair of (success, serverMessage)
     */
    fun postPendantEvent(rawJson: String): Pair<Boolean, String> {
        val url = settings.backendUrl
        if (url.isBlank()) return false to "backend_url not set"

        // Parse, inject zone + device_token, re-serialize
        val obj = try { JSONObject(rawJson) } catch (e: Exception) {
            return false to "invalid JSON from receiver: ${e.message}"
        }
        if (settings.zone.isNotBlank()) obj.put("zone", settings.zone)
        if (settings.deviceToken.isNotBlank()) obj.put("device_token", settings.deviceToken)

        val body = obj.toString().toRequestBody(jsonMt)
        val req = Request.Builder()
            .url("$url/api/pendants/event")
            .post(body)
            .build()

        return try {
            client.newCall(req).execute().use { resp ->
                val code = resp.code
                val text = resp.body?.string()?.take(300) ?: ""
                (code in 200..299) to "HTTP $code — $text"
            }
        } catch (e: Exception) {
            false to "network error: ${e.message}"
        }
    }
}
