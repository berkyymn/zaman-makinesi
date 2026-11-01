"""
Videolarınızı "girdi" klasörüne atın, sonra:
    uv run main.py              -> girdi klasöründeki tüm videoları işler
    uv run main.py video.mp4    -> sadece girdi/video.mp4'ü işler
Sonuçlar "cikti" klasörüne aynı adla (.mp4 olarak) kaydedilir.
"""

# =============================================================================
# AYARLAR - sadece burayı değiştirin
# =============================================================================

import sys

# Saatin başlangıcı. None = scripti çalıştırdığınız an.
START_TIME = None                 # örnek: "10-10-2026 14:30:00"  (gün-ay-yıl)

# Dosyaya özel başlangıç saatleri. Burada olmayan dosyalar START_TIME'ı kullanır.
# Dosya yolu girdi klasörüne göre yazılır (alt klasördeyse "kamera1/a.mp4" gibi).
START_TIMES = {
    "TEST DENEME": "28-08-2026 10:40:14",
    "TEST DENEME1": "28-08-2026 10:44:14",

}

# Font dosyası (.ttf). Courier New Bold, Windows ve macOS'ta hazır gelir.
if sys.platform == "win32":
    FONT_PATH = r"C:\Windows\Fonts\courbd.ttf"
else:
    FONT_PATH = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"

# Yazı boyutu (piksel). 1080p video için ~27, 720p için ~18 iyi durur.
FONT_SIZE = 30 #prev 27

# Kutunun videonun sol ve üst kenarına uzaklığı (piksel)
MARGIN_LEFT = 24 #prev 24
MARGIN_TOP = 60 #prev 44

# Yazı ile siyah kutunun kenarı arasındaki boşluk (piksel)
PADDING = 4

# Renkler (R, G, B)
TEXT_COLOR = (255, 255, 255)      # beyaz
BG_COLOR = (0, 0, 0)              # siyah

# Kutunun opaklığı: 1 = tam dolu, 0.5 = yarı saydam, 0 = kutu yok
BG_OPACITY = 1.0

# Gün kısaltmaları (Pazartesiden başlayarak). Videoya basılan yazıyı ffmpeg ürettiği için
# videoda her zaman bu İngilizce kısaltmalar çıkar; bu liste önizleme içindir.
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Video kalitesi: küçük sayı = daha kaliteli ama büyük dosya (17-23 arası önerilir)
CRF = 23

# Videoyu sıkıştıracak kodlayıcı. "auto" = bilgisayarda hangisi varsa en hızlısı
# (NVIDIA / Intel / AMD grafik, yoksa işlemci). Elle seçmek için: "nvenc", "qsv", "amf", "cpu"
ENCODER = "auto"

# Klasörler (proje klasörüne göre)
INPUT_DIR = "girdi"
OUTPUT_DIR = "cikti"

# Çıktıda zaten aynı isimde dosya varsa: True = üzerine yaz, False = atla
OVERWRITE = False

# =============================================================================

import difflib
import os
import re
import shutil
import subprocess
import tempfile
import threading
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def format_ts(dt):
    return f"{dt:%d-%m-%Y} {WEEKDAYS[dt.weekday()]} {dt:%H:%M:%S}"


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


class TextRenderer:
    def __init__(self):
        self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        left, top, right, bottom = self.font.getbbox(format_ts(datetime(2000, 1, 1)))
        self.offset = (PADDING - left, PADDING - top)
        self.w = right - left + 2 * PADDING
        self.h = bottom - top + 2 * PADDING
        self.text_bgr = np.array(TEXT_COLOR[::-1], np.float32)
        self.bg_bgr = np.array(BG_COLOR[::-1], np.float32)
        self.cache_text = None
        self.cache_mask = None

    def draw(self, frame, text, x, y):
        if text != self.cache_text:
            img = Image.new("L", (self.w, self.h), 0)
            ImageDraw.Draw(img).text(self.offset, text, font=self.font, fill=255)
            self.cache_text = text
            self.cache_mask = np.asarray(img, np.float32)[:, :, None] / 255.0

        h = min(self.h, frame.shape[0] - y)
        w = min(self.w, frame.shape[1] - x)
        if h <= 0 or w <= 0:
            return
        roi = frame[y:y + h, x:x + w].astype(np.float32)
        mask = self.cache_mask[:h, :w]
        roi = roi * (1 - BG_OPACITY) + self.bg_bgr * BG_OPACITY
        roi = roi * (1 - mask) + self.text_bgr * mask
        frame[y:y + h, x:x + w] = roi.astype(np.uint8)


PROJECT_DIR = Path(__file__).resolve().parent
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm"}

# Windows'ta ffmpeg her video için ayrı bir siyah konsol penceresi açmasın
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class Cancelled(Exception):
    pass


