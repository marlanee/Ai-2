"""Objective quality metrics for generated lofi tracks (no listening model available).

  python scripts/music_metrics.py a.flac b.flac ... [--json out.json] [--ffmpeg C:/AI/tools/ffmpeg/bin/ffmpeg.exe]

Per track:
  clip        fraction of samples at full scale (>= 0.999)
  key_clar    correlation of the average chroma with the best of 24 Krumhansl-Kessler key profiles (higher = clearly tonal)
  win_clar    mean key clarity over 8 s windows (local harmonic clarity; dissonant/smeared passages score low)
  key_drift   fraction of 8 s windows whose best key differs from the global key (and is not its relative key)
  chroma_ent  mean per-frame chroma entropy, bits (higher = more pitch classes at once = muddier/dissonant)
  beat        strength of the strongest onset-autocorrelation peak in 60-110 BPM (higher = steadier groove)
  bpm         tempo at that peak
  lo/mid/hi   energy share below 200 Hz, 200-2000 Hz, above 2000 Hz
  score       combined ranking score (see rank())
"""
import argparse, json, subprocess, sys
import numpy as np

SR = 22050
MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def load(path, ffmpeg):
    raw = subprocess.run([ffmpeg, "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def stft_mag(x, n=4096, hop=2048):
    win = np.hanning(n).astype(np.float32)
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[::hop] * win
    return np.abs(np.fft.rfft(frames, axis=1)), np.fft.rfftfreq(n, 1 / SR)


def chroma(mag, freqs):
    sel = (freqs >= 55) & (freqs <= 5000)
    pc = (np.round(12 * np.log2(freqs[sel] / 440.0)) + 9) % 12          # A=9
    C = np.zeros((mag.shape[0], 12))
    for k in range(12):
        C[:, k] = mag[:, sel][:, pc == k].sum(1)
    return C


def key_fit(v):
    """Best (corr, key index 0-23) of a 12-dim chroma vector against all major/minor profiles."""
    best = (-2, 0)
    for i in range(12):
        for j, prof in enumerate((MAJ, MIN)):
            c = np.corrcoef(v, np.roll(prof, i))[0, 1]
            if c > best[0]:
                best = (c, i + 12 * j)
    return best


def related(a, b):
    """Same key, or relative major/minor."""
    if a == b:
        return True
    ma, mb = a % 12, b % 12
    if a < 12 <= b:
        return (ma + 9) % 12 == mb
    if b < 12 <= a:
        return (mb + 9) % 12 == ma
    return False


def analyze(path, ffmpeg):
    x = load(path, ffmpeg)
    mag, freqs = stft_mag(x)
    C = chroma(mag, freqs)
    g_corr, g_key = key_fit(C.mean(0))
    fps = SR / 2048
    w = int(8 * fps)
    wins = [key_fit(C[i:i + w].mean(0)) for i in range(0, len(C) - w + 1, max(1, w // 2))]
    win_clar = float(np.mean([c for c, _ in wins]))
    drift = float(np.mean([not related(k, g_key) for _, k in wins]))
    P = C / (C.sum(1, keepdims=True) + 1e-9)
    ent = float(np.mean(-(P * np.log2(P + 1e-12)).sum(1)))
    # onset envelope from a finer STFT, autocorrelation in 60-110 BPM
    m2, f2 = stft_mag(x, 1024, 256)
    flux = np.maximum(np.diff(np.log1p(m2), axis=0), 0).sum(1)
    flux = (flux - flux.mean()) / (flux.std() + 1e-9)
    ac = np.correlate(flux, flux, "full")[len(flux) - 1:]
    ac /= ac[0]
    ofps = SR / 256
    lags = np.arange(len(ac))
    bpm = 60 * ofps / np.maximum(lags, 1)
    band = (bpm >= 60) & (bpm <= 110)
    i = np.argmax(np.where(band, ac, -1))
    e = (mag ** 2).sum(0)
    tot = e.sum() + 1e-9
    return {
        "file": path,
        "clip": float(np.mean(np.abs(x) >= 0.999)),
        "key": NAMES[g_key % 12] + ("m" if g_key >= 12 else ""),
        "key_clar": float(g_corr), "win_clar": win_clar, "key_drift": drift, "chroma_ent": ent,
        "beat": float(ac[i]), "bpm": float(bpm[i]),
        "lo": float(e[freqs < 200].sum() / tot), "mid": float(e[(freqs >= 200) & (freqs < 2000)].sum() / tot),
        "hi": float(e[freqs >= 2000].sum() / tot),
    }


def rank(r):
    # harmonic clarity matters most for the user's complaint (dissonance); groove second; penalties for drift/clipping
    return 2.0 * r["win_clar"] + 1.0 * r["key_clar"] - 1.0 * r["key_drift"] - 0.25 * r["chroma_ent"] \
        + 0.5 * r["beat"] - 20 * r["clip"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", default=None)
    ap.add_argument("--ffmpeg", default=r"C:\AI\tools\ffmpeg\bin\ffmpeg.exe")
    a = ap.parse_args()
    rows = []
    for f in a.files:
        r = analyze(f, a.ffmpeg); r["score"] = rank(r); rows.append(r)
    rows.sort(key=lambda r: -r["score"])
    print(f"{'score':>6} {'key':>4} {'clar':>5} {'win':>5} {'drift':>5} {'ent':>5} {'beat':>5} {'bpm':>5} {'clip':>6} {'lo/mid/hi':>14}  file")
    for r in rows:
        print(f"{r['score']:6.2f} {r['key']:>4} {r['key_clar']:5.2f} {r['win_clar']:5.2f} {r['key_drift']:5.2f} "
              f"{r['chroma_ent']:5.2f} {r['beat']:5.2f} {r['bpm']:5.1f} {r['clip']:6.4f} "
              f"{r['lo']:.2f}/{r['mid']:.2f}/{r['hi']:.2f}  {r['file']}")
    if a.json:
        json.dump(rows, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
