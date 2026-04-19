package com.caoscare.bridge

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    private lateinit var settings: Settings

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        settings = Settings(this)

        val urlEdit: EditText = findViewById(R.id.edit_url)
        val zoneEdit: EditText = findViewById(R.id.edit_zone)
        val tokenEdit: EditText = findViewById(R.id.edit_token)
        val status: TextView = findViewById(R.id.text_status)
        val startBtn: Button = findViewById(R.id.btn_start)
        val stopBtn: Button = findViewById(R.id.btn_stop)

        urlEdit.setText(settings.backendUrl)
        zoneEdit.setText(settings.zone)
        tokenEdit.setText(settings.deviceToken)

        startBtn.setOnClickListener {
            settings.backendUrl = urlEdit.text.toString()
            settings.zone = zoneEdit.text.toString()
            settings.deviceToken = tokenEdit.text.toString()
            startForegroundService(Intent(this, BridgeService::class.java))
            status.text = "Bridge running. See persistent notification for live status."
        }
        stopBtn.setOnClickListener {
            stopService(Intent(this, BridgeService::class.java))
            status.text = "Bridge stopped."
        }
    }
}
