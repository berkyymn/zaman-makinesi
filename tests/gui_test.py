"""
Arayüzün uçtan uca testi. Ekran açmadan çalışır, deneme videolarını kendisi üretir.
    QT_QPA_PLATFORM=offscreen uv run python tests/gui_test.py [ekran_görüntüsü_klasörü]
Çıkış kodu 0 = hepsi geçti.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

import gui
import main
import updater

WORK = Path(tempfile.mkdtemp(prefix="zm-test-"))
SHOTS = Path(sys.argv[1]) if len(sys.argv) > 1 else None
VIDEOS = WORK / "videolar"
OUT = WORK / "cikti"

app = QApplication([])
app.setStyle("Fusion")
app.setApplicationName("ZM Test")
gui.setup_log()
results = []


def check(name, cond):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name, flush=True)


def pump(ms=50):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def shot(widget, name):
    pump(120)
    if SHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True)
        widget.grab().save(str(SHOTS / name))


def wait_worker(w):
    while w.worker:
        pump(50)


# Mesaj kutuları testte beklemesin: sıradaki cevabı ver (True = onay butonu)
answers = []


def fake_exec(box):
    box.show()
    pump(60)
    want = answers.pop(0) if answers else False
    btn = next((b for b in box.buttons() if box.buttonRole(b) == QMessageBox.AcceptRole), None) if want else None
    box.clickedButton = lambda: btn
    box.hide()
    return 0


QMessageBox.exec = fake_exec

# --- Deneme videoları -------------------------------------------------------
VIDEOS.mkdir(parents=True)
ff = main.find_ffmpeg()
for name, src, size, dur in (("a_deniz.mp4", "testsrc2", "1280x720", 4), ("b_kamera.mp4", "smptehdbars", "640x360", 2),
                             ("c_sahne.mov", "testsrc", "640x360", 2), ("d_telefon.mp4", "testsrc2", "360x640", 2),
                             ("e_toplantı.mp4", "testsrc", "640x360", 2)):
    subprocess.run([ff, "-loglevel", "error", "-f", "lavfi", "-i", f"{src}=s={size}:r=25:d={dur}",
                    "-pix_fmt", "yuv420p", str(VIDEOS / name)], check=True)
(VIDEOS / "not.txt").write_text("video değil")
files = sorted(VIDEOS.glob("*.m*"))

w = gui.MainWindow()
w.settings.clear()
w = gui.MainWindow()
w.out_dir = OUT
gui.apply_theme("light")
w.show()
w.activateWindow()
pump(200)
shot(w, "01_bos.png")

# --- Ekleme ------------------------------------------------------------------
w.overlay.appear(); pump(300); shot(w, "02_surukleme.png"); w.overlay.disappear(); pump(300)
check("sürükleme katmanı kapandı", not w.overlay.isVisible())
w.add_paths(files + [VIDEOS / "not.txt"]); pump(300)
check("5 video eklendi", len(w.videos) == 5)
check("video olmayan reddedildi", "eklenmedi" in w.hint.text())
w.add_paths([files[0]])
check("aynı video tekrar eklenmedi", len(w.videos) == 5)
check("son tarih kutusu kapalı başlar", not w.remember.isChecked())
v = w.videos
check("tek tarihte İptal gizli", not v[0].del_btn.isVisible())
v[0].add_date(); v[0].add_date(); v[0].add_date(); pump()
check("çok tarihte İptal görünür", v[0].del_btn.isVisible())
last = v[0].dates[-1]; v[0].del_btn.click(); pump(300)
check("İptal son tarihi kaldırdı", len(v[0].dates) == 3 and last not in v[0].dates)

# --- Tarih alanı -------------------------------------------------------------
e = v[0].dates[1].edit
QTest.mouseClick(e, Qt.LeftButton, Qt.NoModifier, QPoint(e.width() - 20, e.height() // 2)); pump()
check("boş alana tıklayınca imleç başta", e.cursorPosition() == 0)
v[0].dates[0].edit.setFocus(); pump()
order = []
for _ in range(4):
    order.append(app.focusWidget()); QTest.keyClick(app.focusWidget(), Qt.Key_Tab); pump()
check("Tab ekrandaki sırayla gider", order == [v[0].dates[0].edit, v[0].dates[1].edit, v[0].dates[2].edit, v[1].dates[0].edit])
v[0].dates[0].edit.setFocus(); v[0].dates[0].edit.setCursorPosition(0); pump()
QTest.keyClicks(v[0].dates[0].edit, "12102026143000"); QTest.keyClick(v[0].dates[0].edit, Qt.Key_Return); pump()
check("Enter sıradaki boş alana geçer", app.focusWidget() is v[0].dates[1].edit)
check("son tarih hatırlandı", w.last_date == "12.10.2026 14:30:00")
v[0].dates[1].edit.setText("13.10.2026 09:00:00")
v[1].dates[0].edit.setText("31.02.2026 25:00:00")   # hatalı
v[2].dates[0].edit.setText("20.10.2026 10:15")       # eksik
v[3].dates[0].edit.setText("05.09.2026 08:00:00")
pump(); shot(w, "03_dolu.png")
check("hatalıyken de buton tıklanabilir", w.run_btn.isEnabled() and "(3)" in w.run_btn.text())

# --- Çalıştırma ---------------------------------------------------------------
answers[:] = [False]; w.run_or_stop(); pump()
check("'Önce düzelteyim': başlamadı", w.worker is None)
check("'Önce düzelteyim': ilk hatalı alana gitti", w.focusWidget() is v[1].dates[0].edit)
check("eksik alan kırmızı oldu", v[2].dates[0].problem == "Tarih eksik" and v[2].dates[0].edit.property("invalid"))
answers[:] = [True]; w.run_or_stop(); pump(150)
check("geçerlilerle başladı", w.worker is not None)
check("işlerken saat geri dönüyor", w.clock.spinning)
check("Zaman Adam balonu çıktı", w.toast.isVisible() and w.toast.text.text())
running = next((d for d in w.all_dates() if d.state == gui.RUNNING), None)
check("satırda koşan adam ve canlı süre", running and running.buddy.isVisible() and " sn" in running.status.text())
shot(w, "04_isleniyor.png")
wait_worker(w); pump(900); shot(w, "05_bitti.png")
outs = sorted(str(p.relative_to(OUT)) for p in OUT.rglob("*.mp4"))
print("   çıktılar:", outs)
check("ay klasörü + gün_ay_yıl adı", "2026-10 Ekim/a_deniz_12_10_2026_14_30_00.mp4" in outs
      and "2026-09 Eylül/d_telefon_05_09_2026_08_00_00.mp4" in outs and len(outs) == 3)
check("bitince balon 'hazır'", "hazır" in w.toast.text.text().lower())
check("biten satırda okey veren adam, tik yok", v[0].dates[0].buddy.mode == "ok" and v[0].dates[0].buddy.isVisible()
      and "✓" not in v[0].dates[0].status.text() and "Tamamlandı" in v[0].dates[0].status.text())
check("Bitenleri temizle görünüyor", w.clear_done_btn.isVisible())
check("'Hepsini temizle' adı", w.clear_btn.text() == "Hepsini temizle")
gui.apply_theme("dark"); shot(w, "06_bitti_koyu.png"); gui.apply_theme("light")
pump(5200)
check("balon birkaç saniye sonra kayboldu", not w.toast.isVisible())

answers[:] = [False]; w.run_or_stop(); pump()
check("işlenecek yokken başlamadı", w.worker is None)

# --- Son tarih, gelecek tarih, aynı çıktı ---------------------------------------
w.remember.setChecked(True)
v[0].dates[2].edit.setText("14.10.2026 18:45:00"); pump()
extra = WORK / "ekstra.mp4"; shutil.copy(files[0], extra)
w.add_paths([extra]); pump(200)
check("yeni videoya son tarih yazıldı", w.videos[-1].dates[0].edit.text() == "14.10.2026 18:45:00")
deniz = v[0]
deniz.add_date(); fut = deniz.dates[-1]; fut.edit.setText("01.01.2099 10:00:00"); pump()
check("gelecek tarih uyarısı (engellemez)", "Gelecekte" in fut.status.text() and fut.is_job())
deniz.remove_last_date(); pump(300)

w.clear_finished(); pump(300)
check("Bitenleri temizle: bitenler gitti, bekleyenler kaldı",
      all(d.state not in (gui.DONE, gui.EXISTS) for d in w.all_dates()) and deniz in w.videos
      and any(x.path.name == "e_toplantı.mp4" for x in w.videos))

deniz.add_date(); dup = deniz.dates[-1]; dup.edit.setText("12.10.2026 14:30:00"); pump()
for other in w.all_dates():
    if other is not dup and other.is_pending():
        other.edit.clear()
pump()
answers[:] = [True, False]; w.run_or_stop(); pump(100); wait_worker(w)
check("aynı çıktı: Atla -> zaten vardı", dup.state == gui.EXISTS and "atlandı" in dup.status.text())
target = gui.output_path(w.out_dir, deniz.path, dup.value()); before = target.stat().st_mtime
dup.set_state(gui.READY)
answers[:] = [True, True]; w.run_or_stop(); pump(100); wait_worker(w)
check("aynı çıktı: Yeniden oluştur -> üzerine yazıldı", dup.state == gui.DONE and target.stat().st_mtime > before)

orig_free = gui.free_space; gui.free_space = lambda folder: 1
dup.set_state(gui.READY); dup.edit.setText("12.10.2026 14:31:00")
answers[:] = [True, False]; w.run_or_stop(); pump()
check("disk az: Vazgeç -> başlamadı", w.worker is None)
gui.free_space = orig_free

gone = WORK / "silinecek.mp4"; shutil.copy(files[1], gone)
w.add_paths([gone]); pump(200); gv = w.videos[-1]; gv.dates[0].edit.setText("01.10.2026 10:00:00")
dup.edit.clear(); gone.unlink(); pump()
answers[:] = [True]; w.run_or_stop(); pump(100); wait_worker(w)
check("silinen video için anlaşılır hata", "Video bulunamadı" in gv.dates[0].status.text())
logtext = gui.log_path().read_text(encoding="utf-8")
check("hata kaydı yazıldı", "Hata:" in logtext and "Bitti" in logtext)

# --- Kapatma ve durdurma --------------------------------------------------------
answers[:] = [False]; ev = QCloseEvent(); w.closeEvent(ev)
check("işlenmemiş video varken kapanış soruldu", not ev.isAccepted())
long_src = WORK / "uzun.mp4"
subprocess.run([ff, "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=30:d=40",
                "-pix_fmt", "yuv420p", str(long_src)], check=True)
w.add_paths([long_src]); pump(200); lv = w.videos[-1]; lv.dates[0].edit.setText("15.10.2026 10:00:00")
gv.dates[0].edit.clear(); pump()
answers[:] = [True]; w.run_or_stop(); pump(100)
while not any(d.state == gui.RUNNING for d in w.all_dates()):
    pump(20)
pump(400)
w.run_or_stop(); pump()
check("Durdur: 'Durduruluyor' yazıyor", "Durduruluyor" in w.run_btn.text())
wait_worker(w)
check("durdurunca yarım dosya kalmadı", not list(OUT.rglob("*.part.mp4")) and lv.dates[0].state == gui.READY)

# --- Tek tek iptal: 1. çalışırken iptal, 2. sıradan çıkar, 3. işlensin ----------------
lv.add_date(); lv.add_date(); pump()
lv.dates[1].edit.setText("16.10.2026 10:00:00"); lv.dates[2].edit.setText("17.10.2026 10:00:00"); pump()
first, second, third = lv.dates
answers[:] = [True]; w.run_or_stop(); pump(50)
check("iptal: sıradakinde '✕ İptal' görünüyor", second.state == gui.QUEUED and second.cancel_btn.isVisible())
second.cancel_btn.click(); pump()
check("iptal: sıradaki hemen 'Sıradan çıkarıldı'", second.state == gui.CANCELLED and "çıkarıldı" in second.status.text())
while first.state != gui.RUNNING:
    pump(10)
first.cancel_btn.click(); pump(30)
check("iptal: çalışan 'İptal ediliyor'", first.state == gui.CANCELLED or "İptal ediliyor" in first.status.text())
wait_worker(w); pump(100)
made = sorted(p.name for p in OUT.rglob("uzun_*.mp4"))
print("   çıktılar:", made)
check("iptal: sadece 3. işlendi", first.state == gui.CANCELLED and second.state == gui.CANCELLED
      and third.state == gui.DONE and made == ["uzun_17_10_2026_10_00_00.mp4"])
check("iptal: yarım dosya kalmadı", not list(OUT.rglob("*.part.mp4")))
check("iptal: iptal edilenler yeniden işlenebilir", first.is_pending() and second.is_pending()
      and "(2)" in w.run_btn.text())

# --- Güncelleme duyurusu ve ayarlar -------------------------------------------------
newinfo = updater.UpdateInfo({"latest": "9.9.9", "url": "x", "sha256": "ab", "notes": "Yeni şeyler."})
opened = []
w.open_update = lambda: opened.append(1)
w.announce_update(newinfo); pump(900); shot(w, "07_guncelleme_balonu.png")
check("güncelleme: Zaman Adam haber verdi", w.toast.isVisible() and "Yeni sürüm" in w.toast.text.text())
check("güncelleme: Ayarlar rozeti", w.badge.isVisible())
QTest.mouseClick(w.toast, Qt.LeftButton); pump()
check("güncelleme: balona tıklayınca açılır", opened == [1] and not w.toast.isVisible())
sd = gui.SettingsDialog(w); sd.show(); shot(sd, "08_ayarlar_guncelleme.png")
check("ayarlar: 'Şimdi güncelle'", "Şimdi güncelle" in sd.update_btn.text()); sd.close()
w.update_info = None; w.badge.hide()

vfile = WORK / "v_new.json"
vfile.write_text(json.dumps({"latest": "9.9.9", "min_supported": "1.0.0", "url": "x", "sha256": "ab"}))
updater.VERSION_URL = vfile.as_uri()
w.settings.setValue("last_update_check", 0)
sd = gui.SettingsDialog(w); sd.show(); pump(800)
check("ayarlar: eski kontrolde kendiliğinden denetledi", "Şimdi güncelle" in sd.update_btn.text() and w.badge.isVisible())
sd.close(); w.update_info = None; w.badge.hide()
sd = gui.SettingsDialog(w); sd.show(); pump(800)
check("ayarlar: yeni kontrolde tekrar denetlemedi", "Son kontrol: bugün" in sd.update_status.text())
check("ayarlar: hızlandırma satırı dolu", sd.speed.text() and "Belirleniyor" not in sd.speed.text())
shot(sd, "09_ayarlar.png")
gui.apply_theme("dark"); shot(sd, "10_ayarlar_koyu.png"); sd.close(); gui.apply_theme("light")

wn = gui.WhatsNewDialog(w, "Zaman Adam geldi."); wn.show(); shot(wn, "11_yenilikler.png"); wn.close()

# --- En hızlı ayar ölçümü ------------------------------------------------------------
gui.tune_cache().unlink(missing_ok=True)
main._encoder, main.tuned = None, False
w.start_tuning()
saw_overlay = False
while w.tuner:
    saw_overlay = saw_overlay or w.tune_overlay.isVisible()
    if w.tune_overlay.isVisible() and "deneniyor" in w.tune_overlay.step_label.text():
        shot(w, "12_olcum.png")
    pump(30)
check("ölçüm: ilk açılışta ekran göründü", saw_overlay)
check("ölçüm: en hızlı ayar seçildi ve kaydedildi", main.tuned and gui.tune_cache().exists())
check("ölçüm: bitince 'Buldum'", "Buldum" in w.tune_overlay.title.text()); shot(w, "13_olcum_bitti.png")
pump(2500)
check("ölçüm: ekran kendiliğinden kapandı", not w.tune_overlay.isVisible())
main._encoder, main.tuned = None, False
w.start_tuning(); saw_overlay = False
while w.tuner:
    saw_overlay = saw_overlay or w.tune_overlay.isVisible()
    pump(20)
check("ölçüm: ikinci açılışta tekrar ölçmedi", not saw_overlay and main.tuned)
w.start_tuning(force=True); pump(100)
w.skip_tuning()
while w.tuner:
    pump(20)
check("ölçüm: 'Şimdilik geç' çalışıyor", "güvenli" in w.tune_overlay.title.text())

print(f"\n{sum(results)}/{len(results)} geçti")
shutil.rmtree(WORK, ignore_errors=True)
os._exit(0 if all(results) else 1)
