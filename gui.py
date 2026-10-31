"""
Zaman Makinesi - masaüstü arayüzü.
    uv run gui.py
Videoya saat basma işini main.py yapar; burası sadece kullanıcıdan video ve tarihleri toplar.
Kurallar için TASARIM.md'ye bakın.
"""

import logging
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from string import Template

import cv2
from PySide6.QtCore import (QEasingCurve, QParallelAnimationGroup, QPointF, QPropertyAnimation, QRectF, QSettings, QStandardPaths, Qt,
                            QThread, QTimer, QUrl, QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QDesktopServices, QFont, QImage, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QDialog, QFileDialog, QFrame,
                               QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
                               QProgressBar, QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget)

import main
import updater
from icon import YELLOW, app_icon, draw_icon
from version import __version__

APP_NAME = "Zaman Makinesi"
DATE_FORMAT = "%d.%m.%Y %H:%M:%S"
MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
          "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

log = logging.getLogger("zaman-makinesi")

# Bir işin (video + tarih) durumları
READY, QUEUED, RUNNING, DONE, EXISTS, ERROR = "ready", "queued", "running", "done", "exists", "error"

# =============================================================================
# Tema
# =============================================================================

LIGHT = dict(bg="#f8f9fa", card="#ffffff", border="#dadce0", divider="#eceff1", text="#202124", muted="#5f6368",
             primary="#1a73e8", primary_hover="#1765cc", on_primary="#ffffff", soft="#e8f0fe", soft_text="#174ea6",
             danger="#d93025", danger_hover="#c5221f", danger_soft="#fce8e6", ok="#188038", warn="#b06000", field="#ffffff",
             readonly="#f1f3f4", disabled="#e8eaed", disabled_text="#9aa0a6", thumb="#202124", track="#e8eaed")
DARK = dict(bg="#202124", card="#292a2d", border="#5f6368", divider="#3c4043", text="#e8eaed", muted="#9aa0a6",
            primary="#8ab4f8", primary_hover="#aecbfa", on_primary="#202124", soft="#2f3b50", soft_text="#d2e3fc",
            danger="#f28b82", danger_hover="#f6aea9", danger_soft="#4a2c2a", ok="#81c995", warn="#fdd663", field="#202124",
            readonly="#35363a", disabled="#3c4043", disabled_text="#80868b", thumb="#000000", track="#3c4043")

# O anki renkler. Kendi kendini çizen parçalar (saat, sürükleme katmanı) buradan okur.
theme = dict(LIGHT)

STYLE = Template("""
QWidget { font-size: 13px; color: $text; }
#central, QDialog, QMessageBox { background: $bg; }
#card { background: $card; border: 1px solid $border; border-radius: 14px; }
#list, #listInner { background: $card; }
#videoRow { background: $card; border-bottom: 1px solid $divider; }
#videoRow[highlight="true"] { background: $soft; }
#divider { background: $divider; }
#title { font-size: 16px; font-weight: 600; }
#dialogTitle { font-size: 17px; font-weight: 600; }
#settingsCard { background: $card; border: 1px solid $border; border-radius: 12px; }
#settingsCard QLabel { background: transparent; }
#cardTitle { font-size: 14px; font-weight: 600; }
QPushButton#segLeft, QPushButton#segMid, QPushButton#segRight { border-radius: 0; padding: 6px 14px; }
QPushButton#segLeft { border-top-left-radius: 17px; border-bottom-left-radius: 17px; }
QPushButton#segMid { border-left: none; border-right: none; }
QPushButton#segRight { border-top-right-radius: 17px; border-bottom-right-radius: 17px; }
QPushButton#segLeft:checked, QPushButton#segMid:checked, QPushButton#segRight:checked {
    background: $primary; color: $on_primary; border-color: $primary; }
#muted { color: $muted; }
#small { color: $muted; font-size: 12px; }
#fileName { font-weight: 600; }
#error { color: $danger; }
#ok { color: $ok; }
#warn { color: $warn; }
QPushButton { border: 1px solid $border; border-radius: 17px; padding: 6px 18px; min-height: 22px;
              background: $card; color: $primary; font-weight: 600; }
QPushButton:hover { background: $soft; }
QPushButton:checked { background: $primary; color: $on_primary; border-color: $primary; }
QPushButton:disabled { color: $disabled_text; background: $disabled; border-color: $disabled; }
QPushButton#primary { background: $primary; color: $on_primary; border: none; padding: 7px 22px; }
QPushButton#primary:hover { background: $primary_hover; }
QPushButton#danger { background: $danger; color: $on_primary; border: none; padding: 7px 22px; }
QPushButton#danger:hover { background: $danger_hover; }
QLineEdit { border: 1px solid $border; border-radius: 8px; padding: 6px 8px; background: $field; color: $text;
            font-family: $mono; font-size: 14px; }
QLineEdit:focus { border: 2px solid $primary; padding: 5px 7px; }
QLineEdit[invalid="true"] { border: 2px solid $danger; padding: 5px 7px; }
QLineEdit:read-only { background: $readonly; color: $muted; }
QToolButton { border: none; color: $primary; padding: 4px 8px; border-radius: 6px; background: transparent; }
QToolButton:hover { background: $soft; }
QToolButton:disabled { color: $disabled_text; }
QToolButton#remove { color: $muted; font-size: 16px; padding: 2px 8px; }
QToolButton#remove:hover { background: $danger_soft; color: $danger; }
QCheckBox { spacing: 8px; }
QProgressBar { border: none; background: $track; border-radius: 3px; }
QProgressBar::chunk { background: $primary; border-radius: 3px; }
#dropZone { border: 2px dashed $border; border-radius: 12px; }
#dropZone QLabel { color: $muted; }
#banner { background: $soft; border-radius: 10px; }
#banner QLabel, #info { color: $soft_text; }
#info { background: $soft; border-radius: 8px; padding: 10px 12px; }
#thumb { background: $thumb; border-radius: 6px; color: $disabled_text; }
""")


def apply_theme(choice):
    # choice: "system", "light" veya "dark"
    app = QApplication.instance()
    hints = app.styleHints()
    hints.setColorScheme({"light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark}.get(choice, Qt.ColorScheme.Unknown))
    theme.clear()
    dark = choice == "dark" or (choice == "system" and hints.colorScheme() == Qt.ColorScheme.Dark)
    theme.update(DARK if dark else LIGHT)
    # Kaydırma çubuğu, onay kutusu, mesaj pencereleri gibi standart parçalar da aynı renkleri kullansın
    palette = QPalette()
    for role, key in ((QPalette.Window, "bg"), (QPalette.WindowText, "text"), (QPalette.Base, "field"),
                      (QPalette.AlternateBase, "card"), (QPalette.Text, "text"), (QPalette.Button, "card"),
                      (QPalette.ButtonText, "text"), (QPalette.Highlight, "primary"),
                      (QPalette.HighlightedText, "on_primary"), (QPalette.ToolTipBase, "card"),
                      (QPalette.ToolTipText, "text"), (QPalette.PlaceholderText, "muted"), (QPalette.Mid, "border"),
                      (QPalette.Dark, "border"), (QPalette.Light, "card"), (QPalette.Midlight, "divider")):
        palette.setColor(role, QColor(theme[key]))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor(theme["disabled_text"]))
    app.setPalette(palette)
    mono = "Consolas" if sys.platform == "win32" else "Menlo"
    app.setStyleSheet(STYLE.substitute(theme, mono=mono))
    for w in app.topLevelWidgets():
        w.update()


# =============================================================================
# Yardımcılar
# =============================================================================

def repolish(widget, name, value):
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def fade_in(widget, ms=280):
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget, duration=ms, startValue=0.0, endValue=1.0,
                              easingCurve=QEasingCurve.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start()


def collapse_out(widget, ms=240):
    # Satırı soldurup boyunu sıfırlayarak kaldırır, sonra siler
    widget.setEnabled(False)
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    group = QParallelAnimationGroup(widget)
    group.addAnimation(QPropertyAnimation(effect, b"opacity", duration=ms, startValue=1.0, endValue=0.0))
    group.addAnimation(QPropertyAnimation(widget, b"maximumHeight", duration=ms, startValue=widget.height(),
                                          endValue=0, easingCurve=QEasingCurve.InOutCubic))
    group.finished.connect(widget.deleteLater)
    group.start()


def ease(t, curve=QEasingCurve.OutCubic):
    return QEasingCurve(curve).valueForProgress(min(max(t, 0.0), 1.0))


def frame_to_pixmap(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    return QPixmap.fromImage(QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888).copy())


def read_first_frame(path):
    cap = main.open_video(path)
    try:
        if not cap.isOpened():
            return None, None
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        ok, frame = cap.read()
        if not ok:
            return None, None
        secs = int(frames / fps) if frames > 0 else 0
        h, w = frame.shape[:2]
        short = min(w, h)
        res = "4K" if short >= 2160 else f"{short}p"
        dur = f"{secs // 3600}:{secs // 60 % 60:02}:{secs % 60:02}" if secs >= 3600 else f"{secs // 60:02}:{secs % 60:02}"
        return frame, f"{dur} · {res}"
    finally:
        cap.release()


def reveal(path):
    # Dosyayı Gezgin'de / Finder'da seçili olarak gösterir
    if sys.platform == "win32":
        subprocess.Popen(f'explorer /select,"{path}"')
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))


