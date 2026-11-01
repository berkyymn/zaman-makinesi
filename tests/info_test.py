"""
Video bilgisinin (kare hızı, bit hızı, renk derinliği, HDR) ve okuyucu bilgisinin doğru okunduğunu dener.
Deneme videolarını kendisi üretir.
    uv run python tests/info_test.py
Çıkış kodu 0 = hepsi geçti.
"""

import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main

results = []


def check(name, cond):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name, flush=True)


work = Path(tempfile.mkdtemp())
ff = main.find_ffmpeg()


def make(name, *args):
    path = work / name
    subprocess.run([ff, "-loglevel", "error", "-y", "-f", "lavfi", *args, str(path)], check=True)
    return path


h264 = make("h264.mp4", "-i", "testsrc2=s=1920x1080:r=60:d=2", "-c:v", "libx264", "-b:v", "5000k",
            "-pix_fmt", "yuv420p")
hlg = make("hlg.mp4", "-i", "testsrc2=s=1280x720:r=30000/1001:d=2", "-c:v", "libx265", "-preset", "ultrafast",
           "-pix_fmt", "yuv420p10le", "-tag:v", "hvc1",
           "-x265-params", "log-level=error:colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc")

info = main.video_info(h264)
check("H.264: kodek, çözünürlük, fps", info["codec"] == "h264" and (info["width"], info["height"]) == (1920, 1080)
      and info["fps"] == 60)
check("H.264: 8 bit, HDR yok, bit hızı okundu", info["bit_depth"] == 8 and info["hdr"] is None and info["bitrate"])

info = main.video_info(hlg)
print("   ", info)
check("HEVC 10-bit HLG: renk derinliği ve HDR", info["codec"] == "hevc" and info["bit_depth"] == 10
      and info["hdr"] == "HLG")
check("29,97 fps yuvarlanır", info["fps"] == 30)

stats = {}
main._encoder = "cpu"
main.process(h264, work / "out.mp4", datetime(2026, 1, 1), on_progress=lambda f: None, stats=stats)
print("   ", stats)
check("okuyucu bilgisi kaydedildi", stats.get("decoder", "").startswith("h264"))

print(f"\n{sum(results)}/{len(results)} geçti")
sys.exit(0 if all(results) else 1)
