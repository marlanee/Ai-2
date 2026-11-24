"""Theme pipeline: config/themes.json theme -> key art candidates -> GPT pick -> LTX loop -> music pool -> 5-min demo.

  python scripts/theme_pipeline.py <theme> [--stage image|pick|loop|music|demo|all] [--seeds 4] [--tracks 8]

Stages (each resumable; outputs in test_output/themes/<theme>/):
  image : Qwen-Image-2512 (Lightning) N seeds at 1664x928
  pick  : GPT pairwise knockout (codex) -> best.png ; GPT OCR flags any visible text (themes ask for none)
  loop  : best -> 1920x1088 -> LTX-2.5 FLF2V 5 s loop (start=end)
  music : Stable Audio 3.0 headroom workflow, theme prompts x seeds
  demo  : make_video --mix (theme pool) --master warm -> demo_5min.mp4 (+ youtube.md)
"""
import argparse, json, pathlib, shutil, subprocess, sys
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMFY = pathlib.Path(r"C:\AI\ComfyUI\ComfyUI")
FF = r"C:\AI\tools\ffmpeg\bin\ffmpeg.exe"


def run_wf(wf, sets, label, timeout=1800):
    cmd = [sys.executable, str(ROOT / "scripts" / "run_workflow.py"), str(ROOT / "workflows" / wf)]
    for k, v in sets.items():
        cmd += ["--set", f"{k}={v}"]
    cmd += ["--label", label, "--timeout", str(timeout)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    res = json.loads(r.stdout[r.stdout.index("{"):]) if "{" in r.stdout else {"status": "error", "error": r.stderr[-400:]}
    if res.get("status") != "success":
        raise RuntimeError(f"{label}: {res.get('error')}")
    return [COMFY / "output" / o for o in res["outputs"]], res.get("seconds")


def codex(prompt, images):
    args = ["codex.cmd" if sys.platform == "win32" else "codex", "exec", "--skip-git-repo-check", "-s", "read-only"]
    for i in images:
        args += ["-i", str(i)]
    r = subprocess.run(args, input=prompt, capture_output=True, text=True, encoding="utf-8")
    lines = r.stdout.splitlines()
    try:
        i = len(lines) - 1 - lines[::-1].index("codex"); j = len(lines) - 1 - lines[::-1].index("tokens used")
        return "\n".join(l for l in lines[i + 1:j] if not l.startswith("hook:"))
    except ValueError:
        return r.stdout[-2000:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("theme"); ap.add_argument("--stage", default="all")
    ap.add_argument("--seeds", type=int, default=4); ap.add_argument("--tracks", type=int, default=8)
    a = ap.parse_args()
    th = json.load(open(ROOT / "config" / "themes.json", encoding="utf-8"))[a.theme]
    out = ROOT / "test_output" / "themes" / a.theme; out.mkdir(parents=True, exist_ok=True)
    st = a.stage
    log = lambda m: print(f"[{a.theme}] {m}", flush=True)

    if st in ("image", "all"):
        for s in range(1, a.seeds + 1):
            outs, sec = run_wf("image_qwen2512_api.json", {"238:227.text": th["image"], "238:228.text": th["negative"],
                               "238:229.value": "true", "238:232.width": 1664, "238:232.height": 928, "238:230.seed": s * 101,
                               "60.filename_prefix": f"themes/{a.theme}/cand_s{s * 101}"}, f"{a.theme}_img_s{s * 101}")
            shutil.copy(outs[0], out / f"cand_{s}.png"); log(f"image {s} {sec}s")

    if st in ("pick", "all"):
        cands = sorted(out.glob("cand_*.png"))
        best = cands[0]
        q = (f"Two key-art candidates for a YouTube lofi channel video titled '{th['title']}' (thumbnail + long loop background). "
             "Judge as a strict art director and as the target viewer. Penalize any visible letters/numbers/pseudo-text, "
             "AI artifacts, broken anatomy or perspective. Answer briefly in Korean, last line exactly: WINNER=<1|2>")
        for c in cands[1:]:
            ans = codex(q, [best, c])
            w = "2" if "WINNER=2" in ans else "1"
            log(f"pick {best.name} vs {c.name}: winner {w}")
            if w == "2":
                best = c
        shutil.copy(best, out / "best.png")
        crit = codex("Review this key art for a lofi YouTube channel. Answer in Korean: 1) viewer appeal /10 2) completeness /10 "
                     "3) AI artifacts with location 4) any visible text or pseudo-letters (list) 5) top 3 fixes. Last line exactly: "
                     "SCORES: appeal=<n> completeness=<n>", [out / "best.png"])
        (out / "best_critique.md").write_text(crit, encoding="utf-8")
        log("critique: " + (crit.strip().splitlines()[-1] if crit.strip() else "?"))

    if st in ("loop", "all"):
        Image.open(out / "best.png").convert("RGB").resize((1920, 1088), Image.LANCZOS).save(out / "best_1080.png")
        name = f"theme_{a.theme}.png"
        shutil.copy(out / "best_1080.png", COMFY / "input" / name)
        outs, sec = run_wf("video_ltx25_flf2v_int8_api.json", {"251:252.value": th["motion"], "251:250.value": "false",
                           "251:215.value": 1920, "251:216.value": 1088, "251:198.value": 5, "251:205.value": 24,
                           "251:196.noise_seed": 1980, "31.image": name, "39.image": name,
                           "68.filename_prefix": f"themes/{a.theme}/loop"}, f"{a.theme}_ltx", 2400)
        shutil.copy(outs[0], out / "loop.mp4")
        subprocess.run([FF, "-v", "error", "-y", "-i", str(out / "loop.mp4"), "-vn", "-c:a", "flac", str(out / "ambience.flac")], check=True)
        log(f"loop {sec}s")

    if st in ("music", "all"):
        pool = out / "music"; pool.mkdir(exist_ok=True)
        for i in range(a.tracks):
            p = th["music"][i % len(th["music"])]
            seed = 3000 + i
            outs, sec = run_wf("music_stableaudio3_medium_headroom_api.json", {"52:31.value": p, "52:35.value": "false",
                               "52:36.value": 120, "52:3.seed": seed, "57.filename_prefix": f"themes/{a.theme}/m_p{i % len(th['music'])}_s{seed}"},
                               f"{a.theme}_music_s{seed}", 900)
            shutil.copy(outs[0], pool / outs[0].name)
        log(f"music {a.tracks} tracks")

    if st in ("demo", "all"):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "make_video.py"), "--clip", str(out / "loop.mp4"), "--seam", "0.5",
                        "--duration", "300", "--out", str(out / "demo_5min.mp4"), "--mix", str(out / "music"),
                        "--master", "warm", "--ambience", str(out / "ambience.flac"), "--ambience-db", "-6",
                        "--title", th["title"]], check=True)
        subprocess.run([FF, "-v", "error", "-y", "-i", str(out / "demo_5min.mp4"), "-vf", "scale=1280:720:flags=lanczos",
                        "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                        str(out / "demo_5min_preview720.mp4")], check=True)
        log("demo done")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