def duration_text(secs):
    secs = int(secs)
    return f"{secs // 60} dk {secs % 60:02} sn" if secs >= 60 else f"{secs} sn"


def gb(n):
    return f"{n / 1e9:.1f} GB".replace(".", ",")


def free_space(folder):
    # Klasör henüz yoksa var olan en yakın üst klasörün diskine bakılır
    while not folder.exists() and folder != folder.parent:
        folder = folder.parent
    return shutil.disk_usage(folder).free


def friendly_error(exc, src, dst):
    # Teknik hatayı kullanıcının anlayacağı bir cümleye çevirir; ayrıntı hata kaydına yazılır
    try:
        if free_space(dst.parent) < 200_000_000:
            return "Diskte yer kalmadı"
    except OSError:
        pass
    if not src.exists():
        return "Video bulunamadı (taşınmış veya silinmiş olabilir)"
    if isinstance(exc, PermissionError):
        return "Çıktı klasörüne yazma izni yok"
    if "açılamadı" in str(exc) or "okunamadı" in str(exc):
        return "Video okunamadı (dosya bozuk olabilir)"
    return "Video kaydedilemedi"


@contextmanager
def keep_awake():
    # İşlem sürerken bilgisayar uykuya geçmesin (ekran yine kapanabilir)
    if sys.platform == "win32":
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        try:
            yield
        finally:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    elif sys.platform == "darwin":
        proc = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
        try:
            yield
        finally:
            proc.terminate()
    else:
        yield


def log_path():
    folder = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "zaman-makinesi.log"


