package com.pulselink.cast

import android.content.ContentValues
import android.graphics.Bitmap
import android.os.Build
import android.os.Bundle
import android.provider.MediaStore
import android.view.View
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.animation.AnimationUtils
import android.widget.Button
import android.widget.EditText
import android.widget.HorizontalScrollView
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate
import androidx.lifecycle.lifecycleScope
import com.google.android.material.button.MaterialButton
import com.pulselink.cast.net.PulseLinkClient
import com.pulselink.cast.ui.ZoomableStreamView
import org.json.JSONArray
import org.json.JSONObject

class MainActivity : AppCompatActivity() {

    private lateinit var streamViewport: ZoomableStreamView
    private lateinit var connectCardScroll: ScrollView
    private lateinit var floatingToolsDock: HorizontalScrollView
    private lateinit var tvHudOverlay: TextView
    private lateinit var tvConnectionBadge: TextView
    private lateinit var etHostIp: EditText
    private lateinit var etPort: EditText

    private lateinit var client: PulseLinkClient
    private var isNightMode = true
    private var qualityPresetIndex = 1 // 0 = Ultra 60FPS, 1 = Balanced, 2 = Low-Latency Turbo
    private var activeMonitor = 1
    private var isFullscreen = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        streamViewport = findViewById(R.id.streamViewport)
        connectCardScroll = findViewById(R.id.connectCardScroll)
        floatingToolsDock = findViewById(R.id.floatingToolsDock)
        tvHudOverlay = findViewById(R.id.tvHudOverlay)
        tvConnectionBadge = findViewById(R.id.tvConnectionBadge)
        etHostIp = findViewById(R.id.etHostIp)
        etPort = findViewById(R.id.etPort)

        client = PulseLinkClient(
            scope = lifecycleScope,
            onFrame = { bmp, fps, latency ->
                streamViewport.updateFrame(bmp)
                tvHudOverlay.text = String.format(
                    "LIVE • %.1f FPS • ~%d ms • %dx%d",
                    fps, latency, bmp.width, bmp.height
                )
            },
            onStatus = { statusText, isLive ->
                tvConnectionBadge.text = statusText
                if (isLive) {
                    connectCardScroll.visibility = View.GONE
                    streamViewport.visibility = View.VISIBLE
                    floatingToolsDock.visibility = View.VISIBLE
                    tvHudOverlay.visibility = View.VISIBLE
                } else {
                    connectCardScroll.visibility = View.VISIBLE
                    streamViewport.visibility = View.GONE
                    floatingToolsDock.visibility = View.GONE
                    tvHudOverlay.visibility = View.GONE
                }
            }
        )

