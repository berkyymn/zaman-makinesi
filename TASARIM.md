# Zaman Makinesi — Tasarım ve İş Kuralları

Zaman damgası olmayan videolara, kullanıcının girdiği başlangıç tarihinden itibaren akan bir saat basan
Windows masaüstü uygulaması.

> **Bu belge uygulamanın tek doğru kaynağıdır.** Davranışı değiştiren her değişiklik, aynı commit içinde
> buraya da işlenir. Yeni sürüm yayınlamadan önce en alttaki **Sürüm yayınlama kontrol listesi** eksiksiz
> uygulanır.

---

## 1. Hedef ve ilkeler

- **Platform:** Dümdüz bir Windows 10/11 (x64). Kullanıcı sadece linke tıklar, indirir, kurar, çalıştırır;
  Python, ffmpeg vb. hiçbir şey ayrıca kurulmaz. Geliştirme Mac'te yapılır; Mac'te de çalışır.
- **Kullanıcı:** 50–60 yaşında, bilgisayarla arası iyi olmayan biri rahatça kullanabilmeli. Bu yüzden:
  - Hiçbir buton "bozuk gibi" durmaz. Bir şey eksikse ne yapılacağını düz Türkçeyle söyler.
  - Soru pencerelerinde Enter'a basınca seçilen (mavi) buton **her zaman güvenli seçenektir**
    (Atla, Vazgeç, Önce düzelteyim…). Geri alınamaz işler hep onay ister.
  - Teknik hata metni gösterilmez; düz Türkçe sebep gösterilir, ayrıntı hata kaydına yazılır.
- **Yoğun kullanıcı:** Günde ~100 video işleyen biri için de hızlı ve düzenli kalmalı (en hızlı donanım,
  aylık klasörleme, bitenleri temizleme, tek tek iptal).
- **Sade proje:** Az bağımlılık, ayar ekranı küçük, her şey otomatik.

## 2. Temel kavramlar

- **İş** = bir video + bir tarih. Bir videoya birden çok tarih girilebilir; her tarih ayrı bir çıktı üretir.
- İşler **sırayla, tek tek** işlenir. Çıktıda **ses yoktur**.
- Videoya basılan yazı: `GG-AA-YYYY Gün SS:DD:SS` (ör. `12-10-2026 Mon 14:30:05`). Gün adları İngilizce
  kısaltmadır (ffmpeg üretir). Saat, videonun her saniyesinde bir artar.
- Görünüm (font, boyut, konum, renk, kalite) `main.py`'nin başındaki **AYARLAR** bölümündedir.
  Varsayılan: Courier New Bold 30 px, beyaz yazı, siyah kutu, sol 24 / üst 60 px, CRF 23.
- **Çıktı girişle yaklaşık aynı boyutta kalır (boyut tavanı).** Her videonun bit hızı ve formatı okunur;
  çıktının bit hızı tavanı `min(giriş × format katsayısı, genişlik × yükseklik × fps × MAX_BITS_PER_PIXEL (0,10))`'dur
  (en az 300 kb/s). Format katsayısı (`CODEC_RATE_FACTOR`): H.264 ve diğerleri **1,0**; HEVC/VP9 **1,4**; AV1
  **1,5** (çıktı H.264 olduğu için daha verimli formatlardan gelen videoda görüntü bozulmasın). Küçük taşmalar
  (~%5) kabul edilir; amaç 1,86x gibi büyümeleri önlemek, kaliteyi sıkıştırmak değil.
  NVENC ve işlemci: kalite hedefi (CRF/CQ 23) + tavan; Quick Sync ve AMD: tavanı hedefleyen değişken bit hızı.
  Ölçüm (Mac, x264, 1080p60 5,2 Mbit H.264 giriş): tavan = giriş → 1,03x, SSIM 0,9864; tavan = girişin %90'ı
  → 0,92x, SSIM 0,9860 (fark gözle görülmez; kullanıcı küçük taşmayı kabul etti, girişin kendisi seçildi).
  Sebep: 1.0.12'de kalite hedefiyle 1080p60 5,2 Mbit'lik 400 MB giriş 756 MB (1,86x) çıkmıştı.