def setup_log():
    handler = RotatingFileHandler(log_path(), maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.info("Açıldı: sürüm %s, %s", __version__, sys.platform)


def month_folder(start):
    return f"{start:%Y-%m} {MONTHS[start.month - 1]}"


def output_path(out_dir, src, start, monthly=True):
    # Ör. Zaman Makinesi/2026-10 Ekim/deniz_kenari_12_10_2026_14_30_00.mp4
    folder = out_dir / month_folder(start) if monthly else out_dir
    return folder / f"{src.stem}_{start:%d_%m_%Y_%H_%M_%S}.mp4"


# =============================================================================
# Saatler ve animasyonlu parçalar
# =============================================================================

class Logo(QWidget):
    """Uygulama simgesi. İbreler gerçek saati gösterir; işleme sırasında geriye döner."""

    def __init__(self, size):
        super().__init__()
        self.setFixedSize(size, size)
        self.spinning = False
        self.spin = 0.0
        self.last = time.monotonic()
        self.timer = QTimer(self, interval=33)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def set_spinning(self, on):
        self.spinning = on

    def _tick(self):
        now = time.monotonic()
        dt, self.last = now - self.last, now
        if self.spinning:
            self.spin += dt * 0.7
        elif self.spin:
            # Durunca en yakın tam tura süzülüp gerçek saate döner
            rest = self.spin % 1
            self.spin = self.spin - rest if rest < dt * 1.5 else self.spin - dt * 1.5
        if self.isVisible():
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        now = datetime.now()
        # Saniye ibresi her saniyede küçük bir yaylanmayla ilerler
        second = now.second - 1 + ease(now.microsecond / 250000, QEasingCurve.OutBack)
        minute = now.minute + now.second / 60
        hour = now.hour % 12 + minute / 60
        s = self.width()
        draw_icon(p, QRectF(0, 0, s, s), turn=self.spin,
                  clock=(hour, minute, second if s >= 64 else None))


class Clock(Logo):
    """Sol üstteki sade analog saat. Logo gibi gerçek saati gösterir, işleme sırasında geriye döner."""

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self.width()
        c = QPointF(s / 2, s / 2)
        r = s / 2 - s * 0.06
        p.setPen(QPen(QColor(theme["primary"]), max(s * 0.06, 1.5)))
        p.setBrush(QColor(theme["card"]))
        p.drawEllipse(c, r, r)

        now = datetime.now()
        minute = now.minute + now.second / 60
        hour = now.hour % 12 + minute / 60
        back = self.spin * 360

        def hand(angle, length, width):
            p.save()
            p.translate(c)
            p.rotate(angle)
            p.setPen(QPen(QColor(theme["text"]), width, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(0, r * 0.12), QPointF(0, -length))
            p.restore()

        hand(hour * 30 - back / 12, r * 0.5, max(s * 0.07, 2.2))
        hand(minute * 6 - back, r * 0.75, max(s * 0.05, 1.6))
        p.setPen(Qt.NoPen)
        p.setBrush(YELLOW)
        p.drawEllipse(c, s * 0.05, s * 0.05)


class TimeBuddy(QWidget):
    """Zaman Adam: kollu bacaklı küçük çalar saat. "run" modunda koşar, "wave" modunda el sallar."""

    def __init__(self, size, mode="run"):
        super().__init__()
        self.setFixedSize(size, size)
        self.mode = mode
        self.phase = 0.0
        self.timer = QTimer(self, interval=33)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _tick(self):
        if self.isVisible():
            self.phase += 0.033
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(self.width() / 100, self.height() / 100)  # 100x100'lük bir kutuda çizilir
        t = self.phase
        run = self.mode == "run"
        swing = math.sin(t * 12) if run else 0.0
        p.translate(0, -4 * abs(swing) if run else 1.5 * math.sin(t * 2))
        ink = QColor(theme["text"])
        limb = QPen(ink, 5, Qt.SolidLine, Qt.RoundCap)

        def limb_end(x, y, angle, length):
            # angle: aşağıdan saat yönünde derece; pozitif = öne (sağa)
            a = math.radians(angle)
            end = QPointF(x + math.sin(a) * length, y + math.cos(a) * length)
            p.setPen(limb)
            p.drawLine(QPointF(x, y), end)
            return end

        if run:  # arkada hız çizgileri
            p.setPen(QPen(QColor(theme["border"]), 3, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(4, 38), QPointF(14, 38))
            p.drawLine(QPointF(0, 50), QPointF(12, 50))

        # Bacaklar ve ayaklar
        for x, sign in ((43, 1), (57, -1)):
            foot = limb_end(x, 68, 30 * swing * sign, 18)
            p.setPen(Qt.NoPen)
            p.setBrush(ink)
            p.drawEllipse(foot + QPointF(2, 0), 5, 3)

        # Kollar: koşarken bacakların tersine sallanır, beklerken biri el sallar
        if run:
            arms = ((26, 48, -25 - 40 * swing), (74, 48, 25 + 40 * swing))
        else:
            arms = ((26, 48, -30), (74, 44, 145 + 25 * math.sin(t * 7)))
        for x, y, angle in arms:
            hand = limb_end(x, y, angle, 15)
            p.setPen(Qt.NoPen)
            p.setBrush(ink)
            p.drawEllipse(hand, 3.5, 3.5)

        # Çalar saat zilleri ve gövde
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme["primary"]))
        p.drawEllipse(QPointF(31, 20), 8, 8)
        p.drawEllipse(QPointF(69, 20), 8, 8)
        p.drawEllipse(QPointF(50, 45), 27, 27)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QPointF(50, 45), 21, 21)
        p.setBrush(QColor("#c6d6f2"))
        for dx, dy in ((0, -16), (16, 0), (0, 16), (-16, 0)):
            p.drawEllipse(QPointF(50 + dx, 45 + dy), 1.8, 1.8)

        # Yüz: arada bir göz kırpar
        eye = 0.6 if t % 3.5 < 0.12 else 3.4
        p.setBrush(QColor("#202124"))
        p.drawEllipse(QPointF(43, 41), 2.6, eye)
        p.drawEllipse(QPointF(57, 41), 2.6, eye)
        p.setPen(QPen(QColor("#202124"), 2.5, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(43, 42, 14, 10), 200 * 16, 140 * 16)


class DropOverlay(QWidget):
    """Video sürüklenirken bütün pencerenin üstüne gelen katman."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.hide()
        self.level = 0.0
        self.turn = 0.0
        self.anim = QVariantAnimation(self, duration=180, easingCurve=QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(self._set_level)
        self.anim.finished.connect(self._faded)
        self.spin = QTimer(self, interval=16)
        self.spin.timeout.connect(self._spin)

    def appear(self):
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()
        self.spin.start()
        self._animate(1.0)

    def disappear(self):
        self._animate(0.0)

    def _animate(self, target):
        self.anim.stop()
        self.anim.setStartValue(self.level)
        self.anim.setEndValue(target)
        self.anim.start()

    def _set_level(self, value):
        self.level = value
        self.update()

    def _faded(self):
        if self.level == 0.0:
            self.hide()
            self.spin.stop()

    def _spin(self):
        self.turn += 0.012
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setOpacity(self.level)
        bg = QColor(theme["soft"])
        bg.setAlpha(240)
        p.setBrush(bg)
        pen = QPen(QColor(theme["primary"]), 3, Qt.DashLine)
        p.setPen(pen)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(10, 10, -10, -10), 18, 18)

        size = 128 * (0.8 + 0.2 * self.level)
        cx, cy = self.width() / 2, self.height() / 2 - 40
        draw_icon(p, QRectF(cx - size / 2, cy - size / 2, size, size), turn=self.turn)

        font = QFont(self.font())
        font.setPixelSize(24)
        font.setWeight(QFont.DemiBold)
        p.setFont(font)
        p.setPen(QColor(theme["soft_text"]))
        p.drawText(QRectF(0, cy + size / 2 + 18, self.width(), 34), Qt.AlignCenter, "Videoları bırakın")
        font.setPixelSize(14)
        font.setWeight(QFont.Normal)
        p.setFont(font)
        p.drawText(QRectF(0, cy + size / 2 + 54, self.width(), 22), Qt.AlignCenter,
                   "Her videonun yanında tarih alanı açılacak")


class DropZone(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("dropZone")
        self.clock = Logo(128)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 24)
        layout.setSpacing(18)
        layout.addStretch()
        layout.addWidget(self.clock, 0, Qt.AlignCenter)
        layout.addWidget(self.label)
        layout.addStretch()
        self.set_empty(True)

    def set_empty(self, empty):
        self.clock.setVisible(empty)
        if empty:
            self.label.setText("Videoları buraya sürükleyip bırakın\nveya yukarıdaki “Video ekle” butonuna tıklayın")
            self.setMinimumHeight(300)
            self.layout().setContentsMargins(16, 24, 16, 24)
        else:
            self.label.setText("⤓  Daha fazla video için pencerenin herhangi bir yerine sürükleyip bırakın")
            self.setMinimumHeight(56)
            self.layout().setContentsMargins(16, 8, 16, 8)


# =============================================================================
# Liste satırları
# =============================================================================

class DateEdit(QLineEdit):
    def __init__(self):
        super().__init__()
        self.setInputMask("00.00.0000 00:00:00;_")
        self.setFixedWidth(190)
        self.setToolTip("GG.AA.YYYY SS:DD:SS")
        self.setAcceptDrops(False)  # sürüklenen video dosyası tarih alanına yazılmasın

    def is_blank(self):
        return not re.sub(r"\D", "", self.text())

    # Boş alana tıklanınca imleç tıklanan yerde değil en başta olsun
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if self.is_blank():
            self.setCursorPosition(0)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if self.is_blank():
            QTimer.singleShot(0, self, lambda: self.setCursorPosition(0))


class DateRow(QWidget):
    changed = Signal()
    completed = Signal(str)          # geçerli bir tarih yazıldı
    next_requested = Signal(object)  # Enter'a basıldı
    def __init__(self):
        super().__init__()
        self.state = READY
        self.progress = 0.0
        self.message = ""      # hata mesajı (işleme sırasında)
        self.problem = ""      # tarih alanındaki sorun ("Geçersiz tarih" gibi); işlenmez
        self.warning = ""      # işlenir ama kullanıcıya sorulur ("Gelecekte bir tarih" gibi)
        self.touched = False   # kullanıcı alandan çıktı mı (eksik tarih uyarısı için)
        self.locked = False
        self.output = None

        self.edit = DateEdit()
        self.edit.textChanged.connect(self._on_edit)
        self.edit.editingFinished.connect(self._on_leave)
        self.edit.returnPressed.connect(lambda: self.next_requested.emit(self))

        self.buddy = TimeBuddy(38)
        self.started = 0.0
        self.ticker = QTimer(self, interval=500)  # işlenirken geçen süreyi günceller
        self.ticker.timeout.connect(self.render)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setFixedSize(120, 6)
        self.status = QLabel()
        self.show_btn = QToolButton(text="Göster")
        self.show_btn.setToolTip("Çıktıyı klasöründe göster")
        self.show_btn.clicked.connect(lambda: self.output and reveal(self.output))
        self.show_btn.setFocusPolicy(Qt.ClickFocus)  # Tab sadece tarih alanları arasında gezsin

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.edit)
        layout.addSpacing(10)
        layout.addWidget(self.buddy)
        layout.addWidget(self.bar)
        layout.addSpacing(4)
        layout.addWidget(self.status, 1)
        layout.addWidget(self.show_btn)
        self.render()

    def digits(self):
        return re.sub(r"\D", "", self.edit.text())

    def is_empty(self):
        return not self.digits()

    def value(self):
        if len(self.digits()) != 14:
            return None
        try:
            return datetime.strptime(self.edit.text(), DATE_FORMAT)
        except ValueError:
            return None

    def is_job(self):
        return not self.is_empty() and not self.problem

    def is_pending(self):
        return self.is_job() and self.state in (READY, ERROR)

    def _on_edit(self):
        if self.state == ERROR:
            self.state = READY
        self.changed.emit()
        if self.value() is not None:
            self.completed.emit(self.edit.text())

    def _on_leave(self):
        self.touched = True
        self.changed.emit()

    def set_state(self, state, progress=0.0, message="", output=None):
        appeared = state in (DONE, EXISTS) and self.state != state
        if state == RUNNING and self.state != RUNNING:
            self.started = time.monotonic()
            self.ticker.start()
        elif state != RUNNING:
            self.ticker.stop()
        self.state, self.progress, self.message = state, progress, message
        if output:
            self.output = output
        self.render()
        if appeared:
            fade_in(self.status, 400)
            fade_in(self.show_btn, 400)

    def set_locked(self, locked):
        self.locked = locked
        self.render()

    def render(self):
        finished = self.state in (DONE, EXISTS)
        self.edit.setReadOnly(self.locked or finished)
        visible_problem = self.problem and (self.touched or len(self.digits()) == 14)
        repolish(self.edit, "invalid", bool(visible_problem))

        self.bar.setVisible(self.state == RUNNING)
        self.buddy.setVisible(self.state == RUNNING)
        self.bar.setValue(int(self.progress * 1000))
        self.show_btn.setVisible(finished and self.output is not None)

        if visible_problem:
            text, style = self.problem, "error"
        elif self.state == QUEUED:
            text, style = "Sırada", "muted"
        elif self.state == RUNNING:
            elapsed = duration_text(time.monotonic() - self.started)
            text, style = f"%{int(self.progress * 100)}  ·  {elapsed}", "muted"
        elif self.state == DONE:
            text, style = "✓  Tamamlandı" + (f"  ·  {self.message} sürdü" if self.message else ""), "ok"
        elif self.state == EXISTS:
            text, style = "✓  Zaten vardı, atlandı", "muted"
        elif self.state == ERROR:
            text, style = f"⚠  {self.message}", "error"
        elif self.warning:
            text, style = f"⚠  {self.warning}", "warn"
        else:
            text, style = "", "muted"
        self.status.setText(text)
        self.status.setToolTip(str(self.output) if finished and self.output else
                               self.message if self.state == ERROR else "")
        self.status.setObjectName(style)
        repolish(self.status, "s", style)


class VideoRow(QFrame):
    changed = Signal()
    date_completed = Signal(str)
    next_requested = Signal(object)                # DateRow
    remove_requested = Signal(object)

    def __init__(self, path):
        super().__init__()
        self.setObjectName("videoRow")
        self.path = path
        self.dates = []
        self.locked = False

        frame, info = read_first_frame(path)
        self.readable = frame is not None

        thumb = QLabel()
        thumb.setObjectName("thumb")
        thumb.setFixedSize(96, 54)
        thumb.setAlignment(Qt.AlignCenter)
        if frame is not None:
            pix = frame_to_pixmap(frame).scaled(96, 54, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            thumb.setPixmap(pix.copy((pix.width() - 96) // 2, (pix.height() - 54) // 2, 96, 54))
        else:
            thumb.setText("?")

        name = QLabel()
        name.setObjectName("fileName")
        name.setToolTip(str(path))
        name.setText(name.fontMetrics().elidedText(path.name, Qt.ElideMiddle, 220))
        detail = QLabel(info if self.readable else "Video açılamadı")
        detail.setObjectName("small" if self.readable else "error")
        self.remove_btn = QToolButton(text="Kaldır")
        self.remove_btn.setFocusPolicy(Qt.ClickFocus)
        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))

        # Video bilgisi sütunu sabit genişlikte olsun ki tarih alanları alt alta hizalansın
        about_box = QWidget()
        about_box.setFixedWidth(230)
        about = QVBoxLayout(about_box)
        about.setContentsMargins(0, 0, 0, 0)
        about.setSpacing(2)
        about.addWidget(name)
        about.addWidget(detail)
        about.addWidget(self.remove_btn, 0, Qt.AlignLeft)
        about.addStretch()

        self.date_list = QVBoxLayout()
        self.date_list.setSpacing(8)
        self.add_btn = QToolButton(text="+ Tarih ekle")
        self.add_btn.setFocusPolicy(Qt.ClickFocus)
        self.add_btn.clicked.connect(lambda: self.add_date(focus=True))
        self.del_btn = QToolButton(text="−  Son tarihi sil")
        self.del_btn.setToolTip("En alttaki tarihi siler")
        self.del_btn.setFocusPolicy(Qt.ClickFocus)
        self.del_btn.clicked.connect(self.remove_last_date)
        date_buttons = QHBoxLayout()
        date_buttons.setSpacing(4)
        date_buttons.addWidget(self.add_btn)
        date_buttons.addWidget(self.del_btn)
        date_buttons.addStretch()
        dates = QVBoxLayout()
        dates.setSpacing(8)
        dates.addLayout(self.date_list)
        dates.addLayout(date_buttons)
        dates.addStretch()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)
        layout.addWidget(thumb, 0, Qt.AlignTop)
        layout.addWidget(about_box)
        layout.addLayout(dates, 1)

        self.add_btn.setVisible(self.readable)
        if self.readable:
            self.add_date()

    def add_date(self, focus=False, text=""):
        row = DateRow()
        if text:
            row.edit.setText(text)
        row.changed.connect(self.validate)
        row.completed.connect(self.date_completed)
        row.next_requested.connect(self.next_requested)
        self.dates.append(row)
        self.date_list.addWidget(row)
        if focus:
            row.edit.setFocus()
            fade_in(row)
        self.validate()

    def removable(self):
        # Silinebilecek en alttaki tarih (biten tarihler silinmez; tek tarih kalırsa da silinmez)
        open_rows = [d for d in self.dates if d.state not in (DONE, EXISTS)]
        return open_rows[-1] if len(self.dates) > 1 and open_rows else None

    def remove_last_date(self):
        row = self.removable()
        if row:
            self.remove_date(row)

    def remove_date(self, row, animate=True):
        self.dates.remove(row)
        if animate:
            collapse_out(row)
        else:
            row.deleteLater()
        self.validate()

    def remove_finished(self):
        # Kaldırılan satır sayısını döner
        finished = [d for d in self.dates if d.state in (DONE, EXISTS)]
        for row in finished:
            self.remove_date(row)
        return len(finished)

    def validate(self):
        seen = set()
        now = datetime.now()
        for row in self.dates:
            value = row.value()
            row.warning = "Gelecekte bir tarih, doğru mu?" if value and value > now else ""
            if row.is_empty():
                row.problem = ""
            elif len(row.digits()) < 14:
                row.problem = "Tarih eksik"
            elif value is None:
                row.problem = "Geçersiz tarih"
            elif value in seen:
                row.problem = "Bu tarih zaten ekli"
            else:
                row.problem = ""
                seen.add(value)
            row.render()
        self.del_btn.setVisible(self.removable() is not None)
        self.changed.emit()

    def problems(self):
        # İşlenemeyecek tarihler: [(DateRow veya None, açıklama)]
        if not self.readable:
            return [(None, "video açılamadı")]
        bad = [(d, f"{d.edit.text()} — {d.problem.lower()}") for d in self.dates if d.problem]
        if not bad and not any(d.is_job() for d in self.dates):
            first = self.dates[0] if self.dates else None
            bad = [(first, "tarih girilmedi")]
        return bad

    def is_unprocessed(self):
        # Kapanışta uyarmak için: işlenmeyi bekleyen ya da hiç tarihi girilmemiş video
        if not self.readable:
            return False
        jobs = [d for d in self.dates if d.is_job()]
        return any(d.is_pending() for d in jobs) or not jobs

    def set_locked(self, locked):
        self.locked = locked
        self.remove_btn.setEnabled(not locked)
        self.add_btn.setEnabled(not locked)
        self.del_btn.setEnabled(not locked)
        for row in self.dates:
            row.set_locked(locked)

    def highlight(self):
        repolish(self, "highlight", True)
        QTimer.singleShot(1200, self, lambda: repolish(self, "highlight", False))


# =============================================================================
# Arka planda video işleme
# =============================================================================

class Worker(QThread):
    progress = Signal(object, float)            # DateRow, 0-1
    job_finished = Signal(object, str, str)     # DateRow, durum, mesaj

    def __init__(self, jobs):
        super().__init__()
        self.jobs = jobs  # [(DateRow, kaynak, hedef, başlangıç, üzerine_yaz)]
        self.stopped = False

    def stop(self):
        self.stopped = True

    def run(self):
        with keep_awake():
            self._run()

    def _run(self):
        for row, src, dst, start, overwrite in self.jobs:
            if self.stopped:
                return
            if dst.exists() and not overwrite:
                self.job_finished.emit(row, EXISTS, "")
                continue
            self.progress.emit(row, 0.0)
            log.info("İşleniyor: %s -> %s", src, dst)
            began = time.monotonic()
            try:
                main.process(src, dst, start,
                             on_progress=lambda f, row=row: self.progress.emit(row, f),
                             should_stop=lambda: self.stopped)
                took = duration_text(max(round(time.monotonic() - began), 1))
                log.info("Bitti (%s): %s", took, dst)
                self.job_finished.emit(row, DONE, took)
            except main.Cancelled:
                log.info("Durduruldu: %s", src)
                self.job_finished.emit(row, READY, "")
                return
            except Exception as e:
                log.exception("Hata: %s", src)
                self.job_finished.emit(row, ERROR, friendly_error(e, src, dst))


# =============================================================================
# Pencereler
# =============================================================================

def ask(parent, title, text, details, yes, no, default_yes=True):
    """Büyük, açık butonlu soru penceresi. yes tıklanırsa True döner."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Warning)
    box.setText(f"<b>{text}</b>")
    box.setInformativeText(details)
    yes_btn = box.addButton(yes, QMessageBox.AcceptRole) if yes else None
    no_btn = box.addButton(no, QMessageBox.RejectRole)
    # Varsayılan (Enter'a basınca seçilen) buton mavi olur; tehlikeli seçenek varsayılan yapılmaz
    default = yes_btn if yes_btn and default_yes else no_btn
    default.setObjectName("primary")
    repolish(default, "s", True)
    box.setDefaultButton(default)
    box.exec()
    return yes_btn is not None and box.clickedButton() is yes_btn


class SettingsDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.main = window
        self.setWindowTitle("Ayarlar")
        self.setFixedWidth(560)
        self.check = None

        def card(title, hint, *rows):
            box = QFrame()
            box.setObjectName("settingsCard")
            layout = QVBoxLayout(box)
            layout.setContentsMargins(18, 14, 18, 16)
            layout.setSpacing(8)
            heading = QLabel(title)
            heading.setObjectName("cardTitle")
            layout.addWidget(heading)
            if hint:
                sub = QLabel(hint)
                sub.setObjectName("small")
                layout.addWidget(sub)
            layout.addSpacing(2)
            for row in rows:
                layout.addLayout(row) if isinstance(row, QHBoxLayout) else layout.addWidget(row)
            return box

        # Üst: el sallayan Zaman Adam
        buddy = TimeBuddy(72, mode="wave")
        hello = QLabel("Ayarlar")
        hello.setObjectName("dialogTitle")
        version = QLabel(f"{APP_NAME} · sürüm {__version__}")
        version.setObjectName("muted")
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addStretch()
        titles.addWidget(hello)
        titles.addWidget(version)
        titles.addStretch()
        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(buddy)
        top.addLayout(titles, 1)

        # Görünüm: bitişik üç seçenek
        themes = QHBoxLayout()
        themes.setSpacing(0)
        group = QButtonGroup(self)
        choices = (("system", "Sistem"), ("light", "Açık"), ("dark", "Koyu"))
        for i, (key, text) in enumerate(choices):
            b = QPushButton(text)
            b.setObjectName(("segLeft", "segMid", "segRight")[i])
            b.setCheckable(True)
            b.setChecked(window.theme_choice == key)
            b.setMinimumWidth(110)
            b.clicked.connect(lambda _=False, k=key: window.set_theme(k))
            group.addButton(b)
            themes.addWidget(b)
        themes.addStretch()

        # Çıktılar
        self.out_path = QLabel()
        self.out_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        change = QPushButton("Değiştir")
        change.clicked.connect(self._pick_output)
        change.setEnabled(not window.worker)
        out_row = QHBoxLayout()
        out_row.addWidget(self.out_path, 1)
        out_row.addWidget(change)
        self.monthly = QCheckBox("Aylara göre klasörle")
        self.monthly.setChecked(window.monthly)
        self.monthly.toggled.connect(self._set_monthly)
        self.explain = QLabel()
        self.explain.setObjectName("small")
        self.example = QLabel()
        self.example.setObjectName("small")

        # Yardım
        self.update_btn = QPushButton("Güncellemeleri denetle")
        self.update_btn.clicked.connect(self._check_updates)
        log_btn = QPushButton("Hata kaydını aç")
        log_btn.clicked.connect(self._open_log)
        help_row = QHBoxLayout()
        help_row.addWidget(self.update_btn)
        help_row.addWidget(log_btn)
        help_row.addStretch()
        self.update_status = QLabel()
        self.update_status.setObjectName("small")
        self.update_status.hide()

        close = QPushButton("Kapat")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addLayout(top)
        layout.addSpacing(4)
        layout.addWidget(card("Görünüm", "Sistem seçiliyse bilgisayarınızın açık/koyu ayarına uyar.", themes))
        layout.addWidget(card("Çıktılar", "İşlenen videolar bu klasöre kaydedilir.",
                              out_row, self.monthly, self.explain, self.example))
        layout.addWidget(card("Yardım", "Bir sorun olursa hata kaydını geliştiriciye gönderebilirsiniz.",
                              help_row, self.update_status))
        layout.addSpacing(4)
        layout.addWidget(close, 0, Qt.AlignRight)
        self._refresh()

    def _refresh(self):
        w = self.main
        self.out_path.setText(self.out_path.fontMetrics().elidedText(str(w.out_dir), Qt.ElideMiddle, 360))
        self.out_path.setToolTip(str(w.out_dir))
        example = output_path(w.out_dir, Path("video.mp4"), datetime(2026, 10, 12, 14, 30), w.monthly)
        if w.monthly:
            self.explain.setText("Her ay ayrı klasör açılır: videoya basılan tarihin ayı (işlendiği gün değil).")
        else:
            self.explain.setText("Alt klasör açılmaz; tüm çıktılar doğrudan çıktı klasörüne kaydedilir.")
        self.example.setText(f"Örnek: <b>{example.relative_to(w.out_dir.parent)}</b>")

    def _pick_output(self):
        self.main.pick_output()
        self._refresh()

    def _set_monthly(self, on):
        self.main.set_monthly(on)
        self._refresh()

    def _open_log(self):
        path = log_path()
        path.touch()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _check_updates(self):
        self.update_btn.setEnabled(False)
        self.update_status.show()
        self.update_status.setText("Kontrol ediliyor…")
        self.check = updater.UpdateCheck(self)
        self.check.finished.connect(self._checked)
        self.check.start()

    def _checked(self, info):
        self.update_btn.setEnabled(True)
        if info is None:
            self.update_status.setText("Kontrol edilemedi. İnternet bağlantınızı kontrol edin.")
        elif not info.newer:
            self.update_status.setText("✓  En güncel sürümü kullanıyorsunuz.")
        else:
            self.update_status.setText(f"Yeni sürüm var: {info.latest}")
            self.main.update_info = info
            self.main.open_update()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1040, 700)
        self.setMinimumSize(900, 520)
        self.setAcceptDrops(True)
        self.settings = QSettings("ZamanMakinesi", "ZamanMakinesi")
        default_out = Path(QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)) / APP_NAME
        self.out_dir = Path(self.settings.value("output_dir", str(default_out)))
        self.monthly = self.settings.value("monthly", True, type=bool)
        self.theme_choice = self.settings.value("theme", "system")
        self.videos = []
        self.worker = None
        self.update_info = None
        self.last_date = ""

        # Güncelleme şeridi
        self.banner = QFrame()
        self.banner.setObjectName("banner")
        self.banner_text = QLabel()
        banner_update = QPushButton("Güncelle")
        banner_update.setObjectName("primary")
        banner_update.clicked.connect(self.open_update)
        banner_close = QToolButton(text="×")
        banner_close.setObjectName("remove")
        banner_close.clicked.connect(self.banner.hide)
        b = QHBoxLayout(self.banner)
        b.setContentsMargins(16, 8, 8, 8)
        b.addWidget(self.banner_text, 1)
        b.addWidget(banner_update)
        b.addWidget(banner_close)
        self.banner.hide()

        # Üst bilgi: canlı saat, başlık, ayarlar
        self.clock = Clock(30)
        self.title = QLabel()
        self.title.setObjectName("title")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("muted")
        settings_btn = QPushButton("⚙  Ayarlar")
        settings_btn.clicked.connect(lambda: SettingsDialog(self).exec())
        header = QHBoxLayout()
        header.setContentsMargins(18, 14, 16, 4)
        header.setSpacing(10)
        header.addWidget(self.clock)
        header.addWidget(self.title)
        header.addWidget(self.subtitle)
        header.addStretch()
        header.addWidget(settings_btn)

        # Araç çubuğu
        self.add_btn = QPushButton("+  Video ekle")
        self.add_btn.clicked.connect(self.pick_videos)
        self.remember = QCheckBox("Yeni videolara son girilen tarihi yaz")
        self.remember.setToolTip("İşaretliyken eklenen her videonun tarih alanı, en son yazdığınız tarihle dolu gelir.")
        self.clear_done_btn = QPushButton("Bitenleri temizle")
        self.clear_done_btn.clicked.connect(self.clear_finished)
        self.clear_btn = QPushButton("Listeyi temizle")
        self.clear_btn.clicked.connect(self.clear)
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(16, 8, 16, 12)
        toolbar.setSpacing(10)
        toolbar.addWidget(self.add_btn)
        toolbar.addSpacing(6)
        toolbar.addWidget(self.remember)
        toolbar.addStretch()
        toolbar.addWidget(self.clear_done_btn)
        toolbar.addWidget(self.clear_btn)

        # Video listesi
        self.list_layout = QVBoxLayout()
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        self.drop_zone = DropZone()
        inner = QWidget()
        inner.setObjectName("listInner")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 16)
        inner_layout.addLayout(self.list_layout)
        drop_wrap = QHBoxLayout()
        drop_wrap.setContentsMargins(16, 16, 16, 0)
        drop_wrap.addWidget(self.drop_zone)
        inner_layout.addLayout(drop_wrap)
        inner_layout.addStretch()
        self.scroll = QScrollArea()
        self.scroll.setObjectName("list")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidget(inner)

        def divider():
            line = QFrame()
            line.setObjectName("divider")
            line.setFixedHeight(1)
            return line

        # Alt çubuk: çıktı klasörü + çalıştır
        out_label = QLabel("Çıktı klasörü")
        out_label.setObjectName("small")
        self.out_path = QLabel()
        self.out_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.change_btn = QToolButton(text="Değiştir")
        self.change_btn.clicked.connect(self.pick_output)
        open_btn = QToolButton(text="Klasörü aç")
        open_btn.clicked.connect(self.open_output)
        out_row = QHBoxLayout()
        out_row.setSpacing(4)
        out_row.addWidget(self.out_path)
        out_row.addWidget(self.change_btn)
        out_row.addWidget(open_btn)
        out_row.addStretch()
        out_box = QVBoxLayout()
        out_box.setSpacing(2)
        out_box.addWidget(out_label)
        out_box.addLayout(out_row)

        self.hint = QLabel()
        self.hint.setObjectName("small")
        self.run_btn = QPushButton()
        self.run_btn.setObjectName("primary")
        self.run_btn.setMinimumWidth(200)
        self.run_btn.clicked.connect(self.run_or_stop)
        footer = QHBoxLayout()
        footer.setContentsMargins(20, 12, 16, 14)
        footer.addLayout(out_box, 1)
        footer.addWidget(self.hint)
        footer.addSpacing(8)
        footer.addWidget(self.run_btn)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(1, 1, 1, 1)
        card_layout.setSpacing(0)
        card_layout.addLayout(header)
        card_layout.addLayout(toolbar)
        card_layout.addWidget(divider())
        card_layout.addWidget(self.scroll, 1)
        card_layout.addWidget(divider())
        card_layout.addLayout(footer)

        central = QWidget()
        central.setObjectName("central")
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)
        root.addWidget(self.banner)
        root.addWidget(card, 1)
        self.setCentralWidget(central)
        self.overlay = DropOverlay(central)

        self.flash_timer = QTimer(self, singleShot=True, interval=4000)
        self.flash_timer.timeout.connect(self.refresh)
        self.refresh()

    # --- Durum ----------------------------------------------------------------

    def all_dates(self):
        return [d for v in self.videos for d in v.dates]

    def refresh(self):
        dates = self.all_dates()
        jobs = [d for d in dates if d.is_job()]
        done = sum(d.state in (DONE, EXISTS) for d in jobs)
        errors = sum(d.state == ERROR for d in jobs)
        pending = sum(d.is_pending() for d in dates)
        running = self.worker is not None

        if self.videos:
            self.title.setText(f"{len(self.videos)} video · {len(jobs)} çıktı")
            sub = f"{done} / {len(jobs)} tamamlandı" if jobs else ""
            self.subtitle.setText(sub + (f" · {errors} hata" if errors else ""))
        else:
            self.title.setText(APP_NAME)
            self.subtitle.setText("Videolarınıza zaman damgası ekleyin")
        self.drop_zone.set_empty(not self.videos)
        self.out_path.setText(self.out_path.fontMetrics().elidedText(str(self.out_dir), Qt.ElideMiddle, 340))
        self.out_path.setToolTip(str(self.out_dir))
        self.clock.set_spinning(running)

        self.add_btn.setEnabled(not running)
        self.clear_btn.setEnabled(not running and bool(self.videos))
        self.clear_done_btn.setVisible(not running and done > 0)
        self.change_btn.setEnabled(not running)

        self.run_btn.setEnabled(not (running and self.worker.stopped))
        if running:
            self.run_btn.setText("Durduruluyor…" if self.worker.stopped else "■  Durdur")
            self.run_btn.setObjectName("danger")
        else:
            self.run_btn.setText(f"▶  Videoları işle ({pending})" if pending else "▶  Videoları işle")
            self.run_btn.setObjectName("primary")
        repolish(self.run_btn, "s", running)

        if not self.flash_timer.isActive():
            self.hint.setText("İşleniyor… Pencereyi açık tutun." if running else "")
        self.update_tab_order()

    def update_tab_order(self):
        # Tab tuşu tarih alanları arasında ekrandaki sırayla gezsin
        edits = [d.edit for d in self.all_dates()]
        for a, b in zip(edits, edits[1:]):
            QWidget.setTabOrder(a, b)

    def flash(self, text):
        self.hint.setText(text)
        self.flash_timer.start()

    def focus_next_date(self, row):
        # Enter: sıradaki boş tarih alanına geç
        dates = self.all_dates()
        after = dates[dates.index(row) + 1:]
        target = next((d for d in after if d.is_empty() and not d.locked), None)
        if target:
            self.scroll.ensureWidgetVisible(target)
            target.edit.setFocus()

    def focus_date(self, row):
        video = next(v for v in self.videos if row in v.dates)
        self.scroll.ensureWidgetVisible(video)
        video.highlight()
        row.touched = True
        row.render()
        row.edit.setFocus()

    def remember_date(self, text):
        self.last_date = text

    # --- Video ekleme ---------------------------------------------------------

    def add_paths(self, paths):
        if self.worker:
            return
        files, rejected = [], 0
        for p in paths:
            if p.is_dir():
                files += main.find_videos(p)
            elif p.suffix.lower() in main.VIDEO_EXTS:
                files.append(p)
            else:
                rejected += 1
        known = {v.path.resolve(): v for v in self.videos}
        added = []
        prefill = self.last_date if self.remember.isChecked() else ""
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for f in files:
                if f.resolve() in known:
                    known[f.resolve()].highlight()
                    continue
                row = VideoRow(f)
                if prefill and row.dates:
                    row.dates[0].edit.setText(prefill)
                row.changed.connect(self.refresh)
                row.date_completed.connect(self.remember_date)
                row.next_requested.connect(self.focus_next_date)
                row.remove_requested.connect(self.remove_video)
                self.videos.append(row)
                known[f.resolve()] = row
                self.list_layout.addWidget(row)
                fade_in(row)
                added.append(row)
        finally:
            QApplication.restoreOverrideCursor()
        self.refresh()
        if rejected:
            self.flash(f"{rejected} dosya video olmadığı için eklenmedi")
        first = next((r for r in added if r.dates), None)
        if first:
            QTimer.singleShot(0, self, lambda: self.scroll.ensureWidgetVisible(first))
            empty = next((d for r in added for d in r.dates if d.is_empty()), first.dates[0])
            empty.edit.setFocus()

    def pick_videos(self):
        exts = " ".join(f"*{e}" for e in sorted(main.VIDEO_EXTS))
        last = self.settings.value("last_input_dir", "")
        files, _ = QFileDialog.getOpenFileNames(self, "Video seç", last, f"Videolar ({exts})")
        if files:
            self.settings.setValue("last_input_dir", str(Path(files[0]).parent))
            self.add_paths([Path(f) for f in files])

    def remove_video(self, row):
        self.videos.remove(row)
        collapse_out(row)
        self.refresh()

    def clear(self):
        if not ask(self, "Listeyi temizle", "Tüm videolar listeden kaldırılsın mı?",
                   "Girdiğiniz tarihler de silinir. Videolarınıza ve üretilen çıktılara bir şey olmaz.",
                   "Temizle", "Vazgeç", default_yes=False):
            return
        for row in self.videos:
            collapse_out(row)
        self.videos.clear()
        self.refresh()

    def clear_finished(self):
        # Tamamlanan tarihleri, tarihi kalmayan videoları listeden kaldırır; hatalılar kalır
        for video in list(self.videos):
            if not video.remove_finished():
                continue
            if not any(not d.is_empty() for d in video.dates):
                self.remove_video(video)
        self.refresh()

    # --- Sürükle-bırak ----------------------------------------------------------

    def dragEnterEvent(self, event):
        if not self.worker and event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.overlay.appear()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.overlay.disappear()

    def dropEvent(self, event):
        self.overlay.disappear()
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        event.acceptProposedAction()
        # Bırakma işlemi bitsin, sonra videoları oku (Gezgin donmuş görünmesin)
        QTimer.singleShot(0, self, lambda: self.add_paths(paths))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.overlay.isVisible():
            self.overlay.setGeometry(self.centralWidget().rect())

    # --- Ayarlar ----------------------------------------------------------------

    def pick_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Çıktı klasörünü seç", str(self.out_dir))
        if folder:
            self.out_dir = Path(folder)
            self.settings.setValue("output_dir", folder)
            self.refresh()

    def open_output(self):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.out_dir)))

    def set_monthly(self, on):
        self.monthly = on
        self.settings.setValue("monthly", on)

    def set_theme(self, choice):
        self.theme_choice = choice
        self.settings.setValue("theme", choice)
        apply_theme(choice)

    # --- İşleme -----------------------------------------------------------------

    def run_or_stop(self):
        if self.worker:
            self.worker.stop()
            self.refresh()
            return
        if not self.videos:
            ask(self, "Video yok", "Henüz video eklemediniz.",
                "Videoları pencereye sürükleyip bırakın ya da “Video ekle” butonuna tıklayın.", None, "Tamam")
            return

        pending = sum(d.is_pending() for d in self.all_dates())
        problems = [(v, d, text) for v in self.videos for d, text in v.problems()]
        for _, d, _ in problems:
            if d:
                d.touched = True
                d.render()

        if problems:
            lines = [f"•  {v.path.name}: {text}" for v, _, text in problems[:8]]
            if len(problems) > 8:
                lines.append(f"…ve {len(problems) - 8} tane daha")
            details = "<br>".join(lines)
            fixable = next((d for _, d, _ in problems if d), None)
            if pending:
                go = ask(self, "Eksik tarihler", f"{len(problems)} tarih eksik veya hatalı",
                         f"{details}<br><br>Bunlar işlenmeyecek. Geçerli {pending} tarih şimdi işlensin mi?",
                         f"{pending} tanesini işle", "Önce düzelteyim")
            else:
                ask(self, "İşlenecek video yok", "Tarihler eksik veya hatalı",
                    f"{details}<br><br>Kırmızı alanları düzeltip tekrar deneyin.", None, "Düzelteyim")
                go = False
            if not go:
                if fixable:
                    self.focus_date(fixable)
                return
        elif not pending:
            ask(self, "Hepsi tamam", "Listedeki tüm videolar zaten işlendi.",
                "Yeni video ekleyebilir ya da bir videoya “+ Tarih ekle” ile yeni tarih girebilirsiniz.", None, "Tamam")
            return

        rows = [(v, d) for v in self.videos for d in v.dates if d.is_pending()]
        existing = [(v, d) for v, d in rows if output_path(self.out_dir, v.path, d.value(), self.monthly).exists()]
        overwrite = False
        if existing:
            lines = [f"•  {v.path.name}: {d.edit.text()}" for v, d in existing[:8]]
            if len(existing) > 8:
                lines.append(f"…ve {len(existing) - 8} tane daha")
            overwrite = ask(self, "Çıktı zaten var", f"{len(existing)} tarihin çıktısı zaten var",
                            "<br>".join(lines) + "<br><br>Bunlar daha önce işlenmiş. Atlayabilir ya da yeniden "
                            "oluşturabilirsiniz (yeni dosya eskisinin yerine geçer).",
                            "Yeniden oluştur", "Atla", default_yes=False)
        to_make = rows if overwrite else [r for r in rows if r not in existing]
        if not self.enough_space([v.path for v, _ in to_make]):
            return
        self.start_jobs(overwrite)

    def enough_space(self, sources):
        # Çıktı, kaynak videodan büyük olmaz varsayımıyla kabaca hesaplanır
        need = sum(src.stat().st_size for src in sources if src.exists())
        try:
            free = free_space(self.out_dir)
        except OSError:
            return True
        if free >= need:
            return True
        return ask(self, "Disk dolmak üzere", "Diskte yeterli boş yer olmayabilir",
                   f"Çıktılar için yaklaşık {gb(need)} gerekebilir, diskte {gb(free)} boş.<br><br>"
                   "Yer açıp tekrar deneyebilir ya da Ayarlar'dan çıktı klasörünü başka bir diske alabilirsiniz.",
                   "Yine de başla", "Vazgeç", default_yes=False)

    def start_jobs(self, overwrite=False):
        jobs, used = [], set()
        for video in self.videos:
            for row in video.dates:
                if not row.is_pending():
                    continue
                start = row.value()
                dst = output_path(self.out_dir, video.path, start, self.monthly)
                if dst in used:
                    row.set_state(ERROR, message="Aynı adlı başka bir video aynı tarihle var")
                    continue
                used.add(dst)
                row.set_state(QUEUED, output=dst)
                jobs.append((row, video.path, dst, start, overwrite))
        if not jobs:
            self.refresh()
            return
        try:
            self.out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            for row, *_ in jobs:
                row.set_state(READY)
            QMessageBox.warning(self, "Çıktı klasörü", f"Çıktı klasörü oluşturulamadı:\n{self.out_dir}\n\n{e}")
            self.refresh()
            return

        self.worker = Worker(jobs)
        self.worker.progress.connect(lambda row, f: row.set_state(RUNNING, f))
        self.worker.job_finished.connect(lambda row, state, msg: row.set_state(state, 1.0, msg))
        self.worker.job_finished.connect(lambda *_: self.refresh())
        self.worker.finished.connect(self.on_finished)
        for v in self.videos:
            v.set_locked(True)
        self.worker.start()
        self.refresh()

    def on_finished(self):
        self.worker.deleteLater()
        self.worker = None
        for v in self.videos:
            v.set_locked(False)
            for row in v.dates:
                if row.state in (QUEUED, RUNNING):
                    row.set_state(READY)
        self.refresh()
        QApplication.alert(self)  # pencere arkadaysa görev çubuğunda yanıp söner

    def closeEvent(self, event):
        if self.worker:
            if not ask(self, "İşlem sürüyor", "Videolar hâlâ işleniyor. Durdurup çıkılsın mı?",
                       "Yarım kalan video kaydedilmez; bitmiş olanlar klasöründe durur.",
                       "Durdur ve çık", "Devam et", default_yes=False):
                event.ignore()
                return
            self.worker.stop()
            self.worker.wait()
        else:
            waiting = sum(v.is_unprocessed() for v in self.videos)
            if waiting and not ask(self, "Çıkılsın mı?", f"Listede henüz işlenmemiş {waiting} video var.",
                                   "Çıkarsanız liste ve girdiğiniz tarihler silinir. Videolarınıza bir şey olmaz.",
                                   "Çık", "Vazgeç", default_yes=False):
                event.ignore()
                return
        event.accept()

    # --- Güncelleme -------------------------------------------------------------

    def show_update_banner(self, info):
        self.update_info = info
        self.banner_text.setText(f"Yeni sürüm hazır: <b>{info.latest}</b>. Güncellemek bir dakika sürer.")
        self.banner.show()

    def open_update(self):
        if self.worker:
            QMessageBox.information(self, "Güncelleme", "Videolar işlenirken güncellenemez. İşlem bitince tekrar deneyin.")
            return
        updater.UpdateDialog(self.update_info, self).exec()


