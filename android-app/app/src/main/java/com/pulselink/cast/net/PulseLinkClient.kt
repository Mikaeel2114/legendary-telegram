package com.pulselink.cast.net

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.DataInputStream
import java.io.OutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetSocketAddress
import java.net.Socket

class PulseLinkClient(
    private val scope: CoroutineScope,
    private val onFrame: (Bitmap, Float, Int) -> Unit,
    private val onStatus: (String, Boolean) -> Unit
) {
    private var socket: Socket? = null
    private var outStream: OutputStream? = null
    private var streamJob: Job? = null

    fun connect(host: String, port: Int) {
        disconnect()
        streamJob = scope.launch(Dispatchers.IO) {
            try {
                withContext(Dispatchers.Main) {
                    onStatus("Connecting to $host:$port...", false)
                }
                val s = Socket()
                s.tcpNoDelay = true
                s.connect(InetSocketAddress(host, port), 4500)
                socket = s
                outStream = s.getOutputStream()
                val input = DataInputStream(s.getInputStream())

                val magic = ByteArray(4)
                var frames = 0
                var lastTick = System.currentTimeMillis()
                var measuredFps = 0f

                while (isActive && !s.isClosed) {
                    val tStart = System.currentTimeMillis()
                    input.readFully(magic)
                    val magicStr = String(magic, Charsets.US_ASCII)
                    if (magicStr != "PLNK") {
                        throw IllegalStateException("Invalid protocol header: $magicStr")
                    }
                    val frameType = input.readUnsignedByte()
                    val payloadLen = input.readInt()
                    if (payloadLen <= 0 || payloadLen > 15_000_000) continue

                    val payload = ByteArray(payloadLen)
                    input.readFully(payload)

                    if (frameType == 0x04) {
                        val resp = JSONObject(String(payload, Charsets.UTF_8))
                        val allowed = resp.optBoolean("allowed", false)
                        val pcName = resp.optString("host", host)
                        withContext(Dispatchers.Main) {
                            if (allowed) {
                                onStatus("Connected to $pcName", true)
                            } else {
                                onStatus("Access denied on Windows PC", false)
                            }
                        }
                        if (!allowed) break
                    } else if (frameType == 0x01) {
                        val bmp = BitmapFactory.decodeByteArray(payload, 0, payload.size)
                        if (bmp != null) {
                            frames++
                            val now = System.currentTimeMillis()
                            if (now - lastTick >= 1000L) {
                                measuredFps = (frames * 1000f) / (now - lastTick)
                                frames = 0
                                lastTick = now
                            }
                            val latencyMs = (System.currentTimeMillis() - tStart).toInt().coerceAtLeast(1)
                            withContext(Dispatchers.Main) {
                                onFrame(bmp, measuredFps, latencyMs)
                            }
                        }
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    onStatus("Disconnected: ${e.localizedMessage ?: "Connection closed"}", false)
                }
            } finally {
                disconnect()
            }
        }
    }

    fun sendCommand(json: JSONObject) {
        scope.launch(Dispatchers.IO) {
            try {
                val line = (json.toString() + "\n").toByteArray(Charsets.UTF_8)
                outStream?.write(line)
                outStream?.flush()
            } catch (_: Exception) {
            }
        }
    }

    fun discoverWindowsHostOnLan(onDiscovered: (String, Int, String) -> Unit, onTimeout: () -> Unit) {
        scope.launch(Dispatchers.IO) {
            var udp: DatagramSocket? = null
            try {
                udp = DatagramSocket(5960)
                udp.soTimeout = 3500
                val buf = ByteArray(1024)
                val pkt = DatagramPacket(buf, buf.size)
                udp.receive(pkt)
                val text = String(pkt.data, 0, pkt.length, Charsets.UTF_8)
                val obj = JSONObject(text)
                if (obj.optString("service") == "PulseLinkCast") {
                    val detectedIp = pkt.address.hostAddress ?: "192.168.1.100"
                    val port = obj.optInt("port", 5959)
                    val hostname = obj.optString("hostname", "Windows-PC")
                    withContext(Dispatchers.Main) {
                        onDiscovered(detectedIp, port, hostname)
                    }
                }
            } catch (_: Exception) {
                withContext(Dispatchers.Main) {
                    onTimeout()
                }
            } finally {
                udp?.close()
            }
        }
    }

    fun disconnect() {
        streamJob?.cancel()
        try {
            socket?.close()
        } catch (_: Exception) {
        }
        socket = null
        outStream = null
    }
}
