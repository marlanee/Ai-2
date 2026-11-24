"""One command: loop clip + music pool -> upload-ready video + YouTube text.

  python scripts/make_video.py --clip loop.mp4 --duration 7200 --out test_output/release/long_2h.mp4 \
      [--pool C:/AI/ComfyUI/ComfyUI/output/pool] [--first a.flac b.flac] [--ambience rain.flac] [--title "..."]

- Needs ceil(duration / (track_len - xfade)) tracks. Uses --first tracks in order, then pool tracks (sorted), and
  generates missing ones with Stable Audio 3.0 (headroom workflow, new seeds) through ComfyUI.
- Each track is used for an equal slice (compose.py), so the tracklist timestamps are exact.
- Videos longer than 10 min use compose.py --copy-video (loop unit stream-copied: minutes, not an hour).
- Writes <out>.youtube.md: title, description with timestamps, credits/licence notes, tags.
"""
import argparse, json, math, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMFY_OUT = pathlib.Path(r"C:\AI\ComfyUI\ComfyUI\output")
FF = r"C:/AI/tools/ffmpeg/bin/ffmpeg.exe"
PROMPT = "80s Korean city pop lofi, instrumental, Rhodes piano, warm tape saturation, mellow bass, soft drums, 75 BPM"


def dur(p):
    out = subprocess.run([FF.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error", "-show_entries", "format=duration",
                          "-of", "json", str(p)], capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def gen_track(seed, prompt, seconds=120):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_workflow.py"),
                        str(ROOT / "workflows" / "music_stableaudio3_medium_headroom_api.json"),
                        "--set", f"52:31.value={prompt}", "--set", "52:35.value=false", "--set", f"52:36.value={seconds}",
                        "--set", f"52:3.seed={seed}", "--set", f"57.filename_prefix=pool/sa3h_s{seed}",
                        "--label", f"pool_sa3h_s{seed}", "--timeout", "600"], capture_output=True, text=True)
    res = json.loads(r.stdout[r.stdout.index("{"):])
    if res.get("status") != "success":
        raise RuntimeError(f"seed {seed}: {res.get('error')}")
    return COMFY_OUT / res["outputs"][0]


