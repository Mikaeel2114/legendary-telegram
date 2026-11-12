"""
PulseLink Cast - Core Binary Protocol, Discovery & Access Control Engine
Supports framing for JPEG video frames, remote mouse/keyboard events, and LAN UDP discovery.
"""
import json
import socket
import struct
import secrets
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Tuple, List

MAGIC_HEADER = b"PLNK"
FRAME_TYPE_VIDEO = 0x01
FRAME_TYPE_STATS = 0x02
FRAME_TYPE_AUTH_CHALLENGE = 0x03
FRAME_TYPE_AUTH_RESULT = 0x04

DEFAULT_STREAM_PORT = 5959
DEFAULT_DISCOVERY_PORT = 5960


@dataclass
class StreamConfig:
    fps: int = 30
    jpeg_quality: int = 75
    scale_percent: int = 100
    monitor_index: int = 1
    allow_remote_input: bool = True
    require_access_approval: bool = True


def pack_packet(packet_type: int, payload: bytes) -> bytes:
    """Packs a binary frame: 4B Magic ('PLNK') + 1B Type + 4B Big-Endian Length + Payload."""
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("payload must be bytes or bytearray")
    header = MAGIC_HEADER + struct.pack(">BI", packet_type & 0xFF, len(payload))
    return header + payload


def unpack_header(header_bytes: bytes) -> Tuple[int, int]:
    """Unpacks a 9-byte header and returns (packet_type, payload_length)."""
    if len(header_bytes) != 9:
        raise ValueError(f"Expected 9 header bytes, got {len(header_bytes)}")
    if header_bytes[:4] != MAGIC_HEADER:
        raise ValueError("Invalid magic header bytes")
    pkt_type, length = struct.unpack(">BI", header_bytes[4:9])
    return pkt_type, length


def encode_discovery_beacon(hostname: str, ip_address: str, port: int, pin_code: str) -> bytes:
    """Encodes a UDP broadcast discovery announcement packet."""
    data = {
        "service": "PulseLinkCast",
        "version": "2.4.0",
        "hostname": hostname,
        "ip": ip_address,
        "port": port,
        "pin_required": bool(pin_code),
    }
    return json.dumps(data).encode("utf-8")


def parse_control_command(line: str) -> Dict[str, Any]:
    """Parses a JSON line command sent from the Android client."""
    cleaned = line.strip()
    if not cleaned:
        raise ValueError("Empty command line")
    data = json.loads(cleaned)
    if "cmd" not in data:
        raise ValueError("Missing 'cmd' field in control command")
    return data


def detect_lan_ip_addresses() -> List[str]:
    """Returns all active IPv4 LAN/Wi-Fi addresses plus localhost fallback."""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        primary_ip = s.getsockname()[0]
        s.close()
        if primary_ip and not primary_ip.startswith("127."):
            ips.append(primary_ip)
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            addr = info[4][0]
            if addr not in ips and not addr.startswith("127."):
                ips.append(addr)
    except Exception:
        pass

    if "127.0.0.1" not in ips:
        ips.append("127.0.0.1")
    return ips


def generate_session_pin() -> str:
    """Generates a 4-digit security PIN for pairing."""
    return f"{secrets.randbelow(9000) + 1000}"
