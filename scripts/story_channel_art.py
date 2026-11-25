"""Channel-art drafts for the story channel (files only; no account actions).

  python scripts/story_channel_art.py --name "밤마실 야담" --sub "잠들기 전 듣는 옛날이야기" --bg scene.png --face face.png --out DIR

Writes DIR/banner_2560x1440.jpg (title inside the 1546x423 all-device safe area), DIR/profile_800.png and
DIR/preview_mobile.png (safe-area crop as a phone shows it).
"""
import argparse, pathlib
from PIL import Image, ImageDraw, ImageFilter, ImageFont

TITLE = r"C:\Windows\Fonts\NotoSerifKR-VF.ttf"
SUB = "C:/AI/tools/fonts/DoHyeon-Regular.ttf"


def vf(path, size, weight):
    f = ImageFont.truetype(path, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True); ap.add_argument("--sub", default="")
    ap.add_argument("--bg", required=True); ap.add_argument("--face", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    W, H = 2560, 1440
    bg = Image.open(a.bg).convert("RGB")
    s = max(W / bg.width, H / bg.height)
    bg = bg.resize((round(bg.width * s), round(bg.height * s)), Image.LANCZOS)
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    # darken a soft band behind the safe area so the title reads on every device
    sx, sy, sw, sh = (W - 1546) // 2, (H - 423) // 2, 1546, 423
    band = Image.new("L", (W, H), 0); ImageDraw.Draw(band).rectangle([0, sy - 40, W, sy + sh + 40], fill=170)
    bg = Image.composite(Image.new("RGB", (W, H), (12, 10, 8)), bg, band.filter(ImageFilter.GaussianBlur(60)))
    d = ImageDraw.Draw(bg)
    size = 190
    while True:
        f1 = vf(TITLE, size, 800)
        if f1.getlength(a.name) <= sw - 120 or size < 90:
            break
        size -= 6
    f2 = ImageFont.truetype(SUB, 64)
    tw = f1.getlength(a.name); th = size
    y = sy + (sh - th - (90 if a.sub else 0)) / 2 - 20
    d.text(((W - tw) / 2, y), a.name, font=f1, fill=(255, 238, 200), stroke_width=4, stroke_fill=(20, 14, 8))
    if a.sub:
        d.text(((W - f2.getlength(a.sub)) / 2, y + th + 40), a.sub, font=f2, fill=(235, 225, 205), stroke_width=3, stroke_fill=(20, 14, 8))
    bg.save(out / "banner_2560x1440.jpg", quality=92)
    bg.crop((sx, sy, sx + sw, sy + sh)).save(out / "preview_mobile.png")
    face = Image.open(a.face).convert("RGB")
    m = min(face.size); face = face.crop(((face.width - m) // 2, 0, (face.width - m) // 2 + m, m)).resize((800, 800), Image.LANCZOS)
    mask = Image.new("L", (800, 800), 0); ImageDraw.Draw(mask).ellipse([0, 0, 799, 799], fill=255)
    face.putalpha(mask); face.save(out / "profile_800.png")
    print("wrote", out)


if __name__ == "__main__":
    main()