def open_video(src):
    cap = cv2.VideoCapture(str(src))
    if cap.isOpened() or sys.platform != "win32":
        return cap
    # Windows'ta OpenCV Türkçe karakterli (ş, ğ, ı...) yolları açamayabiliyor.
    # Aynı dosyanın kısa (8.3) adı sadece ASCII içerir, onu deneriz.
    import ctypes
    buf = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.kernel32.GetShortPathNameW(str(src), buf, len(buf)):
        cap = cv2.VideoCapture(buf.value)
    return cap


def parse_time(value):
    return datetime.strptime(value, "%d-%m-%Y %H:%M:%S")


def norm_name(name):
    # macOS Türkçe harfleri (ş, ğ, ü...) bazen iki parça halinde saklar (s + ¸).
    # Ekranda aynı görünse de Python farklı sayar; NFC ile tek biçime çeviriyoruz.
    return unicodedata.normalize("NFC", name.strip())


def start_times():
    return {norm_name(k): v for k, v in START_TIMES.items()}


def start_time_for(rel):
    times = start_times()
    value = times.get(norm_name(rel.as_posix()))  # "video.mp4"
    if value is None:
        value = times.get(norm_name(rel.with_suffix("").as_posix()), START_TIME)  # "video"
    return parse_time(value) if value else datetime.now().replace(microsecond=0)


def check_start_times(input_dir, videos):
    rels = set()
    for v in videos:
        rel = v.relative_to(input_dir)
        rels.add(norm_name(rel.as_posix()))
        rels.add(norm_name(rel.with_suffix("").as_posix()))
    for name, value in start_times().items():
        try:
            parse_time(value)
        except ValueError:
            raise SystemExit(f'START_TIMES hatalı tarih: "{name}": "{value}" (biçim: GG-AA-YYYY SS:DD:SS)')
        if name not in rels:
            close = difflib.get_close_matches(name, rels, n=1, cutoff=0.6)
            hint = f' Bunu mu demek istediniz: "{close[0]}"?' if close else ""
            print(f'UYARI: START_TIMES içindeki "{name}" {INPUT_DIR} klasöründe bulunamadı.{hint}')
    if START_TIME:
        parse_time(START_TIME)


# Denenecek kodlayıcılar, en hızlıdan yavaşa: (ekranda görünen ad, ffmpeg ayarları).
# Ekran kartı ya da işlemcinin içindeki grafik birimi, videoyu işlemcinin kendisinden çok daha hızlı sıkıştırır.
ENCODERS = {
    "nvenc": ("NVIDIA ekran kartı", ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", str(CRF),
                                     "-b:v", "0", "-pix_fmt", "yuv420p"]),
    "qsv": ("Intel grafik (Quick Sync)", ["-c:v", "h264_qsv", "-preset", "medium", "-global_quality", str(CRF),
                                          "-pix_fmt", "nv12"]),
    "amf": ("AMD grafik", ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "cqp",
                           "-qp_i", str(CRF), "-qp_p", str(CRF), "-pix_fmt", "nv12"]),
    "cpu": ("İşlemci", ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(CRF), "-pix_fmt", "yuv420p"]),
}

_encoder = None
_encoder_lock = threading.Lock()


def encoder_works(key):
    # Bir saniyelik boş görüntüyü sıkıştırmayı dener; sürücüsü olmayan kart burada elenir
    cmd = [find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-f", "lavfi",
           "-i", "color=black:s=1280x720:r=30:d=1", "-frames:v", "5", *ENCODERS[key][1], "-f", "null", "-"]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=20, creationflags=NO_WINDOW).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def pick_encoder():
    # Bilgisayardaki en hızlı çalışan kodlayıcı; bir kez denenir, sonra hatırlanır
    global _encoder
    with _encoder_lock:
        if _encoder is None:
            choice = os.environ.get("ZM_ENCODER", ENCODER)
            if choice != "auto":
                _encoder = choice
            else:
                _encoder = next((k for k in ("nvenc", "qsv", "amf") if encoder_works(k)), "cpu")
        return _encoder


