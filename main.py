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

# Boyut tavanı: çıktının bit hızı ne girişin bit hızını ne de "piksel başına bit" sınırını aşar. Böylece çıktı
# girişle yaklaşık aynı boyutta kalır (H.264 girişte ±%5); çok yüksek bit hızlı kaynaklarda makul boyuta iner.
# Çıktı her zaman H.264'tür; H.264'ten verimli girişlerde (HEVC/VP9/AV1) görüntü bozulmasın diye tavan girişin
# bu katı kadardır. Örn. AV1 girişi aynı bit hızına sıkıştırmak görüntüyü belirgin bozar.
CODEC_RATE_FACTOR = {"hevc": 1.4, "vp9": 1.4, "av1": 1.5}
# 0.10 bit/piksel: 1080p30 ≈ 6,2 Mbit/sn, 1080p60 ≈ 12,4 Mbit/sn, 720p25 ≈ 2,3 Mbit/sn.
MAX_BITS_PER_PIXEL = 0.10

# Videoyu sıkıştıracak kodlayıcı. "auto" = bilgisayarda hangisi varsa en hızlısı
# (NVIDIA / Intel / AMD grafik, yoksa işlemci). Elle seçmek için PROFILES'tan bir anahtar: "qsv", "cpu"...
ENCODER = "auto"

# Klasörler (proje klasörüne göre)
INPUT_DIR = "girdi"
OUTPUT_DIR = "cikti"

# Çıktıda zaten aynı isimde dosya varsa: True = üzerine yaz, False = atla
OVERWRITE = False

# =============================================================================

import difflib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
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


# Grafik birimleri ve işlemci için aday ayarlar: anahtar -> (aile, ffmpeg ayarları, donanımla çözme).
# Her ailenin ilki en güvenli ayardır. Hangisinin en hızlı olduğu bilgisayardan bilgisayara değiştiği için
# uygulama bunları bir kez kendi bilgisayarında ölçer (tune) ve en hızlısını kullanır.
FAMILIES = {
    "nvenc": "NVIDIA ekran kartı",
    "qsv": "Intel grafik (Quick Sync)",
    "amf": "AMD grafik",
    "cpu": "İşlemci",
}
# Hız kontrolü (rate_args) ayrıca eklenir: her videonun kendi bit hızı tavanına göre.
_NV = ["-c:v", "h264_nvenc", "-pix_fmt", "yuv420p"]
_QSV = ["-c:v", "h264_qsv", "-pix_fmt", "nv12"]
_AMF = ["-c:v", "h264_amf", "-pix_fmt", "nv12"]
_X264 = ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
PROFILES = {
    "nvenc":      ("nvenc", [*_NV, "-preset", "p4"], True),
    "nvenc_fast": ("nvenc", [*_NV, "-preset", "p1"], True),
    "qsv":        ("qsv", [*_QSV, "-preset", "medium"], True),
    "qsv_fast":   ("qsv", [*_QSV, "-preset", "veryfast"], True),
    "qsv_lp":     ("qsv", [*_QSV, "-preset", "veryfast", "-low_power", "1"], True),  # yeni Intel'lerde
    "amf":        ("amf", [*_AMF, "-quality", "balanced"], True),
    "amf_fast":   ("amf", [*_AMF, "-quality", "speed"], True),
    "cpu":        ("cpu", _X264, False),
    "cpu_hwdec":  ("cpu", _X264, True),  # zayıf işlemcide videoyu grafik birimi çözsün
}

def rate_args(family, kbps):
    """Bit hızı tavanı kbps olacak şekilde hız kontrolü.
    NVENC ve işlemci: kalite hedefi (CRF 23) + tavan; kolay görüntüde tavanın altında kalır.
    Quick Sync ve AMD: tavanı hedefleyen değişken bit hızı (kalite hedefiyle tavan birlikte kullanılamıyor)."""
    cap = ["-maxrate", f"{kbps}k", "-bufsize", f"{2 * kbps}k"]
    if family == "nvenc":
        return ["-rc", "vbr", "-cq", str(CRF), "-b:v", "0", *cap]
    if family == "qsv":
        return ["-b:v", f"{kbps}k", *cap]
    if family == "amf":
        return ["-rc", "vbr_peak", "-b:v", f"{kbps}k", *cap]
    return ["-crf", str(CRF), *cap]


