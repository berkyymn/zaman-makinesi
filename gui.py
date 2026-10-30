"""
Zaman Makinesi - masaüstü arayüzü.
    uv run gui.py
Videoya saat basma işini main.py yapar; burası sadece kullanıcıdan video ve tarihleri toplar.
Kurallar için TASARIM.md'ye bakın.
"""

import re
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

import cv2
from PySide6.QtCore import (QEasingCurve, QPropertyAnimation, QRectF, QSettings, QStandardPaths, Qt,
                            QThread, QTimer, QUrl, QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QDesktopServices, QFont, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea, QToolButton,
                               QVBoxLayout, QWidget)

import main
import updater
from icon import app_icon, draw_icon
from version import __version__

APP_NAME = "Zaman Makinesi"
DATE_FORMAT = "%d.%m.%Y %H:%M:%S"

# Bir işin (video + tarih) durumları
READY, QUEUED, RUNNING, DONE, EXISTS, ERROR = "ready", "queued", "running", "done", "exists", "error"

STYLE = """
QWidget { font-size: 13px; color: #202124; }
#central, QDialog { background: #f8f9fa; }
#card { background: white; border: 1px solid #dadce0; border-radius: 14px; }
#list, #listInner { background: white; }
#videoRow { border-bottom: 1px solid #eceff1; }
#videoRow[highlight="true"] { background: #e8f0fe; }
#title { font-size: 16px; font-weight: 600; }
#dialogTitle { font-size: 17px; font-weight: 600; }
#muted { color: #5f6368; }
#small { color: #5f6368; font-size: 12px; }
#fileName { font-weight: 600; }
#error { color: #d93025; }
#ok { color: #188038; }
QPushButton { border: 1px solid #dadce0; border-radius: 17px; padding: 6px 18px; min-height: 22px;
              background: white; color: #1a73e8; font-weight: 600; }
QPushButton:hover { background: #f1f6fe; }
QPushButton:disabled { color: #9aa0a6; background: #f1f3f4; border-color: #f1f3f4; }
QPushButton#primary { background: #1a73e8; color: white; border: none; padding: 7px 22px; }
QPushButton#primary:hover { background: #1765cc; }
QPushButton#primary:disabled { background: #e8eaed; color: #9aa0a6; }
QPushButton#danger { background: #d93025; color: white; border: none; padding: 7px 22px; }
QPushButton#danger:hover { background: #c5221f; }
QLineEdit { border: 1px solid #dadce0; border-radius: 8px; padding: 6px 8px; background: white;
            font-family: Consolas, Menlo, monospace; font-size: 14px; }
QLineEdit:focus { border: 2px solid #1a73e8; padding: 5px 7px; }
QLineEdit[invalid="true"] { border: 2px solid #d93025; padding: 5px 7px; }
QLineEdit:read-only { background: #f1f3f4; color: #5f6368; }
QToolButton { border: none; color: #1a73e8; padding: 4px 8px; border-radius: 6px; background: transparent; }
QToolButton:hover { background: #e8f0fe; }
QToolButton:disabled { color: #bdc1c6; }
QToolButton#remove { color: #5f6368; font-size: 16px; padding: 2px 8px; }
QToolButton#remove:hover { background: #fce8e6; color: #d93025; }
QProgressBar { border: none; background: #e8eaed; border-radius: 3px; }
QProgressBar::chunk { background: #1a73e8; border-radius: 3px; }
#dropZone { border: 2px dashed #dadce0; border-radius: 12px; color: #5f6368; background: transparent; }
#dropZone[active="true"] { border-color: #1a73e8; background: #e8f0fe; color: #1a73e8; }
#banner { background: #e8f0fe; border-radius: 10px; }
#info { background: #e8f0fe; color: #174ea6; border-radius: 8px; padding: 10px 12px; }
#thumb { background: #202124; border-radius: 6px; color: #9aa0a6; }
"""


def repolish(widget, name, value):
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


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


def output_path(out_dir, src, start):
    return out_dir / f"{src.stem}_{start:%Y%m%d_%H%M%S}.mp4"


