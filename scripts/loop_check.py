"""Loop-seam check for a clip: compares last->first frame jump with typical frame-to-frame motion.

Usage: python scripts/loop_check.py clip.mp4 [--ffmpeg path]
Prints: frames, fps, mean consecutive-frame diff, seam diff (last->first), seam diff when dropping
the duplicate last frame (last-1 -> first), and SSIM(first,last).
A seam diff close to the mean consecutive diff = smooth loop; much larger = visible jump;
near 0 = duplicated frame at the seam (micro-stutter) -> drop the last frame when looping.
"""
import argparse, json, pathlib, subprocess, sys
import numpy as np


def frames(path, ff, w=256):
    p = pathlib.Path(ff)
    ffprobe = str(p.with_name(p.name.replace("ffmpeg", "ffprobe"))) if p.parent != pathlib.Path(".") else "ffprobe"
    probe = json.loads(subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0",
                                       "-show_entries", "stream=width,height,r_frame_rate", "-of", "json", path],
                                      capture_output=True, text=True).stdout)["streams"][0]
    h = int(round(probe["height"] * w / probe["width"] / 2) * 2)
    raw = subprocess.run([ff, "-v", "error", "-i", path, "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    arr = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
    num, den = probe["r_frame_rate"].split("/")
    return arr, float(num) / float(den)


def ssim(a, b):
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    ma, mb = a.mean(), b.mean()
    va, vb = a.var(), b.var()
    cov = ((a - ma) * (b - mb)).mean()
    return ((2 * ma * mb + c1) * (2 * cov + c2)) / ((ma ** 2 + mb ** 2 + c1) * (va + vb + c2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("--ffmpeg", default="ffmpeg")
    a = ap.parse_args()
    f, fps = frames(a.clip, a.ffmpeg)
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))
    res = {
        "frames": len(f), "fps": fps,
        "mean_consecutive_diff": round(float(d.mean()), 3),
        "max_consecutive_diff": round(float(d.max()), 3),
        "seam_diff_last_to_first": round(float(np.abs(f[-1] - f[0]).mean()), 3),
        "seam_diff_drop_last": round(float(np.abs(f[-2] - f[0]).mean()), 3),
        "ssim_first_last": round(float(ssim(f[0], f[-1])), 4),
    }
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    sys.exit(main())
