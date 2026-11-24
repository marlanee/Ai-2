"""Erase small pseudo-text (posters, labels, plates, distant signs) region by region with Qwen-Image-Edit,
then paste protected sign regions back from the input so the verified big signs never change.

  python scripts/erase_small_text.py in.png out.png --tiles x0,y0,x1,y1 ... --protect spec.json [spec2.json] [--seed 1]
"""
import argparse, json, pathlib, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROMPT = ("Remove all small writing in this picture: make every poster, notice, label, menu, sticker, license plate, "
          "record sleeve text and every small distant shop sign blank, keeping their shapes, colors and lighting. "
          "Do not add any letters, numbers or symbols. Keep the same 1980s anime illustration style, the rain, the "
          "lighting and everything else exactly the same.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--tiles", nargs="+", required=True)
    ap.add_argument("--protect", nargs="*", default=[])
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--gentle", action="store_true", help="keep artwork, only remove letters")
    a = ap.parse_args()
    src = Image.open(a.inp).convert("RGB")
    cur = pathlib.Path(a.out).with_suffix(".work.png")
    src.save(cur)
    global PROMPT
    if a.gentle:
        PROMPT = ("Remove only the tiny letters, numbers and scribbles from this picture. Keep every object, picture, "
                  "album cover artwork (colorful illustrations, circles, faces), poster colors, shutter, wall and lighting "
                  "exactly as they are; just make the lettering areas plain. Do not add any new shapes, blocks, letters or "
                  "symbols. Keep the same 1980s anime illustration style and the rain.")
    for i, t in enumerate(a.tiles):
        x0, y0, x1, y1 = map(int, t.split(","))
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "qwen_edit.py"), str(cur), str(cur), "--prompt", PROMPT,
                            "--crop", str(x0), str(y0), str(x1), str(y1), "--seed", str(a.seed + i), "--feather", "16"],
                           capture_output=True, text=True, encoding="utf-8")
        print(f"tile {t}: {r.stdout.strip().splitlines()[0] if r.stdout.strip() else r.stderr[-300:]}", flush=True)
    img = Image.open(cur).convert("RGB")
    mask = Image.new("L", src.size, 0); d = ImageDraw.Draw(mask)
    for sp in a.protect:
        for sg in json.load(open(sp, encoding="utf-8"))["signs"]:
            d.polygon([tuple(p) for p in sg["quad"]], fill=255)
    mask = mask.filter(ImageFilter.MaxFilter(13)).filter(ImageFilter.GaussianBlur(4))
    Image.composite(src, img, mask).save(a.out)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