# =============================================================================
# Açılış animasyonu
# =============================================================================

class Splash(QWidget):
    finished = Signal()

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SplashScreen)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(340, 300)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())
        self.t = 0.0
        self.anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=1600)
        self.anim.valueChanged.connect(self._tick)
        self.anim.finished.connect(self.finished)
        self.fade = None

    def start(self):
        self.show()
        self.anim.start()

    def _tick(self, value):
        self.t = value
        self.update()

    @staticmethod
    def phase(t, start, end, curve=QEasingCurve.OutCubic):
        return ease((t - start) / (end - start), curve)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setPen(QColor(theme["border"]))
        p.setBrush(QColor(theme["card"]))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 24, 24)

        t = self.t
        pop = self.phase(t, 0.0, 0.4, QEasingCurve.OutBack)
        size = 112 * (0.5 + 0.5 * pop)
        cx, cy = self.width() / 2, 112
        p.setOpacity(self.phase(t, 0.0, 0.2))
        draw_icon(p, QRectF(cx - size / 2, cy - size / 2, size, size),
                  arc=self.phase(t, 0.15, 0.7),
                  turn=self.phase(t, 0.15, 0.9, QEasingCurve.InOutCubic))

        text = self.phase(t, 0.5, 0.85)
        p.setOpacity(text)
        shift = 10 * (1 - text)
        font = QFont(self.font())
        font.setPixelSize(24)
        font.setWeight(QFont.DemiBold)
        p.setFont(font)
        p.setPen(QColor(theme["text"]))
        p.drawText(QRectF(0, 190 + shift, self.width(), 32), Qt.AlignCenter, APP_NAME)
        font.setPixelSize(13)
        font.setWeight(QFont.Normal)
        p.setFont(font)
        p.setPen(QColor(theme["muted"]))
        p.drawText(QRectF(0, 226 + shift, self.width(), 20), Qt.AlignCenter, "Videolarınıza zaman damgası")

    def fade_out(self):
        self.fade = QPropertyAnimation(self, b"windowOpacity", self, duration=250, startValue=1.0, endValue=0.0)
        self.fade.finished.connect(self.close)
        self.fade.start()


