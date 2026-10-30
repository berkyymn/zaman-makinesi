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
│ (logo) 3 video · 5 çıktı  2 / 5 tamamlandı                    [⚙ Ayarlar] │
│ [+ Video ekle] ☐ Yeni videolara son girilen tarihi yaz  [Bitenleri temizle] [Listeyi temizle] │
├──────────────────────────────────────────────────────────────────────────┤
│ [kare] toplanti.mp4   [12.10.2026 14:30:00]  ✓ Tamamlandı · 42 sn sürdü  Göster │
│        02:14 · 1080p  [13.10.2026 09:00:00]  ███████░░ %42                  │
│        Kaldır         + Tarih ekle   − Son tarihi sil                       │
│ [kare] sahne.mov      [31.02.2026 25:00:00]  Geçersiz tarih                 │
├──────────────────────────────────────────────────────────────────────────┤
│ Çıktı klasörü                                                            │
│ C:\Users\ali\Downloads\Zaman Makinesi  Değiştir  Klasörü aç  [▶ Videoları işle (3)] │
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
- **+ Tarih ekle** yeni boş alan açar. Yanındaki **− Son tarihi sil** en alttaki
  (bitmemiş) tarihi siler; video tek tarihliyse görünmez. Videonun tamamı **Kaldır** ile silinir.
- Arayüzde önizleme yoktur; gerekirse `uv run onizleme.py` kullanılır.

### İş durumları (sağ sütun)
| Durum | Görünüm |
|---|---|
| Hazır | boş |
| Sırada | gri "Sırada" |
| İşleniyor | mavi ilerleme çubuğu + %X |
| Tamamlandı | yeşil "✓ Tamamlandı · 42 sn sürdü" (yumuşakça belirir) + **Göster** (dosyayı klasöründe seçili açar) |
| Zaten vardı | gri "✓ Zaten vardı, atlandı" + **Göster** |
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

### İş bitince
- Üstte özet: "5 / 6 tamamlandı · 1 hata". Pencere arkadaysa görev çubuğunda yanıp söner.
- Tamamlanan satırlar kilitlenir; tekrar işlenmez.
- **Bitenleri temizle** (sadece biten varken görünür): tamamlananları listeden kaldırır,
  hatalı ve bekleyenler kalır.
- **Listeyi temizle** onay sorup her şeyi sıfırlar; çıktı dosyalarına dokunmaz.

### Kapatırken
- İşlem sürüyorsa: "Durdurup çıkılsın mı?" **[Durdur ve çık] [Devam et]**
- İşlenmemiş video varsa: "Listede henüz işlenmemiş N video var…" **[Çık] [Vazgeç]**

### Ayarlar (⚙)
- Tema: **Sistem / Açık / Koyu** (Sistem seçiliyse Windows teması değişince uygulama da değişir).
- Çıktı klasörü + "Çıktıları aylara göre klasörle"; açıkken de kapalıyken de ne olacağı
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

## Güncelleme

- Açılışta `version.json` okunur (en son sürümün release'inden, 3 sn zaman aşımı):
  `{"latest": "1.3.0", "min_supported": "1.2.0", "url": "...", "sha256": "...", "notes": "..."}`
- Sürüm `< min_supported` → **zorunlu**: ana pencere açılmaz; notlar + [Güncelle] [Çık].
- Sürüm `< latest` → üstte kapatılabilir şerit: "Yeni sürüm var · Güncelle".
- Ulaşılamazsa → sessizce devam (internet yokken de çalışsın).
- Ayarlar'daki **Güncellemeleri denetle** aynı kontrolü elle yapar.
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
