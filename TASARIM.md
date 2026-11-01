# Zaman Makinesi — Tasarım

Zaman damgası olmayan videolara, kullanıcının girdiği başlangıç tarihinden itibaren
akan bir saat basan masaüstü uygulaması. Mevcut `main.py` / `onizleme.py` (CLI)
aynen çalışmaya devam eder; GUI aynı çekirdeği kullanan ince bir katmandır.

## Hedef

- Dümdüz bir Windows 10/11 (x64) bilgisayarda, sadece internet bağlantısıyla:
  linke tıkla → indir → kur → çalıştır. Python, ffmpeg vb. hiçbir şey kurulmaz.
- **50–60 yaşında, bilgisayarla arası iyi olmayan biri rahatça kullanabilmeli.**
  Buton hiç "bozuk gibi" durmaz; bir şey eksikse ne yapılacağını düz Türkçeyle söyler.
- Ayda yüzlerce video işleyen biri için de düzenli kalmalı (klasörleme, bitenleri temizleme).
- Mac'te geliştirme ve CLI kullanımı bozulmaz. Sade kod, az bağımlılık.

## Temel kavram

**İş** = bir video + bir tarih. Bir videoya birden çok tarih girilebilir; her tarih
ayrı bir çıktı üretir. İşler sırayla, tek tek işlenir. Çıktıda ses yoktur.

### Dosyalama
```
İndirilenler\Zaman Makinesi\
├── 2026-09 Eylül\
│   └── toplanti_kaydi_28_09_2026_10_40_14.mp4
└── 2026-10 Ekim\
    ├── deniz_kenari_12_10_2026_14_30_00.mp4
    └── deniz_kenari_13_10_2026_09_00_00.mp4
```
- Klasör, **videoya basılan tarihin ayı**dır (işlendiği gün değil). Ayarlardan kapatılırsa
  her şey tek klasöre gider.
- Ad: `<video adı>_<GG_AA_YYYY_SS_DD_SS>.mp4`.
- Aynı ad zaten varsa işlem başlamadan bir kez sorulur: **[Yeniden oluştur] [Atla]**
  (varsayılan Atla). Atlananlarda "✓ Zaten vardı, atlandı" yazar.

## Ekran

```
┌──────────────────────────────────────────────────────────────────────────┐
│ (saat) 3 video · 5 çıktı  2 / 5 tamamlandı                    [⚙ Ayarlar] │
│ [+ Video ekle] ☐ Yeni videolara son girilen tarihi yaz  [Bitenleri temizle] [Hepsini temizle] │
├──────────────────────────────────────────────────────────────────────────┤
│ [kare] toplanti.mp4   [12.10.2026 14:30:00]  (okey veren adam) Tamamlandı · 42 sn sürdü  Göster │
│        02:14 · 1080p  [13.10.2026 09:00:00]  (koşan adam) ███░░ %42 · 12 sn     │
│        Kaldır         + Tarih ekle   ✕ İptal                                │
│ [kare] sahne.mov      [31.02.2026 25:00:00]  Geçersiz tarih                 │
├──────────────────────────────────────────────────────────────────────────┤
│ [📁 Çıktı klasörünü aç]                              [▶ Videoları işle (3)] │
└──────────────────────────────────────────────────────────────────────────┘
```

## Kurallar

### Video ekleme
- Sürükle-bırak (pencerenin her yeri, klasör de olur) veya **Video ekle** (çoklu seçim).
- Kabul edilen uzantılar: `.mp4 .mov .avi .mkv .m4v .webm`. Diğerleri reddedilir,
  altta kısa bir bildirim çıkar.
- Aynı video tekrar eklenirse yeni satır açılmaz, mevcut satır vurgulanır.
- Video açılamıyorsa satır eklenir ama kırmızı "Video açılamadı" yazar, tarih alanı olmaz.
- Eklenen her videoya bir tarih alanı açılır. Boş gelir; **"Yeni videolara son girilen
  tarihi yaz"** işaretliyse en son yazılan tarihle dolu gelir. Bu kutu her açılışta kapalı başlar.
- İmleç yeni videonun ilk boş tarih alanına gider.

### Tarih alanı
- Biçim `GG.AA.YYYY SS:DD:SS`, saniye dahil.
- Boş alana tıklanınca imleç en baştan başlar.
- **Tab** ekrandaki sırayla bir sonraki tarih alanına, **Enter** bir sonraki *boş* tarih
  alanına geçer. Butonlar Tab ile gezilmez.
- Sorunlu alan kırmızı çerçeve + sebep: "Geçersiz tarih", "Tarih eksik" (alandan
  çıkınca), "Bu tarih zaten ekli".
- **+ Tarih ekle** yeni boş alan açar. Yanındaki kırmızı **✕ İptal** en son eklenen tarihi
  iptal eder; sadece en alttaki tarih bitmemişse ve videoda birden çok tarih varsa görünür,
  işleme sırasında gizlenir. Videonun tamamı **Kaldır** ile silinir.
