import sys
import subprocess
import platform

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
from PyQt6.QtCore import QObject, pyqtSignal, Qt, QTimer
import db


def _create_default_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#4A90D9"))
    painter.setPen(QColor("#2C5F9A"))
    painter.drawRoundedRect(4, 4, 56, 56, 10, 10)
    painter.setBrush(QColor("#FFFFFF"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRect(16, 12, 6, 40)
    painter.drawRect(12, 16, 40, 6)
    painter.end()
    return QIcon(pixmap)


def _simulate_paste():
    system = platform.system()
    if system == "Darwin":
        subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to keystroke "v" using command down'],
            check=False,
        )
    elif system == "Windows":
        import ctypes
        VK_CONTROL = 0x11
        VK_V = 0x56
        KEYEVENTF_KEYUP = 0x0002
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_V, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


class _QuartzHotkeyMonitor(QObject):
    triggered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._v_was_down = False
        try:
            from Quartz import (
                CGEventSourceKeyState, kCGEventSourceStateHIDSystemState,
            )
            self._key_state = CGEventSourceKeyState
            self._source = kCGEventSourceStateHIDSystemState
            self._available = True
        except ImportError:
            self._available = False

    def start(self):
        if self._available:
            self._timer.start(50)

    def stop(self):
        self._timer.stop()

    def _poll(self):
        kVK_Command = 0x37
        kVK_Shift = 0x38
        kVK_V = 0x09
        cmd = self._key_state(self._source, kVK_Command)
        shift = self._key_state(self._source, kVK_Shift)
        v = self._key_state(self._source, kVK_V)
        combo = cmd and shift and v
        if combo and not self._v_was_down:
            self.triggered.emit()
        self._v_was_down = combo


class _PynputHotkeyMonitor(QObject):
    triggered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        from pynput import keyboard
        self._hotkey = keyboard.HotKey(
            keyboard.HotKey.parse("<ctrl>+<shift>+v"),
            self._on_hotkey,
        )
        self._listener = keyboard.Listener(
            on_press=self._for_canonical(self._hotkey.press),
            on_release=self._for_canonical(self._hotkey.release),
        )

    def _for_canonical(self, fn):
        def inner(key):
            canonical = self._listener.canonical(key)
            fn(canonical)
        return inner

    def _on_hotkey(self):
        self.triggered.emit()

    def start(self):
        self._listener.start()

    def stop(self):
        self._listener.stop()


class HotkeyListener(QObject):
    triggered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        if platform.system() == "Darwin":
            self._impl = _QuartzHotkeyMonitor(self)
        else:
            self._impl = _PynputHotkeyMonitor(self)
        self._impl.triggered.connect(self.triggered.emit)

    def start(self):
        self._impl.start()

    def stop(self):
        self._impl.stop()


class TrayManager(QObject):
    show_popup = pyqtSignal()

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self._app = app
        self._icon = _create_default_icon()
        self._tray = QSystemTrayIcon(self._icon, app)
        menu = QMenu()

        show_action = QAction("显示历史", self)
        show_action.triggered.connect(lambda: self.show_popup.emit())
        menu.addAction(show_action)

        menu.addSeparator()

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        self._tray.show()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_popup.emit()

    def _quit(self):
        self._app.quit()
