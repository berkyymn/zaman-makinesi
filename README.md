# Zaman Makinesi

Zaman damgası olmayan videolara, sizin girdiğiniz tarihten başlayıp akan bir saat ekler.

## Kurulum (Windows 10 / 11)

1. **[Zaman Makinesi'ni indirin](https://github.com/berkyymn/zaman-makinesi/releases/latest/download/ZamanMakinesi-Setup.exe)**
2. İnen `ZamanMakinesi-Setup.exe` dosyasına çift tıklayın.
   Mavi bir **"Windows bilgisayarınızı korudu"** penceresi çıkarsa **Ek bilgi**'ye, sonra **Yine de çalıştır**'a tıklayın.
   (Uygulama ücretsiz olduğu için imzalı değil; bu uyarı bundan çıkar.)
3. **İleri → Kur → Son**. Masaüstüne "Zaman Makinesi" kısayolu gelir.

Yönetici izni gerekmez. Yeni sürüm çıktığında uygulama açılışta haber verir; tek tıkla güncellenir.

## Kullanım

1. Videoları pencereye sürükleyin ya da **Video ekle**'ye tıklayın.
2. Her videonun yanına başlangıç tarihini yazın: `GG.AA.YYYY SS:DD:SS`.
   Aynı videodan farklı tarihlerle birden çok çıktı almak için **+ Tarih ekle**.
   **Önizle** saatin videoda nasıl duracağını gösterir.
3. **Videoları işle**'ye tıklayın. Bitenlerin yanında ✓ çıkar, **Göster** dosyayı açar.

Çıktılar varsayılan olarak `İndirilenler\Zaman Makinesi` klasörüne
`<video adı>_<tarih>.mp4` adıyla kaydedilir. Alttaki **Değiştir** ile klasörü seçebilirsiniz.

---

## Geliştirme

[uv](https://docs.astral.sh/uv/) gerekir.

```bash
uv run gui.py                 # arayüz
uv run main.py [video.mp4]    # komut satırı: girdi/ klasöründekileri cikti/'ya işler
uv run onizleme.py            # komut satırı: tek kare önizleme
```

Yazı boyutu, konum, renk ve kalite ayarları `main.py`'nin başındaki **AYARLAR** bölümündedir;
hem arayüz hem komut satırı bunları kullanır. Arayüz kuralları için [TASARIM.md](TASARIM.md).

### Yeni sürüm yayınlama

1. `version.py` içindeki sürümü artırın.
2. `release.json`'da sürüm notunu yazın. Herkesin güncellemesi **zorunlu** olsun istiyorsanız
   `min_supported`'ı da yeni sürüme eşitleyin.
3. Commit'leyip etiket gönderin:
   ```bash
   git tag v1.1.0 && git push && git push --tags
   ```

GitHub Actions Windows'ta derler, paketi test eder, kurulum dosyasını ve `version.json`'u
Releases'a yükler. İndirme linki hep aynı kalır ve en son sürümü verir.

Simgeyi değiştirdiyseniz: `uv run icon.py` (`assets/icon.ico`'yu yeniden üretir).
