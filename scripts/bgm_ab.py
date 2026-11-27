"""Test D: yadam BGM, 3 moods x 60 s x {ACE-Step 1.5 XL SFT, XL turbo, Stable Audio 3.0} -> QC -> blind listening files.

  python scripts/bgm_ab.py gen     # 9 tracks (results.jsonl: seconds / peak VRAM / cold)
  python scripts/bgm_ab.py qc      # audio_qc: integrated LUFS, true peak (clipping), silent stretches -> qc.md
  python scripts/bgm_ab.py blind   # blind/B1.mp3 ... (loudness-matched to -16 LUFS) + answer.txt
Out: test_output/story/model_ab_2611/D_bgm/
ACE-Step SFT settings = official template audio_ace_step1_5_xl_sft.json (50 steps, CFG 7); turbo = 8 steps, CFG 1.
"""
import json, pathlib, random, shutil, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import run_workflow as rw, audio_qc as qc

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMFY = pathlib.Path(r"C:\AI\ComfyUI\ComfyUI")
FF = r"C:\AI\tools\ffmpeg\bin\ffmpeg.exe"
OUT = ROOT / "test_output/story/model_ab_2611/D_bgm"; OUT.mkdir(parents=True, exist_ok=True)
MOODS = {
    "tension": dict(bpm=96, key="D minor",
        ace="Korean traditional instrumental for a chase through a snowy ravine at night, tense and urgent, driving buk and janggu "
            "drums, low geomungo ostinato, sharp haegeum bowing, rising suspense, cinematic, instrumental, no vocals",
        sa="Tense Korean traditional instrumental, urgent buk and janggu drums, low geomungo ostinato, sharp haegeum, suspense, chase "
           "in a snowy ravine at night, 96 BPM, cinematic underscore, no vocals"),
    "warm": dict(bpm=68, key="F major",
        ace="Warm gentle Korean traditional instrumental by a fireplace on a winter night, soft gayageum plucking, breathy daegeum "
            "flute, tender and nostalgic, slow, quiet storytelling background, instrumental, no vocals, no drums",
        sa="Warm gentle Korean traditional instrumental, soft gayageum plucking and breathy daegeum flute, tender nostalgic, "
           "winter night by the fireplace, slow 68 BPM, storytelling background, no drums, no vocals"),
    "ending": dict(bpm=76, key="G major",
        ace="Hopeful Korean traditional instrumental for a spring morning ending, bright gayageum melody, light daegeum, soft "
            "janggu, a gentle whistled-like flute motif, peaceful and uplifting, instrumental, no vocals",
        sa="Hopeful Korean traditional instrumental, bright gayageum melody, light daegeum and soft janggu, spring morning, "
           "peaceful uplifting ending theme, 76 BPM, no vocals"),
}
MODELS = ["ace_sft", "ace_turbo", "sa3"]


def load(name):
    api = json.loads((ROOT / "workflows" / name).read_text(encoding="utf-8"))
    for v in api.values():
        v.pop("_meta", None)
    return api


def gen():
    for model in MODELS:
        first = True
        for mood, m in MOODS.items():
            dst = OUT / f"{mood}_{model}.flac"
            if dst.exists(): continue
            if model.startswith("ace"):
                api = load(f"music_acestep15_xl_{model[4:]}_api.json")
                t = api["94"]["inputs"]
                t.update(tags=m["ace"], lyrics="[Instrumental]", bpm=m["bpm"], duration=60, keyscale=m["key"], seed=7)
                api["98"]["inputs"]["seconds"] = 60
                api["3"]["inputs"]["seed"] = 7
                api["111"]["inputs"]["filename_prefix"] = f"model_ab_2611/bgm_{mood}_{model}"
            else:
                api = load("music_stableaudio3_medium_headroom_api.json")
                rw.apply_sets(api, [f"52:31.value={m['sa']}", "52:35.value=false", "52:36.value=60", "52:3.seed=7",
                                    f"57.filename_prefix=model_ab_2611/bgm_{mood}_{model}"])
            res = rw.run(api, f"bgm_{mood}_{model}", 1800, keep=not first)
            res["cold"] = first
            with open(OUT / "results.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
            if res["status"] != "success":
                print("FAIL", mood, model, res.get("error"), flush=True); continue
            first = False
            subprocess.run([FF, "-v", "error", "-y", "-i", str(COMFY / "output" / res["outputs"][0]), "-ar", "48000", str(dst)], check=True)
            print(mood, model, res["seconds"], "s", res["peak_vram_mb"], "MB", flush=True)


def silences(path, thr=-45.0, min_s=1.5):
    m = qc.measure(path)   # (t, M, S) every 0.1 s
    runs, start = [], None
    for t, M, _ in m:
        if M < thr and start is None: start = t
        if M >= thr and start is not None:
            if t - start >= min_s: runs.append((round(start, 1), round(t, 1)))
            start = None
    if start is not None and m and m[-1][0] - start >= min_s: runs.append((round(start, 1), round(m[-1][0], 1)))
    return runs


def qcrun():
    rows = ["| 파일 | 길이(s) | 통합 음량(LUFS) | True peak(dBTP) | 클리핑 | 무음 구간(M<-45 LUFS, 1.5 s 이상) |", "|---|---|---|---|---|---|"]
    for p in sorted(OUT.glob("*.flac")):
        I, tp = qc.integrated(p)
        sil = silences(p)
        rows.append(f"| {p.stem} | {qc.dur(p):.1f} | {I:.1f} | {tp:.1f} | {'있음' if tp > -0.1 else '없음'} | {sil or '없음'} |")
    (OUT / "qc.md").write_text("\n".join(rows) + "\n", encoding="utf-8"); print("\n".join(rows))


def blind():
    random.seed(2611)
    bd = OUT / "blind"; bd.mkdir(exist_ok=True)
    items = [(mood, model) for mood in MOODS for model in MODELS if (OUT / f"{mood}_{model}.flac").exists()]
    ans = []
    for mood in MOODS:   # shuffle inside each mood so the three versions of a mood sit together
        grp = [x for x in items if x[0] == mood]; random.shuffle(grp)
        for _, model in grp:
            k = len(ans) + 1
            subprocess.run([FF, "-v", "error", "-y", "-i", str(OUT / f"{mood}_{model}.flac"), "-af", "loudnorm=I=-16:TP=-1.5",
                            "-ar", "44100", "-b:a", "192k", str(bd / f"B{k}.mp3")], check=True)
            ans.append(f"B{k}\t{mood}\t{model}")
    (bd / "answer.txt").write_text("\n".join(ans) + "\n", encoding="utf-8"); print("\n".join(ans))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    {"gen": gen, "qc": qcrun, "blind": blind}[sys.argv[1]]()