# =============================================================================
# Liste satırları
# =============================================================================

class DateRow(QWidget):
    changed = Signal()
    remove_requested = Signal(object)
    preview_requested = Signal(object)

    def __init__(self):
        super().__init__()
        self.state = READY
        self.progress = 0.0
        self.message = ""      # hata mesajı (işleme sırasında)
        self.problem = ""      # tarih alanındaki sorun ("Geçersiz tarih" gibi)
        self.touched = False   # kullanıcı alandan çıktı mı (eksik tarih uyarısı için)
        self.locked = False
        self.output = None

        self.edit = QLineEdit()
        self.edit.setInputMask("00.00.0000 00:00:00;_")
        self.edit.setFixedWidth(190)
        self.edit.setToolTip("GG.AA.YYYY SS:DD:SS")
        self.edit.textChanged.connect(self._on_edit)
        self.edit.editingFinished.connect(self._on_leave)

        self.preview_btn = QToolButton(text="Önizle")
        self.preview_btn.clicked.connect(lambda: self.preview_requested.emit(self))
        self.remove_btn = QToolButton(text="×")
        self.remove_btn.setObjectName("remove")
        self.remove_btn.setToolTip("Bu tarihi kaldır")
        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))

        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setFixedSize(140, 6)
        self.status = QLabel()
        self.status.setMinimumWidth(180)
        self.show_btn = QToolButton(text="Göster")
        self.show_btn.setToolTip("Çıktıyı klasöründe göster")
        self.show_btn.clicked.connect(lambda: self.output and reveal(self.output))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.edit)
        layout.addWidget(self.preview_btn)
        layout.addWidget(self.remove_btn)
        layout.addSpacing(10)
        layout.addWidget(self.bar)
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

    def _on_leave(self):
        self.touched = True
        self.changed.emit()

    def set_state(self, state, progress=0.0, message="", output=None):
        self.state, self.progress, self.message = state, progress, message
        if output:
            self.output = output
        self.render()

    def set_locked(self, locked):
        self.locked = locked
        self.render()

    def render(self):
        finished = self.state in (DONE, EXISTS)
        self.edit.setReadOnly(self.locked or finished)
        self.remove_btn.setEnabled(not self.locked)
        self.preview_btn.setEnabled(self.value() is not None and not self.problem)
        visible_problem = self.problem and (self.touched or len(self.digits()) == 14)
        repolish(self.edit, "invalid", bool(visible_problem))

        self.bar.setVisible(self.state == RUNNING)
        self.bar.setValue(int(self.progress * 1000))
        self.show_btn.setVisible(finished and self.output is not None)

        if visible_problem:
            text, style = self.problem, "error"
        elif self.state == QUEUED:
            text, style = "Sırada", "muted"
        elif self.state == RUNNING:
            text, style = f"%{int(self.progress * 100)} işleniyor…", "muted"
        elif self.state == DONE:
            name = self.status.fontMetrics().elidedText(self.output.name, Qt.ElideLeft, 170)
            text, style = f"✓  {name}", "ok"
        elif self.state == EXISTS:
            text, style = "✓  Zaten var", "muted"
        elif self.state == ERROR:
            text, style = f"⚠  {self.message}", "error"
        else:
            text, style = "", "muted"
        self.status.setText(text)
        self.status.setToolTip(str(self.output) if finished and self.output else self.message)
        self.status.setObjectName(style)
        repolish(self.status, "s", style)