### Çıktılar ve dosyalama
```
İndirilenler\Zaman Makinesi\
├── 2026-09 Eylül\
│   └── toplanti_kaydi_28_09_2026_10_40_14.mp4
└── 2026-10 Ekim\
    ├── deniz_kenari_12_10_2026_14_30_00.mp4
    └── deniz_kenari_13_10_2026_09_00_00.mp4
```
- Varsayılan çıktı klasörü: `İndirilenler\Zaman Makinesi` (yoksa oluşturulur). Ayarlar'dan değiştirilir.
- **Aylara göre klasörle** (varsayılan açık): klasör, **videoya basılan tarihin ayıdır** (işlendiği gün değil).
  Kapalıysa her şey doğrudan çıktı klasörüne gider.
- Ad: `<video adı>_<GG_AA_YYYY_SS_DD_SS>.mp4`.
- Önce `.part.mp4` adıyla yazılır, bitince asıl adına çevrilir. Yarıda kalan iş "tamamlandı" sayılmaz;
  yarım dosya her durumda silinir.
- Aynı adlı çıktı zaten varsa işlem başlamadan bir kez sorulur: **[Yeniden oluştur] [Atla]** (varsayılan
  Atla). Aynı çalıştırmada iki iş aynı adı üretiyorsa ikincisi hata olur.

## 3. Ana ekran

```
┌──────────────────────────────────────────────────────────────────────────┐
│ (saat) 3 video · 5 çıktı  2 / 5 tamamlandı · 1 hata             [⚙ Ayarlar•] │
│ [+ Video ekle] ☐ Yeni videolara son girilen tarihi yaz  [Bitenleri temizle] [Hepsini temizle] │
├──────────────────────────────────────────────────────────────────────────┤
│ [kare] toplanti.mp4  [12.10.2026 14:30:00] (okey veren adam) Tamamlandı · 42 sn sürdü   Göster │
│        02:14 · 1080p [13.10.2026 09:00:00] (koşan adam) ███░░ %42 · 12 sn          ✕ İptal │
│        Kaldır        + Tarih ekle   ✕ İptal                                       │
│ [kare] sahne.mov     [31.02.2026 25:00:00]  Geçersiz tarih                        │
├──────────────────────────────────────────────────────────────────────────┤
│ [📁 Çıktı klasörünü aç]                                 [▶ Videoları işle (3)] │
└──────────────────────────────────────────────────────────────────────────┘
```
- Sol üstte gerçek saati gösteren küçük analog saat; işlem sürerken ibreleri **geriye** döner.
- Liste boşken başlık "Başlamak için video ekleyin"dir (uygulamanın adı zaten pencere başlığında) ve ortada
  ibreleri gerçek saati gösteren büyük logo durur.

### Video ekleme
- Sürükle-bırak (pencerenin her yeri; klasör bırakılırsa içindeki videolar) veya **Video ekle** (çoklu seçim,
  son klasör hatırlanır).
- Kabul edilen uzantılar: `.mp4 .mov .avi .mkv .m4v .webm`. Diğerleri reddedilir; altta kısa bildirim çıkar.
- Aynı video tekrar eklenirse yeni satır açılmaz, mevcut satır vurgulanır.
- Video açılamıyorsa satır eklenir ama kırmızı "Video açılamadı" yazar, tarih alanı olmaz.
- Her yeni videoya bir tarih alanı açılır; imleç ilk boş tarih alanına gider.
- **Yeni videolara son girilen tarihi yaz:** işaretliyse yeni videoların tarihi en son yazılan geçerli tarihle
  dolu gelir. Kutu **her açılışta kapalı** başlar (hatırlanmaz).
- Video sürüklenirken bütün pencereye mavi bir katman gelir ("Videoları bırakın").
- İşlem ya da ölçüm sürerken video eklenemez.

### Tarih alanı
- Biçim `GG.AA.YYYY SS:DD:SS`, saniye dahil, boş gelir. Boş alana tıklanınca imleç en baştan başlar.
- **Tab** ekrandaki sırayla bir sonraki tarih alanına, **Enter** bir sonraki *boş* tarih alanına geçer.
  Butonlar Tab ile gezilmez.
- Sorunlu alan kırmızı çerçeve + sebep: "Geçersiz tarih", "Tarih eksik" (alandan çıkınca ya da çalıştırınca),
  "Bu tarih zaten ekli" (aynı videoda). Boş alan iş sayılmaz, hata da değildir.
