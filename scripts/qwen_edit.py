"""Instruction-based image edit with Qwen-Image-Edit-2511 (int8 + Lightning 4-step LoRA).

  python scripts/qwen_edit.py in.png out.png --prompt "..." [--crop x0 y0 x1 y1] [--seed 1] [--steps 40]

--crop edits only that region: it is cut out, edited at the model's working size (~1MP, so small signs
become large), resized back and pasted with a feathered border. Without --crop the whole image is edited
and resized back to the input size.
"""
import argparse, json, pathlib, shutil, subprocess, sys
import numpy as np
from PIL import Image, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMFY = pathlib.Path(r"C:\AI\ComfyUI\ComfyUI")
WF = ROOT / "workflows" / "image_qwen_edit_2511_int8_api.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--crop", type=int, nargs=4, default=None)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--full", action="store_true", help="40 steps cfg 4 instead of Lightning 4 steps")
    ap.add_argument("--feather", type=int, default=24)
    a = ap.parse_args()
    src = Image.open(a.inp).convert("RGB")
    box = a.crop or (0, 0, *src.size)
    src.crop(box).save(COMFY / "input" / "qedit_in.png")
    tag = pathlib.Path(a.out).stem
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_workflow.py"), str(WF),
                        "--set", "41.image=qedit_in.png", "--set", f"170:151.prompt={a.prompt}",
                        "--set", f"170:168.value={'false' if a.full else 'true'}",
                        "--set", f"170:169.seed={a.seed}", "--set", f"195.filename_prefix=qedit/{tag}",
                        "--label", f"qedit_{tag}", "--timeout", "1800"], capture_output=True, text=True)
    res = json.loads(r.stdout[r.stdout.index("{"):])
    if res.get("status") != "success":
        sys.exit(f"FAILED: {res.get('error')}")
    gen = Image.open(COMFY / "output" / res["outputs"][0]).convert("RGB")
    w, h = box[2] - box[0], box[3] - box[1]
    print(f"model output {gen.size} -> {w}x{h}, {res['seconds']}s, peak {res.get('peak_vram_mb')}MB")
    gen = gen.resize((w, h), Image.LANCZOS)
    if a.crop:
        f = a.feather
        m = Image.new("L", (w, h), 0)
        m.paste(255, (f, f, w - f, h - f))
        m = np.asarray(m.filter(ImageFilter.GaussianBlur(f / 2))).astype(float)[..., None] / 255
        reg = np.asarray(src.crop(box)).astype(float)
        out = src.copy()
        out.paste(Image.fromarray((reg * (1 - m) + np.asarray(gen).astype(float) * m).clip(0, 255).astype(np.uint8)), box[:2])
    else:
        out = gen
    out.save(a.out)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
