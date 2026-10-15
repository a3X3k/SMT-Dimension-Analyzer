"""Generate the Windows executable icon from the same PadNexa Qt artwork."""
from pathlib import Path
import struct
import sys
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtWidgets import QApplication
from ui.branding import logo_pixmap

app = QApplication.instance() or QApplication(sys.argv)
images = []
for size in (16, 32, 48, 64, 128, 256):
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    if not logo_pixmap(size).save(buffer, "PNG"):
        raise RuntimeError("Failed to render PadNexa icon")
    images.append((size, bytes(buffer.data())))
header = struct.pack("<HHH", 0, 1, len(images))
entries = bytearray()
payload = bytearray()
offset = 6 + 16 * len(images)
for size, data in images:
    entries.extend(struct.pack("<BBBBHHII", size if size < 256 else 0,
                               size if size < 256 else 0, 0, 0, 1, 32,
                               len(data), offset))
    payload.extend(data)
    offset += len(data)
Path("PadNexa.ico").write_bytes(header + entries + payload)
print("Generated PadNexa.ico")
