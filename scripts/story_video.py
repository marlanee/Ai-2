"""Assemble a narrated story video: scene stills with slow Ken Burns motion, burned-in subtitles, narration + ducked BGM.

  python scripts/story_video.py <story_dir> [--bgm a.flac b.flac ...] [--limit-s 60] [--out name.mp4]

Inputs : <dir>/story.json, <dir>/scenes/sNN.png, <dir>/tts/lines.json (+ wavs from story_tts.py)
Outputs: <dir>/<name>.mp4, <dir>/<name>.srt, <dir>/timeline.json
Timing : 0.6 s lead-in, 0.45 s between lines, +0.9 s between scenes, 3 s tail. A scene's image is on screen from its
         first line to the next scene's first line; scene changes cross-fade over 0.6 s.
"""
import argparse, json, pathlib, re, subprocess
import numpy as np, soundfile as sf
from PIL import Image, ImageDraw, ImageFont

FF = r"C:\AI\tools\ffmpeg\bin\ffmpeg.exe"
FONT = r"C:\Windows\Fonts\NotoSansKR-VF.ttf"
W, H, FPS = 1920, 1080, 24
GAP_LINE, GAP_SCENE, LEAD, TAIL, XF = 0.45, 0.9, 0.6, 3.0, 0.6


def font(size, weight=800):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def wrap(text, f, maxw):
    """Split at spaces into lines no wider than maxw (balanced 2 lines when possible)."""
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    if len(lines) == 2:   # rebalance so the first line is not much longer than the second
        best = min(range(1, len(words)), key=lambda i: abs(f.getlength(" ".join(words[:i])) - f.getlength(" ".join(words[i:]))))
        a, b = " ".join(words[:best]), " ".join(words[best:])
        if max(f.getlength(a), f.getlength(b)) <= maxw:
            lines = [a, b]
    return lines


def sub_chunks(text, maxw=1400):
    """One spoken line -> on-screen subtitle chunks that each fit on one line when possible.
    Splits after , . ? ! … and merges pieces greedily; returns [(chunk, is_dialogue)]."""
    f = font(62)
    dlg = text.startswith(('"', "“"))
    parts = [p for p in re.split(r"(?<=[,.?!…])\s+", text.strip('"“”')) if p]
    out, cur = [], ""
    for p in parts:
        t = (cur + " " + p).strip()
        if f.getlength(t) <= maxw or not cur:
            cur = t
        else:
            out.append(cur); cur = p
    out.append(cur)
    res = []
    for c in out:   # a clause still too wide for one line -> split at the most balanced space
        w = c.split(" ")
        if f.getlength(c) > maxw and len(w) > 1:
            k = min(range(1, len(w)), key=lambda i: abs(f.getlength(" ".join(w[:i])) - f.getlength(" ".join(w[i:]))))
            res += [" ".join(w[:k]), " ".join(w[k:])]
        else:
            res.append(c)
    return [(c, dlg) for c in res]


def subtitle_layer(text, dialogue=None):
    dialogue = text.startswith(('"', "“")) if dialogue is None else dialogue
    f = font(62)
    lines = wrap(text, f, 1600)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lh = 84
    y0 = H - 70 - lh * len(lines)
    for i, l in enumerate(lines):
        x = (W - f.getlength(l)) / 2
        d.text((x, y0 + i * lh), l, font=f, fill=(255, 236, 150) if dialogue else (255, 255, 255),
               stroke_width=6, stroke_fill=(0, 0, 0))
    return layer


def cover(img):
    s = max(W / img.width, H / img.height) * 1.12   # 12% headroom for motion
    return img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)


def kb_frame(src, p, k):
    """Ken Burns: alternate zoom-in / zoom-out with a slight pan, p in [0,1]."""
    p = p * p * (3 - 2 * p)                                   # ease in/out
    z = 1.0 + 0.10 * (p if k % 2 == 0 else 1 - p)            # 1.0 = full 1920x1080 view of the 12%-oversized source
    cw = src.width / 1.12 / z
    ch = cw * H / W
    pan = (0.6, -0.6, 0.0)[k % 3] * (p - 0.5)                # -0.3..0.3 of the spare width
    x0 = min(max(0.0, (src.width - cw) * (0.5 + pan)), src.width - cw)
    y0 = (src.height - ch) * 0.5
    return src.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


