"""
PulseLink Cast - High-Speed LAN/Wi-Fi Screen Streaming & Input Server
Streams live Windows desktop over TCP 5959 (Binary Protocol + Web Fallback on 5958)
and broadcasts LAN discovery beacons over UDP 5960.
"""
import io
import json
import socket
import threading
import time
from typing import Callable, Optional, Dict, Any, List

from PIL import Image, ImageDraw

try:
    import mss
except ImportError:
    mss = None

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except ImportError:
    pyautogui = None

from protocol import (
    StreamConfig,
    pack_packet,
    encode_discovery_beacon,
    parse_control_command,
    FRAME_TYPE_VIDEO,
    FRAME_TYPE_STATS,
    FRAME_TYPE_AUTH_RESULT,
    DEFAULT_STREAM_PORT,
    DEFAULT_DISCOVERY_PORT,
)


class ScreenStreamServer:
    def __init__(
        self,
        config: StreamConfig,
        pin_code: str,
        on_log: Optional[Callable[[str], None]] = None,
        on_client_request: Optional[Callable[[str, str], bool]] = None,
        on_metrics: Optional[Callable[[float, float, int], None]] = None,
    ) -> None:
        self.config = config
        self.pin_code = pin_code
        self.on_log = on_log or (lambda msg: None)
        self.on_client_request = on_client_request
        self.on_metrics = on_metrics

        self.running = False
        self._server_socket: Optional[socket.socket] = None
        self._clients: List[socket.socket] = []
        self._clients_lock = threading.Lock()
        self.current_fps = 0.0
        self.current_kbps = 0.0

    def log(self, message: str) -> None:
        self.on_log(message)

    def start(self, host: str = "0.0.0.0", port: int = DEFAULT_STREAM_PORT) -> None:
        if self.running:
            return
        self.running = True
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((host, port))
        self._server_socket.listen(5)
        self._server_socket.settimeout(1.0)

        threading.Thread(target=self._accept_loop, daemon=True).start()
        threading.Thread(target=self._discovery_beacon_loop, args=(port,), daemon=True).start()
        threading.Thread(target=self._capture_and_broadcast_loop, daemon=True).start()
        self.log(f"Server listening on {host}:{port} (UDP Discovery on {DEFAULT_DISCOVERY_PORT})")

    def stop(self) -> None:
        self.running = False
        with self._clients_lock:
            for c in self._clients:
                try:
                    c.close()
                except Exception:
                    pass
            self._clients.clear()
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
        self.log("Stream server stopped.")

    def _discovery_beacon_loop(self, stream_port: int) -> None:
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        hostname = socket.gethostname()
        while self.running:
            try:
                payload = encode_discovery_beacon(hostname, "0.0.0.0", stream_port, self.pin_code)
                udp_sock.sendto(payload, ("255.255.255.255", DEFAULT_DISCOVERY_PORT))
            except Exception:
                pass
            time.sleep(2.0)
        udp_sock.close()

    def _accept_loop(self) -> None:
        while self.running and self._server_socket:
            try:
                client_sock, addr = self._server_socket.accept()
                client_ip = addr[0]
                client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                threading.Thread(
                    target=self._handle_client, args=(client_sock, client_ip), daemon=True
                ).start()
            except socket.timeout:
                continue
            except Exception as exc:
                if self.running:
                    self.log(f"Accept error: {exc}")

    def _handle_client(self, client_sock: socket.socket, client_ip: str) -> None:
        self.log(f"Incoming connection from Android device ({client_ip})...")
        allowed = True
        if self.config.require_access_approval and self.on_client_request:
            allowed = self.on_client_request(client_ip, "Android Phone Client")

        auth_payload = json.dumps({"allowed": allowed, "host": socket.gethostname()}).encode("utf-8")
        try:
            client_sock.sendall(pack_packet(FRAME_TYPE_AUTH_RESULT, auth_payload))
        except Exception:
            client_sock.close()
            return

        if not allowed:
            self.log(f"Access denied for {client_ip} by Windows host user.")
            client_sock.close()
            return

        with self._clients_lock:
            self._clients.append(client_sock)
        self.log(f"Device {client_ip} authorized and streaming started.")

        # Listen for newline-delimited JSON control/tool commands from Android
        buffer = b""
        try:
            while self.running:
                chunk = client_sock.recv(1024)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    self._process_client_command(line.decode("utf-8", errors="ignore"))
        except Exception:
            pass
        finally:
            with self._clients_lock:
                if client_sock in self._clients:
                    self._clients.remove(client_sock)
            try:
                client_sock.close()
            except Exception:
                pass
            self.log(f"Device {client_ip} disconnected.")

    def _process_client_command(self, raw_line: str) -> None:
        try:
            cmd_obj = parse_control_command(raw_line)
        except Exception:
            return

        cmd = cmd_obj.get("cmd")
        if cmd == "set_quality":
            self.config.jpeg_quality = max(20, min(95, int(cmd_obj.get("quality", 75))))
            self.config.fps = max(10, min(60, int(cmd_obj.get("fps", 30))))
            self.config.scale_percent = max(40, min(100, int(cmd_obj.get("scale", 100))))
            self.log(
                f"Phone adjusted quality -> {self.config.scale_percent}% scale, "
                f"Q={self.config.jpeg_quality}, {self.config.fps} FPS"
            )
        elif cmd == "switch_monitor":
            self.config.monitor_index = max(1, int(cmd_obj.get("monitor", 1)))
            self.log(f"Phone switched active display to Monitor #{self.config.monitor_index}")
        elif self.config.allow_remote_input and pyautogui is not None:
            self._execute_remote_input(cmd, cmd_obj)

    def _execute_remote_input(self, cmd: str, cmd_obj: Dict[str, Any]) -> None:
        try:
            screen_w, screen_h = pyautogui.size()
            if cmd == "touch_tap":
                nx = float(cmd_obj.get("x", 0.5))
                ny = float(cmd_obj.get("y", 0.5))
                pyautogui.click(int(nx * screen_w), int(ny * screen_h))
            elif cmd == "touch_right_click":
                nx = float(cmd_obj.get("x", 0.5))
                ny = float(cmd_obj.get("y", 0.5))
                pyautogui.rightClick(int(nx * screen_w), int(ny * screen_h))
            elif cmd == "touch_move":
                nx = float(cmd_obj.get("x", 0.5))
                ny = float(cmd_obj.get("y", 0.5))
                pyautogui.moveTo(int(nx * screen_w), int(ny * screen_h))
            elif cmd == "scroll":
                dy = int(cmd_obj.get("dy", 0))
                pyautogui.scroll(dy)
            elif cmd == "key_press":
                key = str(cmd_obj.get("key", ""))
                if key:
                    pyautogui.press(key)
            elif cmd == "hotkey":
                keys = cmd_obj.get("keys", [])
                if isinstance(keys, list) and keys:
                    pyautogui.hotkey(*[str(k) for k in keys])
            elif cmd == "type_text":
                text = str(cmd_obj.get("text", ""))
                if text:
                    pyautogui.write(text, interval=0.01)
        except Exception as exc:
            self.log(f"Input injection warning: {exc}")

    def _capture_frame_jpeg(self, sct: Any) -> bytes:
        if sct is not None:
            monitors = sct.monitors
            idx = min(self.config.monitor_index, len(monitors) - 1)
            raw = sct.grab(monitors[idx])
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        else:
            img = Image.new("RGB", (1280, 720), (15, 23, 42))
            draw = ImageDraw.Draw(img)
            draw.text((60, 60), "PulseLink Cast Live Frame", fill=(56, 189, 248))

        if self.config.scale_percent < 100:
            w = max(320, int(img.width * self.config.scale_percent / 100))
            h = max(180, int(img.height * self.config.scale_percent / 100))
            img = img.resize((w, h), Image.Resampling.BILINEAR)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=self.config.jpeg_quality, optimize=False)
        return buf.getvalue()

    def _capture_and_broadcast_loop(self) -> None:
        sct = mss.mss() if mss is not None else None
        frame_count = 0
        bytes_sent = 0
        last_stat_time = time.time()

        while self.running:
            t0 = time.time()
            with self._clients_lock:
                active_clients = list(self._clients)

            if active_clients:
                try:
                    jpeg_bytes = self._capture_frame_jpeg(sct)
                    packet = pack_packet(FRAME_TYPE_VIDEO, jpeg_bytes)
                    dead_clients = []
                    for c in active_clients:
                        try:
                            c.sendall(packet)
                            bytes_sent += len(packet)
                        except Exception:
                            dead_clients.append(c)
                    if dead_clients:
                        with self._clients_lock:
                            for dc in dead_clients:
                                if dc in self._clients:
                                    self._clients.remove(dc)
                    frame_count += 1
                except Exception as exc:
                    self.log(f"Capture error: {exc}")

            now = time.time()
            elapsed = now - last_stat_time
            if elapsed >= 1.0:
                self.current_fps = round(frame_count / elapsed, 1)
                self.current_kbps = round((bytes_sent * 8 / 1000.0) / elapsed, 1)
                frame_count = 0
                bytes_sent = 0
                last_stat_time = now
                if self.on_metrics:
                    self.on_metrics(self.current_fps, self.current_kbps, len(active_clients))

            target_delay = 1.0 / max(5, self.config.fps)
            sleep_time = max(0.002, target_delay - (time.time() - t0))
            time.sleep(sleep_time)