- Gelecekteki bir tarih sarı "⚠ Gelecekte bir tarih, doğru mu?" uyarısı verir; işi engellemez.
- **+ Tarih ekle** yeni boş alan açar. Yanındaki kırmızı **✕ İptal** en alttaki tarihi kaldırır; sadece en
  alttaki tarih bitmemişse ve videoda birden çok tarih varsa görünür, işlem sırasında gizlenir.
- Videonun tamamı **Kaldır** ile silinir. Arayüzde önizleme yoktur (`uv run onizleme.py` komut satırında var).

### İş durumları (satırın sağı)
| Durum | Görünüm |
|---|---|
| Hazır | boş |
| Sırada | gri "Sırada" + kırmızı **✕ İptal** |
| İşleniyor | koşan Zaman Adam + ilerleme çubuğu + "%42 · 12 sn" (süre canlı sayılır) + **✕ İptal** |
| İptal ediliyor | "İptal ediliyor…" (ffmpeg kapanana kadar) |
| Tamamlandı | tik yok; Zaman Adam bir kez zıplayıp başparmağını kaldırır ve öyle kalır + yeşil "Tamamlandı · 42 sn sürdü" + en sağda **Göster** (dosyayı klasöründe seçili açar) |
| Zaten vardı | gri "Zaten vardı, atlandı" + **Göster** |
| Sıradan çıkarıldı | gri "Sıradan çıkarıldı"; bir sonraki çalıştırmada yeniden işlenir |
| Hata | kırmızı "⚠ Diskte yer kalmadı / Video bulunamadı (taşınmış veya silinmiş olabilir) / Video okunamadı (dosya bozuk olabilir) / Çıktı klasörüne yazma izni yok / Video kaydedilemedi"; bir sonraki çalıştırmada yeniden denenir |

Tamamlanan ve "zaten vardı" satırlarının tarihi kilitlenir; tekrar işlenmez. Hatalı / iptal edilen satırın
tarihi değiştirilirse durumu Hazır'a döner.

### "Videoları işle" butonu
- İşlem sırası dışında **her zaman tıklanabilir**; etiketi bekleyen işi sayar: "Videoları işle (3)".
- Liste boşsa: "Henüz video eklemediniz…" açıklaması.
- Eksik/hatalı tarih, tarihi girilmemiş ya da açılamayan video varsa hepsi kırmızı işaretlenir ve bir pencere
  listeler (en fazla 8 satır + "…ve N tane daha"):
  - Geçerli iş varsa: "Bunlar işlenmeyecek. Geçerli N tarih şimdi işlensin mi?" **[N tanesini işle] [Önce düzelteyim]**
  - Geçerli iş yoksa: "Kırmızı alanları düzeltip tekrar deneyin." **[Düzelteyim]**
  - "Düzelteyim" ilk sorunlu alana götürür.
- Her şey zaten işlendiyse: "Listedeki tüm videolar zaten işlendi" açıklaması.
- Ardından sırayla: **aynı çıktı sorusu** (bkz. 2) ve **disk kontrolü** (gereken yer ≈ kaynak videoların
  toplam boyutu; diskte yoksa "Çıktılar için yaklaşık 3,2 GB gerekebilir, diskte 1,1 GB boş"
  **[Yine de başla] [Vazgeç]**).

### İşlem sırasında
- Tarih alanları, ekleme/silme, temizleme ve klasör değiştirme kilitlenir.
- Ana buton **■ Durdur** olur. Durdurulunca o anki iş kesilir, kalanlar Hazır'a döner ("Durduruluyor…").
- Satırdaki **✕ İptal**: sıradakini hemen sıradan çıkarır; işleneni durdurur ve sıradakiyle devam eder.
- Bilgisayar uykuya geçmez (Windows: `SetThreadExecutionState`, macOS: `caffeinate`). Ekranın kapanmasına /
  ekran koruyucuya bilerek izin verilir; işlem arka planda sürer.
- **Zaman Adam balonu** (sağ alt, aşağıdan zıplayarak gelir, hafifçe sallanır, ~4 sn sonra gider; tıklanınca
  hemen kapanır; işlem boyunca ekranda kalmaz):
  - Başlarken iş sayısına göre: 1 → "Tek video mu? Çocuk oyuncağı! 😎", 2–3 → "Hemen hallediyorum…",
    4–10 → "Kolları sıvadım, N video sırada!", 11–30 → "Vay, N video! … bir çay koyun ☕",
    30+ → "N video mu?! Derin bir nefes… Başlıyorum! 💪"
  - 6+ videoda yarıda bir kez "Yarısı bitti, devam ediyorum! 🏃".

