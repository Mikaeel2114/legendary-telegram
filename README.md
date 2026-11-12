# PulseLink Cast Studio — Windows to Android Screen & Control Bridge

**PulseLink Cast Studio** is a full-stack, ultra-low-latency screen sharing and remote control suite designed to stream your **Windows 10/11 desktop** directly to your **Android phone** over:
1. **Wi-Fi / Home Modem LAN** (`192.168.x.x` with zero-config UDP Auto-Discovery on Port `5960` and TCP stream on Port `5959`)
2. **Localhost / USB Cable Tunnel** (`127.0.0.1:5959` via `adb reverse tcp:5959 tcp:5959` for zero-lag wired streaming)

---

## Key Features

### 1. Windows Host Application (`windows-host/`)
- **Interactive Windows Access Question & One-Click Permission Grant**:
  - Automatically asks permission on launch to configure **Desktop Duplication Screen Capture**, **Remote Mouse/Keyboard Injection**, **High-DPI Per-Monitor Scaling**, and **Windows Defender Firewall Inbound/Outbound Rules** (`TCP 5959` & `UDP 5960`) across Private and Public modem/Wi-Fi networks.
  - Displays a live **Incoming Phone Access Approval Prompt** whenever an Android device attempts to connect.
- **Animated Dark/Night & Daylight UI**:
  - Built with smooth color-interpolated theme transitions, animated radar pulse canvas, and `AnimatedPulseButton` controls with hover glow and click-bounce physics.
- **Windows Setup Installer**:
  - Includes `setup_windows.bat` and an **Inno Setup script** (`windows-host/installer/PulseLinkSetup.iss`) that packages `PulseLinkCast_Windows_Setup.exe`.

### 2. Android Client App (`android-app/`)
- **Animated Dark/Night & Day Material 3 Interface**:
  - Instant theme toggle (`🌙 Night / ☀️ Day`) with smooth fade transitions and tactile scale-bounce button animations (`btn_pulse_press.xml`).
- **Built-In Pro Tools Dock for Best Streaming Results**:
  - **⚡ Quality & FPS Mode Switcher**: Cycle live between *Ultra 60 FPS*, *Balanced 30 FPS*, and *Low-Latency Turbo*.
  - **🖱️ Direct Touch & Precision Trackpad Toggle**: Tap directly on Windows buttons, long-press to right-click, or use relative cursor trackpad movement.
  - **🔍 Pinch-to-Zoom & Pan Canvas**: Smoothly zoom up to `4.5x` on fine desktop text.
  - **⌨️ PC Shortcut & Key Deck**: Send `Win`, `Alt+Tab`, `Ctrl+C`, `Ctrl+V`, `Ctrl+Z`, `Win+D`, `Esc`, and `Ctrl+Shift+Esc` with one tap.
  - **🖥️ Multi-Monitor Switcher**: Switch between Monitor #1 and Monitor #2 on the fly.
  - **📸 Instant HD Snapshot**: Save the current Windows screen frame directly to your Android gallery.
  - **⛶ Immersive Fullscreen**: Hide system bars for edge-to-edge viewing.

### 3. Automated GitHub Actions CI/CD (`.github/workflows/build-release.yml`)
- Push this repository to GitHub and GitHub Actions will automatically:
  1. Run the Windows protocol and permissions unit tests.
  2. Compile `PulseLinkCastHost.exe` and `PulseLinkCast_Windows_Setup.exe` on `windows-latest`.
  3. Compile the Android `.apk` (`app-debug.apk`) on `ubuntu-latest` using JDK 17 and Gradle 8.5.
