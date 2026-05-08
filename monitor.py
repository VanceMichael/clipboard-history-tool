import hashlib
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QClipboard
from PyQt6.QtWidgets import QApplication
import db


class ClipboardMonitor(QObject):
    clip_added = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._clipboard = QApplication.clipboard()
        self._last_text_hash = ""
        self._last_image_hash = ""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_clipboard)
        self._timer.start(300)
        self._clipboard.dataChanged.connect(self._on_data_changed)

    def _on_data_changed(self):
        self._process_clipboard()

    def _check_clipboard(self):
        pass

    def _process_clipboard(self):
        mime = self._clipboard.mimeData()
        if mime is None:
            return

        if mime.hasImage():
            image = self._clipboard.pixmap()
            if image.isNull():
                return
            from PyQt6.QtCore import QBuffer, QIODevice
            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
            image.save(buf, "PNG")
            img_bytes = bytes(buf.data().data())
            img_hash = hashlib.sha256(img_bytes).hexdigest()
            if img_hash == self._last_image_hash:
                return
            self._last_image_hash = img_hash
            row_id = db.insert_clip("image", image_data=img_bytes)
            self.clip_added.emit(row_id)
            return

        if mime.hasText():
            text = self._clipboard.text()
            if not text:
                return
            text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if text_hash == self._last_text_hash:
                return
            self._last_text_hash = text_hash
            row_id = db.insert_clip("text", text_content=text)
            self.clip_added.emit(row_id)
