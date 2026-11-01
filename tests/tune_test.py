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


def fake_encoder(speeds, broken=()):
    """Her ayar, verilen "gerçek zamanın kaç katı" hızında ilerleme bildirir. Bazıları hata verir."""
    called = []

    def encode(src, tmp, start, duration, key, hw, on_progress, should_stop, timeout=None):
        called.append(key)
        if key in broken:
            raise RuntimeError("bozuk")
        time.sleep(0.3)  # her ayarın sabit hazırlık süresi: ölçüme katılmamalı
        for i in range(1, 21):
            time.sleep(duration / speeds[key] / 20)
            on_progress(i / 20)
        Path(tmp).write_bytes(b"x")

    return encode, called


cache = Path(tempfile.mkdtemp()) / "hiz.json"
main.TUNE_SAMPLE_SECONDS = 4  # testi kısaltmak için (oranlar değişmez)

# 1) Intel grafik var: denemede işlemci çok hızlı görünse bile işlemci hiç ölçülmez, seçilmez
main.encode, called = fake_encoder({"qsv": 40, "qsv_fast": 44, "qsv_lp": 52, "cpu": 200, "cpu_hwdec": 150})
main._encoder = "qsv"
r, timed_out = main.tune(cache, ["cpu", "qsv"])
print("   ölçüm:", r, "->", main._encoder)
check("grafik varken işlemci ölçülmez", not any(k.startswith("cpu") for k in called))
check("grafik ayarları arasından en hızlısı seçilir", main._encoder == "qsv_lp")

# 2) %10 kuralı: sadece biraz daha hızlı olan, daha az bilinen ayara geçilmez
main.encode, called = fake_encoder({"qsv": 40, "qsv_fast": 42, "qsv_lp": 43})
r, _ = main.tune(cache, ["cpu", "qsv"])
check("%10'dan az fark için güvenli ayarda kalınır", main._encoder == "qsv")

# 3) Hazırlık süresi hariç: yavaş başlayan ama hızlı çalışan ayar kazanır
main.encode, called = fake_encoder({"nvenc": 30, "nvenc_fast": 60, "qsv": 35, "qsv_fast": 36, "qsv_lp": 37})
r, _ = main.tune(cache, ["cpu", "nvenc", "qsv"])
check("birden çok grafik birimi yarıştırılır", any(k.startswith("nvenc") for k in called)
      and any(k.startswith("qsv") for k in called))
check("en hızlı aile ve ayar seçilir", main._encoder == "nvenc_fast")

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

print(f"\n{sum(results)}/{len(results)} geçti")
sys.exit(0 if all(results) else 1)