class VideoRow(QFrame):
    changed = Signal()
    remove_requested = Signal(object)
    preview_requested = Signal(object, object)  # VideoRow, DateRow

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

        name = QLabel(path.name)
        name.setObjectName("fileName")
        name.setToolTip(str(path))
        name.setMaximumWidth(220)
        name.setText(name.fontMetrics().elidedText(path.name, Qt.ElideMiddle, 220))
        detail = QLabel(info if self.readable else "Video açılamadı")
        detail.setObjectName("small" if self.readable else "error")
        self.remove_btn = QToolButton(text="Kaldır")
        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))

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
        self.add_btn.clicked.connect(lambda: self.add_date(focus=True))
        dates = QVBoxLayout()
        dates.setSpacing(8)
        dates.addLayout(self.date_list)
        dates.addWidget(self.add_btn, 0, Qt.AlignLeft)
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

    def add_date(self, focus=False):
        row = DateRow()
        row.changed.connect(self.validate)
        row.remove_requested.connect(self.remove_date)
        row.preview_requested.connect(lambda r: self.preview_requested.emit(self, r))
        self.dates.append(row)
        self.date_list.addWidget(row)
        if focus:
            row.edit.setFocus()
            row.edit.setCursorPosition(0)
        self.validate()

    def remove_date(self, row):
        self.dates.remove(row)
        row.hide()
        row.deleteLater()
        self.validate()

    def validate(self):
        seen = set()
        for row in self.dates:
            value = row.value()
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
        self.changed.emit()

    def set_locked(self, locked):
        self.locked = locked
        self.remove_btn.setEnabled(not locked)
        self.add_btn.setEnabled(not locked)
        for row in self.dates:
            row.set_locked(locked)

    def highlight(self):
        repolish(self, "highlight", True)
        QTimer.singleShot(1200, lambda: repolish(self, "highlight", False))


# =============================================================================
# Arka planda video işleme
# =============================================================================

class Worker(QThread):
    progress = Signal(object, float)            # DateRow, 0-1
    job_finished = Signal(object, str, str)     # DateRow, durum, mesaj

    def __init__(self, jobs):
        super().__init__()
        self.jobs = jobs  # [(DateRow, kaynak, hedef, başlangıç)]
        self.stopped = False

    def stop(self):
        self.stopped = True

    def run(self):
        for row, src, dst, start in self.jobs:
            if self.stopped:
                return
            if dst.exists():
                self.job_finished.emit(row, EXISTS, "")
                continue
            self.progress.emit(row, 0.0)
            try:
                main.process(src, dst, start,
                             on_progress=lambda f, row=row: self.progress.emit(row, f),
                             should_stop=lambda: self.stopped)
                self.job_finished.emit(row, DONE, "")
            except main.Cancelled:
                self.job_finished.emit(row, READY, "")
                return
            except Exception as e:
                self.job_finished.emit(row, ERROR, str(e) or type(e).__name__)


# =============================================================================
# Pencereler
# =============================================================================

class PreviewDialog(QDialog):
    def __init__(self, parent, path, start):
        super().__init__(parent)
        self.setWindowTitle(f"Önizleme · {path.name}")
        frame, _ = read_first_frame(path)
        image = QLabel()
        image.setAlignment(Qt.AlignCenter)
        if frame is None:
            image.setText("Video açılamadı")
        else:
            main.TextRenderer().draw(frame, main.format_ts(start), main.MARGIN_LEFT, main.MARGIN_TOP)
            pix = frame_to_pixmap(frame)
            if pix.width() > 880 or pix.height() > 495:
                pix = pix.scaled(880, 495, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            image.setPixmap(pix)

        info = QLabel("ⓘ  Bu sadece bir önizlemedir. Video henüz işlenmedi; "
                      "videonun ilk karesi saatin nasıl görüneceğini göstermek için kullanıldı.")
        info.setObjectName("info")
        info.setWordWrap(True)
        close = QPushButton("Kapat")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)
        layout.addWidget(info)
        layout.addWidget(image)
        layout.addWidget(close, 0, Qt.AlignRight)


