import os
import socket
import struct
import sys
from collections import deque

from PyQt5 import QtCore, QtGui, QtWidgets

# ─────────────────────────────────────────────────────────────────────────────
# Runtime helpers
# ─────────────────────────────────────────────────────────────────────────────


def _app_icon_path():
    """
    Return the path to fto-icon.ico that works in both dev and PyInstaller exe.
    When bundled by PyInstaller (onefile), bundled files are extracted to
    sys._MEIPASS.  Otherwise fall back to the directory this script lives in.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # Running as PyInstaller onefile bundle
        return os.path.join(sys._MEIPASS, "fto-icon.ico")
    # Running from source
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "fto-icon.ico")


# =========================
# F1 25 UDP Telemetry Config
# =========================
UDP_PORT = 20725

# Official F1 25 PacketHeader layout (29 bytes total):
#   offset 0  : packetFormat      uint16
#   offset 2  : gameYear          uint8
#   offset 3  : gameMajorVersion  uint8
#   offset 4  : gameMinorVersion  uint8
#   offset 5  : packetVersion     uint8
#   offset 6  : packetId          uint8   ← CORRECTED (was 5)
#   offset 7  : sessionUID        uint64
#   offset 15 : sessionTime       float32
#   offset 19 : frameIdentifier   uint32
#   offset 23 : overallFrameIdentifier uint32  ← NEW in F1 24/25
#   offset 27 : playerCarIndex    uint8   ← CORRECTED (was 22/23)
#   offset 28 : secondaryPlayerCarIndex uint8
HEADER_SIZE = 29
PACKET_ID_OFFSET = 6  # CORRECTED
PLAYER_CAR_INDEX_OFFSET = 27  # CORRECTED

PACKET_ID_CAR_TELEMETRY = 6

# Official F1 25 CarTelemetryData layout:
#   offset 0  : speed              uint16
#   offset 2  : throttle           float32
#   offset 6  : steer              float32
#   offset 10 : brake              float32
#   offset 14 : clutch             uint8
#   offset 15 : gear               int8
#   offset 16 : engineRPM          uint16
#   offset 18 : drs                uint8
#   offset 19 : revLightsPercent   uint8
#   offset 20 : revLightsBitValue  uint16
#   offset 22 : brakesTemperature  uint16[4] = 8 bytes
#   offset 30 : tyresSurfaceTemp   uint8[4]
#   offset 34 : tyresInnerTemp     uint8[4]
#   offset 38 : engineTemperature  uint16
#   offset 40 : tyresPressure      float32[4] = 16 bytes
#   offset 56 : surfaceType        uint8[4]
#   Total = 60 bytes  ← confirmed from official spec
CAR_TELEMETRY_SIZE = 60  # CORRECTED back to 60

SPEED_OFFSET = 0
THROTTLE_OFFSET = 2
STEER_OFFSET = 6
BRAKE_OFFSET = 10
GEAR_OFFSET = 15
RPM_OFFSET = 16
DRS_OFFSET = 18

PLAYER_CAR_INDEX_FALLBACK = 0

# Overlay behavior
WINDOW_WIDTH = 500
WINDOW_HEIGHT = 200
WINDOW_X = 60
WINDOW_Y = 60
SAMPLE_BUFFER = 220
FPS = 60

DEBUG_CAR_INDEX = False


class TelemetryReceiver(QtCore.QObject):
    def __init__(self, port: int):
        super().__init__()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", port))
        self.sock.setblocking(False)

    def _get_player_car_index(self, data: bytes) -> int:
        if len(data) > PLAYER_CAR_INDEX_OFFSET:
            idx = data[PLAYER_CAR_INDEX_OFFSET]
            if 0 <= idx <= 21:
                if DEBUG_CAR_INDEX:
                    print(f"[DEBUG] playerCarIndex = {idx}")
                return idx
        return PLAYER_CAR_INDEX_FALLBACK

    def poll_latest(self):
        latest = None

        while True:
            try:
                data, _addr = self.sock.recvfrom(8192)
            except BlockingIOError:
                break
            except OSError:
                break

            if len(data) <= PACKET_ID_OFFSET:
                continue

            packet_id = data[PACKET_ID_OFFSET]
            if packet_id != PACKET_ID_CAR_TELEMETRY:
                continue

            player_car_index = self._get_player_car_index(data)
            base = HEADER_SIZE + player_car_index * CAR_TELEMETRY_SIZE

            needed = base + RPM_OFFSET + 2
            if len(data) < needed:
                continue

            try:
                throttle = struct.unpack_from("<f", data, base + THROTTLE_OFFSET)[0]
                brake = struct.unpack_from("<f", data, base + BRAKE_OFFSET)[0]
                steer = struct.unpack_from("<f", data, base + STEER_OFFSET)[0]
                speed_ms = struct.unpack_from("<H", data, base + SPEED_OFFSET)[0]
                gear = struct.unpack_from("<b", data, base + GEAR_OFFSET)[0]
                rpm = struct.unpack_from("<H", data, base + RPM_OFFSET)[0]
                drs = data[base + DRS_OFFSET]
            except struct.error:
                continue

            throttle = max(0.0, min(1.0, float(throttle)))
            brake = max(0.0, min(1.0, float(brake)))
            steer = max(-1.0, min(1.0, float(steer)))

            latest = {
                "throttle": throttle,
                "brake": brake,
                "steer": steer,
                "speed_kmh": round(speed_ms * 3.6),
                "gear": int(gear),
                "rpm": int(rpm),
                "drs": bool(drs),
            }

        return latest


class OverlayWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.receiver = TelemetryReceiver(UDP_PORT)
        self.throttle_data = deque([0.0] * SAMPLE_BUFFER, maxlen=SAMPLE_BUFFER)
        self.brake_data = deque([0.0] * SAMPLE_BUFFER, maxlen=SAMPLE_BUFFER)

        self.last_throttle = 0.0
        self.last_brake = 0.0
        self.last_steer = 0.0
        self.last_speed = 0
        self.last_gear = 0
        self.last_rpm = 0
        self.last_drs = False

        self._drag_offset = None

        self.setWindowTitle("F1 25 Telemetry Overlay")
        icon_path = _app_icon_path()
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.move(WINDOW_X, WINDOW_Y)

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Window
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(int(1000 / FPS))
        self.timer.timeout.connect(self.on_tick)
        self.timer.start()

        self.hint = QtWidgets.QLabel(
            "Drag to move  |  F2: click-through  |  F3: toggle top-most  |  Esc: quit", self
        )
        self.hint.setStyleSheet(
            "color: rgba(255,255,255,160); background: transparent; font-size: 10px;"
        )
        self.hint.move(10, 6)
        self.hint.adjustSize()

        self.click_through = False
        self.top_most = True

    def on_tick(self):
        sample = self.receiver.poll_latest()
        if sample is not None:
            self.last_throttle = sample["throttle"]
            self.last_brake = sample["brake"]
            self.last_steer = sample["steer"]
            self.last_speed = sample["speed_kmh"]
            self.last_gear = sample["gear"]
            self.last_rpm = sample["rpm"]
            self.last_drs = sample["drs"]

        self.throttle_data.append(self.last_throttle)
        self.brake_data.append(self.last_brake)
        self.update()

    def toggle_click_through(self):
        self.click_through = not self.click_through
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, self.click_through)
        self.update()

    def toggle_top_most(self):
        self.top_most = not self.top_most
        flags = QtCore.Qt.FramelessWindowHint | QtCore.Qt.Window
        if self.top_most:
            flags |= QtCore.Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() == QtCore.Qt.Key_Escape:
            QtWidgets.QApplication.quit()
            return
        if event.key() == QtCore.Qt.Key_F2:
            self.toggle_click_through()
            return
        if event.key() == QtCore.Qt.Key_F3:
            self.toggle_top_most()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.LeftButton and not self.click_through:
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if self._drag_offset is not None and (event.buttons() & QtCore.Qt.LeftButton):
            self.move(event.globalPos() - self._drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def paintEvent(self, _event: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        w, h = self.width(), self.height()

        # Background panel
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 50), 1))
        painter.setBrush(QtGui.QColor(10, 14, 18, 150))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 12, 12)

        # Plot area
        PLOT_TOP = 24
        PLOT_BOTTOM = h - 42
        PLOT_LEFT = 12
        PLOT_RIGHT = w - 12
        plot_rect = QtCore.QRectF(
            PLOT_LEFT, PLOT_TOP, PLOT_RIGHT - PLOT_LEFT, PLOT_BOTTOM - PLOT_TOP
        )

        # Grid lines
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 25), 1))
        for i in range(1, 5):
            y = plot_rect.top() + i * plot_rect.height() / 5.0
            painter.drawLine(
                QtCore.QPointF(plot_rect.left(), y),
                QtCore.QPointF(plot_rect.right(), y),
            )

        # Traces
        self._draw_series(
            painter, plot_rect, self.throttle_data, QtGui.QColor(0, 220, 120, 230), 2.0
        )
        self._draw_series(painter, plot_rect, self.brake_data, QtGui.QColor(255, 70, 70, 230), 2.0)

        # Live bars
        self._draw_live_bars(painter)

        # Info row
        self._draw_info_row(painter, PLOT_BOTTOM + 4, w)

    def _draw_series(self, painter, rect, series, color, width):
        data = list(series)
        n = len(data)
        if n < 2:
            return
        path = QtGui.QPainterPath()
        x_step = rect.width() / float(max(1, n - 1))
        path.moveTo(rect.left(), rect.bottom() - data[0] * rect.height())
        for i in range(1, n):
            x = rect.left() + i * x_step
            y = rect.bottom() - data[i] * rect.height()
            path.lineTo(x, y)
        painter.setPen(QtGui.QPen(color, width))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawPath(path)

    def _draw_live_bars(self, painter):
        throttle = self.last_throttle
        brake = self.last_brake

        base_x = self.width() - 162
        base_y = 6
        bar_w = 68
        bar_h = 10
        gap = 6

        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)

        # Throttle
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 100), 1))
        painter.setBrush(QtGui.QColor(255, 255, 255, 15))
        painter.drawRoundedRect(base_x, base_y + 2, bar_w, bar_h, 4, 4)
        if throttle > 0:
            painter.setBrush(QtGui.QColor(0, 220, 120, 210))
            painter.drawRoundedRect(base_x, base_y + 2, max(4, int(bar_w * throttle)), bar_h, 4, 4)
        painter.setPen(QtGui.QColor(200, 255, 220, 220))
        painter.drawText(base_x + bar_w + gap, base_y + 11, f"T {throttle * 100:5.1f}%")

        # Brake
        y2 = base_y + 16
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 100), 1))
        painter.setBrush(QtGui.QColor(255, 255, 255, 15))
        painter.drawRoundedRect(base_x, y2 + 2, bar_w, bar_h, 4, 4)
        if brake > 0:
            painter.setBrush(QtGui.QColor(255, 70, 70, 210))
            painter.drawRoundedRect(base_x, y2 + 2, max(4, int(bar_w * brake)), bar_h, 4, 4)
        painter.setPen(QtGui.QColor(255, 210, 210, 220))
        painter.drawText(base_x + bar_w + gap, y2 + 11, f"B {brake * 100:5.1f}%")

    def _draw_info_row(self, painter, y, w):
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)

        gear_str = (
            "R" if self.last_gear == -1 else ("N" if self.last_gear == 0 else str(self.last_gear))
        )
        speed_str = f"{self.last_speed} km/h"
        rpm_str = f"{self.last_rpm:,} RPM"
        drs_str = "DRS ✓" if self.last_drs else "DRS ✗"
        drs_color = (
            QtGui.QColor(0, 230, 120, 230) if self.last_drs else QtGui.QColor(160, 160, 160, 160)
        )

        items = [
            (f"Gear {gear_str}", QtGui.QColor(255, 220, 100, 230)),
            (speed_str, QtGui.QColor(180, 210, 255, 230)),
            (rpm_str, QtGui.QColor(200, 200, 200, 200)),
            (drs_str, drs_color),
        ]

        col_w = w // len(items)
        for i, (text, color) in enumerate(items):
            painter.setPen(color)
            rect = QtCore.QRect(i * col_w, y, col_w, 30)
            painter.drawText(rect, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter, text)


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    overlay = OverlayWindow()
    overlay.show()

    print("=" * 52)
    print("  F1 25 Telemetry Overlay  (offsets verified v3)")
    print("=" * 52)
    print(f"  UDP port          : {UDP_PORT}")
    print(f"  Header size       : {HEADER_SIZE} bytes")
    print(f"  packetId offset   : {PACKET_ID_OFFSET}")
    print(f"  playerCarIndex    : byte {PLAYER_CAR_INDEX_OFFSET}")
    print(f"  CarTelemetry size : {CAR_TELEMETRY_SIZE} bytes")
    print()
    print("  Controls:")
    print("    Drag  - move overlay")
    print("    F2    - toggle click-through")
    print("    F3    - toggle always-on-top")
    print("    Esc   - quit")
    print("=" * 52)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
