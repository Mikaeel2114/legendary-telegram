import json
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from protocol import (
    MAGIC_HEADER,
    FRAME_TYPE_VIDEO,
    FRAME_TYPE_AUTH_RESULT,
    pack_packet,
    unpack_header,
    encode_discovery_beacon,
    parse_control_command,
    detect_lan_ip_addresses,
    generate_session_pin,
)
from permissions_manager import WindowsAccessManager


class TestPulseLinkProtocol(unittest.TestCase):
    def test_pack_and_unpack_video_frame(self):
        fake_jpeg = b"\xff\xd8\xff\xe0JFIF_TEST_PAYLOAD\xff\xd9"
        pkt = pack_packet(FRAME_TYPE_VIDEO, fake_jpeg)
        self.assertEqual(pkt[:4], MAGIC_HEADER)
        pkt_type, length = unpack_header(pkt[:9])
        self.assertEqual(pkt_type, FRAME_TYPE_VIDEO)
        self.assertEqual(length, len(fake_jpeg))
        self.assertEqual(pkt[9:], fake_jpeg)

    def test_discovery_beacon_json(self):
        raw = encode_discovery_beacon("WORKSTATION-PC", "192.168.1.42", 5959, "4821")
        decoded = json.loads(raw.decode("utf-8"))
        self.assertEqual(decoded["service"], "PulseLinkCast")
        self.assertEqual(decoded["ip"], "192.168.1.42")
        self.assertEqual(decoded["port"], 5959)
        self.assertTrue(decoded["pin_required"])

    def test_parse_control_command(self):
        cmd = parse_control_command('{"cmd": "touch_tap", "x": 0.45, "y": 0.82}\n')
        self.assertEqual(cmd["cmd"], "touch_tap")
        self.assertAlmostEqual(cmd["x"], 0.45)

    def test_lan_ip_and_pin_generation(self):
        ips = detect_lan_ip_addresses()
        self.assertTrue(len(ips) >= 1)
        self.assertIn("127.0.0.1", ips)
        pin = generate_session_pin()
        self.assertEqual(len(pin), 4)
        self.assertTrue(pin.isdigit())

    def test_permissions_manager_grant_all(self):
        mgr = WindowsAccessManager()
        ok, msg = mgr.grant_all_windows_permissions()
        self.assertTrue(ok)
        self.assertTrue(mgr.permissions_state["screen_capture"])
        self.assertTrue(mgr.permissions_state["input_control"])


if __name__ == "__main__":
    unittest.main()