- Arayüzde önizleme yoktur; gerekirse `uv run onizleme.py` kullanılır.

### İş durumları (sağ sütun)
| Durum | Görünüm |
|---|---|
| Hazır | boş |
| Sırada | gri "Sırada" |
| İşleniyor | koşan Zaman Adam + mavi ilerleme çubuğu + "%X · 12 sn" (süre canlı sayılır) |
| Tamamlandı | tik yok; Zaman Adam bir kez zıplayıp başparmağını kaldırır ve öyle kalır + yeşil "Tamamlandı · 42 sn sürdü" + **Göster** (en sağda) |
| Zaten vardı | gri "Zaten vardı, atlandı" + **Göster** |
| Hata | kırmızı ⚠ + düz Türkçe mesaj ("Diskte yer kalmadı", "Video bulunamadı…", "Video okunamadı…"); ayrıntı hata kaydına yazılır, bir sonraki çalıştırmada tekrar denenir |
| (uyarı) | sarı "⚠ Gelecekte bir tarih, doğru mu?" — işi engellemez |

### "Videoları işle" butonu
- İşleme sırası dışında **her zaman tıklanabilir**; etiketi bekleyen işi sayar: "Videoları işle (3)".
- Liste boşsa: "Henüz video eklemediniz…" açıklaması.
- Eksik/hatalı tarih ya da tarihi girilmemiş video varsa, hepsi kırmızıyla işaretlenir ve
  bir pencere listeler:
  - Geçerli iş varsa: "Bunlar işlenmeyecek. Geçerli N tarih şimdi işlensin mi?"
    **[N tanesini işle] [Önce düzelteyim]**
  - Geçerli iş yoksa: "Kırmızı alanları düzeltip tekrar deneyin." **[Düzelteyim]**
  - "Düzelteyim" ilk sorunlu alana götürür.
- Her şey zaten işlendiyse: "Listedeki tüm videolar zaten işlendi" açıklaması.
- Sonra aynı çıktı sorusu (yukarıda) ve disk kontrolü: çıktılar için gereken yer
  (kaynak videoların toplam boyutu) diskte yoksa **[Yine de başla] [Vazgeç]** sorulur.
- Soru pencerelerinde Enter'a basınca seçilen buton mavidir ve hep güvenli seçenektir.

### İşleme sırasında
- Tarih alanları, ekleme/silme, temizleme, klasör değiştirme kilitlenir.
- Başlıktaki saatin akrebi ve yelkovanı **geriye** döner.
- Bilgisayar uykuya geçmez (Windows: SetThreadExecutionState, macOS: caffeinate).
- Ana buton **Durdur** olur. Durdurulunca o anki iş kesilir (yarım dosya silinir),
  kalan işler Hazır'a döner.

- **Zaman Adam balonu**: sağ altta aşağıdan zıplayarak gelir, "dürtme" gibi hafifçe sallanır,
  ~4 sn sonra kayıp gider (tıklanınca hemen kapanır). İşlem boyunca ekranda kalmaz.
  Başlarken iş sayısına göre konuşur (1: "Tek video mu? Çocuk oyuncağı!", 30+: "Derin bir nefes…");
  6+ videoda yarıda bir kez "Yarısı bitti" der.

### İş bitince
- Balon tekrar gelir, Zaman Adam başparmağını kaldırır: "Hepsi hazır! 🎉" (hata/durdurma varsa
  ne olduğunu söyler).
- Üstte özet: "5 / 6 tamamlandı · 1 hata". Pencere arkadaysa görev çubuğunda yanıp söner.
- Tamamlanan satırlar kilitlenir; tekrar işlenmez.
- **Bitenleri temizle** (sadece biten varken görünür): tamamlananları listeden kaldırır,
  hatalı ve bekleyenler kalır.
- **Hepsini temizle** onay sorup her şeyi sıfırlar; çıktı dosyalarına dokunmaz.

### Kapatırken
- İşlem sürüyorsa: "Durdurup çıkılsın mı?" **[Durdur ve çık] [Devam et]**
- İşlenmemiş video varsa: "Listede henüz işlenmemiş N video var…" **[Çık] [Vazgeç]**

### Ayarlar (⚙)
- Tek pencere, tek kart: üstte el sallayan Zaman Adam ve sürüm; altında satır satır **Tema · Çıktı klasörü ·
  Aylara göre klasörle · Hızlandırma · Güncelleme** (solda ne olduğu, sağda ayarın kendisi); altta "Hata kaydını aç".
- Tema: **Sistem / Açık / Koyu** (bitişik üç seçenek) (Sistem seçiliyse Windows teması değişince uygulama da değişir).
- Çıktı klasörü (**Değiştir**, **Klasörü aç**) + "Aylara göre klasörle"; açıkken de kapalıyken de ne olacağı
  bir cümleyle ve örnek yolla anlatılır.