def whistle(kind, sr, far=False, seed=0):
    """Synthetic signal whistle: S = short chirp (0.24 s, rising), L = long call (0.95 s, slight fall). far = distant
    (quieter, duller, echo). Returns mono float32."""
    rng = np.random.default_rng(seed)
    dur = 0.24 if kind == "S" else 0.95
    n = int(dur * sr); t = np.arange(n) / sr
    f0 = 2050 + rng.uniform(-60, 60)
    f = (f0 - 250 + 320 * np.minimum(1, t / 0.08)) if kind == "S" else (f0 + 120 - 260 * t / dur)
    f = f + 18 * np.sin(2 * np.pi * 5.5 * t)                       # breath vibrato
    w = np.sin(2 * np.pi * np.cumsum(f) / sr) + 0.12 * np.sin(4 * np.pi * np.cumsum(f) / sr)
    w += 0.05 * rng.standard_normal(n)                              # air noise
    a = min(int(0.025 * sr), n // 4); r = min(int(0.07 * sr), n // 3)
    env = np.ones(n); env[:a] = np.linspace(0, 1, a); env[-r:] = np.linspace(1, 0, r)
    w = (w * env).astype(np.float32)
    if far:
        k = int(sr / 2600); w = np.convolve(w, np.ones(k) / k, mode="same")      # duller
        out = np.zeros(n + int(0.9 * sr), np.float32); out[:n] += w
        for dl, g in ((0.11, 0.45), (0.23, 0.3), (0.41, 0.18), (0.62, 0.1)):      # ravine echo
            i = int(dl * sr); out[i:i + n] += w * g
        w = out * 0.35
    return w * 0.25   # was 0.5: listener (11-26) found the whistle close to right but too loud -> -6 dB


def cue_track(seq, sr, far_default=False, seed=0):
    """seq like 'S S . L' (space-separated tokens): S/L whistles (suffix '~' = far), '.' = 0.45 s pause.
    Gap between tokens 0.14 s. Returns mono float32."""
    parts = []
    for i, tok in enumerate(seq.split()):
        if tok == ".":
            parts.append(np.zeros(int(0.45 * sr), np.float32)); continue
        parts.append(whistle(tok[0], sr, far=tok.endswith("~") or far_default, seed=seed + i))
        parts.append(np.zeros(int(0.14 * sr), np.float32))
    return np.concatenate(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story_dir"); ap.add_argument("--bgm", nargs="*", default=[])
    ap.add_argument("--limit-s", type=float, default=0); ap.add_argument("--out", default="")
    ap.add_argument("--bgm-db", type=float, default=-17)
    a = ap.parse_args()
    d = pathlib.Path(a.story_dir)
    rows = json.load(open(d / "tts" / "lines.json", encoding="utf-8"))
    name = a.out or f"{d.name}.mp4"

    # ---- timeline + narration track
    sr = sf.info(d / "tts" / rows[0]["file"]).samplerate
    # timed signal cues (annotate.json scenes[].cues = [{"line": 3, "seq": "S S . L~", "at": "after"|"before"}]):
    # played in the clear — the narration waits for them — and mixed on the voice bus (not ducked).
    cues_at = {}
    if (d / "annotate.json").exists():
        for x in json.load(open(d / "annotate.json", encoding="utf-8"))["scenes"]:
            for c in x.get("cues", []):
                cues_at.setdefault((x["id"], c["line"], c.get("at", "after")), []).append(c["seq"])
    t, prev_scene, tl, pieces, sig = LEAD, None, [], [np.zeros(int(LEAD * sr), np.float32)], []

    def put_cue(key):
        nonlocal t
        for k, seq in enumerate(cues_at.get(key, [])):
            w = cue_track(seq, sr, seed=key[0] * 31 + key[1] * 3 + k)
            pad = np.zeros(int(0.2 * sr), np.float32)
            sig.append((t + 0.2, w)); pieces.append(np.concatenate([pad, np.zeros(len(w), np.float32), pad]))
            t += (2 * len(pad) + len(w)) / sr
            tl_cues.append(dict(scene=key[0], line=key[1], seq=seq, start=round(t - (len(pad) + len(w)) / sr, 3)))

    tl_cues = []
    for r in rows:
        if prev_scene is not None:
            g = GAP_LINE + (GAP_SCENE if r["scene"] != prev_scene else 0)
            pieces.append(np.zeros(int(g * sr), np.float32)); t += g
        put_cue((r["scene"], r["idx"], "before"))
        w, _ = sf.read(d / "tts" / r["file"], dtype="float32")
        tl.append(dict(scene=r["scene"], text=r["text"], start=round(t, 3), end=round(t + len(w) / sr, 3)))
        pieces.append(w); t += len(w) / sr; prev_scene = r["scene"]
        put_cue((r["scene"], r["idx"], "after"))
        if a.limit_s and t > a.limit_s:
            break
    pieces.append(np.zeros(int(TAIL * sr), np.float32))
    voice = np.concatenate(pieces); total = len(voice) / sr
    voice = voice / max(1e-6, np.abs(voice).max()) * 0.8
    for t0, w in sig:
        i = int(t0 * sr); voice[i:i + len(w)] += w[:len(voice) - i]
    if tl_cues:
        print("cues", [(c["scene"], c["line"], c["seq"], c["start"]) for c in tl_cues])
    sf.write(d / "narration.wav", voice, sr)
    json.dump(tl, open(d / "timeline.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # subtitle cues: each spoken line split into one-line chunks, time shared by character count
    cues = []
    for x in tl:
        ch = sub_chunks(x["text"])
        n = [len(c.replace(" ", "")) for c, _ in ch]
        t0 = x["start"]
        for (c, dlg), k in zip(ch, n):
            t1 = t0 + (x["end"] - x["start"]) * k / sum(n)
            cues.append(dict(text=c, dlg=dlg, start=t0, end=t1)); t0 = t1

    # scene spans: from first line start (scene 1 from 0) to next scene's first line start
    order = []
    for x in tl:
        if not order or order[-1]["scene"] != x["scene"]:
            order.append(dict(scene=x["scene"], start=x["start"]))
    order[0]["start"] = 0.0
    for i, o in enumerate(order):
        o["end"] = order[i + 1]["start"] if i + 1 < len(order) else total

    # ---- SRT
    def ts(s):
        return f"{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{int(s % 60):02d},{int(s % 1 * 1000):03d}"
    with open(d / name.replace(".mp4", ".srt"), "w", encoding="utf-8") as f:
        for i, x in enumerate(cues, 1):   # hold 0.25 s after speech, but never past the next cue's start
            end = min(x["end"] + 0.25, cues[i]["start"]) if i < len(cues) else x["end"] + 0.25
            f.write(f"{i}\n{ts(x['start'])} --> {ts(end)}\n{x['text']}\n\n")

    # ---- video frames -> ffmpeg (video only), then mux audio
    srcs = {o["scene"]: cover(Image.open(d / "scenes" / f"s{o['scene']:02d}.png").convert("RGB")) for o in order}
    subs, cur_sub = {}, None
    tmpv = d / "_video.mp4"
    enc = subprocess.Popen([FF, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                            "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(tmpv)],
                           stdin=subprocess.PIPE)
    # motion clips: <dir>/clips/sNN_K.mp4 split the scene span between them (hard cuts inside a scene).
    # A clip is time-stretched to fill its slot up to 2x (slow motion); beyond that it plays at 0.5x and holds its last frame.
    clips = {o["scene"]: sorted((d / "clips").glob(f"s{o['scene']:02d}_*.mp4")) for o in order}
    cache = {}

    def clip_frames(p):
        if p not in cache:
            if len(cache) > 6:
                cache.pop(next(iter(cache)))
            raw = subprocess.run([FF, "-v", "error", "-i", str(p), "-vf", "scale=960:540:force_original_aspect_ratio=increase,crop=960:540",
                                  "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
            n = len(raw) // (960 * 540 * 3)
            cache[p] = [Image.frombuffer("RGB", (960, 540), raw[i * 960 * 540 * 3:(i + 1) * 960 * 540 * 3]) for i in range(n)]
        return cache[p]

    def scene_frame(k, lt):
        o = order[k]; span = o["end"] - o["start"] + XF
        cl = clips.get(o["scene"])
        if not cl:
            return kb_frame(srcs[o["scene"]], min(1, max(0, lt) / span), k)
        seg = span / len(cl)
        i = min(int(max(0, lt) / seg), len(cl) - 1)
        fr = clip_frames(cl[i]); L = len(fr); t = max(0, lt) - i * seg
        idx = int(t / seg * L) if seg <= 2 * L / FPS else int(t * FPS / 2)
        return fr[min(idx, L - 1)].resize((W, H), Image.BILINEAR)

    nf = int(total * FPS)
    for fi in range(nf):
        tt = fi / FPS
        k = next(i for i, o in enumerate(order) if tt < o["end"] or i == len(order) - 1)
        o = order[k]
        frame = scene_frame(k, tt - o["start"])
        if k + 1 < len(order) and tt > o["end"] - XF:   # cross-fade into the next scene
            frame = Image.blend(frame, scene_frame(k + 1, 0.0), (tt - (o["end"] - XF)) / XF)
        # a cue stays up through the short pause after it (until the next cue starts, max +0.25 s)
        line = next((x for x in reversed(cues) if x["start"] <= tt < x["end"] + 0.25), None)
        if line:
            key = (line["text"], line["dlg"])
            if key not in subs:
                subs[key] = subtitle_layer(*key)
            frame = Image.alpha_composite(frame.convert("RGBA"), subs[key]).convert("RGB")
        enc.stdin.write(frame.tobytes())
        if fi % (FPS * 30) == 0:
            print(f"frame {fi}/{nf}", flush=True)
    enc.stdin.close(); enc.wait()

    # ---- scene ambience/SFX bed: sfx/sNN.(flac|wav) looped over the scene span, 1 s fades -> sfx.wav (mixed below)
    sfx_files = {o["scene"]: next(iter(sorted((d / "sfx").glob(f"s{o['scene']:02d}.*"))), None) for o in order} if (d / "sfx").exists() else {}
    foley_dir = d / "sfx" / "foley"
    has_foley = foley_dir.exists() and any(foley_dir.glob("s*_*.wav"))
    has_sfx = any(sfx_files.values()) or has_foley
    if has_sfx:
        SR2 = 44100
        bed = np.zeros((int(total * SR2) + SR2, 2), np.float32)
        for o in order:
            p = sfx_files.get(o["scene"])
            if not p:
                continue
            w, r2 = sf.read(p, dtype="float32", always_2d=True)
            if r2 != SR2:
                w = np.stack([np.interp(np.linspace(0, len(w) - 1, int(len(w) * SR2 / r2)), np.arange(len(w)), w[:, c]) for c in range(w.shape[1])], 1)
            if w.shape[1] == 1:
                w = np.repeat(w, 2, 1)
            a0, a1 = int(o["start"] * SR2), int(min(total, o["end"] + XF) * SR2)
            n = a1 - a0
            seg = np.concatenate([w] * (n // len(w) + 1))[:n]
            f = min(SR2, n // 4)
            env = np.ones(n, np.float32); env[:f] = np.linspace(0, 1, f); env[-f:] = np.linspace(1, 0, f)
            bed[a0:a1] += seg / max(1e-6, np.abs(seg).max()) * 0.7 * env[:, None]
        # event sounds (story_foley.py): sfx/foley/sNN_K.wav belongs to clip K of the scene. The picture plays that clip
        # slowed to fill its slot (same rule as scene_frame), so the sound is time-stretched by the same rate (pitch kept)
        # and starts with the clip. Peak 0.5 = about 3 dB under the ambience bed.
        if has_foley:
            import librosa
            placed = []
            for o in order:
                cl = clips.get(o["scene"]) or []
                if not cl:
                    continue
                span = o["end"] - o["start"] + XF; segd = span / len(cl)
                for i, c in enumerate(cl):
                    fp = foley_dir / f"{c.stem}.wav"
                    if not fp.exists():
                        continue
                    L = len(clip_frames(c))
                    rate = L / (segd * FPS) if segd <= 2 * L / FPS else 0.5     # playback speed of the picture
                    y, r0 = librosa.load(fp, sr=SR2, mono=True)
                    y = y[:int(L / FPS * SR2)]                                   # only the frames that are shown
                    if abs(rate - 1) > 0.02:
                        y = librosa.effects.time_stretch(y, rate=rate)
                    y = y / max(1e-6, np.abs(y).max()) * 0.5
                    f = min(len(y) // 6, int(0.15 * SR2))
                    if f:
                        y[:f] *= np.linspace(0, 1, f); y[-f:] *= np.linspace(1, 0, f)
                    a0 = int((o["start"] + i * segd) * SR2)
                    n = min(len(y), len(bed) - a0)
                    bed[a0:a0 + n] += y[:n, None]
                    placed.append(f"{c.stem}@{o['start'] + i * segd:.1f}s x{rate:.2f}")
            print("foley", placed)
        sf.write(d / "sfx.wav", bed, SR2)

    # ---- audio: narration + BGM (looped, ducked under the voice) + SFX bed, master to about -14 LUFS
    out = d / name
    sfx_in = ["-i", str(d / "sfx.wav")] if has_sfx else []
    if a.bgm:
        ins = []
        for b in a.bgm:
            ins += ["-i", b]
        nb = len(a.bgm)
        cat = "".join(f"[{i + 2}:a]" for i in range(nb)) + f"concat=n={nb}:v=0:a=1,aloop=loop=-1:size=2e9,atrim=0:{total:.2f},"
        if has_sfx:   # input index after BGMs; SFX ~ -6 dB under the BGM level before ducking
            sx = nb + 2
            fc = (f"[1:a]asplit=2[v1][v2];{cat}volume={a.bgm_db}dB,afade=t=in:d=2,afade=t=out:st={total - 3:.2f}:d=3[m0];"
                  f"[{sx}:a]volume={a.bgm_db + 2}dB[sx];[m0][sx]amix=inputs=2:normalize=0[m];"
                  f"[m][v1]sidechaincompress=threshold=0.03:ratio=4:attack=30:release=600[md];"
                  f"[v2][md]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
        else:
            fc = (f"[1:a]asplit=2[v1][v2];{cat}volume={a.bgm_db}dB,afade=t=in:d=2,afade=t=out:st={total - 3:.2f}:d=3[m];"
                  f"[m][v1]sidechaincompress=threshold=0.03:ratio=6:attack=30:release=600[md];"
                  f"[v2][md]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
        cmd = [FF, "-v", "error", "-y", "-i", str(tmpv), "-i", str(d / "narration.wav"), *ins, *sfx_in, "-filter_complex", fc,
               "-map", "0:v", "-map", "[a]"]
    else:
        cmd = [FF, "-v", "error", "-y", "-i", str(tmpv), "-i", str(d / "narration.wav"), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
               "-map", "0:v", "-map", "1:a"]
    subprocess.run(cmd + ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(out)],
                   check=True)
    tmpv.unlink()
    print(f"wrote {out} ({total / 60:.1f} min, {len(order)} scenes, {len(tl)} lines)")


if __name__ == "__main__":
    main()
