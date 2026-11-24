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
    ap.add_argument("--seed-start", type=int, default=1000)
    ap.add_argument("--prompt", default=PROMPT)
    ap.add_argument("--title", default="비 오는 밤, 80년대 서울 골목 다방에서 | Korean City Pop Lofi")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    tracks = [pathlib.Path(p) for p in a.first]
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
           "--duration", str(a.duration), "--seam", "0.5", "--xfade", str(a.xfade), "--size", "1920x1080",
           "--out", str(out), "--ffmpeg", FF]
    if a.ambience:
        cmd += ["--ambience", a.ambience, "--ambience-db", str(a.ambience_db)]
    if a.duration > 600:
        cmd.append("--copy-video")
    subprocess.run(cmd, check=True)

    lines = [f"# {a.title}", "", "## 설명", "",
             "비 내리는 80년대 서울 골목, 다방 간판 불빛 아래에서 듣는 시티팝 로파이.",
             "공부·작업·휴식할 때 틀어 두세요. 🌧️☕", "", "🎵 Tracklist"]
    for i in range(n):
        lines.append(f"{ts(i * (seg - a.xfade))} Track {i + 1:02d}")
    lines += ["", "—", "이 영상의 음악·영상·그림은 AI 도구로 제작했습니다.",
              "Music: Stable Audio 3.0 (Powered by Stability AI) · Video: LTX-2.5 (Lightricks) · "
              "Image: Z-Image Turbo, Qwen-Image-Edit-2511",
              "", "## 태그", "",
              "lofi, city pop, korean city pop, 시티팝, 로파이, 80s, 레트로, 비 오는 날, 공부 음악, 작업 음악, rain, study music",
              "", "## 업로드 체크", "", "- YouTube 'AI 생성·변경 콘텐츠' 공개 항목: 예(사실적인 장면 아님이라도 표시 권장)",
              "- Stability AI Community License: 연매출 100만 달러 미만 무료, 상업 이용 시 Stability AI 등록 필요",
              "- LTX-2 Community License: 연매출 1,000만 달러 미만 무료",
              "", "## 사용한 트랙 파일", ""] + [f"- Track {i + 1:02d}: {t}" for i, t in enumerate(tracks)]
    md = out.with_suffix(".youtube.md")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", out, "and", md)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