class DropZone(QLabel):
    def __init__(self):
        super().__init__()
        self.setObjectName("dropZone")
        self.setAlignment(Qt.AlignCenter)
        self.set_empty(True)

    def set_empty(self, empty):
        if empty:
            self.setText("Videoları buraya sürükleyip bırakın\nveya yukarıdan “Video ekle”ye tıklayın")
            self.setMinimumHeight(260)
        else:
            self.setText("⤓  Videoları pencerenin herhangi bir yerine sürükleyip bırakın")
            self.setMinimumHeight(64)

    def set_active(self, active):
        repolish(self, "active", active)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1000, 660)
        self.setMinimumSize(860, 480)
        self.setAcceptDrops(True)
        self.settings = QSettings("ZamanMakinesi", "ZamanMakinesi")
        default_out = Path(QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)) / APP_NAME
        self.out_dir = Path(self.settings.value("output_dir", str(default_out)))
        self.videos = []
        self.worker = None
        self.update_info = None

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

        # Üst bilgi
        self.title = QLabel()
        self.title.setObjectName("title")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("muted")
        self.add_btn = QPushButton("+  Video ekle")
        self.add_btn.clicked.connect(self.pick_videos)
        self.clear_btn = QPushButton("Listeyi temizle")
        self.clear_btn.clicked.connect(self.clear)
        header = QHBoxLayout()
        header.setContentsMargins(20, 16, 16, 12)
        header.addWidget(self.title)
        header.addSpacing(8)
        header.addWidget(self.subtitle)
        header.addStretch()
        header.addWidget(self.add_btn)
        header.addWidget(self.clear_btn)

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
        self.scroll.setWidget(inner)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #eceff1;")

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
        self.run_btn.setMinimumWidth(190)
        self.run_btn.clicked.connect(self.run_or_stop)
        version = QLabel(f"v{__version__}")
        version.setObjectName("small")
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
        card_layout.addWidget(self.scroll, 1)
        card_layout.addWidget(line)
        card_layout.addLayout(footer)

        central = QWidget()
        central.setObjectName("central")
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 8)
        root.setSpacing(10)
        root.addWidget(self.banner)
        root.addWidget(card, 1)
        root.addWidget(version, 0, Qt.AlignRight)
        self.setCentralWidget(central)

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
        invalid = sum(bool(d.problem) for d in dates)
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

        self.add_btn.setEnabled(not running)
        self.clear_btn.setEnabled(not running and bool(self.videos))
        self.change_btn.setEnabled(not running)

        if running:
            self.run_btn.setText("Durdur")
            self.run_btn.setObjectName("danger")
            self.run_btn.setEnabled(True)
        else:
            self.run_btn.setText(f"▶  Videoları işle ({pending})" if pending else "▶  Videoları işle")
            self.run_btn.setObjectName("primary")
            self.run_btn.setEnabled(pending > 0 and invalid == 0)
        repolish(self.run_btn, "s", running)

        if self.flash_timer.isActive():
            return
        if running:
            self.hint.setText("İşleniyor… Pencereyi açık tutun.")
        elif invalid:
            self.hint.setText(f"{invalid} tarih eksik veya geçersiz")
        elif self.videos and not jobs:
            self.hint.setText("Videolara tarih girin")
        else:
            self.hint.setText("")

    def flash(self, text):
        self.hint.setText(text)
        self.flash_timer.start()

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
        first_new = None
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for f in files:
                if f.resolve() in known:
                    known[f.resolve()].highlight()
                    continue
                row = VideoRow(f)
                row.changed.connect(self.refresh)
                row.remove_requested.connect(self.remove_video)
                row.preview_requested.connect(self.preview)
                self.videos.append(row)
                known[f.resolve()] = row
                self.list_layout.addWidget(row)
                first_new = first_new or row
        finally:
            QApplication.restoreOverrideCursor()
        self.refresh()
        if rejected:
            self.flash(f"{rejected} dosya video olmadığı için eklenmedi")
        if first_new and first_new.dates:
            QTimer.singleShot(0, lambda: self.scroll.ensureWidgetVisible(first_new))
            first_new.dates[0].edit.setFocus()
            first_new.dates[0].edit.setCursorPosition(0)

    def pick_videos(self):
        exts = " ".join(f"*{e}" for e in sorted(main.VIDEO_EXTS))
        last = self.settings.value("last_input_dir", "")
        files, _ = QFileDialog.getOpenFileNames(self, "Video seç", last, f"Videolar ({exts})")
        if files:
            self.settings.setValue("last_input_dir", str(Path(files[0]).parent))
            self.add_paths([Path(f) for f in files])

    def remove_video(self, row):
        self.videos.remove(row)
        row.hide()
        row.deleteLater()
        self.refresh()

    def clear(self):
        answer = QMessageBox.question(self, "Listeyi temizle",
                                      "Tüm videolar ve tarihler listeden kaldırılsın mı?\n"
                                      "Üretilen çıktı dosyaları silinmez.")
        if answer != QMessageBox.Yes:
            return
        for row in self.videos:
            row.hide()
            row.deleteLater()
        self.videos.clear()
        self.refresh()

    def preview(self, video, date_row):
        start = date_row.value()
        if start:
            PreviewDialog(self, video.path, start).exec()

    # --- Sürükle-bırak ----------------------------------------------------------

    def dragEnterEvent(self, event):
        if not self.worker and event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_zone.set_active(True)

    def dragLeaveEvent(self, event):
        self.drop_zone.set_active(False)

    def dropEvent(self, event):
        self.drop_zone.set_active(False)
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        event.acceptProposedAction()
        # Bırakma işlemi bitsin, sonra videoları oku (Gezgin donmuş görünmesin)
        QTimer.singleShot(0, lambda: self.add_paths(paths))

    # --- Çıktı klasörü ----------------------------------------------------------

    def pick_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Çıktı klasörünü seç", str(self.out_dir))
        if folder:
            self.out_dir = Path(folder)
            self.settings.setValue("output_dir", folder)
            self.refresh()

    def open_output(self):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.out_dir)))

    # --- İşleme -----------------------------------------------------------------

    def run_or_stop(self):
        if self.worker:
            self.worker.stop()
            self.run_btn.setEnabled(False)
            self.run_btn.setText("Durduruluyor…")
            return
        try:
            self.out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            QMessageBox.warning(self, "Çıktı klasörü", f"Çıktı klasörü oluşturulamadı:\n{self.out_dir}\n\n{e}")
            return

        jobs, used = [], set()
        for video in self.videos:
            for row in video.dates:
                if not row.is_pending():
                    continue
                start = row.value()
                dst = output_path(self.out_dir, video.path, start)
                if dst in used:
                    row.set_state(ERROR, message="Aynı adlı başka bir video aynı tarihle var")
                    continue
                used.add(dst)
                row.set_state(QUEUED, output=dst)
                jobs.append((row, video.path, dst, start))
        if not jobs:
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
            answer = QMessageBox.question(self, "İşlem sürüyor",
                                          "Videolar hâlâ işleniyor. Durdurup çıkmak istiyor musunuz?\n"
                                          "Yarım kalan video kaydedilmez.")
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.worker.stop()
            self.worker.wait()
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
        x = min(max((t - start) / (end - start), 0.0), 1.0)
        return QEasingCurve(curve).valueForProgress(x)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setPen(QColor("#e3e6ea"))
        p.setBrush(Qt.white)
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
        p.setPen(QColor("#202124"))
        p.drawText(QRectF(0, 190 + shift, self.width(), 32), Qt.AlignCenter, APP_NAME)
        font.setPixelSize(13)
        font.setWeight(QFont.Normal)
        p.setFont(font)
        p.setPen(QColor("#5f6368"))
        p.drawText(QRectF(0, 226 + shift, self.width(), 20), Qt.AlignCenter, "Videolarınıza zaman damgası")

    def fade_out(self):
        self.fade = QPropertyAnimation(self, b"windowOpacity", self, duration=250, startValue=1.0, endValue=0.0)
        self.fade.finished.connect(self.close)
        self.fade.start()


# =============================================================================

def show_error(exc_type, exc, tb):
    text = "".join(traceback.format_exception(exc_type, exc, tb))
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
            dst = output_path(Path(d), src, datetime(2026, 1, 1, 12, 0, 0))
            main.process(src, dst, datetime(2026, 1, 1, 12, 0, 0), on_progress=lambda f: None)
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
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setStyleSheet(STYLE)
    sys.excepthook = show_error

    window = MainWindow()
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
