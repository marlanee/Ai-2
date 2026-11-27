"""Freeze text regions of a static-camera loop clip to the key-art pixels.

Video models (LTX) smear small sign text while animating. With a static camera the signs do not move, so we
overlay the key art back onto those regions in every frame (feathered alpha), keeping all motion elsewhere.

  python scripts/freeze_regions.py clip.mp4 keyart.png spec.json out.mp4 [--names ...] [--grow 6] [--feather 4]

spec.json: the sign spec used by sign_fix.py ("signs": [{"quad": ...}]) and/or {"freeze": [[x0,y0,x1,y1], ...]}.
"""
import argparse, json, pathlib, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFilter

FF = r"C:\AI\tools\ffmpeg\bin\ffmpeg.exe"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip"); ap.add_argument("keyart"); ap.add_argument("spec"); ap.add_argument("out")
    ap.add_argument("--names", nargs="*", default=None, help="only signs whose name contains one of these")
    ap.add_argument("--grow", type=int, default=6)
    ap.add_argument("--feather", type=int, default=4)
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    art = Image.open(a.keyart).convert("RGB")
    mask = Image.new("L", art.size, 0); d = ImageDraw.Draw(mask)
    for sg in spec.get("signs", []):
        if a.names and not any(n in sg.get("name", "") for n in a.names):
            continue
        d.polygon([tuple(p) for p in sg["quad"]], fill=255)
    for box in spec.get("freeze", []):
        d.rectangle(box, fill=255)
    mask = mask.filter(ImageFilter.MaxFilter(a.grow * 2 + 1)).filter(ImageFilter.GaussianBlur(a.feather))
    rgba = art.copy(); rgba.putalpha(mask)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="freeze_")) / "overlay.png"
    rgba.save(tmp)
    subprocess.run([FF, "-v", "error", "-y", "-i", a.clip, "-i", str(tmp), "-filter_complex",
                    "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[v]", "-map", "[v]", "-map", "0:a?",
                    "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-c:a", "copy", a.out], check=True)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
