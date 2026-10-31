"""Windows SmartScreen uyarısının temsili, adım adım rehber görseli (README için).
    uv run python packaging/kurulum_uyarisi_gorseli.py assets/kurulum-uyarisi.png
"""
import sys
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]
S = 2  # retina için 2x çiz
F = "/System/Library/Fonts/Supplemental/"


def font(name, size):
    return ImageFont.truetype(F + name, size * S)


BLUE = (0, 99, 177)
WHITE = (255, 255, 255)
SOFT = (210, 228, 245)
MARK = (255, 196, 0)
INK = (32, 33, 36)
PW, PH = 520, 380          # bir panelin boyutu
GAP, TOP, PAD = 40, 92, 36

W = PAD * 2 + PW * 2 + GAP
H = TOP + PH + 100
img = Image.new("RGB", (W * S, H * S), (248, 249, 250))
d = ImageDraw.Draw(img)


def r(x0, y0, x1, y1):
    return [x0 * S, y0 * S, x1 * S, y1 * S]


def text(x, y, s, f, fill, anchor="la"):
    d.text((x * S, y * S), s, font=f, fill=fill, anchor=anchor)


def wrap(x, y, s, f, fill, width, leading=22):
    words, line = s.split(), ""
    for w in words:
        test = (line + " " + w).strip()
        if d.textlength(test, font=f) / S > width:
            text(x, y, line, f, fill)
            y += leading
            line = w
        else:
            line = test
    text(x, y, line, f, fill)
    return y + leading


def button(x, y, w, label, highlight=False):
    d.rectangle(r(x, y, x + w, y + 34), outline=WHITE, width=2 * S,
                fill=(255, 255, 255) if highlight else BLUE)
    text(x + w / 2, y + 17, label, font("Arial.ttf", 14), BLUE if highlight else WHITE, "mm")


def badge(x, y, n):
    d.ellipse(r(x - 17, y - 17, x + 17, y + 17), fill=MARK, outline=INK, width=2 * S)
    text(x, y, str(n), font("Arial Bold.ttf", 18), INK, "mm")


def ring(x0, y0, x1, y1):
    d.rounded_rectangle(r(x0, y0, x1, y1), radius=10 * S, outline=MARK, width=4 * S)


# Başlık
text(PAD, 26, "Kurulumda bu mavi ekranı görürseniz", font("Arial Bold.ttf", 24), INK)
text(PAD, 60, "Uygulama ücretsiz olduğu için Microsoft imzası yok; Windows bu yüzden uyarır. Güvenle devam edebilirsiniz.",
     font("Arial.ttf", 14), (95, 99, 104))

title_f = font("Arial.ttf", 25)
body_f = font("Arial.ttf", 14)
body = ("Microsoft Defender SmartScreen tanınmayan bir uygulamanın başlatılmasını engelledi. "
        "Bu uygulamanın çalıştırılması bilgisayarınızı riske atabilir.")

for i in range(2):
    x0 = PAD + i * (PW + GAP)
    y0 = TOP
    d.rectangle(r(x0, y0, x0 + PW, y0 + PH), fill=BLUE)
    text(x0 + PW - 22, y0 + 18, "✕", font("Arial Unicode.ttf", 16), WHITE)
    text(x0 + 28, y0 + 40, "Windows bilgisayarınızı korudu", title_f, WHITE)
    y = wrap(x0 + 28, y0 + 92, body, body_f, WHITE, PW - 56)
    if i == 0:
        link_y = y + 8
        text(x0 + 28, link_y, "Ek bilgi", font("Arial.ttf", 14), WHITE)
        d.line(r(x0 + 28, link_y + 18, x0 + 79, link_y + 18), fill=WHITE, width=1 * S)
        ring(x0 + 18, link_y - 8, x0 + 94, link_y + 28)
        badge(x0 + 112, link_y + 10, 1)
        button(x0 + PW - 28 - 130, y0 + PH - 58, 130, "Çalıştırma")
        text(x0, y0 + PH + 34, "1.  “Ek bilgi” yazısına tıklayın", font("Arial Bold.ttf", 16), INK)
    else:
        y += 10
        text(x0 + 28, y, "Uygulama:", body_f, SOFT)
        text(x0 + 120, y, "ZamanMakinesi-Setup.exe", body_f, WHITE)
        text(x0 + 28, y + 24, "Yayımcı:", body_f, SOFT)
        text(x0 + 120, y + 24, "Bilinmeyen yayımcı", body_f, WHITE)
        bx = x0 + PW - 28 - 130 - 12 - 150
        by = y0 + PH - 58
        button(bx, by, 150, "Yine de çalıştır", highlight=False)
        button(x0 + PW - 28 - 130, by, 130, "Çalıştırma")
        ring(bx - 8, by - 8, bx + 158, by + 42)
        badge(bx - 20, by - 18, 2)
        text(x0, y0 + PH + 34, "2.  “Yine de çalıştır” butonuna tıklayın", font("Arial Bold.ttf", 16), INK)

text(W - PAD, H - 16, "Temsili görseldir; Windows sürümüne göre küçük farklar olabilir.",
     font("Arial Italic.ttf", 11), (128, 134, 139), "rs")
img.save(OUT, optimize=True)
print(OUT, img.size)
