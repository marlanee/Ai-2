"""Long-form video builder with an edit table (agreed with GPT strategy review, 2026-11-25).

  python scripts/build_long.py --clip loop.mp4 --pools poolA poolB --duration 7200 --out out.mp4 \
      [--title ...] [--ambience rain.flac] [--exclude f.flac ...] [--seam 1.0] [--no-lead-first d] [--lead-free-min 10]

Rules
- style tag = prompt variant in file name (_pa_, _pb_, _pc_, _pd_ ...). Tracks < 60 s skipped.
- order: style blocks of 2-3 tracks, models interleaved; no 'lead' style (default d = saxophone) before --lead-free-min.
- per track: mastering preset (warm) + loudness normalize to -16 LUFS (single pass) -> cached.
- transitions: 8 s if same style, 5 s if style changes.
- edit table (JSON) is the single source for the mix, tracklist timestamps and chapters.
- after render: short-term loudness around every transition; |diff| >= 2 LU flagged for listening.
"""
import argparse, json, math, pathlib, random, re, statistics, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
FF = r"C:\AI\tools\ffmpeg\bin\ffmpeg.exe"
FP = r"C:\AI\tools\ffmpeg\bin\ffprobe.exe"
STYLE_NAMES = {"a": "재즈 코드의 밤", "b": "빗속의 기타", "c": "조용한 건반", "d": "늦은 밤 색소폰"}
STYLE_TRACK = {"a": "Jazz Chords", "b": "Rain Guitar", "c": "Quiet Keys", "d": "Late Sax"}


def dur(p):
    return float(subprocess.run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout.strip())


def style(p):
    m = re.search(r"_p([a-z])_", p.name)
    return m.group(1) if m else "x"


def ts(t):
    t = int(round(t)); h, m, s = t // 3600, t % 3600 // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def body_loudness(path):
    """Median short-term loudness of the track body (first/last 15 s excluded)."""
    import statistics
    r = subprocess.run([FF, "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=framelog=info", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    v = [(float(m.group(1)), float(m.group(2))) for m in re.finditer(r"t:\s*([\d.]+).*?S:\s*(-?[\d.]+)", r.stderr)]
    end = v[-1][0] if v else 0
    body = [s for t, s in v if 15 <= t <= end - 15 and s > -70] or [s for t, s in v if s > -70]
    return statistics.median(body)


def prep(src, cache, target=-16.0):
    """warm mastering -> gain so the BODY sits at `target` LUFS short-term -> true-peak safe limiter."""
    o = cache / (src.stem + ".flac")
    if not o.exists():
        tmp = cache / (src.stem + ".m.flac")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "master_lofi.py"), str(src), str(tmp), "--preset", "warm"],
                       check=True, capture_output=True)
        g = target - body_loudness(tmp)
        subprocess.run([FF, "-v", "error", "-y", "-i", str(tmp), "-af", f"volume={g:.2f}dB,alimiter=limit=0.79:attack=5:release=80:level=false:latency=true",
                        "-ar", "48000", str(o)], check=True)
        tmp.unlink()
    return o


