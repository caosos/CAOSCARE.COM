package care.caos.vision

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Matrix
import android.os.Bundle
import android.util.Log
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.*
import java.io.ByteArrayOutputStream
import java.util.concurrent.Executors

/**
 * CAOS Vision companion app.
 *
 * Streams a camera frame every FRAME_INTERVAL_MS to the CAOS Care backend
 * (/api/vision/describe). Plays back the returned TTS through the connected
 * earbuds so the resident hears an ongoing audio description of the world.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var previewView: PreviewView
    private lateinit var statusView: TextView
    private val cameraExecutor = Executors.newSingleThreadExecutor()
    private var latestBitmap: Bitmap? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private val uploader by lazy { VisionUploader(
        baseUrl = getString(R.string.caos_base_url),
        deviceToken = getString(R.string.caos_device_token),
    ) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        previewView = findViewById(R.id.preview_view)
        statusView  = findViewById(R.id.status_view)

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
            != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), 1001)
        } else {
            startCamera()
        }
    }

    private fun startCamera() {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            val provider = future.get()
            val preview = Preview.Builder().build().also {
                it.setSurfaceProvider(previewView.surfaceProvider)
            }
            val analyzer = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build().also { ia ->
                    ia.setAnalyzer(cameraExecutor) { img ->
                        latestBitmap = img.toBitmap()
                        img.close()
                    }
                }
            provider.unbindAll()
            provider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, preview, analyzer)
            startLoop()
        }, ContextCompat.getMainExecutor(this))
    }

    /** Every 4s, push the latest frame to CAOS and speak the reply. */
    private fun startLoop() = scope.launch {
        while (isActive) {
            delay(FRAME_INTERVAL_MS)
            val bmp = latestBitmap ?: continue
            runCatching {
                val bytes = ByteArrayOutputStream().apply {
                    bmp.compress(Bitmap.CompressFormat.JPEG, 75, this)
                }.toByteArray()
                val result = uploader.describe(bytes)
                withContext(Dispatchers.Main) {
                    statusView.text = result.reply
                }
                result.audioBase64?.let { AudioPlayback.playBase64Mp3(it) }
            }.onFailure { Log.w("CAOSVision", "describe failed", it) }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        cameraExecutor.shutdown()
        scope.cancel()
    }

    companion object { const val FRAME_INTERVAL_MS = 4000L }
}

/** Minimal ImageProxy→Bitmap helper. Production builds should use an optimized conversion. */
private fun ImageProxy.toBitmap(): Bitmap {
    val buffer = planes[0].buffer
    val bytes = ByteArray(buffer.remaining()).also(buffer::get)
    val bmp = android.graphics.BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
    val m = Matrix().apply { postRotate(imageInfo.rotationDegrees.toFloat()) }
    return Bitmap.createBitmap(bmp, 0, 0, bmp.width, bmp.height, m, true)
}
