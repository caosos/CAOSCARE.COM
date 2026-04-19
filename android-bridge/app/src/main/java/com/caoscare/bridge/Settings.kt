package com.caoscare.bridge

import android.content.Context
import android.content.SharedPreferences

/** SharedPreferences-backed config. */
class Settings(ctx: Context) {
    private val prefs: SharedPreferences =
        ctx.getSharedPreferences("caos_bridge", Context.MODE_PRIVATE)

    var backendUrl: String
        get() = prefs.getString(KEY_URL, "") ?: ""
        set(v) { prefs.edit().putString(KEY_URL, v.trimEnd('/')).apply() }

    var zone: String
        get() = prefs.getString(KEY_ZONE, "") ?: ""
        set(v) { prefs.edit().putString(KEY_ZONE, v).apply() }

    var deviceToken: String
        get() = prefs.getString(KEY_TOKEN, "") ?: ""
        set(v) { prefs.edit().putString(KEY_TOKEN, v).apply() }

    var autoStart: Boolean
        get() = prefs.getBoolean(KEY_AUTO, false)
        set(v) { prefs.edit().putBoolean(KEY_AUTO, v).apply() }

    companion object {
        private const val KEY_URL = "backend_url"
        private const val KEY_ZONE = "zone"
        private const val KEY_TOKEN = "device_token"
        private const val KEY_AUTO = "auto_start"
    }
}
