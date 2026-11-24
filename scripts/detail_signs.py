"""Per-sign detailer: crop each sign, upscale it so the glyphs are large for the model, run a masked
Z-Image img2img touch-up on the crop, scale it back and blend it in with a feathered mask.

Full-image touch-up breaks small text (a 50px sign is only ~6 latent pixels); working on an upscaled crop
keeps the glyph shapes while the model repaints texture, light bleed and edges in the image's own style.

  python scripts/detail_signs.py fixed.png spec.json out_prefix --denoise 0.3 0.4 [--seed 7] [--long 1024]
"""
import argparse, json, pathlib, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMFY = pathlib.Path(r"C:\AI\ComfyUI\ComfyUI")
WF = ROOT / "workflows" / "image_zimage_turbo_inpaint_api.json"
STYLE = ("close-up of a hand-painted shop sign in a retro 1980s anime cel illustration, rainy night in a Seoul alley, "
         "soft glow, film grain. The sign reads \"{text}\" in clean Korean hangul letters.")


def run(prompt, dn, seed, tag):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_workflow.py"), str(WF),
                        "--set", f"57:27.text={prompt}", "--set", f"57:3.denoise={dn}", "--set", f"57:3.seed={seed}",
                        "--set", f"9.filename_prefix=fix/{tag}", "--label", f"detail_{tag}", "--timeout", "600"],
                       capture_output=True, text=True)
    res = json.loads(r.stdout[r.stdout.index("{"):])
    if res.get("status") != "success":
        raise RuntimeError(f"{tag}: {res.get('error')}")
    return Image.open(COMFY / "output" / res["outputs"][0]).convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fixed"); ap.add_argument("spec"); ap.add_argument("out_prefix")
    ap.add_argument("--denoise", type=float, nargs="+", default=[0.3, 0.4])
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--long", type=int, default=1024, help="long side of the upscaled crop")
    ap.add_argument("--pad", type=int, default=16)
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    base = Image.open(a.fixed).convert("RGB")
    W, H = base.size
    for dn in a.denoise:
        img = base.copy()
        for i, sg in enumerate(spec["signs"]):
            if not sg.get("text") or not sg.get("touchup", True):
                continue
            q = np.array(sg["quad"], float)
            x0, y0 = np.maximum(q.min(0) - a.pad, 0).astype(int)
            x1, y1 = np.minimum(q.max(0) + a.pad, [W, H]).astype(int)
            cw, ch = x1 - x0, y1 - y0
            s = min(a.long / max(cw, ch), 8.0)
            uw, uh = max(16, round(cw * s / 16) * 16), max(16, round(ch * s / 16) * 16)
            crop = img.crop((x0, y0, x1, y1)).resize((uw, uh), Image.LANCZOS)
            # mask: the sign quad in upscaled crop coordinates, grown a little and feathered
            mk = Image.new("L", (uw, uh), 0)
            ImageDraw.Draw(mk).polygon([((x - x0) * uw / cw, (y - y0) * uh / ch) for x, y in q], fill=255)
            g = max(2, int(4 * s))
            mk = mk.filter(ImageFilter.MaxFilter(g | 1)).filter(ImageFilter.GaussianBlur(g))
            crop.save(COMFY / "input" / "fix_in.png"); mk.convert("RGB").save(COMFY / "input" / "fix_mask.png")
            gen = run(STYLE.format(text=sg["text"]), dn, a.seed + i, f"d{dn:.2f}_s{i}")
            gen = gen.resize((cw, ch), Image.LANCZOS)
            m = np.asarray(mk.resize((cw, ch), Image.LANCZOS)).astype(float)[..., None] / 255
            region = np.asarray(img.crop((x0, y0, x1, y1))).astype(float)
            out = region * (1 - m) + np.asarray(gen).astype(float) * m
            img.paste(Image.fromarray(out.clip(0, 255).astype(np.uint8)), (x0, y0))
            print(f"d{dn:.2f} sign {sg['text']!r} crop {cw}x{ch} -> {uw}x{uh}")
        p = f"{a.out_prefix}_d{dn:.2f}.png"
        img.save(p)
        print("wrote", p)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