def target_kbps(info):
    # Çıktının bit hızı tavanı: girişin bit hızı ve piksel başına bit sınırından küçük olanı
    ceiling = info["width"] * info["height"] * max(info["fps"] or 30, 1) * MAX_BITS_PER_PIXEL / 1000
    source = info["bitrate"] * CODEC_RATE_FACTOR.get(info.get("codec"), 1.0) if info.get("bitrate") else ceiling
    return max(int(min(source, ceiling)), 300)


_encoder = None  # kullanılan ayar (PROFILES anahtarı)
_encoder_lock = threading.Lock()
tuned = False  # bu bilgisayar için ölçülerek mi seçildi


SHORT_NAMES = {"nvenc": "NVIDIA NVENC", "qsv": "Intel Quick Sync", "amf": "AMD AMF", "cpu": "İşlemci"}


def profile_name(key):
    return FAMILIES[PROFILES[key][0]]


def short_name(key):
    return SHORT_NAMES[PROFILES[key][0]]


def encoder_works(key):
    # Bir saniyelik boş görüntüyü sıkıştırmayı dener; sürücüsü olmayan kart burada elenir
    cmd = [find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-f", "lavfi",
           "-i", "color=black:s=1280x720:r=30:d=1", "-frames:v", "5", *PROFILES[key][1],
           *rate_args(PROFILES[key][0], 3000), "-f", "null", "-"]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=20, creationflags=NO_WINDOW).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def pick_encoder():
    # Hemen kullanılabilecek güvenli seçim: çalışan ilk grafik biriminin varsayılan ayarı, yoksa işlemci.
    # tune() sonra bunu bu bilgisayar için en hızlı ayarla değiştirebilir.
    global _encoder
    with _encoder_lock:
        if _encoder is None:
            choice = os.environ.get("ZM_ENCODER", ENCODER)
            if choice != "auto":
                _encoder = choice
            else:
                _encoder = next((k for k in ("nvenc", "qsv", "amf") if encoder_works(k)), "cpu")
        return _encoder


# Ölçümün ne zaman yeniden yapılacağı: aday ayarlar ya da ölçüm yöntemi değişince bu sayıyı artırın.
# Uygulamanın her sürümünde değil; metin değişikliği gibi güncellemeler yeniden ölçtürmez.
# 1: ilk ölçüm. 2: grafik birimi varsa işlemciyle yarıştırılmaz; ölçüm daha uzun, kumlu videoyla ve
#    hazırlık süresi hariç (1. sürüm kısa/kolay denemede işlemciyi turbo sayesinde hızlı sanıyordu).
# 3: dosya boyutu da ölçülür; varsayılandan belirgin büyük dosya üreten ayar elenir (v2, i5-1135G7'de
#    qsv_lp'yi seçti: %20 daha hızlı ama 400 MB'lık girişten 1 GB çıktı).
# 4: çıktıya bit hızı tavanı (girişten büyük olmasın) ve görüntü kalitesi (SSIM) kuralı.
TUNE_VERSION = 4
TUNE_SIZE_TOLERANCE = 0.10  # bir ayar, ailesinin varsayılanından en fazla %10 büyük dosya üretebilir
TUNE_QUALITY_TOLERANCE = 0.005  # görüntü benzerliği (SSIM) varsayılandan en fazla bu kadar düşük olabilir

# Ölçüm süre sınırları (saniye). Bir ayar takılırsa ya da bilgisayar çok yavaşsa ölçüm bunları aşmaz;
# toplam süre dolarsa güvenli varsayılan ayar seçilir.
TUNE_STEP_LIMIT = 45
TUNE_TOTAL_LIMIT = 120
TUNE_SAMPLE_SECONDS = 20  # deneme videosunun uzunluğu
TUNE_WARMUP = 0.2         # videonun ilk %20'si hazırlık sayılır, hıza katılmaz


