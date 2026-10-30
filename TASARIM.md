# Zaman Makinesi — Tasarım

Zaman damgası olmayan videolara, kullanıcının girdiği başlangıç tarihinden itibaren
akan bir saat basan masaüstü uygulaması. Mevcut `main.py` / `onizleme.py` (CLI)
aynen çalışmaya devam eder; GUI aynı çekirdeği kullanan ince bir katmandır.

## Hedef

- Dümdüz bir Windows 10/11 (x64) bilgisayarda, sadece internet bağlantısıyla:
  linke tıkla → indir → kur → çalıştır. Python, ffmpeg vb. hiçbir şey kurulmaz.
- Mac'te geliştirme ve CLI kullanımı bozulmaz.
- Sade kod, az bağımlılık, ayar ekranı yok.

## Temel kavram

**İş** = bir video + bir tarih. Bir videoya birden çok tarih girilebilir; her tarih
ayrı bir çıktı üretir. İşler sırayla, tek tek işlenir.

Çıktı adı: `<video adı>_<YYYYMMDD_HHMMSS>.mp4` (ör. `toplanti_20261012_143000.mp4`).
Çıktıda ses yoktur (bugünkü davranış).

## Ekran

```
┌──────────────────────────────────────────────────────────────────────┐
│ 3 video · 5 çıktı   2/5 tamamlandı      [+ Video ekle] [Listeyi temizle] │
├──────────────────────────────────────────────────────────────────────┤
│ [kare] toplanti.mp4   [12.10.2026 14:30:00] Önizle ×  ✓ …_143000 Göster │
│        02:14 · 1080p  [13.10.2026 09:00:00] Önizle ×  ███████░░ %42     │
│                       [+ Tarih ekle]                                 │
│ [kare] sahne.mov      [31.02.2026 25:00:00] Önizle ×  Geçersiz tarih    │
│                       [+ Tarih ekle]                                 │
├──────────────────────────────────────────────────────────────────────┤
│      Videoları pencerenin herhangi bir yerine sürükleyip bırakın      │
├──────────────────────────────────────────────────────────────────────┤
│ Çıktı klasörü: C:\Users\ali\Downloads\Zaman Makinesi                 │
│                [Değiştir] [Klasörü aç]                [Videoları işle (3)] │
└──────────────────────────────────────────────────────────────────────┘
```

## Kurallar

### Video ekleme
- Sürükle-bırak (pencerenin her yeri) veya **Video ekle** (çoklu seçim).
- Kabul edilen uzantılar: `.mp4 .mov .avi .mkv .m4v .webm`. Diğerleri reddedilir,
  altta kısa bir bildirim çıkar.
- Aynı video tekrar eklenirse yeni satır açılmaz, mevcut satır vurgulanır.
- Video açılamıyorsa satır eklenir ama kırmızı "Video açılamadı" yazar, tarih alanı olmaz.
- Satırda: ilk kareden küçük resim, dosya adı, süre · çözünürlük, sil (×).
- Eklenen her videoya **boş** bir tarih alanı açılır.

### Tarih alanı
- Biçim `GG.AA.YYYY SS:DD:SS`, saniye dahil, boş gelir.
- Geçersizse kırmızı çerçeve + sebep: "Geçersiz tarih", "Bu tarih zaten ekli".
- Boş alan geçersiz sayılmaz ama iş de sayılmaz (yok hükmünde).
- **Önizle**: tarih geçerliyse aktif. Videonun ilk karesine filigranı basıp bir
  pencerede gösterir. Pencerede açıkça yazar: *"Bu sadece bir önizlemedir. Video
  henüz işlenmedi; videonun ilk karesi gösteriliyor."*
- **+ Tarih ekle** yeni boş alan açar; her alanın sil (×) butonu vardır.

