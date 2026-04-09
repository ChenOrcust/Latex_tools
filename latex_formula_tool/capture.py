from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QGuiApplication, QMouseEvent, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QDialog


class SnipDialog(QDialog):
    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setCursor(Qt.CursorShape.CrossCursor)

        screen = QGuiApplication.screenAt(QGuiApplication.cursor().pos())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            raise RuntimeError("无法读取屏幕。")

        self._screen = screen
        self._geometry = screen.geometry()
        self._pixmap = screen.grabWindow(0)
        self._origin = QPoint()
        self._selection = QRect()
        self.result_pixmap: QPixmap | None = None

        self.setGeometry(self._geometry)
        self.setWindowOpacity(0.96)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._selection = QRect(self._origin, self._origin)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._selection = QRect(self._origin, event.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            selection = self._selection.normalized()
            if selection.width() > 4 and selection.height() > 4:
                ratio = self._pixmap.devicePixelRatio()
                source = QRect(
                    int(selection.x() * ratio),
                    int(selection.y() * ratio),
                    int(selection.width() * ratio),
                    int(selection.height() * ratio),
                )
                self.result_pixmap = self._pixmap.copy(source)
                self.accept()
            else:
                self.reject()

    def keyPressEvent(self, event) -> None:  # noqa: ANN001 - Qt override.
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: ANN001 - Qt override.
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)
        painter.setOpacity(0.45)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        painter.setOpacity(1.0)

        if not self._selection.isNull():
            selection = self._selection.normalized()
            painter.drawPixmap(selection, self._pixmap, selection)
            painter.setPen(QPen(Qt.GlobalColor.cyan, 2))
            painter.drawRect(selection)


def capture_screen_region() -> QPixmap | None:
    QApplication.processEvents()
    dialog = SnipDialog()
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.result_pixmap
    return None
