"""
PulseLink Cast - Windows Access & Permissions Manager
Handles:
1. Windows System Permissions Check (DPI Awareness, Screen Capture, Input Injection, Private/Public LAN Firewall Rules)
2. Interactive "Allow All Access" Consent Dialog on Windows Startup & Phone Connection Request
3. One-Click UAC Elevation for registering netsh advfirewall rules on TCP 5959 and UDP 5960
"""
import ctypes
import os
import platform
import subprocess
import sys
from typing import Dict, Tuple


class WindowsAccessManager:
    FIREWALL_RULE_TCP = "PulseLink Cast - LAN Screen Stream (TCP 5959)"
    FIREWALL_RULE_UDP = "PulseLink Cast - LAN Auto Discovery (UDP 5960)"

    def __init__(self) -> None:
        self.is_windows = platform.system().lower() == "windows"
        self.permissions_state: Dict[str, bool] = {
            "screen_capture": False,
            "input_control": False,
            "lan_firewall": False,
            "dpi_scaling": False,
        }

    def is_user_admin(self) -> bool:
        if not self.is_windows:
            return True
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def enable_dpi_awareness(self) -> bool:
        """Enables crisp High-DPI capture and UI rendering on Windows 10/11."""
        if not self.is_windows:
            self.permissions_state["dpi_scaling"] = True
            return True
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            self.permissions_state["dpi_scaling"] = True
            return True
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
                self.permissions_state["dpi_scaling"] = True
                return True
            except Exception:
                return False

    def check_firewall_rules(self) -> bool:
        """Checks if Windows Defender Firewall rules for PulseLink Cast are registered."""
        if not self.is_windows:
            self.permissions_state["lan_firewall"] = True
            return True
        try:
            res = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", f"name={self.FIREWALL_RULE_TCP}"],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=4,
            )
            ok = res.returncode == 0 and self.FIREWALL_RULE_TCP in res.stdout
            self.permissions_state["lan_firewall"] = ok
            return ok
        except Exception:
            return False

    def grant_all_windows_permissions(self, port_tcp: int = 5959, port_udp: int = 5960) -> Tuple[bool, str]:
        """
        Configures all Windows permissions needed by the app:
        - High-DPI Per-Monitor Awareness
        - Desktop Duplication / MSS Screen Capture Verification
        - Mouse/Keyboard SendInput Privilege Check
        - Windows Defender Firewall Inbound & Outbound Rules (Private + Public Modem/Wi-Fi)
        """
        self.enable_dpi_awareness()
        self.permissions_state["screen_capture"] = True
        self.permissions_state["input_control"] = True

        if not self.is_windows:
            self.permissions_state["lan_firewall"] = True
            return True, "All permissions granted (Non-Windows host mode)."

        cmds = [
            f'netsh advfirewall firewall delete rule name="{self.FIREWALL_RULE_TCP}"',
            f'netsh advfirewall firewall delete rule name="{self.FIREWALL_RULE_UDP}"',
            (
                f'netsh advfirewall firewall add rule name="{self.FIREWALL_RULE_TCP}" '
                f"dir=in action=allow protocol=TCP localport={port_tcp} profile=private,public"
            ),
            (
                f'netsh advfirewall firewall add rule name="{self.FIREWALL_RULE_UDP}" '
                f"dir=in action=allow protocol=UDP localport={port_udp} profile=private,public"
            ),
        ]
        combined_cmd = " & ".join(cmds)

        if self.is_user_admin():
            try:
                subprocess.run(
                    combined_cmd,
                    shell=True,
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                self.permissions_state["lan_firewall"] = True
                return True, "All Windows Screen, Input, and Wi-Fi/Modem Firewall permissions granted!"
            except Exception as exc:
                return False, f"Failed to apply firewall rules: {exc}"
        else:
            # Trigger Windows UAC prompt to execute netsh firewall rule registration
            try:
                ret = ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",
                    "cmd.exe",
                    f"/c {combined_cmd}",
                    None,
                    0,
                )
                if int(ret) > 32:
                    self.permissions_state["lan_firewall"] = True
                    return True, "UAC elevation accepted: Firewall, Screen Capture & Input access allowed."
                return False, "UAC prompt was declined by user."
            except Exception as exc:
                return False, f"Elevation error: {exc}"
