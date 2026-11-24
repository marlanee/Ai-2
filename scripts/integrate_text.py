"""Make sign letters sit IN the sign surface instead of on top of it (no generative model -> text cannot change).

Per sign quad (from a sign spec):
  1) glyph mask = pixels far in color from the local median (letters vs panel)
  2) panel texture: high-pass of the region (vertical streaks, grain) is re-applied over the letters
  3) light bleed: a soft halo of the letter color spreads into the panel (lit signs)
  4) depth softness: letters are blurred by `soft` px (distant signs softer than near ones)

  python scripts/integrate_text.py in.png spec.json out.png [--only name ...]
Spec keys per sign (optional): "soft" (px, default 0.6), "bleed" (0-1, default 0.18), "tex" (default 1.0), "lit" (bool).
"""
import argparse, json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("spec"); ap.add_argument("out")
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args()
    img = Image.open(a.inp).convert("RGB")
    out = np.asarray(img).astype(float)
    W, H = img.size
    for sg in json.load(open(a.spec, encoding="utf-8"))["signs"]:
        if not sg.get("text") or (a.only and not any(n in sg.get("name", "") for n in a.only)):
            continue
        q = np.array(sg["quad"], float)
        x0, y0 = np.maximum(q.min(0) - 6, 0).astype(int); x1, y1 = np.minimum(q.max(0) + 6, [W, H]).astype(int)
        reg = Image.fromarray(out[y0:y1, x0:x1].clip(0, 255).astype(np.uint8))
        r = np.asarray(reg).astype(float)
        quad = Image.new("L", reg.size, 0)
        ImageDraw.Draw(quad).polygon([(x - x0, y - y0) for x, y in q], fill=255)
        quad = np.asarray(quad.filter(ImageFilter.MinFilter(5))) > 0
        k = max(9, int(min(reg.size) * 0.25) | 1)
        med = np.asarray(reg.filter(ImageFilter.MedianFilter(min(k, 31) | 1))).astype(float)
        dist = np.linalg.norm(r - med, axis=2)
        glyph = (dist > max(25, np.percentile(dist[quad], 70))) & quad
        gm = Image.fromarray((glyph * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
        g = np.asarray(gm).astype(float)[..., None] / 255
        # 2) panel texture over letters: high-pass of the panel (glyphs replaced by median) added onto letters
        # texture taken ONLY from panel pixels (letters + a margin excluded) -> no glyph ghosts:
        # column profile (vertical streaks) + matched-std grain
        hp_raw = r - np.asarray(reg.filter(ImageFilter.GaussianBlur(2.5))).astype(float)
        far = np.asarray(Image.fromarray((glyph * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))) == 0
        ok = far & quad
        lum = hp_raw.mean(2)
        cols = np.array([lum[ok[:, j], j].mean() if ok[:, j].sum() > 3 else 0.0 for j in range(lum.shape[1])])
        std = float(lum[ok].std()) if ok.any() else 2.0
        rng = np.random.default_rng(0)
        grain = rng.normal(0, std * 0.8, lum.shape)
        grain = np.asarray(Image.fromarray((grain + 128).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.5))).astype(float) - 128
        tex = (cols[None, :] + grain)[..., None]
        res = r + g * tex * sg.get("tex", 1.0)
        # 3) light bleed: letter color halo into the panel
        if sg.get("lit", True):
            col = r[glyph].mean(0) if glyph.any() else r.mean((0, 1))
            halo = np.asarray(gm.filter(ImageFilter.GaussianBlur(max(2, min(reg.size) * 0.03)))).astype(float)[..., None] / 255
            res = res * (1 - halo * sg.get("bleed", 0.18)) + col * halo * sg.get("bleed", 0.18)
        # 4) depth softness on the letters only
        s = sg.get("soft", 0.6)
        if s > 0:
            soft = np.asarray(Image.fromarray(res.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(s))).astype(float)
            res = res * (1 - g) + soft * g
        qm = np.asarray(Image.fromarray((quad * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))).astype(float)[..., None] / 255
        out[y0:y1, x0:x1] = r * (1 - qm) + res * qm
        print(f"{sg['text']}: glyph px {int(glyph.sum())}")
    Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(a.out)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
