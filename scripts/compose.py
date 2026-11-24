"""Compose a looping video with crossfaded music using ffmpeg.

1) Build a seamless loop unit from a clip: the last `seam` seconds are crossfaded into the first
   `seam` seconds (unit length = clip - seam), so the end of the unit flows into its start.
   --seam 0 skips this and loops the raw clip.
2) Loop the unit with -stream_loop to the target duration, mix the music tracks with acrossfade,
   loudness-normalize (default -14 LUFS / -1 dBTP) and mux to H.264/AAC mp4.

Usage:
  python scripts/compose.py --clip loop.mp4 --music a.flac b.flac --duration 60 --out out.mp4 \
      [--seam 0.5] [--xfade 8] [--ffmpeg C:/AI/tools/ffmpeg/bin/ffmpeg.exe]
"""
import argparse, json, pathlib, subprocess, tempfile


def probe_duration(ffprobe, path):
    out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def run(cmd):
    print(" ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", required=True)
    ap.add_argument("--music", nargs="+", required=True)
    ap.add_argument("--duration", type=float, default=60)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seam", type=float, default=0.5, help="loop-seam crossfade seconds (0 = off)")
    ap.add_argument("--xfade", type=float, default=8, help="music crossfade seconds")
    ap.add_argument("--lufs", type=float, default=-14)
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--unit-out", default=None, help="also keep the loop unit at this path")
    a = ap.parse_args()

    ff = pathlib.Path(a.ffmpeg)
    ffprobe = str(ff.with_name(ff.name.replace("ffmpeg", "ffprobe"))) if ff.parent != pathlib.Path(".") else "ffprobe"
    clip_len = probe_duration(ffprobe, a.clip)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="compose_"))

    # 1) loop unit
    unit = pathlib.Path(a.unit_out) if a.unit_out else tmp / "unit.mp4"
    if a.seam > 0:
        d = a.seam
        fc = (f"[0:v]trim={d}:{clip_len},setpts=PTS-STARTPTS[main];"
              f"[0:v]trim=0:{d},setpts=PTS-STARTPTS[head];"
              f"[main][head]xfade=transition=fade:duration={d}:offset={clip_len - 2 * d:.4f},format=yuv420p[v]")
        run([a.ffmpeg, "-v", "error", "-y", "-i", a.clip, "-filter_complex", fc, "-map", "[v]", "-an",
             "-c:v", "libx264", "-crf", "16", "-preset", "medium", str(unit)])
    else:
        run([a.ffmpeg, "-v", "error", "-y", "-i", a.clip, "-an", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(unit)])

    # 2) music: equal slices per track so every crossfade lands inside the target duration
    n = len(a.music)
    x = a.xfade if n > 1 else 0
    seg = (a.duration + x * (n - 1)) / n
    inputs, chains = [], []
    for i, m in enumerate(a.music):
        inputs += ["-i", m]
        chains.append(f"[{i + 1}:a]atrim=0:{seg:.3f},asetpts=PTS-STARTPTS,aresample=48000[m{i}]")
    cur = "m0"
    for i in range(1, n):
        chains.append(f"[{cur}][m{i}]acrossfade=d={x}:c1=tri:c2=tri[x{i}]")
        cur = f"x{i}"
    chains.append(f"[{cur}]afade=t=in:d=2,afade=t=out:st={a.duration - 3}:d=3,"
                  f"loudnorm=I={a.lufs}:TP=-1:LRA=11[a]")
    fc = ";".join(chains)
    run([a.ffmpeg, "-v", "error", "-y", "-stream_loop", "-1", "-i", str(unit), *inputs,
         "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-t", str(a.duration),
         "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", a.out])
    print(f"wrote {a.out}  (clip {clip_len:.2f}s -> unit {clip_len - a.seam:.2f}s, music slices {seg:.1f}s, xfade {x}s)")


if __name__ == "__main__":
    main()
