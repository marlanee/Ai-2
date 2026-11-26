"""Story-channel thumbnail: scene image + 2 bold lines at the bottom with per-word colours and a thick black stroke.

  python scripts/story_thumbnail.py scene.png out.jpg --line "거지 노인에게 [y:국밥] 준 과부" --line "사흘 뒤 [p:사또]가 찾아온 [g:이유]"

Markup: [y:..] yellow, [g:..] green, [p:..] pink, [c:..] cyan; plain text is white. Writes out.jpg (1280x720) + _320.png preview.
"""
import argparse, re
from PIL import Image, ImageDraw, ImageFilter, ImageFont

COL = {"w": (255, 255, 255), "y": (255, 226, 60), "g": (120, 240, 90), "p": (255, 110, 170), "c": (90, 220, 255)}
FONT = "C:/AI/tools/fonts/BlackHanSans-Regular.ttf"


def parse(line):
    out, pos = [], 0
    for m in re.finditer(r"\[(\w):([^\]]+)\]", line):
        if m.start() > pos:
            out.append(("w", line[pos:m.start()]))
        out.append((m[1], m[2])); pos = m.end()
    if pos < len(line):
        out.append(("w", line[pos:]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key"); ap.add_argument("out"); ap.add_argument("--line", action="append", required=True)
    ap.add_argument("--size", type=int, default=104); ap.add_argument("--crop", type=int, nargs=4)
    ap.add_argument("--top", action="store_true", help="text top-left (keeps the action in the lower half visible)")
    a = ap.parse_args()
    im = Image.open(a.key).convert("RGB")
    if a.crop:
        im = im.crop(a.crop)
    W, H = 1280, 720
    im = im.resize((W, round(im.height * W / im.width)), Image.LANCZOS).crop((0, 0, W, H)) if im.width / im.height < W / H \
        else im.resize((round(im.width * H / im.height), H), Image.LANCZOS)
    im = im.crop(((im.width - W) // 2, 0, (im.width - W) // 2 + W, H))
    # darken the lower third so the text pops
    grad = Image.linear_gradient("L").resize((W, H))
    grad = (grad.transpose(Image.FLIP_TOP_BOTTOM) if a.top else grad).point(lambda v: max(0, (v - 110) * 1.4))
    im = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), im, grad.point(lambda v: min(170, v)))
    lines = [parse(l) for l in a.line]
    size = a.size
    while True:   # shrink until every line fits with a 40 px margin
        f = ImageFont.truetype(FONT, size)
        widths = [sum(f.getlength(t) for _, t in segs) for segs in lines]
        if max(widths) <= W - 80 or size < 60:
            break
        size -= 4
    d = ImageDraw.Draw(im)
    lh = int(size * 1.12)
    y = 30 if a.top else H - 34 - lh * len(lines)
    for segs, w in zip(lines, widths):
        x = 44 if a.top else (W - w) / 2
        for c, t in segs:
            d.text((x, y), t, font=f, fill=COL[c], stroke_width=max(6, size // 11), stroke_fill=(0, 0, 0))
            x += f.getlength(t)
        y += lh
    im.save(a.out, quality=93)
    im.resize((320, 180), Image.LANCZOS).save(a.out.rsplit(".", 1)[0] + "_320.png")
    print("wrote", a.out, "font", size)


if __name__ == "__main__":
    main()
