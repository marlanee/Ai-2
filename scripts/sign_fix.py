"""Replace broken text on signs in a generated image with real Korean text.

For each sign (a 4-corner quad in image coordinates) the script:
  1) rectifies the quad to a flat rectangle (perspective transform),
  2) erases the inner area by interpolating the colors of its border pixels (old glyphs disappear),
  3) draws new text with a real font (text color sampled from the old glyphs unless given),
     optionally with a soft glow for lit signs,
  4) warps the rectangle back and pastes it with a feathered mask, then adds light grain.

Usage:
  python scripts/sign_fix.py in.png spec.json out.png [--debug dbg.png]

spec.json: {"fonts": {"name": "path.ttf"}, "signs": [{
   "quad": [[x,y] TL, TR, BR, BL], "rect": [w, h],        # rectified size (real proportions)
   "margin": 4, "axis": "xy" | "x" | "y",                  # border ring used for erase interpolation
   "text": "다방" | null, "vertical": false, "font": "name", "fill": 0.8,   # text box fraction
   "color": [r,g,b] | "auto-dark" | "auto-light", "glow": 0, "blur": 0.6, "opacity": 1.0}]}
"""
import argparse, json, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def coeffs(dst, src):
    """PIL PERSPECTIVE coefficients mapping output points `dst` to input points `src`."""
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B.append(v)
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


def smooth(profile, frac=0.15):
    """Sliding median along a border profile (n,3); window ~15% of its length."""
    n = len(profile)
    k = max(3, int(n * frac) | 1)
    pad = np.pad(profile, ((k // 2, k // 2), (0, 0)), mode="edge")
    win = np.lib.stride_tricks.sliding_window_view(pad, k, axis=0)          # (n,3,k)
    return np.median(win, -1)


def erase(rect, m, axis):
    """Fill the inside of `rect` (HxWx3 float) by interpolating its border ring of width m."""
    h, w, _ = rect.shape
    # median-smooth each border profile so old glyph strokes touching the edge do not streak across
    left = smooth(np.median(rect[:, :m], 1)); right = smooth(np.median(rect[:, w - m:], 1))   # (h,3)
    top = smooth(np.median(rect[:m], 0)); bot = smooth(np.median(rect[h - m:], 0))           # (w,3)
    t = np.linspace(0, 1, w)[None, :, None]
    s = np.linspace(0, 1, h)[:, None, None]
    fx = left[:, None] * (1 - t) + right[:, None] * t
    fy = top[None] * (1 - s) + bot[None] * s
    fill = fx if axis == "x" else fy if axis == "y" else (fx + fy) / 2
    out = rect.copy()
    out[m:h - m, m:w - m] = fill[m:h - m, m:w - m]
    return out


def sample_color(rect, mode):
    lum = rect.mean(2)
    q = np.percentile(lum, 12 if mode == "auto-dark" else 88)
    sel = lum <= q if mode == "auto-dark" else lum >= q
    return tuple(int(c) for c in rect[sel].mean(0))


def draw_text(size, text, font_path, vertical, fill, color, glow, blur, opacity):
    w, h = size
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    chars = list(text) if vertical else [text]
    # find the largest font size that fits fill*box
    lo, hi = 4, 400
    while lo < hi:
        mid = (lo + hi + 1) // 2
        f = ImageFont.truetype(font_path, mid)
        boxes = [f.getbbox(c) for c in chars]
        tw = max(b[2] - b[0] for b in boxes) if vertical else boxes[0][2] - boxes[0][0]
        th = sum(b[3] - b[1] for b in boxes) * 1.12 if vertical else boxes[0][3] - boxes[0][1]
        if tw <= w * fill and th <= h * fill:
            lo = mid
        else:
            hi = mid - 1
    f = ImageFont.truetype(font_path, lo)
    d = ImageDraw.Draw(layer)
    a = int(255 * opacity)
    if vertical:
        boxes = [f.getbbox(c) for c in chars]
        total = sum(b[3] - b[1] for b in boxes) * 1.12
        y = (h - total) / 2
        for c, b in zip(chars, boxes):
            cw, ch = b[2] - b[0], b[3] - b[1]
            d.text(((w - cw) / 2 - b[0], y - b[1]), c, font=f, fill=color + (a,))
            y += ch * 1.12
    else:
        b = f.getbbox(text)
        d.text(((w - (b[2] - b[0])) / 2 - b[0], (h - (b[3] - b[1])) / 2 - b[1]), text, font=f, fill=color + (a,))
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    if glow:
        g = layer.filter(ImageFilter.GaussianBlur(glow))
        ga = np.array(g); ga[..., 3] = (ga[..., 3] * 0.8).astype(np.uint8)
        layer = Image.alpha_composite(Image.fromarray(ga), layer)
    return layer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("spec"); ap.add_argument("out")
    ap.add_argument("--debug", default=None, help="also save the image with sign quads outlined")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    fonts = spec.get("fonts", {})
    img = Image.open(a.inp).convert("RGB")
    W, H = img.size
    rng = np.random.default_rng(a.seed)
    for sg in spec["signs"]:
        quad = [tuple(p) for p in sg["quad"]]
        rw, rh = sg["rect"]
        rc = [(0, 0), (rw, 0), (rw, rh), (0, rh)]
        flat = img.transform((rw, rh), Image.PERSPECTIVE, coeffs(rc, quad), Image.BICUBIC)
        arr = np.asarray(flat).astype(float)
        m = sg.get("margin", 4)
        color = sg.get("color", "auto-dark")
        if isinstance(color, str):
            color = sample_color(arr[m:-m, m:-m], color)
        arr = erase(arr, m, sg.get("axis", "xy"))
        flat = Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert("RGBA")
        if sg.get("text"):
            layer = draw_text((rw, rh), sg["text"], fonts[sg.get("font", "default")], sg.get("vertical", False),
                              sg.get("fill", 0.8), tuple(color), sg.get("glow", 0), sg.get("blur", 0.6),
                              sg.get("opacity", 1.0))
            flat = Image.alpha_composite(flat, layer)
        # warp back and paste with a feathered mask (keeps the sign's own edge from the original)
        back = flat.convert("RGB").transform((W, H), Image.PERSPECTIVE, coeffs(quad, rc), Image.BICUBIC)
        mask_flat = Image.new("L", (rw, rh), 0)
        ImageDraw.Draw(mask_flat).rectangle([m // 2, m // 2, rw - 1 - m // 2, rh - 1 - m // 2], fill=255)
        mask_flat = mask_flat.filter(ImageFilter.GaussianBlur(max(1, m / 3)))
        mask = mask_flat.transform((W, H), Image.PERSPECTIVE, coeffs(quad, rc), Image.BICUBIC)
        # light grain inside the patch so it does not look smoother than the painting around it
        noise = rng.normal(0, sg.get("grain", 2.5), (H, W, 1))
        back = Image.fromarray((np.asarray(back).astype(float) + noise).clip(0, 255).astype(np.uint8))
        img = Image.composite(back, img, mask)
        print(f"sign {sg.get('text')!r:12} color={tuple(color)}")
    img.save(a.out)
    if a.debug:
        dbg = img.copy(); d = ImageDraw.Draw(dbg)
        for sg in spec["signs"]:
            d.polygon([tuple(p) for p in sg["quad"]], outline=(255, 0, 255))
        dbg.save(a.debug)
    print("wrote", a.out)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
