import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
import db
from monitor import ClipboardMonitor
from popup import HistoryPopup
from tray import TrayManager, HotkeyListener, _simulate_paste


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    db.init_db()

    popup = HistoryPopup()
    monitor = ClipboardMonitor()
    tray = TrayManager(app)
    hotkey = HotkeyListener()
    hotkey.start()

    def on_show_popup():
        popup.show_at_cursor()

    def on_paste_selected(clip_id: int):
        text = db.get_clip_text(clip_id)
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
        else:
            img_bytes = db.get_clip_image(clip_id)
            if img_bytes:
                from PyQt6.QtGui import QImage, QPixmap
                qimg = QImage()
                qimg.loadFromData(img_bytes)
                clipboard = QApplication.clipboard()
                clipboard.setPixmap(QPixmap.fromImage(qimg))
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, _simulate_paste)

    tray.show_popup.connect(on_show_popup)
    hotkey.triggered.connect(on_show_popup)
    popup.paste_selected.connect(on_paste_selected)

    ret = app.exec()
    hotkey.stop()
    sys.exit(ret)


if __name__ == "__main__":
    main()
