import struct
import sys
import os
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5 import QtCore, QtGui, QtWidgets


# ---- helpers to build fake F1 25 packets ----

def _build_header(packet_id=6, player_car_index=0, secondary=255):
    h = bytearray(29)
    struct.pack_into('<H', h, 0, 2500)
    h[2] = 25; h[3] = 1; h[4] = 0; h[5] = 1; h[6] = packet_id
    struct.pack_into('<Q', h, 7, 0)
    struct.pack_into('<f', h, 15, 0.0)
    struct.pack_into('<I', h, 19, 0)
    struct.pack_into('<I', h, 23, 0)
    h[27] = player_car_index; h[28] = secondary
    return bytes(h)

def _build_car_telemetry(throttle=0.0, brake=0.0, speed=0, gear=0, rpm=0, drs=0):
    data = bytearray(60)
    struct.pack_into('<H', data, 0, speed)
    struct.pack_into('<f', data, 2, throttle)
    struct.pack_into('<f', data, 6, 0.0)
    struct.pack_into('<f', data, 10, brake)
    data[14] = 0
    struct.pack_into('<b', data, 15, gear)
    struct.pack_into('<H', data, 16, rpm)
    data[18] = drs
    return bytes(data)

def build_full_telemetry_packet(packet_id=6, player_car_index=0,
                                throttle=0.0, brake=0.0,
                                speed=0, gear=0, rpm=0, drs=0):
    return _build_header(packet_id, player_car_index) + _build_car_telemetry(
        throttle=throttle, brake=brake, speed=speed, gear=gear, rpm=rpm, drs=drs)


# ---- tests: packet structure ----

def test_header_is_29_bytes():
    assert len(_build_header()) == 29

def test_car_telemetry_is_60_bytes():
    assert len(_build_car_telemetry()) == 60

def test_player_car_index_at_offset_27():
    pkt = build_full_telemetry_packet(player_car_index=7)
    assert pkt[27] == 7

def test_secondary_player_car_index_at_offset_28():
    pkt = _build_header(secondary=255)
    assert pkt[28] == 255

def test_packet_id_at_offset_6():
    from main import PACKET_ID_OFFSET
    pkt = build_full_telemetry_packet(packet_id=6)
    assert pkt[PACKET_ID_OFFSET] == 6

def test_player_car_index_offset_is_27():
    from main import PLAYER_CAR_INDEX_OFFSET
    assert PLAYER_CAR_INDEX_OFFSET == 27

def test_throttle_offset_is_2():
    from main import THROTTLE_OFFSET
    assert THROTTLE_OFFSET == 2

def test_brake_offset_is_10():
    from main import BRAKE_OFFSET
    assert BRAKE_OFFSET == 10

def test_throttle_unpack():
    from main import HEADER_SIZE, CAR_TELEMETRY_SIZE, THROTTLE_OFFSET
    pkt = build_full_telemetry_packet(throttle=0.876)
    base = HEADER_SIZE
    val = struct.unpack_from('<f', pkt, base + THROTTLE_OFFSET)[0]
    assert abs(val - 0.876) < 1e-6

def test_brake_unpack():
    from main import HEADER_SIZE, CAR_TELEMETRY_SIZE, BRAKE_OFFSET
    pkt = build_full_telemetry_packet(brake=0.543)
    base = HEADER_SIZE
    val = struct.unpack_from('<f', pkt, base + BRAKE_OFFSET)[0]
    assert abs(val - 0.543) < 1e-6

def test_speed_unpack():
    from main import HEADER_SIZE, CAR_TELEMETRY_SIZE, SPEED_OFFSET
    pkt = build_full_telemetry_packet(speed=287)
    base = HEADER_SIZE
    val = struct.unpack_from('<H', pkt, base + SPEED_OFFSET)[0]
    assert val == 287

def test_gear_unpack():
    from main import HEADER_SIZE, CAR_TELEMETRY_SIZE, GEAR_OFFSET
    pkt = build_full_telemetry_packet(gear=7)
    base = HEADER_SIZE
    val = struct.unpack_from('<b', pkt, base + GEAR_OFFSET)[0]
    assert val == 7

def test_rpm_unpack():
    from main import HEADER_SIZE, CAR_TELEMETRY_SIZE, RPM_OFFSET
    pkt = build_full_telemetry_packet(rpm=11500)
    base = HEADER_SIZE
    val = struct.unpack_from('<H', pkt, base + RPM_OFFSET)[0]
    assert val == 11500

def test_drs_unpack():
    from main import HEADER_SIZE, CAR_TELEMETRY_SIZE, DRS_OFFSET
    pkt = build_full_telemetry_packet(drs=1)
    base = HEADER_SIZE
    assert pkt[base + DRS_OFFSET] == 1


