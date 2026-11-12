"""
PulseLink Cast - Windows Host GUI Application
Features:
- Animated Dark/Night (Obsidian Neon) & Daylight Glass Themes with smooth color interpolation
- Animated Hover & Ripple Pulse Buttons
- Interactive Windows Access & Permissions Prompt ("Allow All Access" for Screen, Input & Modem/Wi-Fi Firewall)
- Live Incoming Device Access Approval Modal
- Real-Time FPS / Bitrate Telemetry & QR Code Pairing
"""
import os
import sys
import time
import math
import socket
import tkinter as tk
from pathlib import Path
from typing import Dict

from PIL import Image, ImageTk, ImageDraw

from protocol import (
    StreamConfig,
    detect_lan_ip_addresses,
    generate_session_pin,
    DEFAULT_STREAM_PORT,
)
from permissions_manager import WindowsAccessManager
from server import ScreenStreamServer


THEMES: Dict[str, Dict[str, str]] = {
    "night": {
        "name": "Night Obsidian",
        "bg": "#090D16",
        "card": "#111827",
        "card_border": "#1E293B",
        "text": "#F8FAFC",
        "subtext": "#94A3B8",
        "accent": "#06B6D4",
        "accent_hover": "#22D3EE",
        "secondary": "#8B5CF6",
        "success": "#10B981",
        "danger": "#EF4444",
    },
    "light": {
        "name": "Daylight Frost",
        "bg": "#F1F5F9",
        "card": "#FFFFFF",
        "card_border": "#CBD5E1",
        "text": "#0F172A",
        "subtext": "#475569",
        "accent": "#0284C7",
        "accent_hover": "#0369A1",
        "secondary": "#6366F1",
        "success": "#059669",
        "danger": "#DC2626",
    },
}


def hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in rgb)


