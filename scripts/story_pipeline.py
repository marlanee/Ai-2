"""One command for a narrated story episode.

  python scripts/story_pipeline.py <story_dir> [--from STAGE] [--to STAGE] [--qa-rounds 2]

Stages (resumable; each skips work whose output already exists):
  script_review  GPT text-only review -> review/script_review.md (run once; revise story.json yourself, then go on)
  chars          character sheets (story_images --stage chars)
  scenes         scene images (story_images --stage scenes)
  gptimg         story.json "gpt" stems (thumb / opening / multi-character key scenes) -> GPT image (story_gptimg.py gen)
  stylize        other local shots re-drawn toward the GPT look with story.json "style_anchor" (story_images --stage stylize)
  qa             GPT scene QA; text-only problems -> qwen_edit erase, other problems -> regenerate with a new seed
  lora_collect   GPT originals approved with `story_gptimg.py approve` -> style-LoRA dataset C:/AI/train/data/style_gpt
  tts            narration with the fixed voice (TTS venv)
  bgm            3 x 120 s Stable Audio tracks unless bgm/*.flac exists (story.json "bgm" = list of prompts)
  video          story_video.py -> <name>.mp4 + .srt + timeline.json
  thumb          story_thumbnail.py from story.json "thumb": {"key": "scenes/s07.png", "lines": [...]} -> thumb.jpg
  preview        540p preview under 30 MB (phone)
  review         GPT post review -> review/video_review.md
"""
import argparse, json, pathlib, shutil, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
VPY = r"C:\AI\tts\venv\Scripts\python.exe"
FF = r"C:\AI\tools\ffmpeg\bin\ffmpeg.exe"
COMFY = pathlib.Path(r"C:\AI\ComfyUI\ComfyUI")
STAGES = ["script_review", "chars", "scenes", "gptimg", "stylize", "qa", "lora_collect", "voices", "tts", "bgm", "sfx",
          "motion", "video", "thumb", "preview", "review"]
ERASE = ("Remove every written character, letter and calligraphy from all signboards, banners, papers and documents so "
         "they are completely blank (plain wood, plain cloth, blank paper). Keep everything else exactly identical: same "
         "people, faces, composition, colors and art style.")
BGM = ["Calm traditional Korean folk instrumental, gentle gayageum zither plucking and soft daegeum bamboo flute melody, "
       "slow tempo 70 BPM, warm and nostalgic, storytelling background music, sparse, no percussion, no vocals",
       "Peaceful Korean traditional ambient music, soft haegeum strings and gayageum, slow and tender, gentle and "
       "heartwarming, background for an old folk tale, no drums, no vocals",
       "Quiet meditative Korean instrumental, geomungo low plucks and breathy daegeum flute, slow, calm night "
       "atmosphere, soft and warm, storytelling underscore, no vocals"]