        setupAnimatedButtons()
        setupViewportTouchForwarding()
    }

    private fun attachPulseAnimation(view: View, action: () -> Unit) {
        val anim = AnimationUtils.loadAnimation(this, R.anim.btn_pulse_press)
        view.setOnClickListener {
            it.startAnimation(anim)
            action()
        }
    }

    private fun setupAnimatedButtons() {
        val btnToggleTheme = findViewById<MaterialButton>(R.id.btnToggleTheme)
        val btnScanLan = findViewById<Button>(R.id.btnScanLan)
        val btnLocalhostPreset = findViewById<Button>(R.id.btnLocalhostPreset)
        val btnStartConnect = findViewById<Button>(R.id.btnStartConnect)

        val toolQualityPreset = findViewById<MaterialButton>(R.id.toolQualityPreset)
        val toolTouchMode = findViewById<MaterialButton>(R.id.toolTouchMode)
        val toolKeyboard = findViewById<MaterialButton>(R.id.toolKeyboard)
        val toolSwitchMonitor = findViewById<MaterialButton>(R.id.toolSwitchMonitor)
        val toolSnapshot = findViewById<MaterialButton>(R.id.toolSnapshot)
        val toolFullscreen = findViewById<MaterialButton>(R.id.toolFullscreen)
        val toolDisconnect = findViewById<MaterialButton>(R.id.toolDisconnect)

        // 1. Animated Night/Dark & Day Theme Switcher
        attachPulseAnimation(btnToggleTheme) {
            isNightMode = !isNightMode
            AppCompatDelegate.setDefaultNightMode(
                if (isNightMode) AppCompatDelegate.MODE_NIGHT_YES
                else AppCompatDelegate.MODE_NIGHT_NO
            )
        }

        // 2. Auto-Scan Wi-Fi / Modem LAN Broadcast
        attachPulseAnimation(btnScanLan) {
            tvConnectionBadge.text = "Scanning Modem / Wi-Fi LAN (UDP 5960)..."
            client.discoverWindowsHostOnLan(
                onDiscovered = { ip, port, host ->
                    etHostIp.setText(ip)
                    etPort.setText(port.toString())
                    tvConnectionBadge.text = "Found $host at $ip:$port"
                    Toast.makeText(this, "Discovered $host ($ip)", Toast.LENGTH_SHORT).show()
                },
                onTimeout = {
                    tvConnectionBadge.text = "No broadcast found — enter Windows IP manually"
                }
            )
        }

        // 3. One-Tap Localhost (127.0.0.1) Preset for USB / ADB Reverse Tunnel
        attachPulseAnimation(btnLocalhostPreset) {
            etHostIp.setText("127.0.0.1")
            etPort.setText("5959")
            Toast.makeText(this, "Localhost 127.0.0.1:5959 selected", Toast.LENGTH_SHORT).show()
        }

        // 4. Start Live Screen Stream
        attachPulseAnimation(btnStartConnect) {
            val host = etHostIp.text.toString().trim().ifEmpty { "127.0.0.1" }
            val port = etPort.text.toString().toIntOrNull() ?: 5959
            client.connect(host, port)
        }

        // 5. Pro Tool: Adaptive Quality & FPS Optimizer
        attachPulseAnimation(toolQualityPreset) {
            qualityPresetIndex = (qualityPresetIndex + 1) % 3
            val cmd = JSONObject().put("cmd", "set_quality")
            when (qualityPresetIndex) {
                0 -> {
                    cmd.put("fps", 60).put("quality", 90).put("scale", 100)
                    toolQualityPreset.text = "⚡ Mode: Ultra 60FPS"
                }
                1 -> {
                    cmd.put("fps", 30).put("quality", 75).put("scale", 85)
                    toolQualityPreset.text = "⚡ Mode: Balanced"
                }
                else -> {
                    cmd.put("fps", 45).put("quality", 55).put("scale", 65)
                    toolQualityPreset.text = "⚡ Mode: Low-Latency Turbo"
                }
            }
            client.sendCommand(cmd)
        }

        // 6. Pro Tool: Direct Touch vs Precision Trackpad Cursor Mode
        attachPulseAnimation(toolTouchMode) {
            streamViewport.trackpadMode = !streamViewport.trackpadMode
            toolTouchMode.text = if (streamViewport.trackpadMode) "🖱️ Trackpad Mode" else "🖱️ Direct Touch"
        }

        // 7. Pro Tool: Windows Shortcut & Special Key Deck
        attachPulseAnimation(toolKeyboard) {
            showWindowsShortcutDeckDialog()
        }

        // 8. Pro Tool: Multi-Monitor Display Switcher
        attachPulseAnimation(toolSwitchMonitor) {
            activeMonitor = if (activeMonitor == 1) 2 else 1
            toolSwitchMonitor.text = "🖥️ Display #$activeMonitor"
            client.sendCommand(JSONObject().put("cmd", "switch_monitor").put("monitor", activeMonitor))
        }

        // 9. Pro Tool: Instant HD Frame Snapshot to Phone Gallery
        attachPulseAnimation(toolSnapshot) {
            val bmp = streamViewport.getCurrentBitmap()
            if (bmp != null) {
                saveSnapshotToGallery(bmp)
            } else {
                Toast.makeText(this, "No active stream frame to capture", Toast.LENGTH_SHORT).show()
            }
        }

        // 10. Pro Tool: Immersive Fullscreen & Zoom Reset
        attachPulseAnimation(toolFullscreen) {
            isFullscreen = !isFullscreen
            streamViewport.resetZoom()
            toggleImmersiveMode(isFullscreen)
        }

        // 11. Disconnect Button
        attachPulseAnimation(toolDisconnect) {
            client.disconnect()
            connectCardScroll.visibility = View.VISIBLE
            streamViewport.visibility = View.GONE
            floatingToolsDock.visibility = View.GONE
            tvHudOverlay.visibility = View.GONE
        }
    }

    private fun setupViewportTouchForwarding() {
        streamViewport.onNormalizedTap = { nx, ny, isRightClick ->
            val cmdName = if (isRightClick) "touch_right_click" else "touch_tap"
            client.sendCommand(
                JSONObject()
                    .put("cmd", cmdName)
                    .put("x", nx)
                    .put("y", ny)
            )
        }
        streamViewport.onNormalizedMove = { nx, ny ->
            client.sendCommand(
                JSONObject()
                    .put("cmd", "touch_move")
                    .put("x", nx)
                    .put("y", ny)
            )
        }
    }

    private fun showWindowsShortcutDeckDialog() {
        val labels = arrayOf(
            "🪟 Windows Key (Start Menu)",
            "🔀 Alt + Tab (Switch App)",
            "📋 Ctrl + C (Copy)",
            "📌 Ctrl + V (Paste)",
            "⏪ Ctrl + Z (Undo)",
            "🖥️ Win + D (Show Desktop)",
            "🔒 Esc Key",
            "🛠️ Ctrl + Shift + Esc (Task Manager)"
        )
        AlertDialog.Builder(this)
            .setTitle("Send Windows Shortcut")
            .setItems(labels) { _, which ->
                val payload = JSONObject()
                when (which) {
                    0 -> payload.put("cmd", "key_press").put("key", "win")
                    1 -> payload.put("cmd", "hotkey").put("keys", JSONArray(listOf("alt", "tab")))
                    2 -> payload.put("cmd", "hotkey").put("keys", JSONArray(listOf("ctrl", "c")))
                    3 -> payload.put("cmd", "hotkey").put("keys", JSONArray(listOf("ctrl", "v")))
                    4 -> payload.put("cmd", "hotkey").put("keys", JSONArray(listOf("ctrl", "z")))
                    5 -> payload.put("cmd", "hotkey").put("keys", JSONArray(listOf("win", "d")))
                    6 -> payload.put("cmd", "key_press").put("key", "esc")
                    7 -> payload.put("cmd", "hotkey").put("keys", JSONArray(listOf("ctrl", "shift", "esc")))
                }
                client.sendCommand(payload)
            }
            .show()
    }

    private fun saveSnapshotToGallery(bitmap: Bitmap) {
        val filename = "PulseLink_${System.currentTimeMillis()}.jpg"
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, filename)
            put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg")
        }
        val uri = contentResolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
        if (uri != null) {
            contentResolver.openOutputStream(uri)?.use { out ->
                bitmap.compress(Bitmap.CompressFormat.JPEG, 95, out)
            }
            Toast.makeText(this, "Saved snapshot: $filename", Toast.LENGTH_SHORT).show()
        }
    }

    private fun toggleImmersiveMode(enable: Boolean) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val controller = window.insetsController ?: return
            if (enable) {
                controller.hide(WindowInsets.Type.systemBars())
                controller.systemBarsBehavior = WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            } else {
                controller.show(WindowInsets.Type.systemBars())
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        client.disconnect()
    }
}
