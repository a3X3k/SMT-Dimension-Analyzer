"""PadNexa visual identity: scalable circuit-pad mark and launch splash."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QBrush, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSplashScreen

APP_NAME = "PadNexa"
TAGLINE = "PCB Geometry Intelligence"

def logo_pixmap(size=256):
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    k = size / 256.0
    p.scale(k, k)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#101D32"))
    p.drawRoundedRect(QRectF(4, 4, 248, 248), 55, 55)
    p.setPen(QPen(QColor("#19D7D2"), 11, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    for a, b, c, d in ((53, 83, 92, 83), (53, 128, 92, 128),
                       (53, 173, 92, 173), (164, 83, 203, 83),
                       (164, 128, 203, 128), (164, 173, 203, 173)):
        p.drawLine(a, b, c, d)
    p.setPen(QPen(QColor("#8A9FFF"), 9))
    p.setBrush(QColor("#182F51"))
    p.drawRoundedRect(QRectF(91, 58, 74, 140), 15, 15)
    p.setPen(QPen(QColor("#FFFFFF"), 9, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(113, 153, 113, 103)
    p.drawLine(113, 103, 145, 153)
    p.drawLine(145, 153, 145, 103)
    p.end()
    return pix

def app_icon():
    return QIcon(logo_pixmap())

def launch_splash():
    pix = QPixmap(760, 410)
    pix.fill(QColor("#0B1424"))
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor("#243A57"), 1))
    for x in range(24, 760, 32):
        p.drawLine(x, 0, x, 410)
    for y in range(24, 410, 32):
        p.drawLine(0, y, 760, y)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#101F35"))
    p.drawRoundedRect(QRectF(36, 38, 688, 330), 26, 26)
    p.drawPixmap(72, 98, logo_pixmap(174))
    p.setPen(QColor("#FFFFFF"))
    font = QFont("Segoe UI", 48, QFont.Bold)
    p.setFont(font)
    p.drawText(QRectF(280, 109, 420, 80), Qt.AlignVCenter, APP_NAME)
    p.setFont(QFont("Segoe UI", 17))
    p.setPen(QColor("#51DDD5"))
    p.drawText(QRectF(283, 194, 420, 38), Qt.AlignVCenter, TAGLINE)
    p.setPen(QColor("#A6B7CF"))
    p.setFont(QFont("Segoe UI", 11))
    p.drawText(QRectF(78, 291, 615, 35), Qt.AlignVCenter,
               "CAD  /  BOM  /  GERBER  /  FOOTPRINT RECOGNITION")
    p.setBrush(QColor("#19D7D2"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(78, 343, 604, 3), 1.5, 1.5)
    p.end()
    splash = QSplashScreen(pix)
    splash.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    return splash