def working_families():
    # Bu bilgisayarda çalışan grafik birimleri. Ekran kartı takılır/çıkarılırsa değişir ve yeniden ölçülür.
    return ["cpu"] + [f for f in ("nvenc", "qsv", "amf") if encoder_works(f)]


def load_tuning(cache_file, families):
    """Daha önce bu donanım için ölçülmüş ayar varsa onu kullanır. Ölçüm gerekiyorsa False döner."""
    global _encoder, tuned
    if os.environ.get("ZM_ENCODER", ENCODER) != "auto":
        return True  # elle seçilmiş; ölçüme gerek yok
    try:
        cached = json.loads(Path(cache_file).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if (cached.get("tune_version") != TUNE_VERSION or cached.get("families") != families
            or cached.get("profile") not in PROFILES):
        return False
    with _encoder_lock:
        _encoder, tuned = cached["profile"], True
    return True


def ssim(reference, encoded, timeout=None):
    """İki videonun görüntü benzerliği (SSIM, 1 = aynı). Hız için her 6. kare, yarı çözünürlükte karşılaştırılır.
    Saat yazısı her adayda aynı yerde olduğu için karşılaştırmayı adaylar arasında eşit etkiler."""
    pick = "select='not(mod(n\\,6))',scale=960:540,setpts=N/TB"
    cmd = [find_ffmpeg(), "-hide_banner", "-nostats", "-i", str(encoded), "-i", str(reference), "-lavfi",
           f"[0:v]{pick}[a];[1:v]{pick}[b];[a][b]ssim", "-f", "null", "-"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                             timeout=timeout, creationflags=NO_WINDOW).stderr
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"All:([\d.]+)", out)
    return float(m.group(1)) if m else None


def tune_candidates(families):
    return [k for k, (fam, _, _) in PROFILES.items() if fam in families]