def video_duration(src):
    out = subprocess.run([find_ffmpeg(), "-hide_banner", "-i", str(src)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         creationflags=NO_WINDOW).stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", out)
    if not m or "Video:" not in out:
        raise RuntimeError("video açılamadı")
    h, mnt, sec = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(sec)


def drawtext_filter(start):
    # Saati ffmpeg'in kendisi basar: her kare için "başlangıç + videodaki saniye".
    # gmtime kullanıldığı için başlangıç, saat dilimi hesabı yapılmadan olduğu gibi verilir.
    epoch = int((start - datetime(1970, 1, 1)).total_seconds())
    font = Path(FONT_PATH).as_posix().replace(":", "\\:")
    text = f"%{{pts\\:gmtime\\:{epoch}\\:%d-%m-%Y %a %H\\\\\\:%M\\\\\\:%S}}"
    color = "0x%02x%02x%02x" % TEXT_COLOR
    box = "0x%02x%02x%02x@%.2f" % (*BG_COLOR, BG_OPACITY)
    return (f"drawtext=fontfile='{font}':text='{text}':fontsize={FONT_SIZE}:fontcolor={color}:"
            f"box={1 if BG_OPACITY > 0 else 0}:boxcolor={box}:boxborderw={PADDING}:"
            f"x={MARGIN_LEFT + PADDING}:y={MARGIN_TOP + PADDING}")


def encode(src, tmp, start, duration, encoder, hw_decode, on_progress, should_stop):
    cmd = [find_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-nostats",
           "-progress", "pipe:1", "-stats_period", "0.5"]
    if hw_decode:
        cmd += ["-hwaccel", "auto"]  # kodlamayı da mümkünse grafik birimi çözsün
    cmd += ["-i", str(src), "-map", "0:v:0", "-vf", drawtext_filter(start), *ENCODERS[encoder][1],
            "-an", "-movflags", "+faststart", str(tmp)]
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err, creationflags=NO_WINDOW,
                                text=True, encoding="utf-8", errors="replace")
        try:
            for line in proc.stdout:
                if should_stop and should_stop():
                    proc.terminate()
                    proc.wait()
                    raise Cancelled()
                if line.startswith("out_time_us=") and duration > 0:
                    us = line.split("=", 1)[1].strip()
                    if us.lstrip("-").isdigit():
                        fraction = min(max(int(us) / 1e6 / duration, 0.0), 1.0)
                        if on_progress:
                            on_progress(fraction)
                        else:
                            print(f"\r  %{int(fraction * 100)}", end="", flush=True)
            code = proc.wait()
        except BaseException:
            proc.kill()
            proc.wait()
            raise
        if code != 0:
            err.seek(0)
            detail = err.read().decode("utf-8", "replace").strip().splitlines()[-3:]
            raise RuntimeError("ffmpeg hata verdi: " + " | ".join(detail))


def process(src, dst, start, on_progress=None, should_stop=None):
    # on_progress(oran): 0-1 arası ilerleme. should_stop(): True dönerse iş iptal edilir.
    # Hangi kodlayıcıyla yapıldığını döner ("qsv", "cpu"...).
    duration = video_duration(src)

    # Önce geçici dosyaya yazılır, bitince asıl adına çevrilir.
    # Böylece yarıda kesilen işlem "tamamlanmış" sanılıp atlanmaz.
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + ".part.mp4")

    # Önce en hızlı yol denenir; grafik birimi bu videoda sorun çıkarırsa işlemciyle baştan yapılır
    # (İşlemci yolunda donanımla çözme kullanılmaz; ölçümde yavaşlattı.)
    encoder = pick_encoder()
    attempts = [("cpu", False)] if encoder == "cpu" else [(encoder, True), ("cpu", False)]
    try:
        for i, (enc, hw_decode) in enumerate(attempts):
            try:
                encode(src, tmp, start, duration, enc, hw_decode, on_progress, should_stop)
                tmp.replace(dst)
                if not on_progress:
                    print()
                return enc
            except RuntimeError:
                if i == len(attempts) - 1:
                    raise
    finally:
        tmp.unlink(missing_ok=True)


def find_videos(input_dir):
    # rglob("*") = girdi klasörü ve içindeki TÜM alt klasörler
    return sorted(
        f for f in input_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in VIDEO_EXTS and not f.name.startswith(".")
    )


def main():
    input_dir = PROJECT_DIR / INPUT_DIR
    output_dir = PROJECT_DIR / OUTPUT_DIR
    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    if len(sys.argv) > 1:
        videos = [input_dir / name for name in sys.argv[1:]]
        missing = [str(v.relative_to(input_dir)) for v in videos if not v.is_file()]
        if missing:
            raise SystemExit(f"{INPUT_DIR} klasöründe bulunamadı: {', '.join(missing)}")
    else:
        videos = find_videos(input_dir)
        if not videos:
            raise SystemExit(f"{INPUT_DIR} klasöründe video yok.")

    check_start_times(input_dir, videos)

    done, skipped, failed = 0, 0, []
    used = set()
    for i, src in enumerate(videos, 1):
        rel = src.relative_to(input_dir)
        # Çıktıda girdi ile aynı klasör yapısı kurulur:
        # girdi/kamera1/a.mp4 -> cikti/kamera1/a.mp4  (a.mov -> a.mp4)
        dst = output_dir / rel.parent / f"{src.stem}.mp4"
        if dst in used:
            print(f"[{i}/{len(videos)}] {rel}\n  Atlandı: aynı adlı başka bir video da {dst.relative_to(PROJECT_DIR)} üretiyor, birini yeniden adlandırın.")
            failed.append(str(rel))
            continue
        used.add(dst)
        print(f"[{i}/{len(videos)}] {rel}")
        if dst.exists() and not OVERWRITE:
            print("  Atlandı (çıktısı zaten var)")
            skipped += 1
            continue
        try:
            process(src, dst, start_time_for(rel))
            done += 1
        except Exception as e:
            print(f"\n  HATA: {e}")
            failed.append(str(rel))

    print(f"\nBitti: {done} işlendi, {skipped} atlandı, {len(failed)} hatalı.")
    for name in failed:
        print(f"  Hatalı: {name}")


if __name__ == "__main__":
    main()
