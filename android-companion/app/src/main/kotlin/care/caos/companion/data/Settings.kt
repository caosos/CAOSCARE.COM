package care.caos.companion.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.serialization.Serializable

/**
 * Provisioned settings — three values that come from the QR payload at
 * /api/rf/kiosk/.../install-info. Persisted with DataStore so they survive
 * reboots and process death.
 */
@Serializable
data class CompanionSettings(
    val apiUrl: String = "",
    val kioskId: String = "",
    val rfSecret: String = "",
) {
    val isComplete: Boolean get() = apiUrl.isNotBlank() && kioskId.isNotBlank() && rfSecret.isNotBlank()
}

private val Context.dataStore by preferencesDataStore("companion")

class SettingsStore(private val ctx: Context) {
    private val K_API = stringPreferencesKey("api_url")
    private val K_KIOSK = stringPreferencesKey("kiosk_id")
    private val K_SECRET = stringPreferencesKey("rf_secret")

    val settings: Flow<CompanionSettings> = ctx.dataStore.data.map {
        CompanionSettings(
            apiUrl = it[K_API].orEmpty(),
            kioskId = it[K_KIOSK].orEmpty(),
            rfSecret = it[K_SECRET].orEmpty(),
        )
    }

    suspend fun peek(): CompanionSettings? = settings.first().takeIf { it.isComplete }

    suspend fun save(s: CompanionSettings) {
        ctx.dataStore.edit {
            it[K_API] = s.apiUrl
            it[K_KIOSK] = s.kioskId
            it[K_SECRET] = s.rfSecret
        }
    }

    suspend fun clear() {
        ctx.dataStore.edit { it.clear() }
    }
}
