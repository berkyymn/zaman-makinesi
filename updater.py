"""
Güncelleme kontrolü.

Her yayında GitHub Release'e bir version.json konur:
    {"latest": "1.3.0", "min_supported": "1.2.0", "url": "...Setup.exe", "sha256": "...", "notes": "..."}
- Sürümümüz min_supported'dan eskiyse güncelleme zorunludur.
- latest'ten eskiyse isteğe bağlıdır.
- version.json'a ulaşılamazsa uygulama normal açılır.

Deneme için: ZM_VERSION_URL=file:///.../version.json uv run gui.py
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

from version import __version__

REPO = "berkyymn/zaman-makinesi"
VERSION_URL = os.environ.get("ZM_VERSION_URL", f"https://github.com/{REPO}/releases/latest/download/version.json")
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"


def parse_version(value):
    return tuple(int(x) for x in value.strip().lstrip("v").split("."))


class UpdateInfo:
    def __init__(self, data):
        self.latest = data["latest"]
        self.min_supported = data.get("min_supported", "0.0.0")
        self.url = data["url"]
        self.sha256 = data["sha256"].lower()
        self.notes = data.get("notes", "")
        current = parse_version(__version__)
        self.newer = parse_version(self.latest) > current
        self.forced = current < parse_version(self.min_supported)


class UpdateCheck(QObject):
    finished = Signal(object)  # UpdateInfo veya None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.net = QNetworkAccessManager(self)
        self.reply = None

    def start(self):
        req = QNetworkRequest(QUrl(VERSION_URL))
        req.setTransferTimeout(3000)
        self.reply = self.net.get(req)
        self.reply.finished.connect(self._done)

    def _done(self):
        info = None
        if self.reply.error() == QNetworkReply.NoError:
            try:
                info = UpdateInfo(json.loads(bytes(self.reply.readAll())))
            except (ValueError, KeyError, AttributeError):
                info = None
        self.reply.deleteLater()
        self.finished.emit(info)


def can_install():
    # Kendi kendine kurulum sadece kurulmuş Windows sürümünde. Geliştirirken release sayfası açılır.
    return sys.platform == "win32" and getattr(sys, "frozen", False)


class UpdateDialog(QDialog):
    def __init__(self, info, parent=None):
        super().__init__(parent)
        self.info = info
        self.setWindowTitle("Güncelleme")
        self.setMinimumWidth(420)
        self.net = QNetworkAccessManager(self)
        self.reply = None
        self.file = None
        self.hash = None

        if info.forced:
            title = "Güncelleme gerekli"
            text = (f"Kullandığınız sürüm ({__version__}) artık desteklenmiyor.\n"
                    f"Devam etmek için {info.latest} sürümüne güncelleyin.")
        else:
            title = "Yeni sürüm hazır"
            text = f"Zaman Makinesi {info.latest} yayınlandı. Şu an kullandığınız: {__version__}."

        heading = QLabel(title)
        heading.setObjectName("dialogTitle")
        body = QLabel(text)
        body.setWordWrap(True)
        notes = QLabel(info.notes)
        notes.setWordWrap(True)
        notes.setObjectName("muted")
        notes.setVisible(bool(info.notes))
        self.status = QLabel()
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.bar.hide()

        self.later = QPushButton("Çık" if info.forced else "Sonra")
        self.later.clicked.connect(self.reject)
        self.update_btn = QPushButton("Güncelle")
        self.update_btn.setObjectName("primary")
        self.update_btn.setDefault(True)
        self.update_btn.clicked.connect(self.start)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.later)
        buttons.addWidget(self.update_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)
        for w in (heading, body, notes, self.bar, self.status):
            layout.addWidget(w)
        layout.addSpacing(6)
        layout.addLayout(buttons)

    def start(self):
        if not can_install():
            QDesktopServices.openUrl(QUrl(RELEASES_URL))
            self.accept()
            return
        self.update_btn.setEnabled(False)
        self.update_btn.setText("İndiriliyor…")
        self.later.setText("Vazgeç")
        self.bar.show()
        self.status.setText("Lütfen bekleyin, bu bir iki dakika sürebilir. Pencereyi kapatmayın.")
        path = Path(tempfile.gettempdir()) / f"ZamanMakinesi-Setup-{self.info.latest}.exe"
        self.file = open(path, "wb")
        self.hash = hashlib.sha256()
        req = QNetworkRequest(QUrl(self.info.url))
        req.setTransferTimeout(30000)
        self.reply = self.net.get(req)
        self.reply.readyRead.connect(self._read)
        self.reply.downloadProgress.connect(self._progress)
        self.reply.finished.connect(self._done)

    def _read(self):
        chunk = bytes(self.reply.readAll())
        self.file.write(chunk)
        self.hash.update(chunk)

    def _progress(self, received, total):
        if total > 0:
            self.bar.setMaximum(total)
            self.bar.setValue(received)
            self.update_btn.setText(f"İndiriliyor… %{received * 100 // total}")

    def _done(self):
        self._read()
        self.file.close()
        path = Path(self.file.name)
        if self.reply.error() != QNetworkReply.NoError:
            self._fail("İndirme başarısız oldu. İnternet bağlantınızı kontrol edip tekrar deneyin.")
        elif self.hash.hexdigest() != self.info.sha256:
            self._fail("İndirilen dosya bozuk görünüyor. Tekrar deneyin.")
        else:
            self.update_btn.setText("Kuruluyor…")
            self.later.setEnabled(False)
            self.status.setText("Kuruluyor… Uygulama birazdan kendiliğinden yeniden açılacak.")
            # Kurulum, uygulama kapandıktan sonra eski sürümün üzerine kurar ve yeniden başlatır.
            subprocess.Popen([str(path), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])
            QApplication.quit()
            return
        path.unlink(missing_ok=True)

    def _fail(self, message):
        self.status.setText(message)
        self.bar.hide()
        self.update_btn.setEnabled(True)
        self.update_btn.setText("Tekrar dene")
        self.later.setText("Çık" if self.info.forced else "Sonra")

    def reject(self):
        if self.reply and self.reply.isRunning():
            self.reply.abort()
        super().reject()