### İş bitince
- Balon: "Hepsi hazır! 🎉" (başparmak). Durdurulduysa "Kalanlar sırada bekliyor", hata varsa
  "N video hazır, M tanesinde sorun çıktı", hepsi iptal edildiyse "Tamam, hepsini sıradan çıkardım".
- Başlıkta özet: "5 / 6 tamamlandı · 1 hata". Pencere arkadaysa görev çubuğunda yanıp söner.
- **Bitenleri temizle** (sadece biten varken görünür): tamamlananları listeden kaldırır; tarihi kalmayan
  videoyu da kaldırır; hatalı, bekleyen ve hiç tarih girilmemiş videolar kalır.
- **Hepsini temizle**: onay sorup listeyi sıfırlar; çıktı dosyalarına dokunmaz.

### Kapatırken
- İşlem sürüyorsa: "Durdurup çıkılsın mı?" **[Durdur ve çık] [Devam et]** (varsayılan Devam et).
- İşlenmemiş video varsa: "Listede henüz işlenmemiş N video var…" **[Çık] [Vazgeç]** (varsayılan Vazgeç).

## 4. Ayarlar (⚙)

Tek pencere, tek kart. Üstte el sallayan Zaman Adam, "Ayarlar" ve sürüm. Satırlar (solda ad + kısa açıklama,
sağda ayar):

| Satır | Ayar |
|---|---|
| Tema | **Sistem / Açık / Koyu** (Sistem: Windows teması değişince uygulama da değişir) |
| Çıktı klasörü | yol (ortadan kısaltılmış) + **Aç** + **Değiştir** (işlem sürerken pasif) |
| Aylara göre klasörle | onay kutusu; altında "Ör. 2026-10 Ekim klasörüne…" / "Kapalı: hepsi doğrudan…" |
| Hızlandırma | kısa ad "⚡ Intel Quick Sync" / "⚡ NVIDIA NVENC" / "⚡ AMD AMF" / "⚙️ İşlemci" + **Yeniden ölç**; altında "Bu bilgisayar için ölçülüp seçildi · düşük güç" |
| Güncelleme | "Son kontrol: bugün 14:07" + **Denetle**; yeni sürüm varsa "🎉 Yeni sürüm hazır: 1.0.8" + mavi **Şimdi güncelle** |

Altta **Hata kaydını aç**, **Teşhis bilgisini kopyala** (bağlantılar) ve **Kapat**. Ayarlar butonunda yeni sürüm
varken kırmızı nokta olur. Pencere en az 580 px'tir; yazı tipi büyük bilgisayarlarda (Windows ölçekleme) hiçbir
yazı kırpılmasın diye kendiliğinden genişler.

Saklanan ayarlar (QSettings `ZamanMakinesi/ZamanMakinesi`): `theme`, `output_dir`, `monthly`,
`last_input_dir`, `last_update_check`.

## 5. Hız: video işleme ve en hızlı ayar

- Saat, ffmpeg'in `drawtext` filtresiyle basılır. Okuma + yazı + sıkıştırma **tek ffmpeg sürecinde** yapılır.
- **Aday ayarlar** (`main.PROFILES`), aile sırasıyla:

  | Aile | Ayarlar |
  |---|---|
  | NVIDIA (NVENC) | `nvenc` (p4), `nvenc_fast` (p1) |
  | Intel (Quick Sync) | `qsv` (medium), `qsv_fast` (veryfast), `qsv_lp` (veryfast + düşük güç) |
  | AMD (AMF) | `amf` (balanced), `amf_fast` (speed) |
  | İşlemci (x264 veryfast) | `cpu`, `cpu_hwdec` (videoyu grafik birimi çözer) |

  Grafik ailelerinde video mümkünse grafik biriminde çözülür (`-hwaccel auto`).
- **Hemen kullanılabilir seçim** (`pick_encoder`): açılışta 1 sn'lik denemeyle NVIDIA → Intel → AMD yoklanır,
  ilk çalışanın varsayılan ayarı; yoksa `cpu`.
