from __future__ import annotations

import tempfile
from pathlib import Path

from PyQt6.QtCore import QByteArray, QBuffer, QIODevice
from PyQt6.QtGui import QImage, QPixmap


def save_qimage_to_temp(image: QImage, suffix: str = ".png") -> Path:
    target = Path(tempfile.NamedTemporaryFile(delete=False, suffix=suffix).name)
    if not image.save(str(target)):
        raise ValueError("图片保存失败。")
    return target


def save_qpixmap_to_temp(pixmap: QPixmap, suffix: str = ".png") -> Path:
    if pixmap.isNull():
        raise ValueError("截图为空。")
    return save_qimage_to_temp(pixmap.toImage(), suffix=suffix)


def qimage_to_bytes(image: QImage, image_format: str = "PNG") -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, image_format)
    data = bytes(QByteArray(buffer.data()))
    buffer.close()
    return data


