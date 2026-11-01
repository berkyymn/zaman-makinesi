# Zaman Makinesi — çalışma kuralları

Bu depo, videolara akan saat basan bir Windows masaüstü uygulamasıdır (PySide6 + ffmpeg).

- **Tek doğru kaynak [TASARIM.md](TASARIM.md)'dir.** Bir işe başlamadan önce oku. Davranışı değiştiren her
  değişikliği **aynı commit içinde** TASARIM.md'ye işle (ekran, kurallar, durumlar, metinler, dosyalar).
- **Sürüm yayınlarken** TASARIM.md bölüm 9'daki kontrol listesini sırayla uygula. Özellikle:
  - `main.TUNE_VERSION`: aday ayarlar (`PROFILES`), ölçüm yöntemi (`tune`) ya da işleme hattı (`encode`)
    değiştiyse artır; değişmediyse dokunma.
  - `release.json` → `min_supported` sadece zorunlu güncellemede değişir.
  - Etiketi (`git tag vX.Y.Z`) kullanıcı onayı olmadan gönderme.
- **Testler** (her değişiklikten sonra):
  - `QT_QPA_PLATFORM=offscreen uv run python tests/gui_test.py`
  - `uv run gui.py --self-test`
  - `uv run python tests/tune_test.py`
  - Yeni davranış eklediysen `tests/gui_test.py`'ye kontrolünü de ekle.
- **Kullanıcı 50–60 yaşında olabilir:** arayüz metinleri düz Türkçe; soru pencerelerinde varsayılan (mavi)
  buton güvenli seçenek; teknik hata metni gösterme (hata kaydına yaz).
- **Windows önceliklidir:** yol/font/alt süreç kodu Windows'ta da çalışmalı (`CREATE_NO_WINDOW`, Türkçe
  karakterli yollar). Mac sadece geliştirme ortamı.
- Commit mesajları Türkçe.