# =============================================================================

def show_error(exc_type, exc, tb):
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    log.error("Beklenmeyen hata:\n%s", text)
    box = QMessageBox(QMessageBox.Critical, APP_NAME, "Beklenmeyen bir hata oluştu.")
    box.setDetailedText(text)
    box.exec()


def self_test():
    # Kurulum paketinin Windows'ta çalıştığını doğrular (ffmpeg, OpenCV, font, Türkçe dosya adı).
    # Çıkış kodu 0 = başarılı. Hata olursa ayrıntı geçici klasördeki log dosyasına yazılır.
    log = Path(tempfile.gettempdir()) / "zaman-makinesi-selftest.log"
    try:
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "deneme şğüıöç.mp4"
            subprocess.run([main.find_ffmpeg(), "-loglevel", "error", "-f", "lavfi",
                            "-i", "testsrc=duration=2:size=320x240:rate=25", "-pix_fmt", "yuv420p", str(src)],
                           check=True, creationflags=main.NO_WINDOW)
            frame, info = read_first_frame(src)
            assert frame is not None, "video okunamadı"
            start = datetime(2026, 1, 1, 12, 0, 0)
            dst = output_path(Path(d), src, start)
            main.process(src, dst, start, on_progress=lambda f: None)
            assert dst.stat().st_size > 0, "çıktı boş"
        log.write_text(f"OK {info}\n", encoding="utf-8")
        return 0
    except Exception:
        log.write_text(traceback.format_exc(), encoding="utf-8")
        return 1


def run():
    if "--self-test" in sys.argv:
        sys.exit(self_test())

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")
    sys.excepthook = show_error
    setup_log()

    window = MainWindow()
    apply_theme(window.theme_choice)
    # "Sistem" seçiliyken Windows/macOS teması değişirse uygulama da değişsin
    app.styleHints().colorSchemeChanged.connect(
        lambda _: window.theme_choice == "system" and apply_theme("system"))

    splash = Splash()
    check = updater.UpdateCheck()
    pending = {"splash", "check"}
    result = {}

    def ready(part, info=None):
        if part == "check":
            result["info"] = info
        pending.discard(part)
        if pending:
            return
        info = result.get("info")
        if info and info.forced:
            splash.close()
            dialog = updater.UpdateDialog(info)
            dialog.setWindowIcon(app_icon())
            dialog.exec()  # Windows'ta kurulum başlarsa uygulama zaten kapanır
            app.quit()
            return
        window.show()
        if info and info.newer:
            window.show_update_banner(info)
        splash.raise_()
        splash.fade_out()

    splash.finished.connect(lambda: ready("splash"))
    check.finished.connect(lambda info: ready("check", info))
    splash.start()
    check.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
