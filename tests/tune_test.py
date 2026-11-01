"""
En hızlı ayar ölçümünün kuralları (gerçek grafik birimi gerekmez; kodlayıcı taklit edilir).
    uv run python tests/tune_test.py
Çıkış kodu 0 = hepsi geçti.
"""

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main

results = []


def check(name, cond):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name, flush=True)


QUALITY = {}  # ayar -> taklit SSIM (verilmezse 0.98)


def fake_ssim(reference, encoded, timeout=None):
    return QUALITY.get(Path(encoded).stem, 0.98)


main.ssim = fake_ssim


def fake_encoder(speeds, broken=(), sizes=None):
    """Her ayar, verilen "gerçek zamanın kaç katı" hızında ilerleme bildirir ve verilen boyutta dosya yazar.
    Bazıları hata verir."""
    called = []

    def encode(src, tmp, start, duration, key, hw, on_progress, should_stop, timeout=None, kbps=None):
        called.append(key)
        if key in broken:
            raise RuntimeError("bozuk")
        time.sleep(0.3)  # her ayarın sabit hazırlık süresi: ölçüme katılmamalı
        for i in range(1, 21):
            time.sleep(duration / speeds[key] / 20)
            on_progress(i / 20)
        Path(tmp).write_bytes(b"x" * (sizes or {}).get(key, 1000))

    return encode, called


cache = Path(tempfile.mkdtemp()) / "hiz.json"
main.TUNE_SAMPLE_SECONDS = 10  # sahte süreler (oranlar gerçek değil; ölçüm titreşimi az olsun diye 10)

# 1) Intel grafik var: denemede işlemci çok hızlı görünse bile işlemci hiç ölçülmez, seçilmez
main.encode, called = fake_encoder({"qsv": 40, "qsv_fast": 44, "qsv_lp": 52, "cpu": 200, "cpu_hwdec": 150})
main._encoder = "qsv"
r, timed_out = main.tune(cache, ["cpu", "qsv"])
print("   ölçüm:", r, "->", main._encoder)
check("grafik varken işlemci ölçülmez", not any(k.startswith("cpu") for k in called))
check("grafik ayarları arasından en hızlısı seçilir", main._encoder == "qsv_lp")

# 2) %10 kuralı: sadece biraz daha hızlı olan, daha az bilinen ayara geçilmez
main.encode, called = fake_encoder({"qsv": 40, "qsv_fast": 41, "qsv_lp": 41.5})  # en fazla %4 fark
r, _ = main.tune(cache, ["cpu", "qsv"])
check("%10'dan az fark için güvenli ayarda kalınır", main._encoder == "qsv")

# 3) Hazırlık süresi hariç: yavaş başlayan ama hızlı çalışan ayar kazanır
main.encode, called = fake_encoder({"nvenc": 30, "nvenc_fast": 60, "qsv": 35, "qsv_fast": 36, "qsv_lp": 37})
r, _ = main.tune(cache, ["cpu", "nvenc", "qsv"])
check("birden çok grafik birimi yarıştırılır", any(k.startswith("nvenc") for k in called)
      and any(k.startswith("qsv") for k in called))
check("en hızlı aile ve ayar seçilir", main._encoder == "nvenc_fast")

# 3b) Boyut kuralı: çok daha büyük dosya üreten ayar, en hızlısı olsa da seçilmez
#    (gerçek olay: i5-1135G7'de qsv_lp %20 hızlıydı ama 400 MB'tan 1 GB çıkardı)
main.encode, called = fake_encoder({"qsv": 40, "qsv_fast": 50, "qsv_lp": 60},
                                   sizes={"qsv": 1000, "qsv_fast": 1050, "qsv_lp": 2500})
r, _ = main.tune(cache, ["cpu", "qsv"])
print("   ölçüm:", r)
check("büyük dosya üreten ayar elenir", r["qsv_lp"]["ok"] is False and main._encoder != "qsv_lp")
check("benzer boyutta ve hızlı olan seçilir", main._encoder == "qsv_fast")
main.encode, called = fake_encoder({"qsv": 40, "qsv_fast": 50, "qsv_lp": 60},
                                   sizes={"qsv": 1000, "qsv_fast": 1500, "qsv_lp": 2500})
r, _ = main.tune(cache, ["cpu", "qsv"])
check("hepsi büyükse varsayılanda kalınır", main._encoder == "qsv")

# 3c) Kalite kuralı: aynı boyutta ama görüntüsü belirgin kötü olan hızlı ayar seçilmez
QUALITY.update({"qsv": 0.985, "qsv_fast": 0.984, "qsv_lp": 0.970})
main.encode, called = fake_encoder({"qsv": 40, "qsv_fast": 44, "qsv_lp": 60})
r, _ = main.tune(cache, ["cpu", "qsv"])
print("   ölçüm:", r)
check("düşük kaliteli hızlı ayar elenir", r["qsv_lp"]["ok"] is False and main._encoder != "qsv_lp")
QUALITY.clear()

# 4) Grafik ayarlarının hepsi bozuksa işlemciye dönülür
main.encode, called = fake_encoder({"cpu": 20, "cpu_hwdec": 10}, broken=("qsv", "qsv_fast", "qsv_lp"))
r, _ = main.tune(cache, ["cpu", "qsv"])
check("grafik bozuksa işlemci ölçülür ve seçilir", main._encoder == "cpu")

# 5) Grafik birimi yoksa sadece işlemci ölçülür
main.encode, called = fake_encoder({"cpu": 20, "cpu_hwdec": 30})
r, _ = main.tune(cache, ["cpu"])
check("grafik yokken işlemci ayarları yarışır", set(called) == {"cpu", "cpu_hwdec"} and main._encoder == "cpu_hwdec")

# 6) Kayıt ve sürüm: aynı donanım + aynı TUNE_VERSION ise yeniden ölçülmez
main._encoder, main.tuned = None, False
check("kayıttan okunur", main.load_tuning(cache, ["cpu"]) and main._encoder == "cpu_hwdec")
check("donanım değişince yeniden ölçülür", not main.load_tuning(cache, ["cpu", "qsv"]))
main.TUNE_VERSION += 1
check("TUNE_VERSION artınca yeniden ölçülür", not main.load_tuning(cache, ["cpu"]))

# 7) Boyut tavanı: H.264 girişte girişin kendisi, verimli formatlarda daha fazlası, hepsinde üst sınır
t = main.target_kbps
check("tavan: H.264 giriş = giriş bit hızı", t({"width": 1920, "height": 1080, "fps": 60, "bitrate": 5200, "codec": "h264"}) == 5200)
check("tavan: AV1 giriş 1,5 katı", t({"width": 1920, "height": 1080, "fps": 60, "bitrate": 4000, "codec": "av1"}) == 6000)
check("tavan: yüksek bit hızlı kamera üst sınırda", t({"width": 1920, "height": 1080, "fps": 30, "bitrate": 50000, "codec": "h264"}) == 6220)

print(f"\n{sum(results)}/{len(results)} geçti")
sys.exit(0 if all(results) else 1)
