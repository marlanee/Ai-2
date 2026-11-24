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
    ap.add_argument("--ambience", default=None, help="looped ambience audio mixed under the music (e.g. rain)")
    ap.add_argument("--ambience-db", type=float, default=-12, help="ambience gain in dB before mixing")
    ap.add_argument("--size", default=None, help="output WxH, scaled to cover then center-cropped (e.g. 1920x1080)")
    ap.add_argument("--copy-video", action="store_true",
                    help="repeat the encoded loop unit with stream copy (fast for 1h+ videos)")
    ap.add_argument("--unit-crf", type=int, default=16)
    ap.add_argument("--static-gain", type=float, default=None,
                    help="dB; replaces loudnorm with fixed gain + limiter (for tracks already loudness-matched)")
    ap.add_argument("--curves", default=None, help="comma list of acrossfade curves per transition (tri, qsin, ...)")
    ap.add_argument("--audio-wav", default=None, help="write only the final audio mix to this WAV and exit")
    ap.add_argument("--xfades", default=None, help="comma list of per-transition crossfade seconds (n-1 values)")
    ap.add_argument("--natural", action="store_true",
                    help="use each track at full length (no equal slicing); output is cut at --duration")
    a = ap.parse_args()

    ff = pathlib.Path(a.ffmpeg)
    ffprobe = str(ff.with_name(ff.name.replace("ffmpeg", "ffprobe"))) if ff.parent != pathlib.Path(".") else "ffprobe"
    clip_len = probe_duration(ffprobe, a.clip)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="compose_"))

    # 1) loop unit
    unit = pathlib.Path(a.unit_out) if a.unit_out else tmp / "unit.mp4"
    fit = ""
    if a.size:
        w, h = a.size.lower().split("x")
        fit = f",scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}"
    if a.seam > 0:
        d = a.seam
        fc = (f"[0:v]trim={d}:{clip_len},setpts=PTS-STARTPTS[main];"
              f"[0:v]trim=0:{d},setpts=PTS-STARTPTS[head];"
              f"[main][head]xfade=transition=fade:duration={d}:offset={clip_len - 2 * d:.4f}{fit},format=yuv420p[v]")
        run([a.ffmpeg, "-v", "error", "-y", "-i", a.clip, "-filter_complex", fc, "-map", "[v]", "-an",
             "-c:v", "libx264", "-crf", str(a.unit_crf), "-preset", "medium", str(unit)])
    else:
        vf = ["-vf", fit.lstrip(",")] if fit else []
        run([a.ffmpeg, "-v", "error", "-y", "-i", a.clip, *vf, "-an", "-c:v", "libx264", "-crf", str(a.unit_crf), "-pix_fmt", "yuv420p", str(unit)])

    # 2) music: equal slices per track so every crossfade lands inside the target duration
    n = len(a.music)
    x = a.xfade if n > 1 else 0
    seg = (a.duration + x * (n - 1)) / n
    inputs, chains = [], []
    for i, m in enumerate(a.music):
        inputs += ["-i", m]
        trim = "" if a.natural else f"atrim=0:{seg:.3f},"
        chains.append(f"[{i + 1}:a]{trim}asetpts=PTS-STARTPTS,aresample=48000[m{i}]")
    xl = [float(v) for v in a.xfades.split(",")] if a.xfades else [x] * (n - 1)
    cl = a.curves.split(",") if a.curves else ["tri"] * (n - 1)
    cur = "m0"
    for i in range(1, n):
        cv = cl[i - 1]
        chains.append(f"[{cur}][m{i}]acrossfade=d={xl[i - 1]}:c1={cv}:c2={cv}[x{i}]")
        cur = f"x{i}"
    if a.ambience:
        k = n + 1
        inputs += ["-stream_loop", "-1", "-i", a.ambience]
        chains.append(f"[{k}:a]aresample=48000,atrim=0:{a.duration},volume={a.ambience_db}dB[amb]")
        chains.append(f"[{cur}][amb]amix=inputs=2:duration=first:normalize=0[mix]")
        cur = "mix"
    # dynamic single-pass loudnorm drifts gain over long programs; for pre-normalized tracks use a static gain + limiter
    final = (f"volume={a.static_gain}dB,aresample=192000,alimiter=limit=0.78:attack=5:release=80:level=false:latency=true,aresample=48000"
             if a.static_gain is not None else f"loudnorm=I={a.lufs}:TP=-1.5:LRA=11")
    chains.append(f"[{cur}]afade=t=in:d=2,afade=t=out:st={a.duration - 3}:d=3,{final}[a]")
    fc = ";".join(chains)
    if a.audio_wav:
        # audio-only pass (for 2-pass static-gain mastering): same graph, PCM out. Audio inputs are numbered
        # from 1 (0 = video), so a tiny dummy video input keeps the indices valid.
        run([a.ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=16x16:r=1:d=1", *inputs,
             "-filter_complex", fc, "-map", "[a]", "-t", str(a.duration), "-c:a", "pcm_s24le", "-ar", "48000", a.audio_wav])
        print(f"wrote {a.audio_wav}")
        return
    if a.copy_video:
        # fast path for long videos: repeat the already-encoded loop unit with the concat demuxer (no re-encode)
        unit_len = probe_duration(ffprobe, unit)
        reps = int(a.duration / unit_len) + 2
        lst = tmp / "concat.txt"
        lst.write_text("".join(f"file '{unit.as_posix()}'\n" for _ in range(reps)), encoding="utf-8")
        run([a.ffmpeg, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), *inputs,
             "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-t", str(a.duration),
             "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", a.out])
    else:
        run([a.ffmpeg, "-v", "error", "-y", "-stream_loop", "-1", "-i", str(unit), *inputs,
             "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-t", str(a.duration),
             "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", a.out])
    print(f"wrote {a.out}  (clip {clip_len:.2f}s -> unit {clip_len - a.seam:.2f}s, music slices {seg:.1f}s, xfade {x}s)")


if __name__ == "__main__":
    main()