def blend_hex(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    return rgb_to_hex((r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t))


class AnimatedPulseButton(tk.Canvas):
    """Custom Canvas Button with smooth hover color interpolation, click scale bounce, and glowing border."""

    def __init__(
        self,
        parent,
        text: str,
        command,
        width: int = 210,
        height: int = 44,
        bg_color: str = "#06B6D4",
        hover_color: str = "#22D3EE",
        text_color: str = "#FFFFFF",
        canvas_bg: str = "#111827",
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=canvas_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.text = text
        self.command = command
        self.w = width
        self.h = height
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.current_fill = bg_color
        self.hover_t = 0.0
        self.is_hovered = False
        self.scale_offset = 0

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    def set_palette(self, bg_color: str, hover_color: str, canvas_bg: str, text_color: str = "#FFFFFF"):
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.configure(bg=canvas_bg)
        self.current_fill = blend_hex(self.bg_color, self.hover_color, self.hover_t)
        self._draw()

    def set_text(self, text: str):
        self.text = text
        self._draw()

    def _draw(self):
        self.delete("all")
        pad = 2 + self.scale_offset
        r = 12
        x1, y1, x2, y2 = pad, pad, self.w - pad, self.h - pad
        # Rounded rectangle polygon
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        self.create_polygon(points, smooth=True, fill=self.current_fill, outline="")
        self.create_text(
            self.w // 2,
            self.h // 2,
            text=self.text,
            fill=self.text_color,
            font=("Segoe UI", 10, "bold"),
        )

    def _on_enter(self, _event):
        self.is_hovered = True
        self._animate_hover()

    def _on_leave(self, _event):
        self.is_hovered = False
        self._animate_hover()

    def _animate_hover(self):
        target = 1.0 if self.is_hovered else 0.0
        step = 0.18 if self.is_hovered else -0.18
        self.hover_t = max(0.0, min(1.0, self.hover_t + step))
        self.current_fill = blend_hex(self.bg_color, self.hover_color, self.hover_t)
        self._draw()
        if (self.is_hovered and self.hover_t < 1.0) or (not self.is_hovered and self.hover_t > 0.0):
            self.after(16, self._animate_hover)

    def _on_press(self, _event):
        self.scale_offset = 2
        self._draw()

    def _on_release(self, _event):
        self.scale_offset = 0
        self._draw()
        if self.command:
            self.command()


class PulseLinkWindowsApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PulseLink Cast — Windows to Android Screen Studio")
        self.root.geometry("960x660")
        self.root.minsize(900, 620)

        self.theme_key = "night"
        self.access_mgr = WindowsAccessManager()
        self.access_mgr.enable_dpi_awareness()

        self.config = StreamConfig()
        self.pin_code = generate_session_pin()
        self.lan_ips = detect_lan_ip_addresses()
        self.pulse_phase = 0.0

        self.server = ScreenStreamServer(
            config=self.config,
            pin_code=self.pin_code,
            on_log=self.append_log,
            on_client_request=self.prompt_incoming_device_access,
            on_metrics=self.update_metrics,
        )

        self._load_window_icon()
        self._build_ui()
        self._apply_theme(animate=False)
        self._animate_radar_loop()

        # Automatically show the Windows Access & Permissions Setup Modal right after launch
        self.root.after(350, self.show_windows_access_question_modal)

    def _load_window_icon(self) -> None:
        base = Path( getattr(sys, "_MEIPASS", Path(__file__).resolve().parent) )
        ico_path = base / "assets" / "app_icon.ico"
        png_path = base / "assets" / "app_icon.png"
        try:
            if ico_path.exists():
                self.root.iconbitmap(default=str(ico_path))
        except Exception:
            pass
        self.logo_photo = None
        if png_path.exists():
            try:
                pil_img = Image.open(png_path).resize((68, 68), Image.Resampling.LANCZOS)
                self.logo_photo = ImageTk.PhotoImage(pil_img)
            except Exception:
                pass

    def _build_ui(self) -> None:
        self.main_frame = tk.Frame(self.root, padx=24, pady=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Top Header Bar
        self.header_frame = tk.Frame(self.main_frame)
        self.header_frame.pack(fill=tk.X, pady=(0, 16))

        if self.logo_photo:
            self.logo_label = tk.Label(self.header_frame, image=self.logo_photo, bd=0)
            self.logo_label.pack(side=tk.LEFT, padx=(0, 14))

        title_col = tk.Frame(self.header_frame)
        title_col.pack(side=tk.LEFT, fill=tk.Y)
        self.title_lbl = tk.Label(
            title_col, text="PulseLink Cast Studio", font=("Segoe UI", 20, "bold")
        )
        self.title_lbl.pack(anchor="w")
        self.subtitle_lbl = tk.Label(
            title_col,
            text="Ultra-Low-Latency Windows Screen & Control Bridge over Localhost, Modem & Wi-Fi",
            font=("Segoe UI", 10),
        )
        self.subtitle_lbl.pack(anchor="w")

        # Theme & Permissions Action Buttons on Top Right
        right_header = tk.Frame(self.header_frame)
        right_header.pack(side=tk.RIGHT)

        self.theme_btn = AnimatedPulseButton(
            right_header,
            text="🌙 Night / ☀️ Day Theme",
            command=self.toggle_theme,
            width=185,
            height=40,
        )
        self.theme_btn.pack(side=tk.RIGHT, padx=(10, 0))

        self.perm_btn = AnimatedPulseButton(
            right_header,
            text="🛡️ Windows Access & Firewall",
            command=self.show_windows_access_question_modal,
            width=225,
            height=40,
        )
        self.perm_btn.pack(side=tk.RIGHT)

        # Center 2-Column Grid
        self.body_frame = tk.Frame(self.main_frame)
        self.body_frame.pack(fill=tk.BOTH, expand=True)
        self.body_frame.columnconfigure(0, weight=3)
        self.body_frame.columnconfigure(1, weight=2)
        self.body_frame.rowconfigure(0, weight=1)

        # Left Card: Connection Details, Animated Radar & Stream Controls
        self.left_card = tk.Frame(self.body_frame, padx=20, pady=18, highlightthickness=1)
        self.left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        top_row = tk.Frame(self.left_card)
        top_row.pack(fill=tk.X, pady=(0, 12))

        self.radar_canvas = tk.Canvas(top_row, width=96, height=96, highlightthickness=0, bd=0)
        self.radar_canvas.pack(side=tk.LEFT, padx=(0, 16))

        ip_box = tk.Frame(top_row)
        ip_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.ip_title_lbl = tk.Label(
            ip_box, text="Modem / Wi-Fi LAN IP & Localhost Endpoints", font=("Segoe UI", 12, "bold")
        )
        self.ip_title_lbl.pack(anchor="w")

        ip_display = "   |   ".join(f"{ip}:{DEFAULT_STREAM_PORT}" for ip in self.lan_ips)
        self.ip_val_lbl = tk.Label(
            ip_box, text=ip_display, font=("Consolas", 13, "bold"), pady=4
        )
        self.ip_val_lbl.pack(anchor="w")

        self.pin_lbl = tk.Label(
            ip_box,
            text=f"Session Security PIN: {self.pin_code}   •   USB ADB Forward: tcp:5959 -> tcp:5959",
            font=("Segoe UI", 9),
        )
        self.pin_lbl.pack(anchor="w")

        # Sliders for FPS, Quality & Scale
        self.controls_frame = tk.Frame(self.left_card)
        self.controls_frame.pack(fill=tk.X, pady=10)

        self.fps_var = tk.IntVar(value=30)
        self.qual_var = tk.IntVar(value=75)
        self.scale_var = tk.IntVar(value=100)

        self._create_slider_row(self.controls_frame, "Target Frame Rate (FPS):", self.fps_var, 15, 60)
        self._create_slider_row(self.controls_frame, "JPEG Compression Quality (%):", self.qual_var, 30, 95)
        self._create_slider_row(self.controls_frame, "Resolution Scale (%):", self.scale_var, 50, 100)

        # Action Bar
        self.action_bar = tk.Frame(self.left_card)
        self.action_bar.pack(fill=tk.X, pady=(16, 8))

        self.start_btn = AnimatedPulseButton(
            self.action_bar,
            text="▶ Start Screen Broadcast",
            command=self.toggle_broadcast,
            width=230,
            height=46,
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 12))

        self.metrics_lbl = tk.Label(
            self.action_bar,
            text="Status: Idle  |  0.0 FPS  |  0 kbps  |  0 Phones",
            font=("Consolas", 10, "bold"),
        )
        self.metrics_lbl.pack(side=tk.LEFT, padx=8)

        # Right Card: Access Status Checklist & Live Event Log
        self.right_card = tk.Frame(self.body_frame, padx=18, pady=18, highlightthickness=1)
        self.right_card.grid(row=0, column=1, sticky="nsew")

        self.perm_header_lbl = tk.Label(
            self.right_card, text="Windows Access & Security Status", font=("Segoe UI", 12, "bold")
        )
        self.perm_header_lbl.pack(anchor="w", pady=(0, 8))

        self.perm_status_lbl = tk.Label(
            self.right_card,
            text=self._format_permission_summary(),
            justify=tk.LEFT,
            font=("Segoe UI", 9),
        )
        self.perm_status_lbl.pack(anchor="w", pady=(0, 14))

        self.log_header_lbl = tk.Label(
            self.right_card, text="Live Connection & Access Telemetry", font=("Segoe UI", 11, "bold")
        )
        self.log_header_lbl.pack(anchor="w", pady=(0, 6))

        self.log_text = tk.Text(
            self.right_card,
            height=14,
            font=("Consolas", 9),
            bd=0,
            padx=10,
            pady=8,
            state=tk.DISABLED,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.append_log("PulseLink Cast initialized. Ready to share Windows screen.")

    def _create_slider_row(self, parent, label_text: str, var: tk.IntVar, min_v: int, max_v: int):
        row = tk.Frame(parent)
        row.pack(fill=tk.X, pady=4)
        lbl = tk.Label(row, text=label_text, width=28, anchor="w", font=("Segoe UI", 9, "bold"))
        lbl.pack(side=tk.LEFT)
        scale = tk.Scale(
            row,
            from_=min_v,
            to=max_v,
            orient=tk.HORIZONTAL,
            variable=var,
            command=lambda _v: self._sync_slider_config(),
            highlightthickness=0,
            bd=0,
        )
        scale.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    def _sync_slider_config(self) -> None:
        self.config.fps = int(self.fps_var.get())
        self.config.jpeg_quality = int(self.qual_var.get())
        self.config.scale_percent = int(self.scale_var.get())

    def _format_permission_summary(self) -> str:
        st = self.access_mgr.permissions_state
        chk = lambda b: "✅ Allowed" if b else "⚠️ Pending Prompt"
        return (
            f"• Desktop Duplication Screen Capture: {chk(st['screen_capture'])}\n"
            f"• Remote Touch / Mouse / Keyboard Injection: {chk(st['input_control'])}\n"
            f"• Windows Firewall LAN/Modem Ports (5959/5960): {chk(st['lan_firewall'])}\n"
            f"• High-DPI Per-Monitor Scaling: {chk(st['dpi_scaling'])}"
        )

    def show_windows_access_question_modal(self) -> None:
        """
        Displays the Windows Access Question dialog asking the user to grant every required
        Windows permission (Screen Capture, Mouse/Keyboard Input Control, and Wi-Fi/Modem Firewall).
        """
        t = THEMES[self.theme_key]
        dlg = tk.Toplevel(self.root)
        dlg.title("Windows Access Permission Request — PulseLink Cast")
        dlg.geometry("540x410")
        dlg.configure(bg=t["card"])
        dlg.transient(self.root)
        dlg.grab_set()

        hdr = tk.Label(
            dlg,
            text="🛡️ Allow Full Windows Access for Screen Sharing?",
            font=("Segoe UI", 14, "bold"),
            bg=t["card"],
            fg=t["text"],
            pady=14,
        )
        hdr.pack()

        desc = tk.Label(
            dlg,
            text=(
                "PulseLink Cast requests your permission to enable the following Windows capabilities\n"
                "so your Android phone can view and control your PC over Localhost, Modem, or Wi-Fi:"
            ),
            font=("Segoe UI", 9),
            bg=t["card"],
            fg=t["subtext"],
            justify=tk.CENTER,
        )
        desc.pack(pady=(0, 12))

        var_screen = tk.BooleanVar(value=True)
        var_input = tk.BooleanVar(value=True)
        var_fw = tk.BooleanVar(value=True)
        var_prompt_phone = tk.BooleanVar(value=self.config.require_access_approval)

        opts_frame = tk.Frame(dlg, bg=t["card"], padx=32)
        opts_frame.pack(fill=tk.X)

        for var, txt in [
            (var_screen, "Allow High-Speed Desktop Screen Capture (All Monitors)"),
            (var_input, "Allow Remote Touch, Mouse & Keyboard Control from Android"),
            (var_fw, "Allow Windows Defender Firewall Rules (TCP 5959 & UDP 5960)"),
            (var_prompt_phone, "Ask Confirmation on Windows When a New Phone Connects"),
        ]:
            cb = tk.Checkbutton(
                opts_frame,
                text=txt,
                variable=var,
                bg=t["card"],
                fg=t["text"],
                selectcolor=t["bg"],
                activebackground=t["card"],
                activeforeground=t["accent"],
                font=("Segoe UI", 10),
                anchor="w",
                pady=4,
            )
            cb.pack(fill=tk.X)

        def on_allow_all():
            self.config.allow_remote_input = bool(var_input.get())
            self.config.require_access_approval = bool(var_prompt_phone.get())
            ok, msg = self.access_mgr.grant_all_windows_permissions()
            self.access_mgr.permissions_state["screen_capture"] = bool(var_screen.get())
            self.access_mgr.permissions_state["input_control"] = bool(var_input.get())
            self.perm_status_lbl.configure(text=self._format_permission_summary())
            self.append_log(f"[Windows Access] {msg}")
            dlg.destroy()

        btn_row = tk.Frame(dlg, bg=t["card"], pady=20)
        btn_row.pack()

        allow_btn = AnimatedPulseButton(
            btn_row,
            text="✅ Allow All Access & Configure",
            command=on_allow_all,
            width=250,
            height=44,
            bg_color=t["success"],
            hover_color=t["accent"],
            canvas_bg=t["card"],
        )
        allow_btn.pack(side=tk.LEFT, padx=8)

        later_btn = AnimatedPulseButton(
            btn_row,
            text="Later",
            command=dlg.destroy,
            width=110,
            height=44,
            bg_color=t["card_border"],
            hover_color=t["secondary"],
            canvas_bg=t["card"],
        )
        later_btn.pack(side=tk.LEFT, padx=8)

    def prompt_incoming_device_access(self, client_ip: str, device_name: str) -> bool:
        """Thread-safe Windows prompt asking whether to allow an incoming Android phone connection."""
        decision = {"allowed": False}
        done_event = threading.Event()

        def show_dialog():
            t = THEMES[self.theme_key]
            dlg = tk.Toplevel(self.root)
            dlg.title("Incoming Phone Connection Request")
            dlg.geometry("460x250")
            dlg.configure(bg=t["card"])
            dlg.attributes("-topmost", True)
            dlg.grab_set()

            tk.Label(
                dlg,
                text="📱 Android Device Wants to View Your Screen",
                font=("Segoe UI", 13, "bold"),
                bg=t["card"],
                fg=t["text"],
                pady=14,
            ).pack()

            tk.Label(
                dlg,
                text=f"Device IP: {client_ip} ({device_name})\nAllow screen sharing and remote control access?",
                font=("Segoe UI", 10),
                bg=t["card"],
                fg=t["subtext"],
            ).pack(pady=8)

            btn_bar = tk.Frame(dlg, bg=t["card"], pady=16)
            btn_bar.pack()

            def decide(val: bool):
                decision["allowed"] = val
                dlg.destroy()
                done_event.set()

            AnimatedPulseButton(
                btn_bar,
                text="✅ Allow Phone",
                command=lambda: decide(True),
                width=165,
                height=42,
                bg_color=t["success"],
                hover_color=t["accent"],
                canvas_bg=t["card"],
            ).pack(side=tk.LEFT, padx=8)

            AnimatedPulseButton(
                btn_bar,
                text="❌ Block",
                command=lambda: decide(False),
                width=130,
                height=42,
                bg_color=t["danger"],
                hover_color=t["secondary"],
                canvas_bg=t["card"],
            ).pack(side=tk.LEFT, padx=8)

            dlg.protocol("WM_DELETE_WINDOW", lambda: decide(False))

        import threading
        self.root.after(0, show_dialog)
        done_event.wait(timeout=30.0)
        return decision["allowed"]

    def toggle_broadcast(self) -> None:
        t = THEMES[self.theme_key]
        if not self.server.running:
            self._sync_slider_config()
            self.server.start()
            self.start_btn.set_text("⏹ Stop Screen Broadcast")
            self.start_btn.set_palette(t["danger"], "#F87171", t["card"])
        else:
            self.server.stop()
            self.start_btn.set_text("▶ Start Screen Broadcast")
            self.start_btn.set_palette(t["accent"], t["accent_hover"], t["card"])

    def update_metrics(self, fps: float, kbps: float, clients: int) -> None:
        self.root.after(
            0,
            lambda: self.metrics_lbl.configure(
                text=f"Status: LIVE  |  {fps:.1f} FPS  |  {kbps:.0f} kbps  |  {clients} Phone(s)"
            ),
        )

    def append_log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        def _write():
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
        self.root.after(0, _write)

    def toggle_theme(self) -> None:
        old_theme = THEMES[self.theme_key]
        self.theme_key = "light" if self.theme_key == "night" else "night"
        new_theme = THEMES[self.theme_key]
        self._animate_theme_transition(old_theme, new_theme, step=0, total_steps=12)

    def _animate_theme_transition(self, old_t: Dict[str, str], new_t: Dict[str, str], step: int, total_steps: int) -> None:
        frac = step / float(total_steps)
        interp = {
            k: blend_hex(old_t[k], new_t[k], frac)
            if old_t[k].startswith("#")
            else new_t[k]
            for k in new_t
        }
        self._apply_palette_dict(interp)
        if step < total_steps:
            self.root.after(18, lambda: self._animate_theme_transition(old_t, new_t, step + 1, total_steps))

    def _apply_theme(self, animate: bool = False) -> None:
        self._apply_palette_dict(THEMES[self.theme_key])

    def _apply_palette_dict(self, t: Dict[str, str]) -> None:
        self.root.configure(bg=t["bg"])
        self.main_frame.configure(bg=t["bg"])
        self.header_frame.configure(bg=t["bg"])
        self.body_frame.configure(bg=t["bg"])
        self.title_lbl.configure(bg=t["bg"], fg=t["text"])
        self.subtitle_lbl.configure(bg=t["bg"], fg=t["subtext"])

        for card in (self.left_card, self.right_card):
            card.configure(bg=t["card"], highlightbackground=t["card_border"])

        self.radar_canvas.configure(bg=t["card"])
        self.ip_title_lbl.configure(bg=t["card"], fg=t["text"])
        self.ip_val_lbl.configure(bg=t["card"], fg=t["accent"])
        self.pin_lbl.configure(bg=t["card"], fg=t["subtext"])
        self.metrics_lbl.configure(bg=t["card"], fg=t["success"])
        self.perm_header_lbl.configure(bg=t["card"], fg=t["text"])
        self.perm_status_lbl.configure(bg=t["card"], fg=t["subtext"])
        self.log_header_lbl.configure(bg=t["card"], fg=t["text"])
        self.log_text.configure(bg=t["bg"], fg=t["text"])

        self.theme_btn.set_palette(t["secondary"], t["accent"], t["bg"])
        self.perm_btn.set_palette(t["accent"], t["accent_hover"], t["bg"])
        if self.server.running:
            self.start_btn.set_palette(t["danger"], "#F87171", t["card"])
        else:
            self.start_btn.set_palette(t["accent"], t["accent_hover"], t["card"])

    def _animate_radar_loop(self) -> None:
        t = THEMES[self.theme_key]
        self.radar_canvas.delete("all")
        cx, cy = 48, 48
        self.pulse_phase = (self.pulse_phase + 0.08) % (2 * math.pi)
        for i in range(3):
            r = 14 + ((self.pulse_phase * 8 + i * 11) % 32)
            color = t["accent"] if self.server.running else t["subtext"]
            self.radar_canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=2)
        core_color = t["success"] if self.server.running else t["secondary"]
        self.radar_canvas.create_oval(cx - 10, cy - 10, cx + 10, cy + 10, fill=core_color, outline="")
        self.root.after(45, self._animate_radar_loop)


if __name__ == "__main__":
    root = tk.Tk()
    app = PulseLinkWindowsApp(root)
    root.mainloop()
