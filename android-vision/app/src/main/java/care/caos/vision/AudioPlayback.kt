package care.caos.vision

import android.media.AudioAttributes
import android.media.MediaDataSource
import android.media.MediaPlayer
import android.util.Base64

/** Plays a base64-encoded MP3 clip through the connected audio output (earbuds, etc). */
object AudioPlayback {
    fun playBase64Mp3(b64: String) {
        val mp3 = Base64.decode(b64, Base64.DEFAULT)
        val mp = MediaPlayer()
        mp.setAudioAttributes(
            AudioAttributes.Builder()
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
                .build()
        )
        mp.setDataSource(object : MediaDataSource() {
            override fun readAt(position: Long, buffer: ByteArray?, offset: Int, size: Int): Int {
                if (position >= mp3.size) return -1
                val remaining = (mp3.size - position).toInt()
                val toRead = minOf(remaining, size)
                System.arraycopy(mp3, position.toInt(), buffer!!, offset, toRead)
                return toRead
            }
            override fun getSize(): Long = mp3.size.toLong()
            override fun close() {}
        })
        mp.setOnCompletionListener { it.release() }
        mp.prepare()
        mp.start()
    }
}
