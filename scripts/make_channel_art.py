"""YouTube channel art: profile 800x800 (shown as a circle) + banner 2560x1440 (text inside the 1546x423 safe area)."""
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = "test_output/channel/"
F1, F2 = "C:/AI/tools/fonts/BlackHanSans-Regular.ttf", "C:/AI/tools/fonts/DoHyeon-Regular.ttf"


def glyph_ok(font, text):
    def sig(c):
        m = font.getmask(c); return m.size, bytes(m)
    tofu = sig("\U0010FFFD")
    bad = [c for c in text if not c.isspace() and sig(c) == tofu]
    if bad:
        sys.exit(f"missing glyphs {bad} in {text!r}")


# --- profile: crop the ring so it fills the circle mask
p = Image.open(OUT + "profile_s1.png").convert("RGB")
cx, cy, r = 486, 486, 420
p.crop((cx - r, cy - r, cx + r, cy + r)).resize((800, 800), Image.LANCZOS).save(OUT + "profile_800.png")

# --- banner
b = Image.open(OUT + "banner_s2.png").convert("RGB")
s = 1440 / b.height
b = b.resize((round(b.width * s), 1440), Image.LANCZOS)
x0 = (b.width - 2560) // 2
b = b.crop((x0, 0, x0 + 2560, 1440))
W, H = b.size
SX0, SY0, SX1, SY1 = (W - 1546) // 2, (H - 423) // 2, (W + 1546) // 2, (H + 423) // 2   # safe area
title, sub = "서울 골목 라디오", "Seoul Alley Radio  |  비 오는 밤의 시티팝 로파이"
f1, f2 = ImageFont.truetype(F1, 200), ImageFont.truetype(F2, 72)
glyph_ok(f1, title); glyph_ok(f2, sub)
b1, b2 = f1.getbbox(title), f2.getbbox(sub)
tw1, th1, tw2, th2 = b1[2] - b1[0], b1[3] - b1[1], b2[2] - b2[0], b2[3] - b2[1]
gap = 34
ty = SY0 + (423 - (th1 + gap + th2)) // 2
shade = Image.new("L", (W, H), 0)
ImageDraw.Draw(shade).rounded_rectangle([SX0 + 60, SY0 - 10, SX1 - 60, SY1 + 10], 60, fill=160)
shade = shade.filter(ImageFilter.GaussianBlur(70))
b = Image.composite(Image.new("RGB", (W, H), (8, 12, 22)), b, shade)
layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
d.text(((W - tw1) // 2 - b1[0], ty - b1[1]), title, font=f1, fill="#fff1d0")
d.text(((W - tw2) // 2 - b2[0], ty + th1 + gap - b2[1]), sub, font=f2, fill="#bff3df")
glow = layer.filter(ImageFilter.GaussianBlur(14))
out = Image.alpha_composite(b.convert("RGBA"), Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 0)), glow, 0.45))
out = Image.alpha_composite(out, layer).convert("RGB")
out.save(OUT + "banner_2560x1440.jpg", quality=92)
# previews: TV (full), desktop (2560x423 band), mobile (1546x423 safe area)
out.crop((0, SY0, W, SY1)).resize((1280, 212), Image.LANCZOS).save(OUT + "preview_desktop.png")
out.crop((SX0, SY0, SX1, SY1)).resize((773, 212), Image.LANCZOS).save(OUT + "preview_mobile.png")
print("ok")
