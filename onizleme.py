"""
Ayarları denemek için hızlı önizleme.
girdi klasöründeki ilk videonun tek bir karesine overlay'i basar,
sonucu onizleme.png olarak kaydedip açar.

Ayarlar main.py'deki AYARLAR bölümünden okunur. Orayı değiştirip bunu tekrar çalıştırın.
"""

import os
import subprocess
import sys

import cv2

import main

# Videonun kaçıncı saniyesindeki kare kullanılsın
PREVIEW_SECOND = 0


def run():
    input_dir = main.PROJECT_DIR / main.INPUT_DIR
    videos = main.find_videos(input_dir) if input_dir.exists() else []
    if not videos:
        raise SystemExit(f"{main.INPUT_DIR} klasöründe video yok.")
    src = videos[0]

    cap = main.open_video(src)
    cap.set(cv2.CAP_PROP_POS_MSEC, PREVIEW_SECOND * 1000)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise SystemExit(f"Kare okunamadı: {src.name}")

    start = main.start_time_for(src.relative_to(input_dir))
    main.TextRenderer().draw(frame, main.format_ts(start), main.MARGIN_LEFT, main.MARGIN_TOP)

    out = main.PROJECT_DIR / "onizleme.png"
    cv2.imwrite(str(out), frame)
    print(f"Kaynak: {src.relative_to(input_dir)}  ->  {out.name}")

    if sys.platform == "darwin":
        subprocess.run(["open", str(out)])
    elif sys.platform == "win32":
        os.startfile(out)


if __name__ == "__main__":
    run()