### İş durumları (sağ sütun)
| Durum | Görünüm |
|---|---|
| Hazır | boş, soluk |
| Sırada | gri "Sırada" |
| İşleniyor | mavi ilerleme çubuğu + %X |
| Tamamlandı | yeşil ✓ + kısa çıktı adı + **Göster** (Gezgin'de dosyayı seçili açar) |
| Zaten var | gri ✓ "Zaten var" + **Göster** — aynı adlı çıktı vardı, atlandı |
| Hata | kırmızı ⚠ + kısa mesaj; bir sonraki çalıştırmada tekrar denenir |

### "Videoları işle" butonu
- Aktif olması için: en az bir **Hazır** iş var **ve** hiçbir alan geçersiz değil.
- Etiket bekleyen işi sayar: "Videoları işle (3)".
- Geçersiz alan varken pasiftir ve altında yazar: "1 geçersiz tarih var".

### İşleme sırasında
- Tarih alanları, ekleme/silme, Listeyi temizle, Değiştir kilitlenir.
- Ana buton **Durdur** olur. Durdurulunca o anki iş kesilir (`.part` dosyası silinir),
  kalan işler Hazır'a döner.
- Pencere kapatılmak istenirse onay sorulur; onaylanırsa aynı şekilde durdurulur.

### İş bitince
- Üstte özet: "5 / 6 tamamlandı · 1 hata". Pencere arka plandaysa görev çubuğunda yanıp söner.
- Tamamlanan satırlar ✓ ile kalır ve kilitlenir; tekrar işlenmez.
- Buton yalnızca yeni eklenen veya hatalı işler için tekrar aktif olur.
- **Listeyi temizle** her şeyi sıfırlar; çıktı dosyalarına dokunmaz.

### Çıktı klasörü
- Varsayılan: `İndirilenler\Zaman Makinesi` (yoksa oluşturulur).
- Alt çubukta tam yol her zaman görünür; **Değiştir** ve **Klasörü aç** butonları yanında.
- Seçim hatırlanır (QSettings).

## Güncelleme

- Açılışta `version.json` okunur (en son sürümün release'inden, 3 sn zaman aşımı):
  `{"latest": "1.3.0", "min_supported": "1.2.0", "url": "...", "sha256": "...", "notes": "..."}`
- Sürüm `< min_supported` → **zorunlu**: ana pencere açılmaz; notlar + [Güncelle] [Çık].
- Sürüm `< latest` → üstte kapatılabilir şerit: "Yeni sürüm var · Güncelle".
- Ulaşılamazsa → sessizce devam (internet yokken de çalışsın).
- Güncelle → kurulum dosyası indirilir (ilerleme gösterilir), sha256 doğrulanır,
  kurulum sessiz modda başlatılır, uygulama kapanır, kurulum bitince yeniden açılır.

## Dağıtım

- Depo: `github.com/berkyymn/zaman-makinesi` (public, MIT lisans).
- Kullanıcıya verilen tek link:
  `https://github.com/berkyymn/zaman-makinesi/releases/latest/download/ZamanMakinesi-Setup.exe`
- Kurulum adımları (README'de):
  1. Linke tıklayın, dosya iner.
  2. Çift tıklayın. "Windows bilgisayarınızı korudu" çıkarsa **Ek bilgi → Yine de çalıştır**.
  3. **İleri → Kur → Bitir.** Masaüstüne kısayol gelir.
- Kurulum kullanıcı klasörüne yapılır (`%LOCALAPPDATA%\Programs`), yönetici izni gerekmez.
- Paketleme: PyInstaller (klasör modu, hızlı açılış) + Inno Setup kurulum dosyası.
  Paket Python, Qt, OpenCV ve ffmpeg'i (imageio-ffmpeg) içerir.
- Font: Windows'ta `C:\Windows\Fonts\courbd.ttf`, Mac'te mevcut yol (Courier New
  Microsoft'a ait olduğu için depoya konmaz).

### Yeni sürüm yayınlama
1. `version.py` içindeki sürümü artır; `release.json`'a notu yaz (zorunluysa
   `min_supported`'ı da yeni sürüme eşitle).
2. `git tag v1.3.0 && git push --tags`
3. GitHub Actions (Windows) derler, kurulum dosyasını ve `version.json`'u release'e yükler.

## Dosyalar

| Dosya | Görev |
|---|---|
| `main.py` | Çekirdek + CLI (aynen kalır; ilerleme/iptal parametreleri eklenir, font yolu OS'a göre) |
| `onizleme.py` | CLI önizleme (aynen kalır; Windows'ta da dosyayı açar) |
| `gui.py` | PySide6 arayüz, uygulamanın giriş noktası |
| `updater.py` | Sürüm kontrolü, indirme, kurulumu başlatma |
| `version.py` | Tek sürüm kaynağı (`__version__`) |
| `icon.py` | Simge çizimi (açılış animasyonu da kullanır) + `assets/icon.ico` üretimi |
| `release.json` | `min_supported` + sürüm notu |
| `packaging/` | Inno Setup betiği + `version.json` üreten betik |
| `.github/workflows/release.yml` | Tag'de derle ve yayınla |
| `README.md`, `LICENSE` | Kurulum adımları, MIT |

## Bilinen riskler (ilk sürümde test edilecek)
- Türkçe karakterli dosya yolları + OpenCV (Windows). CI'daki self-test bunu dener.
- ffmpeg alt sürecinin Windows'ta konsol penceresi açmaması (`CREATE_NO_WINDOW`).
- Antivirüs/SmartScreen'in imzasız kurulumu engellemesi.
