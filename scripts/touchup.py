"""Masked img2img touch-up of composited signs with Z-Image, then blend back only inside the mask.

  python scripts/touchup.py fixed.png mask.png out_prefix --prompt "..." --denoise 0.2 0.3 0.4 [--seed 7]

Copies the inputs into ComfyUI's input folder, runs workflows/image_zimage_turbo_inpaint_api.json per
denoise value through scripts/run_workflow.py, and writes <out_prefix>_d0.30.png etc. Pixels outside the
mask are taken from fixed.png unchanged (avoids the VAE round-trip softening the whole image).
"""
import argparse, json, pathlib, shutil, subprocess, sys
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMFY = pathlib.Path(r"C:\AI\ComfyUI\ComfyUI")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fixed"); ap.add_argument("mask"); ap.add_argument("out_prefix")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--denoise", type=float, nargs="+", default=[0.2, 0.3, 0.4])
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    shutil.copy(a.fixed, COMFY / "input" / "fix_in.png")
    shutil.copy(a.mask, COMFY / "input" / "fix_mask.png")
    base = Image.open(a.fixed).convert("RGB")
    m = np.asarray(Image.open(a.mask).convert("L")).astype(float)[..., None] / 255
    for dn in a.denoise:
        tag = f"d{dn:.2f}"
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_workflow.py"),
                            str(ROOT / "workflows" / "image_zimage_turbo_inpaint_api.json"),
                            "--set", f"57:27.text={a.prompt}", "--set", f"57:3.denoise={dn}",
                            "--set", f"57:3.seed={a.seed}", "--set", f"9.filename_prefix=fix/{tag}",
                            "--label", f"touchup_{tag}", "--timeout", "600"], capture_output=True, text=True)
        res = json.loads(r.stdout[r.stdout.index("{"):])
        if res.get("status") != "success":
            print(tag, "FAILED", res.get("error")); continue
        gen = Image.open(COMFY / "output" / res["outputs"][0]).convert("RGB").resize(base.size, Image.LANCZOS)
        out = np.asarray(base).astype(float) * (1 - m) + np.asarray(gen).astype(float) * m
        p = f"{a.out_prefix}_{tag}.png"
        Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(p)
        print(tag, f"{res['seconds']}s", p)


if __name__ == "__main__":
    main()
