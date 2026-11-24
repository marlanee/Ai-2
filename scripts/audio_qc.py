"""Audio QC helpers agreed in the GPT workflow review (test_output/strategy/workflow_round1/2.md).

- measure(path)                      -> list of (t, M, S) from ebur128 (100 ms hop, M = 400 ms, S = 3 s)
- integrated(path)                   -> (I LUFS, true peak dBTP)
- eval_transition(prev, nxt, d, c)   -> deviation of the crossfade from the equal-power baseline of the two sources
- choose_transition(prev, nxt, D)    -> pick curve/length among (D tri, D qsin, short qsin) by the agreed rule
- listen_pack(...)                   -> MP3s + index for morning human listening
"""
import math, re, subprocess, tempfile, pathlib

FF = r"C:\AI\tools\ffmpeg\bin\ffmpeg.exe"
FP = r"C:\AI\tools\ffmpeg\bin\ffprobe.exe"
RX = re.compile(r"t:\s*([\d.]+)\s+TARGET:.*?M:\s*(-?[\d.]+)\s+S:\s*(-?[\d.]+)")


def dur(p):
    return float(subprocess.run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout.strip())


def measure(path, extra=()):
    r = subprocess.run([FF, "-hide_banner", "-nostats", *extra, "-i", str(path), "-vn", "-af", "ebur128=framelog=info",
                        "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="ignore")
    v = [(float(a), float(b), float(c)) for a, b, c in RX.findall(r.stderr)]
    if len(v) < 5:
        raise RuntimeError(f"ebur128 log not parsed for {path}")
    return v


def integrated(path):
    r = subprocess.run([FF, "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    I = float(re.findall(r"I:\s*(-?[\d.]+) LUFS", r.stderr)[-1])
    tp = float(re.findall(r"Peak:\s*(-?[\d.]+) dBFS", r.stderr)[-1])
    return I, tp


def _p(lufs):
    return 10 ** (lufs / 10)


def _db(p):
    return 10 * math.log10(max(p, 1e-12))


def eval_transition(prev, nxt, d, curve, pad=4.0, tmpdir=None):
    """Render tail(prev)+head(nxt) with acrossfade(d, curve); compare momentary loudness inside the overlap with the
    power-interpolated baseline of the two sources. Returns dict(p95, run, before, after, warn)."""
    tmpdir = pathlib.Path(tmpdir or tempfile.mkdtemp(prefix="xf_"))
    L = dur(prev)
    tail = tmpdir / "tail.wav"; head = tmpdir / "head.wav"; mix = tmpdir / f"mix_{curve}_{d}.wav"
    subprocess.run([FF, "-v", "error", "-y", "-ss", f"{L - d - pad:.3f}", "-i", str(prev), "-ac", "2", "-ar", "48000", str(tail)], check=True)
    subprocess.run([FF, "-v", "error", "-y", "-t", f"{d + pad + 4:.3f}", "-i", str(nxt), "-ac", "2", "-ar", "48000", str(head)], check=True)
    subprocess.run([FF, "-v", "error", "-y", "-i", str(tail), "-i", str(head), "-filter_complex",
                    f"[0:a][1:a]acrossfade=d={d}:c1={curve}:c2={curve}", str(mix)], check=True)
    mt, mh, mm = measure(tail), measure(head), measure(mix)
    Mt = {round(t, 1): M for t, M, _ in mt}; Mh = {round(t, 1): M for t, M, _ in mh}
    devs = []
    for t, M, _ in mm:
        if pad + 0.4 <= t <= pad + d:
            u = (t - 0.2 - pad) / d
            a = Mt.get(round(t, 1)); b = Mh.get(round(t - pad, 1))
            if a is None or b is None or M < -70:
                continue
            ref = _db((1 - u) * _p(a) + u * _p(b))  # source loudness weighted by fade progress
            devs.append(M - ref)
    p95 = sorted(abs(x) for x in devs)[int(0.95 * (len(devs) - 1))] if devs else 0.0
    run = best = 0
    for x in devs:
        run = run + 1 if abs(x) > 2.5 else 0; best = max(best, run)
    S = {round(t, 1): s for t, _, s in mm}
    before = [S[k] for k in S if pad - 0.05 <= k <= pad + 0.05]
    after = [S[k] for k in S if pad + d + 3 - 0.05 <= k <= pad + d + 4]
    jump = abs((sum(after) / len(after)) - (sum(before) / len(before))) if before and after else 0.0
    # warn = the crossfade itself misbehaves (dip/bump vs baseline). The before/after jump is a property of the two
    # sources (quiet intro vs loud outro, measured identical for every curve) -> reported for listening, not used to pick.
    warn = best * 0.1 >= 0.6
    return {"d": d, "curve": curve, "p95": round(p95, 2), "run_s": round(best * 0.1, 1), "jump": round(jump, 1), "warn": warn,
            "listen": warn or jump >= 3}


def choose_transition(prev, nxt, D, short):
    """Agreed rule: start from (D, tri). Prefer (D, qsin) if it has no warning and its P95 is >= 0.5 LU lower.
    If tri warns, take the lowest-P95 non-warning candidate. Otherwise keep tri (flag if it still warns)."""
    tmp = tempfile.mkdtemp(prefix="xf_")
    cands = [eval_transition(prev, nxt, D, "tri", tmpdir=tmp), eval_transition(prev, nxt, D, "qsin", tmpdir=tmp),
             eval_transition(prev, nxt, short, "qsin", tmpdir=tmp)]
    tri, qs, sh = cands
    pick = tri
    if not qs["warn"] and qs["p95"] <= tri["p95"] - 0.5:
        pick = qs
    if tri["warn"]:
        # keep the musical length when possible: same-length qsin first, short fade only as a last resort
        pick = qs if not qs["warn"] else (sh if not sh["warn"] else min(cands, key=lambda c: c["p95"]))
    return pick, cands


def listen_pack(tracks, final_video, flagged, out_dir, first_full=True):
    """tracks: list of prepped files in order; flagged: list of (start_s, xfade_s, label). Writes 2 MP3 + index.txt."""
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    gap = "anullsrc=r=48000:cl=stereo,atrim=0:0.7"
    idx = ["# 청취 팩 (미검수) — 곡 샘플: 첫 12초 + 중앙 10초 + 끝 8초, 구분 0.7초 무음", ""]
    parts, t = [], 0.0
    for i, p in enumerate(tracks):
        L = dur(p)
        segs = [(0, L)] if (i == 0 and first_full) else [(0, 12), (L / 2 - 5, 10), (L - 8, 8)]
        for s, ln in segs:
            parts.append((p, s, ln)); idx.append(f"{t / 60:5.1f}분  곡 {i + 1:02d} {pathlib.Path(p).stem}  @{s:.0f}s"); t += ln + 0.7
    _concat(parts, out / "listen_tracks.mp3")
    idx += ["", "# 의심 전환 (겹침 앞뒤 4초)", ""]
    parts, t = [], 0.0
    for s, xf, label in flagged:
        parts.append((final_video, max(0, s - 4), xf + 8)); idx.append(f"{t / 60:5.1f}분  {label}"); t += xf + 8.7
    if parts:
        _concat(parts, out / "listen_transitions.mp3")
    (out / "index.txt").write_text("\n".join(idx) + "\n", encoding="utf-8")


def _concat(parts, dst):
    """Cut each part to a temp WAV (one ffmpeg call per part -> no Windows command-line limit), then concat demuxer."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="lp_"))
    sil = tmp / "gap.wav"
    subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "0.7", str(sil)], check=True)
    lst = []
    for k, (p, s, ln) in enumerate(parts):
        w = tmp / f"p{k:04d}.wav"
        subprocess.run([FF, "-v", "error", "-y", "-ss", f"{s:.2f}", "-t", f"{ln:.2f}", "-i", str(p), "-vn", "-ac", "2",
                        "-ar", "48000", str(w)], check=True)
        lst += [f"file '{w.as_posix()}'", f"file '{sil.as_posix()}'"]
    (tmp / "list.txt").write_text("\n".join(lst) + "\n", encoding="utf-8")
    subprocess.run([FF, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"), "-c:a", "libmp3lame",
                    "-b:a", "160k", str(dst)], check=True)