def ts(t):
    t = int(round(t)); h, m, s = t // 3600, t % 3600 // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", required=True)
    ap.add_argument("--duration", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pool", default=str(COMFY_OUT / "pool"))
    ap.add_argument("--first", nargs="*", default=[], help="tracks to use first, in order")
    ap.add_argument("--exclude", nargs="*", default=[], help="pool file names to skip")
    ap.add_argument("--ambience", default=None)
    ap.add_argument("--ambience-db", type=float, default=-4)
    ap.add_argument("--xfade", type=float, default=8)
    ap.add_argument("--seam", type=float, default=0.5, help="loop-seam crossfade seconds")
    ap.add_argument("--seed-start", type=int, default=1000)
    ap.add_argument("--prompt", default=PROMPT)
    ap.add_argument("--title", default="비 오는 밤, 80년대 서울 골목 다방에서 | Korean City Pop Lofi")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mix", nargs="*", default=None, help="pool folders to interleave, tracks at natural length")
    ap.add_argument("--min-len", type=float, default=60, help="skip pool tracks shorter than this (mix mode)")
    ap.add_argument("--master", default=None, choices=["warm", "tape", "clean"], help="master each track first")
    a = ap.parse_args()

    tracks = [pathlib.Path(p) for p in a.first]
    if a.mix:
        # natural-length mode: interleave several pools (e.g. SA3 + MiniMax), each track at full length
        pools = [sorted(p for p in pathlib.Path(d).glob("*.flac") if p.name not in a.exclude) for d in a.mix]
        lens = {}
        for pl in pools:
            for p in pl:
                lens[p] = dur(p)
        pools = [[p for p in pl if lens[p] >= a.min_len] for pl in pools]
        seq, i = list(tracks), 0
        for t in seq:
            lens.setdefault(t, dur(t))
        total = sum(lens[t] for t in seq) - a.xfade * max(0, len(seq) - 1)
        while total < a.duration + 2 and any(pools):
            pl = pools[i % len(pools)]; i += 1
            if not pl:
                continue
            t = pl.pop(0)
            if t in seq:
                continue
            seq.append(t); total += lens[t] - a.xfade
        if total < a.duration:
            sys.exit(f"pools too short: {total:.0f}s < {a.duration}s")
        print(f"{len(seq)} tracks (natural length), music {total:.0f}s")
        if a.dry_run:
            return
        if a.master:
            mdir = pathlib.Path(a.out).parent / f"_master_{a.master}"; mdir.mkdir(parents=True, exist_ok=True)
            mastered = []
            for t in seq:
                o = mdir / (pathlib.Path(t).stem + ".flac")
                if not o.exists():
                    subprocess.run([sys.executable, str(ROOT / "scripts" / "master_lofi.py"), str(t), str(o),
                                    "--preset", a.master], check=True, capture_output=True)
                mastered.append(o)
            play = mastered
        else:
            play = seq
        out = pathlib.Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, str(ROOT / "scripts" / "compose.py"), "--clip", a.clip, "--music", *map(str, play),
               "--natural", "--duration", str(a.duration), "--seam", str(a.seam), "--xfade", str(a.xfade),
               "--size", "1920x1080", "--out", str(out), "--ffmpeg", FF]
        if a.ambience:
            cmd += ["--ambience", a.ambience, "--ambience-db", str(a.ambience_db)]
        if a.duration > 600:
            cmd.append("--copy-video")
        subprocess.run(cmd, check=True)
        starts, t0 = [], 0.0
        for t in seq:
            if t0 >= a.duration - 5:
                break
            starts.append((t0, t)); t0 += lens[t] - a.xfade
        write_md(a, out, starts)
        return
    pool = sorted(p for p in pathlib.Path(a.pool).glob("*.flac") if p.name not in a.exclude)
    tracks += [p for p in pool if p.resolve() not in {t.resolve() for t in tracks}]
    tlen = 120.0
    need = max(1, math.ceil((a.duration - a.xfade) / (tlen - a.xfade)))
    seed = a.seed_start
    while len(tracks) < need:
        if a.dry_run:
            print(f"would generate seed {seed}"); tracks.append(pathlib.Path(f"<gen s{seed}>")); seed += 1; continue
        print(f"generating track {len(tracks) + 1}/{need} (seed {seed})", flush=True)
        tracks.append(gen_track(seed, a.prompt)); seed += 1
    tracks = tracks[:need]
    n = len(tracks)
    seg = (a.duration + a.xfade * (n - 1)) / n
    if seg > tlen + 0.5 and not a.dry_run:
        sys.exit(f"slice {seg:.1f}s longer than tracks ({tlen}s): add tracks")
    print(f"{n} tracks, slice {seg:.1f}s, xfade {a.xfade}s")
    if a.dry_run:
        return
    out = pathlib.Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(ROOT / "scripts" / "compose.py"), "--clip", a.clip, "--music", *map(str, tracks),
           "--duration", str(a.duration), "--seam", str(a.seam), "--xfade", str(a.xfade), "--size", "1920x1080",
           "--out", str(out), "--ffmpeg", FF]
    if a.ambience:
        cmd += ["--ambience", a.ambience, "--ambience-db", str(a.ambience_db)]
    if a.duration > 600:
        cmd.append("--copy-video")
    subprocess.run(cmd, check=True)
    write_md(a, out, [(i * (seg - a.xfade), t) for i, t in enumerate(tracks)])


def write_md(a, out, starts):
    mm = any("mm3" in str(t) for _, t in starts)
    lines = [f"# {a.title}", "", "## 설명", "",
             "비 내리는 80년대 서울 골목, 레코드 가게와 다방 간판 불빛 아래에서 듣는 시티팝 로파이.",
             "공부·작업·휴식할 때 틀어 두세요. 🌧️☕", "", "🎵 Tracklist"]
    for i, (s, _) in enumerate(starts):
        lines.append(f"{ts(s)} Track {i + 1:02d}")
    music = "Stable Audio 3.0 (Powered by Stability AI)" + (", MiniMax-Music3" if mm else "")
    lines += ["", "—", "이 영상의 음악·영상·그림은 AI 도구로 제작했습니다.",
              f"Music: {music} · Video: LTX-2.5 (Lightricks) · "
              "Image: Qwen-Image-2512, Qwen-Image-Edit-2511",
              "", "## 태그", "",
              "lofi, city pop, korean city pop, 시티팝, 로파이, 80s, 레트로, 비 오는 날, 공부 음악, 작업 음악, rain, study music",
              "", "## 업로드 체크", "", "- YouTube 'AI 생성·변경 콘텐츠' 공개 항목: 예(사실적인 장면 아님이라도 표시 권장)",
              "- Stability AI Community License: 연매출 100만 달러 미만 무료, 상업 이용 시 Stability AI 등록 필요",
              "- LTX-2 Community License: 연매출 1,000만 달러 미만 무료"]
    if mm:
        lines.append("- MiniMax-Music3 Community License: 상업 이용 시 \"MiniMax-Music3\" 표기 필요(설명란 크레딧에 포함)")
    lines += ["", "## 사용한 트랙 파일", ""] + [f"- Track {i + 1:02d}: {t}" for i, (_, t) in enumerate(starts)]
    md = out.with_suffix(".youtube.md")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", out, "and", md)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
