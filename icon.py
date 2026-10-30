"""
Uygulama simgesi: geriye dönen bir okla çevrili saat.
Kodla çizilir, böylece açılış animasyonu aynı çizimi kullanabilir.

    uv run icon.py   -> assets/icon.ico dosyasını (Windows .exe ve kurulum simgesi) yeniden üretir
"""

import io
import math
from pathlib import Path

from PySide6.QtCore import QBuffer, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

BLUE_LIGHT = QColor("#5b9bff")
BLUE = QColor("#1a73e8")
BLUE_DARK = QColor("#1558c0")
YELLOW = QColor("#fbbc04")
TICK = QColor("#c6d6f2")


def draw_icon(p, rect, arc=1.0, turn=0.0, clock=None):
    # arc: dış okun ne kadarı çizilsin (0-1). turn: akrep/yelkovan kaç tur geri dönsün.
    # clock: (saat, dakika, saniye) verilirse ibreler o saati gösterir; saniye None olabilir.
    s = rect.width()
    cx, cy = rect.center().x(), rect.center().y()
    p.save()
    p.setRenderHint(QPainter.Antialiasing)

    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0, BLUE_LIGHT)
    grad.setColorAt(1, BLUE_DARK)
    p.setPen(Qt.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(rect, s * 0.23, s * 0.23)

    # Saat kadranı
    p.setBrush(Qt.white)
    face = s * 0.29
    p.drawEllipse(QPointF(cx, cy), face, face)
    p.setBrush(TICK)
    for i in range(4):
        a = i * math.pi / 2
        p.drawEllipse(QPointF(cx + math.cos(a) * face * 0.78, cy + math.sin(a) * face * 0.78), s * 0.018, s * 0.018)

    # Saatin etrafında saat yönünün tersine dönen ok ("zamanda geri")
    if arc > 0:
        r = s * 0.385
        start, sweep = 70.0, 290.0 * arc
        pen = QPen(Qt.white, s * 0.055, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), int(start * 16), int(sweep * 16))
        end = math.radians(start + sweep)
        tip_base = QPointF(cx + r * math.cos(end), cy - r * math.sin(end))
        d = QPointF(-math.sin(end), -math.cos(end))   # ilerleme yönü
        n = QPointF(math.cos(end), -math.sin(end))    # dışa doğru
        h, w = s * 0.11, s * 0.075
        head = QPainterPath(tip_base + d * h)
        head.lineTo(tip_base + n * w)
        head.lineTo(tip_base - n * w)
        head.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(Qt.white)
        p.drawPath(head)

    # Varsayılan: akrep 10'da, yelkovan 12'de (simgedeki duruş); turn kadar geri döner
    def hand(angle_deg, length, width):
        a = math.radians(angle_deg)
        p.setPen(QPen(BLUE, width, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(cx, cy), QPointF(cx + math.sin(a) * length, cy - math.cos(a) * length))

    hour, minute, second = clock if clock else (10, 0, None)
    hand(hour * 30 - turn * 30, face * 0.48, s * 0.05)
    hand(minute * 6 - turn * 360, face * 0.72, s * 0.042)
    if second is not None:
        a = math.radians(second * 6 - turn * 1080)
        p.setPen(QPen(YELLOW, s * 0.016, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(cx - math.sin(a) * face * 0.15, cy + math.cos(a) * face * 0.15),
                   QPointF(cx + math.sin(a) * face * 0.8, cy - math.cos(a) * face * 0.8))
    p.setPen(Qt.NoPen)
    p.setBrush(YELLOW)
    p.drawEllipse(QPointF(cx, cy), s * 0.038, s * 0.038)
    p.restore()


def icon_image(size):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    m = size * 0.04
    draw_icon(p, QRectF(m, m, size - 2 * m, size - 2 * m))
    p.end()
    return img


def app_icon():
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(QPixmap.fromImage(icon_image(size)))
    return icon


if __name__ == "__main__":
    from PIL import Image
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication([])
    buf = QBuffer()
    buf.open(QBuffer.WriteOnly)
    icon_image(256).save(buf, "PNG")
    out = Path(__file__).resolve().parent / "assets" / "icon.ico"
    out.parent.mkdir(exist_ok=True)
    Image.open(io.BytesIO(bytes(buf.data()))).save(out, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    icon_image(512).save(str(out.with_name("icon.png")))
    print(out)