def tune(cache_file, families, on_step=None, should_stop=None):
    """Bu bilgisayardaki en hızlı ayarı ölçer, seçer ve kaydeder.

    Kurallar:
    - Çalışan bir grafik birimi varsa sadece grafik ayarları yarıştırılır; işlemci hiç seçilmez.
      Kısa bir denemede işlemci turbo sayesinde hızlı görünür ama uzun, gerçek videolarda grafik birimi
      çok daha hızlıdır (i5-1135G7: deneme işlemci 4,9x / Quick Sync 3,2x; gerçek 10 dk video işlemci 2,2x /
      Quick Sync 3,2x). İşlemci ayarları sadece grafik birimi yoksa ya da hiçbiri çalışmazsa ölçülür.
    - TUNE_SAMPLE_SECONDS sn'lik, kumlu (gerçek kameraya yakın) 1080p30 deneme videosu kullanılır.
    - Hız, hazırlık süresi hariç ölçülür: videonun ilk TUNE_WARMUP kısmı sayılmaz; kalanının
      işlenme hızı (gerçek zamanın kaç katı) karşılaştırılır.
    - Her ayar en fazla TUNE_STEP_LIMIT sn sürebilir; toplam TUNE_TOTAL_LIMIT sn dolarsa ölçüm bırakılır ve
      güvenli varsayılan ayar (pick_encoder) seçilip kaydedilir.
    on_step(sıra, toplam, ayar): her denemeden önce çağrılır.
    should_stop(): True dönerse (uygulama kapanıyor) hiçbir şey kaydedilmeden çıkılır.
    - Dosya boyutu ve görüntü benzerliği (SSIM) de ölçülür: varsayılan ayarlardan TUNE_SIZE_TOLERANCE'tan
      fazla büyük dosya ya da TUNE_QUALITY_TOLERANCE'tan fazla düşük benzerlik üreten ayar, ne kadar hızlı
      olursa olsun seçilmez.
    Döner: ({ayar: {"speed": gerçek zamanın kaç katı, "size": bayt, "ok": boyut kuralını geçti mi}},
            süre_aşıldı_mı) ya da kapatıldıysa (None, False).
    """
    global _encoder, tuned
    stop = should_stop or (lambda: False)
    deadline = time.monotonic() + TUNE_TOTAL_LIMIT
    out_of_time = lambda: time.monotonic() > deadline
    gpu = [f for f in families if f != "cpu"]
    results = {}
    timed_out = False
    seconds = TUNE_SAMPLE_SECONDS
    with tempfile.TemporaryDirectory() as d:
        sample = Path(d) / "olcum.mp4"
        try:
            subprocess.run([find_ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi",
                            "-i", f"testsrc2=s=1920x1080:r=30:d={seconds},noise=alls=12:allf=t+u",
                            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p",
                            str(sample)], check=True, creationflags=NO_WINDOW, timeout=TUNE_STEP_LIMIT)
        except (subprocess.SubprocessError, OSError):
            timed_out = True
        start = datetime(2026, 1, 1)
        kbps = target_kbps({"width": 1920, "height": 1080, "fps": 30, "bitrate": None})

        def measure(candidates):
            nonlocal timed_out
            for i, key in enumerate(candidates):
                if timed_out or stop():
                    return
                if out_of_time():
                    timed_out = True
                    return
                if on_step:
                    on_step(i, len(candidates), key)
                marks = []  # (ilerleme, zaman)
                limit = min(TUNE_STEP_LIMIT, max(deadline - time.monotonic(), 1))
                out = Path(d) / f"{key}.mp4"
                try:
                    encode(sample, out, start, seconds, key, None,
                           lambda f: marks.append((f, time.perf_counter())),
                           lambda: stop() or out_of_time(), timeout=limit, kbps=kbps)
                except (RuntimeError, Cancelled):
                    continue
                end = time.perf_counter()
                warm = next(((f, t) for f, t in marks if f >= TUNE_WARMUP), None)
                if warm and warm[0] < 0.95 and end > warm[1] and out.exists():
                    quality = ssim(sample, out, timeout=max(deadline - time.monotonic(), 1))
                    results[key] = {"speed": round(seconds * (1 - warm[0]) / (end - warm[1]), 2),
                                    "size": out.stat().st_size,
                                    "ssim": round(quality, 4) if quality is not None else None}

        # Önce grafik birimleri; hiçbiri yoksa ya da hiçbiri çalışmadıysa işlemci
        if gpu:
            measure(tune_candidates(gpu))
        if not results and not stop():
            measure(tune_candidates(["cpu"]))
    if stop():
        return None, False

    candidates = tune_candidates(families)
    if results:
        # Boyut kuralı: hız, dosyayı büyütmenin bedeli olamaz. Ölçülen varsayılan ayarların (nvenc, qsv, amf,
        # cpu) en küçük çıktısı ölçüttür; ondan TUNE_SIZE_TOLERANCE'tan fazla büyük dosya üreten ayar elenir.
        defaults = [results[k]["size"] for k in results if k in FAMILIES]
        limit_size = min(defaults or [r["size"] for r in results.values()]) * (1 + TUNE_SIZE_TOLERANCE)
        # Kalite kuralı: hız, görüntüyü bozmanın bedeli de olamaz. Ölçülen varsayılanların en iyi benzerliğinden
        # TUNE_QUALITY_TOLERANCE'tan fazla düşük olan ayar elenir (ölçülemeyen benzerlik kuralı atlar).
        default_q = [results[k]["ssim"] for k in results if k in FAMILIES and results[k].get("ssim") is not None]
        limit_q = max(default_q) - TUNE_QUALITY_TOLERANCE if default_q else None
        for r in results.values():
            r["ok"] = r["size"] <= limit_size and (limit_q is None or r.get("ssim") is None or r["ssim"] >= limit_q)
    eligible = [k for k in sorted(results, key=candidates.index) if results[k]["ok"]]
    if timed_out or not eligible:
        # Süre doldu (ya da uygun ayar yok): güvenli varsayılanla çalışılır
        best, timed_out = pick_encoder(), timed_out or not results
    else:
        # Aday sırası güvenliden hızlıya; daha az bilinen bir ayara ancak en az %10 daha hızlıysa geçilir
        best = eligible[0]
        for key in eligible:
            if results[key]["speed"] > results[best]["speed"] * 1.1:
                best = key
    with _encoder_lock:
        _encoder, tuned = best, True
    try:
        Path(cache_file).write_text(json.dumps({"tune_version": TUNE_VERSION, "families": families,
                                                "profile": best, "results": results,
                                                "timed_out": timed_out}), encoding="utf-8")
    except OSError:
        pass
    return results, timed_out


