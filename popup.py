import sys
import db
from PyQt6.QtCore import Qt, QEvent, QSize, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QPixmap, QImage, QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLineEdit, QMenu, QLabel, QApplication,
)


class HistoryPopup(QWidget):
    paste_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedWidth(420)
        self.setFixedHeight(500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("搜索剪贴板历史...")
        self.search_edit.setFixedHeight(36)
        self.search_edit.textChanged.connect(self._on_search)
        self.search_edit.installEventFilter(self)
        layout.addWidget(self.search_edit)

        self.list_widget = QListWidget(self)
        self.list_widget.setSpacing(1)
        self.list_widget.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.list_widget.itemActivated.connect(self._on_item_activated)
        self.list_widget.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.list_widget.customContextMenuRequested.connect(
            self._on_context_menu
        )
        layout.addWidget(self.list_widget)

        self._clips_data: list[dict] = []
        self._image_cache: dict[int, QPixmap] = {}

    def show_at_cursor(self):
        self._refresh_list()
        self.search_edit.clear()
        self.list_widget.setCurrentRow(0)
        cursor_pos = self.screen().availableGeometry()
        from PyQt6.QtGui import QCursor
        pos = QCursor.pos()
        x = pos.x()
        y = pos.y()
        screen = self.screen().availableGeometry()
        if x + self.width() > screen.right():
            x = screen.right() - self.width()
        if y + self.height() > screen.bottom():
            y = screen.bottom() - self.height()
        self.move(x, y)
        self.show()
        self.search_edit.setFocus()
        self.activateWindow()

    def _refresh_list(self):
        search = self.search_edit.text().strip()
        self._clips_data = db.get_clips(search)
        self._image_cache.clear()
        self.list_widget.clear()
        for clip in self._clips_data:
            item = QListWidgetItem()
            if clip["content_type"] == "image":
                item.setText("[图片]")
            else:
                text = clip["text_content"] or ""
                display = text.replace("\n", " ")[:120]
                item.setText(display)
            if clip["pinned"]:
                item.setText("📌 " + item.text())
            item.setData(Qt.ItemDataRole.UserRole, clip["id"])
            self.list_widget.addItem(item)
        self._load_visible_images()

    def _load_visible_images(self):
        for i in range(min(len(self._clips_data), 50)):
            clip = self._clips_data[i]
            if clip["content_type"] != "image":
                continue
            clip_id = clip["id"]
            if clip_id in self._image_cache:
                continue
            img_bytes = db.get_clip_image(clip_id)
            if img_bytes:
                qimg = QImage()
                qimg.loadFromData(img_bytes)
                if not qimg.isNull():
                    pixmap = QPixmap.fromImage(qimg).scaled(
                        60, 60,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self._image_cache[clip_id] = pixmap
                    item = self.list_widget.item(i)
                    if item:
                        item.setIcon(pixmap)

    def _on_search(self, text: str):
        self._refresh_list()

    def _on_item_activated(self, item: QListWidgetItem):
        clip_id = item.data(Qt.ItemDataRole.UserRole)
        self.paste_selected.emit(clip_id)
        self.hide()

    def _on_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        clip_id = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)

        copy_action = QAction("复制", self)
        copy_action.triggered.connect(lambda: self._copy_clip(clip_id))
        menu.addAction(copy_action)

        clip_data = next(
            (c for c in self._clips_data if c["id"] == clip_id), None
        )
        pin_label = "取消钉住" if (clip_data and clip_data["pinned"]) else "钉住"
        pin_action = QAction(pin_label, self)
        pin_action.triggered.connect(lambda: self._toggle_pin(clip_id))
        menu.addAction(pin_action)

        delete_action = QAction("删除", self)
        delete_action.triggered.connect(lambda: self._delete_clip(clip_id))
        menu.addAction(delete_action)

        menu.exec(self.list_widget.mapToGlobal(pos))

    def _copy_clip(self, clip_id: int):
        clip_data = next(
            (c for c in self._clips_data if c["id"] == clip_id), None
        )
        if not clip_data:
            return
        clipboard = QApplication.clipboard()
        if clip_data["content_type"] == "image":
            img_bytes = db.get_clip_image(clip_id)
            if img_bytes:
                qimg = QImage()
                qimg.loadFromData(img_bytes)
                clipboard.setPixmap(QPixmap.fromImage(qimg))
        else:
            text = db.get_clip_text(clip_id)
            if text:
                clipboard.setText(text)

    def _toggle_pin(self, clip_id: int):
        db.toggle_pin(clip_id)
        self._refresh_list()

    def _delete_clip(self, clip_id: int):
        db.delete_clip(clip_id)
        self._refresh_list()

    def eventFilter(self, obj, event):
        if obj is self.search_edit and isinstance(event, QKeyEvent):
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Down:
                    row = self.list_widget.currentRow()
                    if row < self.list_widget.count() - 1:
                        self.list_widget.setCurrentRow(row + 1)
                    return True
                elif event.key() == Qt.Key.Key_Up:
                    row = self.list_widget.currentRow()
                    if row > 0:
                        self.list_widget.setCurrentRow(row - 1)
                    return True
                elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    current = self.list_widget.currentItem()
                    if current:
                        self._on_item_activated(current)
                    return True
                elif event.key() == Qt.Key.Key_Escape:
                    self.hide()
                    return True
        return super().eventFilter(obj, event)

    def focusOutEvent(self, event):
        if not self.isActiveWindow():
            self.hide()
        super().focusOutEvent(event)