def sh(cmd, py=PY, check=True):
    t = time.time()
    r = subprocess.run([py, *map(str, cmd)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    if check and r.returncode:
        raise SystemExit(f"FAILED {cmd[0]}: {out[-800:]}")
    return out, round(time.time() - t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story_dir"); ap.add_argument("--from", dest="frm", default="chars"); ap.add_argument("--to", default="review")
    ap.add_argument("--qa-rounds", type=int, default=2)
    a = ap.parse_args()
    d = pathlib.Path(a.story_dir).resolve()
    s = json.load(open(d / "story.json", encoding="utf-8-sig"))
    run = STAGES[STAGES.index(a.frm):STAGES.index(a.to) + 1]
    log = d / "pipeline_log.txt"

    def note(m):
        line = f"{time.strftime('%H:%M:%S')} {m}"
        print(line, flush=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    for st in run:
        if st == "script_review":
            out, t = sh([ROOT / "scripts/story_gpt.py", "review_script", d]); note(f"script_review {t}s {out.strip()[-80:]}")
        elif st in ("chars", "scenes"):
            out, t = sh([ROOT / "scripts/story_images.py", d, "--stage", st]); note(f"{st} {t}s")
        elif st == "gptimg":   # story["gpt"] stems (thumb, opening, multi-character key scenes) -> GPT image
            if s.get("gpt"):
                out, t = sh([ROOT / "scripts/story_gptimg.py", "gen", d]); note(f"gptimg {t}s " + " | ".join(out.split("\n")))
        elif st == "stylize":  # remaining local shots re-drawn toward the GPT look (story["style_anchor"])
            if s.get("style_anchor"):
                out, t = sh([ROOT / "scripts/story_images.py", d, "--stage", "stylize"]); note(f"stylize {t}s")
        elif st == "lora_collect":   # approved GPT originals (review/gpt_approved.json) -> C:/AI/train/data/style_gpt
            out, t = sh([ROOT / "scripts/story_gptimg.py", "collect", d]); note(out.strip())
        elif st == "qa":
            for rnd in range(a.qa_rounds):
                only = "" if rnd == 0 else ",".join(str(x) for x in bad_ids)
                out, t = sh([ROOT / "scripts/story_gpt.py", "scene_qa", d] + (["--only", only] if only else []))
                res = json.load(open(d / "review/scene_qa.json", encoding="utf-8"))
                bad = [r for r in res if not r["ok"]]
                bad_ids = [r["id"] for r in bad]
                note(f"qa round {rnd + 1} {t}s: {len(bad)} flagged {[(r['id'], 'T' if r.get('text') else '', 'D' if r.get('dup') else '', r.get('issue', '')[:40]) for r in bad]}")
                if not bad:
                    break
                for r in bad:
                    p = d / "scenes" / f"s{r['id']:02d}.png"
                    shutil.copy(p, p.with_name(f"s{r['id']:02d}_r{rnd}.png"))
                    if r.get("text") and not r.get("dup") and not r.get("severe"):
                        sh([ROOT / "scripts/qwen_edit.py", p.with_name(f"s{r['id']:02d}_r{rnd}.png"), p, "--prompt", ERASE, "--seed", 3])
                    else:
                        sh([ROOT / "scripts/story_images.py", d, "--stage", "scenes", "--only", r["id"], "--seed", 11 + rnd * 7])
                note(f"qa round {rnd + 1} fixed {bad_ids}")
            else:   # last round's fixes were never checked: verify once, report what is still wrong (no more auto-fix)
                out, t = sh([ROOT / "scripts/story_gpt.py", "scene_qa", d, "--only", ",".join(str(x) for x in bad_ids)])
                left = [r for r in json.load(open(d / "review/scene_qa.json", encoding="utf-8")) if not r["ok"]]
                note(f"qa verify {t}s: STILL BAD {[(r['id'], r.get('issue', '')[:50]) for r in left]} -> fix by hand" if left
                     else f"qa verify {t}s: all fixed")
        elif st == "tts":
            out, t = sh([ROOT / "scripts/story_tts.py", d], py=VPY)
            note(f"tts {t}s " + " | ".join(l for l in out.splitlines() if "total" in l or "CHECK" in l))
        elif st == "bgm":
            (d / "bgm").mkdir(exist_ok=True)
            if not list((d / "bgm").glob("*.flac")):
                for i, p in enumerate(s.get("bgm", BGM), 1):
                    out, t = sh([ROOT / "scripts/run_workflow.py", ROOT / "workflows/music_stableaudio3_medium_headroom_api.json",
                                 "--set", f"52:31.value={p}", "--set", "52:35.value=false", "--set", "52:36.value=120",
                                 "--set", f"52:3.seed={7100 + i}", "--set", f"57.filename_prefix=story/{d.name}/bgm_{i}",
                                 "--label", f"{d.name}_bgm_{i}", "--timeout", "900"])
                    res = json.loads(out[out.index("{"):out.rindex("}") + 1])
                    shutil.copy(COMFY / "output" / res["outputs"][0], d / "bgm" / f"bgm_{i}.flac")
            note(f"bgm {len(list((d / 'bgm').glob('*.flac')))} tracks")
        elif st == "voices":   # only when annotate.json exists (story_gpt.py annotate)
            if (d / "annotate.json").exists():
                out, t = sh([ROOT / "scripts/story_voices.py", d], py=VPY); note(f"voices {t}s " + " | ".join(l for l in out.splitlines() if l.startswith("voice")))
        elif st == "sfx":      # 20 s ambience/foley bed per scene from annotate.json "sfx" (Stable Audio 3)
            if (d / "annotate.json").exists():
                (d / "sfx").mkdir(exist_ok=True)
                n = 0
                for x in json.load(open(d / "annotate.json", encoding="utf-8"))["scenes"]:
                    dst = d / "sfx" / f"s{x['id']:02d}.flac"
                    if dst.exists() or not x.get("sfx"):
                        continue
                    out, t = sh([ROOT / "scripts/run_workflow.py", ROOT / "workflows/music_stableaudio3_medium_headroom_api.json",
                                 "--set", f"52:31.value={x['sfx']}, ambience sound effects only, no music, no melody, no voices",
                                 "--set", "52:35.value=false", "--set", "52:36.value=20", "--set", f"52:3.seed={8000 + x['id']}",
                                 "--set", f"57.filename_prefix=story/{d.name}/sfx_{x['id']:02d}", "--label", f"{d.name}_sfx_{x['id']}",
                                 "--timeout", "600", "--keep-models"])
                    res = json.loads(out[out.index("{"):out.rindex("}") + 1])
                    if res.get("status") == "success":
                        shutil.copy(COMFY / "output" / res["outputs"][0], dst); n += 1
                note(f"sfx {n} new beds")
        elif st == "motion":   # I2V clips per scene shot (story_motion.py); long — run alone on the GPU
            if not any(sc.get("motion") for sc in s["scenes"]):   # only stories written with per-scene motion prompts
                note("motion skipped (no motion prompts in story.json)"); continue
            for passes in ("1", "9"):   # pass 1: first shot of every scene; pass 2: the extra shots
                out, t = sh([ROOT / "scripts/story_motion.py", d, "--shots", passes])
                note(f"motion pass shots<={passes} {t}s " + (out.strip().splitlines()[-1] if out.strip() else ""))
        elif st == "video":
            out, t = sh([ROOT / "scripts/story_video.py", d, "--bgm", *sorted((d / "bgm").glob("*.flac"))], py=VPY)
            note(f"video {t}s " + " ".join(l for l in out.splitlines() if "wrote" in l))
        elif st == "thumb":
            th = s.get("thumb")
            if th:
                cmd = [ROOT / "scripts/story_thumbnail.py", d / th["key"], d / "thumb.jpg"]
                for l in th["lines"]:
                    cmd += ["--line", l]
                out, t = sh(cmd + ["--size", th.get("size", 120)]); note(f"thumb {out.strip()}")
        elif st == "preview":
            v = d / f"{d.name}.mp4"; pv = d / f"{d.name}_preview.mp4"
            subprocess.run([FF, "-v", "error", "-y", "-i", v, "-vf", "scale=960:540:flags=lanczos", "-c:v", "libx264", "-crf", "30",
                            "-preset", "medium", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", pv], check=True)
            mb = pv.stat().st_size / 2 ** 20
            if mb > 29:
                subprocess.run([FF, "-v", "error", "-y", "-i", v, "-vf", "scale=854:480:flags=lanczos", "-c:v", "libx264", "-crf", "33",
                                "-preset", "medium", "-c:a", "aac", "-b:a", "80k", "-movflags", "+faststart", pv], check=True)
                mb = pv.stat().st_size / 2 ** 20
            note(f"preview {mb:.1f} MB")
        elif st == "review":
            out, t = sh([ROOT / "scripts/story_gpt.py", "review_video", d]); note(f"review {t}s {out.strip()[-80:]}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