class TestTelemetryReceiver(unittest.TestCase):
    """Tests for TelemetryReceiver.poll_latest() via socket mocking."""
    def setUp(self):
        from main import TelemetryReceiver, UDP_PORT
        self.UDP_PORT = UDP_PORT
        self.receiver = TelemetryReceiver(self.UDP_PORT)

    def _mock_once(self, packet):
        """Replace sock with one that returns packet once, then raises BlockingIOError."""
        call_count = [0]
        def fake_recvfrom(size):
            call_count[0] += 1
            if call_count[0] == 1:
                return (packet, ('127.0.0.1', self.UDP_PORT))
            raise BlockingIOError()
        fake_sock = MagicMock()
        fake_sock.recvfrom = fake_recvfrom
        self.receiver.sock = fake_sock

    def test_poll_latest_returns_dict_on_valid_packet(self):
        fake = build_full_telemetry_packet(
            player_car_index=0, throttle=0.5, brake=0.3,
            speed=210, gear=6, rpm=9000, drs=1)
        self._mock_once(fake)
        result = self.receiver.poll_latest()
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
        self.assertAlmostEqual(result['throttle'], 0.5, places=5)
        self.assertAlmostEqual(result['brake'], 0.3, places=5)
        self.assertEqual(result['speed_kmh'], 756)
        self.assertEqual(result['gear'], 6)
        self.assertEqual(result['rpm'], 9000)
        self.assertTrue(result['drs'])

    def test_poll_latest_returns_none_for_wrong_packet_id(self):
        wrong = build_full_telemetry_packet(packet_id=5)
        self._mock_once(wrong)
        self.assertIsNone(self.receiver.poll_latest())

    def test_poll_latest_returns_none_for_short_packet(self):
        self._mock_once(bytes([1, 2]))
        self.assertIsNone(self.receiver.poll_latest())

    def test_poll_latest_returns_none_for_empty_packet(self):
        self._mock_once(b'')
        self.assertIsNone(self.receiver.poll_latest())

    def test_poll_latest_handles_truncated_telemetry(self):
        bad = _build_header(packet_id=6) + bytes([0]) * 10
        self._mock_once(bad)
        self.assertIsNone(self.receiver.poll_latest())


def test_overlay_window_instantiates():
    from main import OverlayWindow
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = OverlayWindow()
    assert window is not None
    assert window.receiver is not None

def test_overlay_has_all_telemetry_attributes():
    from main import OverlayWindow
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = OverlayWindow()
    for attr in ('last_throttle', 'last_brake', 'last_steer',
                 'last_speed', 'last_gear', 'last_rpm', 'last_drs'):
        assert hasattr(window, attr), f'Missing: {attr}'

def test_all_config_constants_are_integers():
    from main import (
        HEADER_SIZE, PACKET_ID_OFFSET, PLAYER_CAR_INDEX_OFFSET,
        CAR_TELEMETRY_SIZE, THROTTLE_OFFSET, BRAKE_OFFSET,
        SPEED_OFFSET, GEAR_OFFSET, RPM_OFFSET, DRS_OFFSET,
        UDP_PORT, SAMPLE_BUFFER, FPS,
    )
    for name, value in [
        ('HEADER_SIZE', HEADER_SIZE), ('PACKET_ID_OFFSET', PACKET_ID_OFFSET),
        ('PLAYER_CAR_INDEX_OFFSET', PLAYER_CAR_INDEX_OFFSET),
        ('CAR_TELEMETRY_SIZE', CAR_TELEMETRY_SIZE),
        ('THROTTLE_OFFSET', THROTTLE_OFFSET), ('BRAKE_OFFSET', BRAKE_OFFSET),
        ('SPEED_OFFSET', SPEED_OFFSET), ('GEAR_OFFSET', GEAR_OFFSET),
        ('RPM_OFFSET', RPM_OFFSET), ('DRS_OFFSET', DRS_OFFSET),
        ('UDP_PORT', UDP_PORT), ('SAMPLE_BUFFER', SAMPLE_BUFFER), ('FPS', FPS),
    ]:
        assert isinstance(value, int), f'{name}={value!r} is not int'

def test_offsets_match_f1_25_spec():
    from main import (
        HEADER_SIZE, CAR_TELEMETRY_SIZE,
        THROTTLE_OFFSET, BRAKE_OFFSET, SPEED_OFFSET,
        GEAR_OFFSET, RPM_OFFSET, DRS_OFFSET,
    )
    assert HEADER_SIZE == 29
    assert CAR_TELEMETRY_SIZE == 60
    assert SPEED_OFFSET == 0
    assert THROTTLE_OFFSET == 2
    assert BRAKE_OFFSET == 10
    assert GEAR_OFFSET == 15
    assert RPM_OFFSET == 16
    assert DRS_OFFSET == 18

if __name__ == '__main__':
    unittest.main()
