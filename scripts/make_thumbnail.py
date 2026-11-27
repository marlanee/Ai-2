"""Thumbnail with a real-font title (text is rendered by a font, so it can never be 'broken').

  python scripts/make_thumbnail.py key.png out.jpg --title "비 오는 밤" --sub "공부·작업용 시티팝 2시간" \
      [--crop x0 y0 x1 y1] [--font path.ttf] [--pos bl|br|tl|tr] [--color "#ffe7b3"]

Design rules (from GPT strategy review + common lofi thumbnails): <= 2 short lines, large, warm off-white with a
soft dark shadow/glow, placed away from the bottom-right timestamp badge, readable at 160x90.
"""
import argparse
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key"); ap.add_argument("out")
    ap.add_argument("--title", required=True); ap.add_argument("--sub", default="")
    ap.add_argument("--crop", type=int, nargs=4, default=None)
    ap.add_argument("--font", default="C:/AI/tools/fonts/BlackHanSans-Regular.ttf")
    ap.add_argument("--subfont", default="C:/AI/tools/fonts/DoHyeon-Regular.ttf")
    ap.add_argument("--pos", default="bl", choices=["bl", "tl", "tr", "br"])
    ap.add_argument("--color", default="#fff1d0")
    a = ap.parse_args()
    im = Image.open(a.key).convert("RGB")
    if a.crop:
        im = im.crop(a.crop)
    im = im.resize((1280, 720), Image.LANCZOS)
    W, H = im.size
    f1 = ImageFont.truetype(a.font, 112); f2 = ImageFont.truetype(a.subfont, 50)
    # refuse characters the font cannot draw (they render as tofu boxes = broken text)
    for f, txt in ((f1, a.title), (f2, a.sub)):
        def sig(c):
            m = f.getmask(c)
            return m.size, bytes(m)
        tofu = sig("\U0010FFFD")
        bad = sorted({c for c in txt if not c.isspace() and sig(c) == tofu})
        if bad:
            raise SystemExit(f"font {f.getname()} has no glyph for {bad!r} in {txt!r}")
    b1 = f1.getbbox(a.title); b2 = f2.getbbox(a.sub) if a.sub else (0, 0, 0, 0)
    tw = max(b1[2] - b1[0], b2[2] - b2[0]); th = (b1[3] - b1[1]) + (b2[3] - b2[1] + 18 if a.sub else 0)
    m = 56
    x = m if a.pos in ("bl", "tl") else W - m - tw
    y = m if a.pos in ("tl", "tr") else H - m - th - (60 if a.pos == "bl" else 90)
    # soft dark vignette behind text for contrast
    shade = Image.new("L", (W, H), 0); ImageDraw.Draw(shade).rectangle([x - 40, y - 30, x + tw + 40, y + th + 30], fill=150)
    shade = shade.filter(ImageFilter.GaussianBlur(45))
    im = Image.composite(Image.new("RGB", (W, H), (8, 10, 18)), im, shade)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    d.text((x - b1[0], y - b1[1]), a.title, font=f1, fill=a.color)
    if a.sub:
        d.text((x - b2[0], y + (b1[3] - b1[1]) + 18 - b2[1]), a.sub, font=f2, fill="#e9e3d6")
    glow = layer.filter(ImageFilter.GaussianBlur(8))
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); shadow.putalpha(layer.split()[3].filter(ImageFilter.GaussianBlur(4)))
    out = Image.alpha_composite(im.convert("RGBA"), shadow)
    out = Image.alpha_composite(out, Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 0)), glow, 0.35))
    out = Image.alpha_composite(out, layer).convert("RGB")
    out.save(a.out, quality=92)
    out.resize((160, 90), Image.LANCZOS).save(a.out.rsplit(".", 1)[0] + "_160.png")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