- Sürüm + **Güncellemeleri denetle** + **Hata kaydını aç** (kullanıcının uygulama veri
  klasöründe `zaman-makinesi.log`, en fazla ~3 MB; sorun olursa geliştiriciye gönderilir).
- Tüm seçimler hatırlanır (QSettings).

### Animasyonlar
- Açılış: simge yaylanarak büyür, ok çizilir, ibreler bir tur geri döner, yazı belirir.
- Sol üstte gerçek saati gösteren sade, küçük bir analog saat.
- Açılış, boş liste ve sürükleme katmanında uygulama logosu. Boş listedeki logonun ibreleri
  gerçek saati gösterir; sarı saniye ibresi yaylanarak ilerler.
- Video sürüklenince bütün pencereye mavi bir katman gelir; ortada ibreleri geriye dönen logo.
- Yeni satırlar ve "✓ Tamamlandı" yumuşakça belirir; silinen tarih ve videolar solup kapanarak gider.
- **Zaman Adam**: uygulama simgesinin kollu bacaklı, yüzlü hali. İşlenen satırda koşar, ayarlarda el sallar,
  arada bir göz kırpar. **Göster** butonu satırın en sağında durur.

## Hız (video kodlama)

- Saat, ffmpeg'in kendi `drawtext` filtresiyle basılır; okuma + yazı + sıkıştırma tek ffmpeg sürecinde
  yapılır (Python'da kare kare işlem ve kare başına 6 MB'lık aktarım yok).
- Kodlayıcı otomatik seçilir (`main.ENCODER = "auto"`): açılışta arka planda 1 sn'lik denemeyle sırayla
  **NVIDIA (NVENC) → Intel (Quick Sync) → AMD (AMF)** yoklanır, ilk çalışan kullanılır; hiçbiri yoksa
  **işlemci (x264 veryfast)**. Seçim Ayarlar'daki "Hız" kartında ve hata kaydında görünür.
- Yedek: grafik birimi bir videoda hata verirse o video kendiliğinden işlemciyle baştan yapılır.
  İşlemci kodlayıcısı uygulamanın içinde geldiği için her bilgisayarda çalışır.
- Ölçüm (Mac, 60 sn 1080p30, 2 çekirdekle sınırlı): x264 medium 21,8 sn → veryfast 6,2 sn (3,5x).
  Ofis bilgisayarında 10 dk'lık 1080p video için tahmin: işlemci ~3 dk, Intel/AMD grafik ~1–2 dk,
  NVIDIA ~1 dk. Kodlayıcısı olmayan kartlar: GT 710/730/1030, RX 6400/6500 XT; "F" Intel işlemcilerde
  grafik birimi yoktur.
- `ZM_ENCODER=cpu` (ya da `nvenc`/`qsv`/`amf`) ortam değişkeni seçimi zorlar (deneme için).

## Güncelleme

- Açılışta `version.json` okunur (en son sürümün release'inden, 3 sn zaman aşımı):
  `{"latest": "1.3.0", "min_supported": "1.2.0", "url": "...", "sha256": "...", "notes": "..."}`
- Sürüm `< min_supported` → **zorunlu**: ana pencere açılmaz; notlar + [Güncelle] [Çık].
- Sürüm `< latest` → açılıştan ~1 sn sonra Zaman Adam sağ altta bir kez haber verir
  ("Yeni sürüm hazır! Güncellemek için bana tıklayın"; tıklayınca güncelleme penceresi açılır).
  **⚙ Ayarlar** butonunda kırmızı nokta kalır; Ayarlar'ın Yardım kartında "Şimdi güncelle" görünür.
- Ulaşılamazsa → sessizce devam (internet yokken de çalışsın).
- Ayarlar'daki **Güncellemeleri denetle** aynı kontrolü elle yapar; altında "Son kontrol: bugün 14:32" yazar.
- Ayarlar açıldığında son kontrolün üzerinden **12 saat** geçtiyse kendiliğinden denetler
  (açılışta zaten her seferinde denetlendiği için bu, günlerce açık kalan pencereler içindir).
- Güncelle → kurulum dosyası indirilir (buton "İndiriliyor… %42" olur ve pasifleşir, "Lütfen
  bekleyin" yazar), sha256 doğrulanır, kurulum sessiz modda başlatılır, uygulama kapanır,
  kurulum bitince `--updated` ile yeniden açılır ve **"Güncelleme tamamlandı!"** penceresi
  (Zaman Adam + sürüm notu) gösterilir.

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
| `main.py` | Çekirdek + CLI: tek ffmpeg süreci (drawtext), kodlayıcı seçimi ve yedek, ilerleme/iptal |
| `tests/gui_test.py` | Arayüzün uçtan uca testi (ekransız, deneme videolarını kendisi üretir) |
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
