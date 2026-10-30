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

# Gün kısaltmaları (Pazartesiden başlayarak)
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Video kalitesi: küçük sayı = daha kaliteli ama büyük dosya (17-23 arası önerilir)
CRF = 23

# Klasörler (proje klasörüne göre)
INPUT_DIR = "girdi"
OUTPUT_DIR = "cikti"

# Çıktıda zaten aynı isimde dosya varsa: True = üzerine yaz, False = atla
OVERWRITE = False

# =============================================================================

import difflib
import shutil
import subprocess
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


def process(src, dst, start, on_progress=None, should_stop=None):
    # on_progress(oran): 0-1 arası ilerleme. should_stop(): True dönerse iş iptal edilir.
    cap = open_video(src)
    if not cap.isOpened():
        raise RuntimeError("video açılamadı")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Önce geçici dosyaya yazılır, bitince asıl adına çevrilir.
    # Böylece yarıda kesilen işlem "tamamlanmış" sanılıp atlanmaz.
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + ".part.mp4")

    renderer = TextRenderer()
    proc = subprocess.Popen([
        find_ffmpeg(), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", str(CRF), "-pix_fmt", "yuv420p",
        "-an", "-movflags", "+faststart", str(tmp),
    ], stdin=subprocess.PIPE, creationflags=NO_WINDOW)

    idx = 0
    ok_done = False
    try:
        while True:
            if should_stop and should_stop():
                raise Cancelled()
            ok, frame = cap.read()
            if not ok:
                break
            if frame.shape[1] != w or frame.shape[0] != h:
                frame = cv2.resize(frame, (w, h))

            ms = cap.get(cv2.CAP_PROP_POS_MSEC)
            elapsed = ms / 1000.0 if ms > 0 or idx == 0 else idx / fps
            renderer.draw(frame, format_ts(start + timedelta(seconds=int(elapsed))), MARGIN_LEFT, MARGIN_TOP)

            proc.stdin.write(frame.tobytes())
            idx += 1
            if on_progress:
                if idx % 10 == 0 and total:
                    on_progress(min(idx / total, 1.0))
            elif idx % 100 == 0 and total:
                print(f"\r  {idx}/{total} kare (%{min(idx * 100 // total, 100)})", end="", flush=True)
        ok_done = idx > 0
    finally:
        cap.release()
        proc.stdin.close()
        ffmpeg_ok = proc.wait() == 0
        if ok_done and ffmpeg_ok:
            tmp.replace(dst)
        else:
            tmp.unlink(missing_ok=True)
    if not ok_done:
        raise RuntimeError("videodan kare okunamadı")
    if not ffmpeg_ok:
        raise RuntimeError("ffmpeg hata verdi")
    if not on_progress:
        print()


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