def video_info(src):
    # ffmpeg'in dosya özetinden süre, çözünürlük, fps ve kodek (ayrıca ffprobe gerekmesin)
    out = subprocess.run([find_ffmpeg(), "-hide_banner", "-i", str(src)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         creationflags=NO_WINDOW).stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", out)
    video = re.search(r"Video: (\w+).*?, (\d{2,5})x(\d{2,5})", out)
    if not m or not video:
        raise RuntimeError("video açılamadı")
    h, mnt, sec = m.groups()
    fps = re.search(r"([\d.]+) fps", out)
    # Önce video akışının kendi bit hızı, yoksa dosyanın toplam bit hızı (kb/s)
    line = out[video.start():].split("\n", 1)[0]
    rate = re.search(r"(\d+) kb/s", line) or re.search(r"bitrate: (\d+) kb/s", out)
    return {"duration": int(h) * 3600 + int(mnt) * 60 + float(sec), "codec": video.group(1),
            "width": int(video.group(2)), "height": int(video.group(3)),
            "fps": round(float(fps.group(1))) if fps else 0, "bitrate": int(rate.group(1)) if rate else None}


def video_duration(src):
    return video_info(src)["duration"]


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


def encode(src, tmp, start, duration, profile, hw_decode, on_progress, should_stop, timeout=None, kbps=6000):
    # hw_decode None ise ayarın kendi tercihi kullanılır. timeout: bu kadar saniyede bitmezse ffmpeg kapatılır
    # (sürücü takılıp hiç çıktı vermese bile). kbps: çıktının bit hızı tavanı (target_kbps).
    family, args, prefers_hw = PROFILES[profile]
    args = [*args, *rate_args(family, kbps)]
    cmd = [find_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-nostats",
           "-progress", "pipe:1", "-stats_period", "0.25"]
    if prefers_hw if hw_decode is None else hw_decode:
        cmd += ["-hwaccel", "auto"]  # videoyu da mümkünse grafik birimi çözsün
    cmd += ["-i", str(src), "-map", "0:v:0", "-vf", drawtext_filter(start), *args,
            "-an", "-movflags", "+faststart", str(tmp)]
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err, creationflags=NO_WINDOW,
                                text=True, encoding="utf-8", errors="replace")
        watchdog = threading.Timer(timeout, proc.kill) if timeout else None
        if watchdog:
            watchdog.start()
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
                        elif on_progress is not False:
                            print(f"\r  %{int(fraction * 100)}", end="", flush=True)
            code = proc.wait()
        except BaseException:
            proc.kill()
            proc.wait()
            raise
        finally:
            if watchdog:
                watchdog.cancel()
        if code != 0:
            err.seek(0)
            detail = err.read().decode("utf-8", "replace").strip().splitlines()[-3:]
            raise RuntimeError("ffmpeg hata verdi: " + " | ".join(detail))


def process(src, dst, start, on_progress=None, should_stop=None):
    # on_progress(oran): 0-1 arası ilerleme. should_stop(): True dönerse iş iptal edilir.
    # Hangi kodlayıcıyla yapıldığını döner ("qsv", "cpu"...).
    info = video_info(src)
    duration, kbps = info["duration"], target_kbps(info)

    # Önce geçici dosyaya yazılır, bitince asıl adına çevrilir.
    # Böylece yarıda kesilen işlem "tamamlanmış" sanılıp atlanmaz.
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + ".part.mp4")

    # Önce bu bilgisayar için seçilen en hızlı ayar denenir; grafik birimi bu videoda sorun çıkarırsa
    # işlemciyle (donanım yardımı olmadan, en güvenli yol) baştan yapılır.
    profile = pick_encoder()
    attempts = [(profile, None)] if profile == "cpu" else [(profile, None), ("cpu", False)]
    try:
        for i, (prof, hw_decode) in enumerate(attempts):
            try:
                encode(src, tmp, start, duration, prof, hw_decode, on_progress, should_stop, kbps=kbps)
                tmp.replace(dst)
                if not on_progress:
                    print()
                return prof
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