- **En hızlı ayar ölçümü** (`tune`):
  - **Grafik birimi varsa işlemci yarıştırılmaz.** Sadece çalışan grafik ailelerinin (birden çok varsa
    hepsinin) ayarları ölçülür. İşlemci ayarları yalnızca grafik birimi yoksa ya da grafik ayarlarının hiçbiri
    çalışmazsa ölçülür. Sebep (i5-1135G7'de ölçüldü): kısa denemede işlemci turbo ve kolay içerik sayesinde
    hızlı görünür (4,9x) ama gerçek 10 dk'lık videoda yavaştır (2,2x); Quick Sync ikisinde de 3,2x.
  - Deneme videosu: `TUNE_SAMPLE_SECONDS` (20) sn'lik, kumlu (gerçek kameraya yakın) 1080p30.
  - Hız **hazırlık süresi hariç** ölçülür: videonun ilk `TUNE_WARMUP` (%20) kısmı sayılmaz; kalanının
    işlenme hızı "gerçek zamanın kaç katı" olarak karşılaştırılır (büyük = hızlı).
  - **Kalite kuralı: hız, görüntüyü bozmanın bedeli olamaz.** Her adayın çıktısı deneme videosuyla
    karşılaştırılır (SSIM, her 6. kare, yarım çözünürlük). Ölçülen varsayılan ayarların en iyi benzerliğinden
    `TUNE_QUALITY_TOLERANCE` (0,005) fazla düşük olan ayar elenir.
  - **Boyut kuralı: hız, dosyayı büyütmenin bedeli olamaz.** Her ayarın ürettiği dosya boyutu da ölçülür.
    Ölçülen varsayılan ayarların (`nvenc`, `qsv`, `amf`, `cpu`) en küçük çıktısı ölçüttür; ondan
    `TUNE_SIZE_TOLERANCE` (%10) fazla büyük dosya üreten ayar, ne kadar hızlı olursa olsun **elenir**.
    Sebep: TUNE v2, i5-1135G7'de `qsv_lp`'yi seçti; %20 daha hızlıydı ama 400 MB'lık girişten **1 GB**
    çıkardı (varsayılan `qsv` girişle aynı boyutta).
  - Kalanlar arasında aday sırası güvenliden hızlıya; daha az bilinen (listede sonra gelen) bir ayara ancak
    **en az %10 daha hızlıysa** geçilir. Uygun ayar kalmazsa güvenli varsayılan kullanılır.
    Sonuç `hiz-olcumu.json`'a, ayrıntı hata kaydına yazılır
    (`Hız ölçümü: qsv_lp 4.4x 52.0 MB (büyük dosya, elendi), qsv_fast 3.9x 21.5 MB, qsv 3.5x 21.0 MB -> seçilen: qsv_fast`).
  - Her biten işin işlem süresi, gerçek hızı, **çıktı/giriş boyut oranı** ve bit hızı tavanı da kayda yazılır
    (`Bitti (3 dk 05 sn, 3.2x gerçek zaman, boyut 0.98x girişin, qsv): …`); ölçümün doğru seçip
    seçmediği buradan kontrol edilir.
- **Ne zaman ölçülür** — sadece:
  1. İlk açılışta (kayıt yoksa),
  2. Çalışan grafik aileleri değişince (ör. ekran kartı takıldı/çıkarıldı),
  3. `main.TUNE_VERSION` artırılınca,
  4. Kullanıcı Ayarlar'da **Yeniden ölç**'e basınca.

  Normal sürüm güncellemeleri **yeniden ölçtürmez**.
- **Ölçüm ekranı** ("Genelde yarım dakika, en fazla iki dakika sürer"): pencerenin üstünü kaplar, **iptal edilemez**, bitene kadar işlem başlatılamaz. Büyüteçle
  arayan Zaman Adam, "En hızlı ayar aranıyor…", ilerleme ve "Intel grafik (Quick Sync) · hızlı ayar
  deneniyor · 3 / 7". Bitince Zaman Adam başparmağını kaldırır: "Buldum! 🎉 Bu bilgisayarda en hızlısı: …",
  ekran 2 sn sonra kapanır. Ölçüm sürerken gelen güncelleme duyurusu ölçüm bitince gösterilir.
- **Süre sınırı:** her ayar en fazla `TUNE_STEP_LIMIT` (45 sn; aşılırsa ffmpeg kapatılır, o ayar elenir),
  ölçümün tamamı en fazla `TUNE_TOTAL_LIMIT` (120 sn). Toplam süre dolarsa ölçüm bırakılır, **güvenli
  varsayılan** (`pick_encoder` sonucu) seçilip kaydedilir ("Güvenli ayarla devam ediyorum"); yeniden ölçüm
  sadece yukarıdaki 2–4. durumlarda olur.
- **Yedek:** seçilen ayar bir videoda hata verirse o video kendiliğinden `cpu` ile (donanım yardımı olmadan)
  baştan yapılır. İşlemci kodlayıcısı uygulamanın içinde geldiği için her bilgisayarda çalışır.
- `ZM_ENCODER=<ayar>` ortam değişkeni (ya da `main.ENCODER`) seçimi zorlar ve ölçümü kapatır (deneme için).
- Ölçülen gerçek sonuçlar, i5-1135G7 (Iris Xe), 10 dk 1080p30 video:

  | Sürüm | Yöntem | Süre | Gerçek zamanın |
  |---|---|---|---|
  | 1.0.6 | Python'da kare kare + x264 medium | 15 dk 13 sn | 0,66x |
  | 1.0.7 | ffmpeg + Quick Sync (varsayılan) | 3 dk 05 sn | 3,2x |
  | 1.0.10 | TUNE v1 yanlışlıkla işlemci seçti | 4 dk 36 sn | 2,2x |
  | 1.0.11 | TUNE v2: `qsv_lp` (düşük güç) seçti | 2 dk 29 sn | 4,0x — ama dosya 400 MB → **1 GB** ❌ |
  | 1.0.12 | TUNE v3: `qsv_fast` (boyut kuralı) | — | 3,5x — ama kalite hedefi yüzünden 400 MB → **756 MB** ❌ |
  | 1.0.13 | Boyut tavanı + TUNE v4 (kalite kuralı) | (ölçülecek) | (ölçülecek) |
- `TUNE_VERSION` geçmişi: **1** ilk ölçüm (6 sn, kolay içerik, işlemci dahil). **2** grafik birimi varsa
  işlemci yarıştırılmaz; 20 sn kumlu deneme, hazırlık hariç hız. **3** dosya boyutu kuralı (varsayılandan
  %10'dan büyük dosya üreten ayar elenir). **4** çıktıya bit hızı tavanı (adaylar aynı tavanla yarışır) ve
  görüntü kalitesi (SSIM) kuralı.
- Grafik kodlayıcısı olmayan donanımlar işlemciye düşer: "F" ile biten Intel işlemciler, grafiksiz Ryzen,
  GT 710/730/1030, **MX serisi (MX150–MX550; i5-1135G7 + MX450'li bilgisayarda görüldü)**, RX 6400/6500 XT.
  Bu kartlar listede görünür ama "Çalışan kodlayıcılar"da yer almaz; bu doğrudur.

## 6. Teşhis bilgisi (kullanıcıdan teknik veri)

- **Sunucu yok, izin sorulmaz.** Sadece teknik veriler **yerelde** tutulur; kullanıcı istediğinde panoya kopyalar
  ve WhatsApp/e-posta ile geliştiriciye gönderir. Geliştirici bunları değerlendirip ölçüm kurallarını düzeltir.
- **Toplanan:** her biten/hatalı iş için saat, video çözünürlüğü/fps/kodek/süresi/bit hızı, kullanılan ayar,
  işlem süresi, gerçek hız (x), çıktı/giriş boyut oranı, bit hızı tavanı, sonuç (tamam / hata türü), işlemciye
  düşüp düşmediği. Son 50 iş + toplam iş sayısı
  (`istatistik.json`). Rapor anında ayrıca işletim sistemi, işlemci, RAM, grafik birim(ler)i + sürücü sürümü
  (Windows'ta PowerShell `Win32_VideoController`) ve son hız ölçümü (`hiz-olcumu.json`) eklenir.
- **Asla toplanmaz:** dosya/klasör adları, girilen tarihler, video içeriği, kullanıcı/bilgisayar adı.
- **Ne zaman gönderilir:** Sadece kullanıcı isteyince: Ayarlar → **Teşhis bilgisini kopyala** (tıklayınca
  "✓ Kopyalandı, gönderebilirsiniz"). Uygulama hatırlatmaz, balon çıkarmaz. En faydalı an: ölçümden sonra
  birkaç video işlenmişken (rapor hem ölçümü hem gerçek hızları içerir); geliştirici istediğinde gönderilir.
- Rapor biçimi:
  ```
  Zaman Makinesi teşhis raporu · sürüm 1.0.12
  Sistem: Windows 11 (build 22631) · RAM 16 GB
  İşlemci: 11th Gen Intel(R) Core(TM) i5-1135G7 @ 2.40GHz · 8 çekirdek
  Grafik: Intel(R) Iris(R) Xe Graphics (sürücü 31.0.101.4502)
  Çalışan kodlayıcılar: cpu, qsv
  Hız ölçümü (v3): qsv_lp 4.4x 52.0 MB (büyük dosya, elendi), qsv_fast 3.9x 21.5 MB, qsv 3.5x 21.0 MB -> qsv_fast
  Şu an kullanılan: qsv_fast
  İşler (toplam 12, son 12):
    01.11 15:50 · 1920x1080 60fps h264 10 dk 11 sn 5200 kb/s · qsv_fast · 2 dk 51 sn sürdü · 3.5x · boyut 0.9x · tavan 4680 kb/s · tamam
  ```

## 7. Güncelleme

- Her yayında GitHub Release'e `version.json` konur:
  `{"latest", "min_supported", "url", "sha256", "notes"}`.
- Açılışta okunur (3 sn zaman aşımı). Ulaşılamazsa sessizce devam edilir.
- Sürüm `< min_supported` → **zorunlu güncelleme**: ana pencere açılmaz; "Güncelleme gerekli" + notlar +
  **[Çık] [Güncelle]**.
- Sürüm `< latest` → **normal güncelleme**: açılıştan ~1 sn sonra (ölçüm sürüyorsa ölçüm bitince) Zaman Adam
  balonu bir kez "Yeni sürüm hazır (x.y.z)! Güncellemek için bana tıklayın…" der (tıklayınca güncelleme
  penceresi). Ayarlar butonunda kırmızı nokta kalır, Ayarlar'da "Şimdi güncelle" görünür.
- Ayarlar açıldığında son kontrolün üzerinden **12 saat** geçtiyse kendiliğinden denetler; **Denetle** elle
  denetler. Bulunan yeni sürüm pencereyi kendiliğinden açmaz.
- Güncelle: kurulum dosyası indirilir (buton "İndiriliyor… %42" olur ve pasifleşir, "Lütfen bekleyin…"),
  sha256 doğrulanır, kurulum sessiz başlatılır, uygulama kapanır; kurulum bitince uygulamayı `--updated` ile
  açar ve **"Güncelleme tamamlandı!"** penceresi (Zaman Adam + sürüm notu) gösterilir. İşlem sürerken
  güncellenemez.
- GitHub'ın "latest" linki birkaç dakika önbellekte kalabilir; yeni sürüm herkese birkaç dakika içinde ulaşır.

## 8. Zaman Adam ve animasyonlar

- **Zaman Adam:** uygulama simgesinin (mavi kare, kadran, geri dönen ok) kollu bacaklı, yüzlü hali. Pozlar:
  `run` (koşar), `wave` (el sallar), `ok` (bir kez zıplayıp başparmağını kaldırır, sonra durur),
  `search` (büyüteçle tarar, gözleri büyüteci izler, ağzı "o", etrafında sarı yıldızlar). Arada göz kırpar.
- Açılış: simge yaylanarak büyür, ok çizilir, ibreler bir tur geri döner, ad belirir (~1,6 sn).
- Yeni satırlar yumuşakça belirir; silinen tarih/video solup kapanarak gider.
- Açık ve koyu tema renkleri `gui.LIGHT` / `gui.DARK`; kendi kendini çizen parçalar `theme`'den okur.

## 9. Dağıtım

- Depo: `github.com/berkyymn/zaman-makinesi` (public, MIT lisans). Kişisel hesap.
- Kullanıcıya verilen tek link (hep en son sürüm):
  `https://github.com/berkyymn/zaman-makinesi/releases/latest/download/ZamanMakinesi-Setup.exe`
- Kurulum: imzasız olduğu için SmartScreen uyarısı çıkar → **Ek bilgi → Yine de çalıştır** (README'de
  `assets/kurulum-uyarisi.png` rehber görseli) → **İleri → Kur → Son**.
- Kullanıcı klasörüne kurulur (`%LOCALAPPDATA%\Programs\Zaman Makinesi`), yönetici izni gerekmez.
- Paket: PyInstaller (klasör modu) + Inno Setup (Türkçe). İçinde Python, Qt, OpenCV, ffmpeg (imageio-ffmpeg;
  NVENC/Quick Sync/AMF destekli) gelir. Font: Windows'ta `C:\Windows\Fonts\courbd.ttf`.
- `AppId` asla değiştirilmez (değişirse güncelleme ayrı uygulama sanılır).
- Kullanıcı verileri (`%LOCALAPPDATA%\Zaman Makinesi\`): `zaman-makinesi.log` (hata kaydı, ~3 MB'ı geçmez),
  `hiz-olcumu.json` (en hızlı ayar), `istatistik.json` (teşhis için son 50 işin teknik bilgisi).

## 10. Sürüm yayınlama kontrol listesi

Her yayında **sırayla, eksiksiz**:

1. **Belge:** Davranış değiştiyse bu dosya (TASARIM.md) güncellendi mi? Kullanıcıyı ilgilendiriyorsa README?
2. **Testler:**
   - `QT_QPA_PLATFORM=offscreen uv run python tests/gui_test.py` → hepsi geçmeli.
   - `uv run gui.py --self-test` → çıkış kodu 0.
   - `uv run python tests/tune_test.py` → hız ölçümü kuralları (grafik varken işlemci seçilmez vb.).
   - Görsel değişiklik varsa Mac'te `uv run gui.py` ile elle bakıldı (açık + koyu tema).
3. **`TUNE_VERSION` kararı** (`main.py`): Şunlardan biri değiştiyse **artır**, yoksa **dokunma**:
   `PROFILES` (aday ekleme/çıkarma/ayar değişikliği), ölçüm yöntemi (`tune`: deneme videosu, seçim ve boyut
   kuralı, süre sınırları), işleme hattı (`encode`: drawtext, `-hwaccel`, filtreler). **Yeni bir aday ayar
   eklerken boyutunu ve kalitesini de ölçüp kontrol et; hız tek başına ölçüt değildir. Hız kontrolünü
   (`rate_args`, `target_kbps`) değiştirirsen gerçek bir düşük bit hızlı 1080p60 girişle çıktı/giriş oranının
   1'in altında kaldığını doğrula.** Artırılırsa sürüm notunda
   "ilk açılışta hız ölçümü yapılacak" yazılır.
4. **`version.py`:** sürüm artırıldı (`1.0.9 → 1.0.10`).
5. **`release.json`:**
   - `notes`: kullanıcıya görünen, düz Türkçe, 1–2 cümle.
   - `min_supported`: normal güncellemede **değişmez**. Zorunlu güncellemede yeni sürüme eşitlenir.
     Asla yeni sürümden büyük olamaz (yayın betiği engeller).
6. **Commit + push** (`main`), sonra etiket: `git tag vX.Y.Z && git push origin vX.Y.Z`
   (etiket `version.py` ile aynı olmalı; değilse derleme durur). **Etiket kullanıcı onayı olmadan atılmaz.**
7. **Derlemeyi izle:** GitHub Actions'ta "Paketlenmiş uygulamayı dene" adımı geçmeli (Türkçe dosya adı,
   işleme, hız ölçümü). Sonra `releases/download/vX.Y.Z/version.json` kontrol edilir.

## 11. Dosyalar

| Dosya | Görev |
|---|---|
| `main.py` | Çekirdek + CLI: ffmpeg hattı (drawtext), aday ayarlar, kodlayıcı seçimi, hız ölçümü, yedek, ilerleme/iptal |
| `gui.py` | PySide6 arayüz, uygulamanın giriş noktası |
| `updater.py` | Sürüm kontrolü, indirme, sha256, kurulumu başlatma |
| `icon.py` | Simge çizimi (Zaman Adam ve açılış da kullanır) + `assets/icon.ico` üretimi |
| `version.py` | Tek sürüm kaynağı (`__version__`) |
| `release.json` | `min_supported` + sürüm notu |
| `onizleme.py` | Komut satırı: saatin nasıl duracağını tek karede gösterir |
| `tests/gui_test.py` | Arayüzün uçtan uca testi (ekransız, deneme videolarını kendisi üretir) |
| `tests/tune_test.py` | Hız ölçümü kuralları (kodlayıcı taklit edilir, grafik birimi gerekmez) |
| `packaging/` | Inno Setup betiği, `version.json` üreten betik, kurulum uyarısı görselini çizen betik |
| `.github/workflows/release.yml` | `v*` etiketinde Windows'ta derle, kendi testini çalıştır, yayınla |
| `README.md`, `LICENSE` | Kurulum adımları, geliştirme komutları, MIT |