def order(tracks, lens, duration, lead, lead_free, seed):
    rnd = random.Random(seed)
    by = {}
    for t in tracks:
        by.setdefault(style(t), []).append(t)
    for v in by.values():
        rnd.shuffle(v)
        v.sort(key=lambda t: "mm3" in t.name)          # SA3 and MiniMax alternate inside a block below
    seq, total, last = [], 0.0, None
    styles = sorted(by)
    while total < duration + 30 and any(by.values()):
        cands = [s for s in styles if by[s] and s != last and not (s == lead and total < lead_free)]
        if not cands:
            cands = [s for s in styles if by[s] and not (s == lead and total < lead_free)] or [s for s in styles if by[s]]
        s = rnd.choice(cands)
        for _ in range(rnd.choice([2, 3])):
            if not by[s] or total >= duration + 30:
                break
            # alternate model inside the block when possible
            pick = next((t for t in by[s] if seq and ("mm3" in t.name) != ("mm3" in seq[-1].name)), by[s][0])
            by[s].remove(pick)
            xf = 0 if not seq else (8.0 if style(seq[-1]) == s else 5.0)
            seq.append(pick); total += lens[pick] - xf
        last = s
    return seq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", required=True); ap.add_argument("--pools", nargs="+", required=True)
    ap.add_argument("--duration", type=float, required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="비 오는 80년대 서울, 레코드 가게 | 공부·작업용 시티팝 로파이 2시간")
    ap.add_argument("--ambience"); ap.add_argument("--ambience-db", type=float, default=-4)
    ap.add_argument("--exclude", nargs="*", default=[]); ap.add_argument("--seam", type=float, default=1.0)
    ap.add_argument("--lead", default="d"); ap.add_argument("--lead-free-min", type=float, default=10)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--target", type=float, default=-14.0, help="final integrated loudness (LUFS) via fixed gain")
    ap.add_argument("--amb-rel", type=float, default=-18.0, help="ambience body relative to music body (LU)")
    ap.add_argument("--fast", action="store_true", help="skip per-transition evaluation (tri everywhere)")
    ap.add_argument("--listen-pack", action="store_true", help="write MP3 listening pack + index")
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    tracks = [p for d in a.pools for p in sorted(pathlib.Path(d).glob("*.flac")) if p.name not in a.exclude]
    lens = {p: dur(p) for p in tracks}
    tracks = [p for p in tracks if lens[p] >= 60]
    seq = order(tracks, lens, a.duration, a.lead, a.lead_free_min * 60, a.seed)
    cache = out.parent / "_prep_warm_body16_v2"; cache.mkdir(exist_ok=True)
    prepped = [prep(t, cache) for t in seq]
    plens = [dur(p) for p in prepped]
    # --- transitions: agreed rule (audio_qc.choose_transition): D tri / D qsin / short qsin per transition
    import audio_qc as qc
    xfs, curves, tq = [], [], []
    xcache_path = cache / "_xfade_choices.json"
    xcache = json.loads(xcache_path.read_text(encoding="utf-8")) if xcache_path.exists() else {}
    for i in range(1, len(seq)):
        D, sh = (8.0, 4.0) if style(seq[i]) == style(seq[i - 1]) else (5.0, 2.0)
        if a.fast:
            pick = {"d": D, "curve": "tri", "p95": None, "listen": False}
        else:
            key = f"{prepped[i - 1].name}|{prepped[i].name}|{D}|{sh}"
            if key not in xcache:
                xcache[key], _ = qc.choose_transition(prepped[i - 1], prepped[i], D, sh)
                xcache_path.write_text(json.dumps(xcache), encoding="utf-8")
            pick = xcache[key]
        xfs.append(pick["d"]); curves.append(pick["curve"]); tq.append(pick)
    starts, t0 = [0.0], 0.0
    for i in range(1, len(seq)):
        t0 += plens[i - 1] - xfs[i - 1]; starts.append(t0)
    keep = [i for i, s in enumerate(starts) if s < a.duration - 5]
    seq, prepped, plens, starts = [seq[i] for i in keep], [prepped[i] for i in keep], [plens[i] for i in keep], [starts[i] for i in keep]
    xfs, curves, tq = xfs[:len(seq) - 1], curves[:len(seq) - 1], tq[:len(seq) - 1]
    music_len = starts[-1] + plens[-1]
    if music_len < a.duration:
        sys.exit(f"music {music_len:.0f}s < duration")
    table = {"title": a.title, "duration": a.duration, "tracks": [
        {"n": i + 1, "file": str(seq[i]), "prepped": str(prepped[i]), "style": style(seq[i]), "start": round(starts[i], 2),
         "len": round(plens[i], 2), "xfade_in": (xfs[i - 1] if i else 0), "curve_in": (curves[i - 1] if i else None),
         "xfade_qc": (tq[i - 1] if i else None)} for i in range(len(seq))]}
    (out.with_suffix(".edit.json")).write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(seq)} tracks, music {music_len:.0f}s, curves {curves.count('qsin')} qsin / {curves.count('tri')} tri, "
          f"first lead-style at {next((ts(s) for s, t in zip(starts, seq) if style(t) == a.lead), 'none')}", flush=True)

    # --- ambience level relative to the music body (tracks are prepped to body -16 LUFS short-term)
    amb_db = a.ambience_db
    if a.ambience and a.amb_rel is not None:
        amb_s = statistics.median([s for _, _, s in qc.measure(a.ambience) if s > -70])
        amb_db = round((-16.0 + a.amb_rel) - amb_s, 2)
        print(f"ambience body {amb_s:.1f} LUFS -> gain {amb_db:+.1f} dB (music body -16, rel {a.amb_rel})", flush=True)

    def compose(extra, gain):
        cmd = [sys.executable, str(ROOT / "scripts" / "compose.py"), "--clip", a.clip, "--music", *map(str, prepped), "--natural",
               "--xfades", ",".join(str(x) for x in xfs), "--curves", ",".join(curves), "--duration", str(a.duration),
               "--seam", str(a.seam), "--xfade", "8", "--size", "1920x1080", "--ffmpeg", FF.replace("\\", "/"), "--static-gain", f"{gain:.2f}"]
        if a.ambience:
            cmd += ["--ambience", a.ambience, "--ambience-db", str(amb_db)]
        if a.duration > 600:
            cmd.append("--copy-video")
        subprocess.run(cmd + extra, check=True, capture_output=True)

    # --- 2-pass static-gain master (no time-varying loudnorm): measure the unity mix, one fixed gain, verify AAC
    wav = out.with_suffix(".pass1.wav")
    compose(["--out", str(out), "--audio-wav", str(wav)], 0.0)
    I0, tp0 = qc.integrated(wav); wav.unlink()
    g = a.target - I0
    # limiter ceiling -2.2 dBFS (sample) leaves room for AAC overshoot; retry once with less gain if TP still > -1.0
    for attempt in range(2):
        compose(["--out", str(out)], g)
        I1, tp1 = qc.integrated(out)
        print(f"master pass {attempt + 1}: gain {g:+.2f} dB -> {I1:.1f} LUFS, {tp1:.1f} dBTP", flush=True)
        if tp1 <= -1.0 or attempt == 1:
            break
        g -= (tp1 + 1.0) + 0.2
    flags = [(s, xf, f"{ts(s)} 전환 ({c}, {xf:g}s, 앞뒤 음량차 {q.get('jump', '?')} LU)")
             for s, xf, c, q in zip(starts[1:], xfs, curves, tq) if q.get("listen")]
    if a.listen_pack:
        qc.listen_pack(prepped, out, flags, out.parent / (out.stem + "_listen"))
    # chapters: style blocks merged to ~5-6 chapters
    target = max(5, min(6, int(a.duration // 1200)))
    step = a.duration / target
    chapters, nxt = [], 0.0
    for i, s in enumerate(starts):
        name = STYLE_NAMES.get(style(seq[i]), "비 오는 밤")
        if s >= nxt and (not chapters or chapters[-1][1] != name):
            chapters.append((s if chapters else 0.0, name))
            nxt = s + step * 0.9
    mm = any("mm3" in str(t) for t in seq)
    music = "Stable Audio 3.0 (Powered by Stability AI)" + (", MiniMax-Music3" if mm else "")
    lines = [f"# {a.title}", "", "## 설명", "",
             "비 내리는 80년대 서울 골목, 레코드 가게와 다방 간판 불빛 아래에서 듣는 시티팝 로파이.",
             "공부·작업·휴식할 때 틀어 두세요. 🌧️☕", "", "## 챕터"] + [f"{ts(s)} {n}" for s, n in chapters] + \
            ["", "🎵 Tracklist"] + [f"{ts(s)} {STYLE_TRACK.get(style(t), 'Track')} {i + 1:02d}" for i, (s, t) in enumerate(zip(starts, seq))] + \
            ["", "—", "이 영상의 음악·영상·그림은 AI 도구로 생성한 뒤 곡 선별·편성·전환·환경음 믹스를 직접 편집했습니다.",
             f"Music: {music} · Video: LTX-2.5 (Lightricks) · Image: Qwen-Image-2512, Qwen-Image-Edit-2511",
             "", "## 업로드 체크", "", "- Studio 'AI 사용(변경되거나 합성된 콘텐츠)' 표시: 예",
             "- Stability AI Community License(연매출 100만 달러 미만), LTX-2 Community License(1,000만 달러 미만)"] + \
            (["- MiniMax-Music3 Community License: 'MiniMax-Music3' 크레딧 표기(위 설명란)"] if mm else []) + \
            ["", "## 자동 검수", "", f"- 곡 수 {len(seq)}, 첫 색소폰 곡 {next((ts(s) for s, t in zip(starts, seq) if style(t) == a.lead), '없음')}",
             f"- 크로스페이드: qsin {curves.count('qsin')} / tri {curves.count('tri')} (겹침 내부 편차 기준 자동 선택)",
             f"- 최종 음량 {I1:.1f} LUFS / {tp1:.1f} dBTP (고정 게인 {g:+.1f} dB, 2-pass)",
             f"- 청취 권장 전환 {len(flags)}건: " + ", ".join(ts(s) for s, _, _ in flags[:25])]
    out.with_suffix(".youtube.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}; listen-flagged transitions: {len(flags)}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
