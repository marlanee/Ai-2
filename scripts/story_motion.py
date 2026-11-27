"""Image-to-video motion clips for every scene shot (LTX-2.5, low resolution; story_video upsizes them).

  python scripts/story_motion.py <story_dir> [--only 3,7] [--w 640 --h 352 --sec 5] [--max N]

Shots per scene: scenes/sNN.png (shot 1) and optional scenes/sNN_b.png, sNN_c.png ... (extra shots).
Motion prompt per shot: scene["motion"][k] if present (should describe the story action of that moment),
else the scene image description + 'subtle natural motion, nearly static camera' (a bare 'slow push-in' made
LTX zoom into giant faces, ep5c s02_1). Scene "seed_offset" shifts all clip seeds of a scene (redo a defect).
Scene "anchor_end": true -> shot clips also end on the same still (end-frame strength 0.8): the face cannot drift into a
new expression or zoom (ep5c s02_1 kept pushing into a growing open-mouth grin even with "static camera"). Output: clips/sNN_K.mp4 (resumable; delete to redo).

Engines: LTX-2.5 (default). scene "motion_engine": "k6" -> Kandinsky 6 Lite distill (864x480, ~4 min/clip, video only;
  A/B 2026-11-26: best on animal/nature action, but adds people or warps props in crowded scenes -> use only there).
Continuation clips (no frozen frames; 11-26 ep5c had 56 % of its runtime frozen on last frames): scene "beats":
  [{"motion": "what happens during the clip", "end": "edit instruction for the end pose"}, ...]. Each beat = one more clip
  after the shot clips, LTX first+last frame: start = last frame of the previous clip (seamless), end = Qwen-Edit of the
  scene's main still (scenes/sNN.png) with "end" (same faces/composition, no GPT quota). Keyframes in scenes/chain/.
  Rule of thumb: clips per scene = ceil(scene seconds / 10) (story_video plays clips at about 0.5x).
Dark-tail trim: LTX often fades to dark in the last 1-2 s. After every new clip the per-frame brightness is measured and the
  clip is cut where it drops below 85% of its first-half median (only if >= 2 s remain; full clip kept in clips/_full/).
  `--trim-only` applies the same check to existing clips.
"""
import argparse, json, pathlib, shutil, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMFY = pathlib.Path(r"C:\AI\ComfyUI\ComfyUI")
FF = r"C:\AI\tools\ffmpeg\bin\ffmpeg.exe"
WF = ROOT / "workflows" / "video_ltx25_flf2v_int8_api.json"
TAIL = (" Keep the exact same characters, faces, clothes and 2D illustration art style; smooth natural motion; faces stay stable "
        "with calm, subtle expressions; no new people; no text. Audio: quiet ambience, no music, no voices.")
LTX_NEG_ADD = (", deformed hands, extra fingers, fused fingers, missing fingers, morphing objects, melting, warping props, "
               "distorted face, morphing face, rolling eyes, crossed eyes, bulging eyes, exaggerated expression, grimace, "
               "gaping mouth, head spinning, sudden zoom")
EDIT_KEEP = (" Keep exactly the same characters, faces, ages, hair, clothes, setting, lighting, camera angle and 2D illustration "
             "style; change only the pose/action described. Keep facial expressions subtle and natural, "
             "no exaggerated cartoon expression (no gaping mouth, no bulging eyes). No new people, no text.")
K6_NEG = ("Static, worst quality, low quality, ugly, deformed, melting, morphing objects, morphing faces, extra people, children "
          "appearing, new characters, text, watermark, walking backwards")


def trim_dark_tail(clip, ratio=0.85, min_frames=48):
    """Cut a clip where it fades to dark; returns the kept frame count or None when untouched."""
    import numpy as np
    raw = subprocess.run([FF, "-v", "error", "-i", str(clip), "-vf", "scale=64:36", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(-1, 36 * 64).mean(1)
    if len(a) < min_frames:
        return None
    ref = float(np.median(a[:len(a) // 2]))
    low = a < ref * ratio
    # first frame from which the clip stays dark to the end (a short dip that recovers is left alone)
    cut = next((i for i in range(len(a)) if low[i:].all()), None)
    if cut is None or cut < min_frames:
        return None
    full = clip.parent / "_full"; full.mkdir(exist_ok=True)
    shutil.move(str(clip), full / clip.name)
    subprocess.run([FF, "-v", "error", "-y", "-i", str(full / clip.name), "-frames:v", str(cut), "-c:v", "libx264", "-crf", "16",
                    "-an", str(clip)], check=True)
    return cut


def k6_clip(img, prompt, seed, prefix, label):
    sys.path.insert(0, str(ROOT / "scripts"))
    import kandinsky_ab, run_workflow as rw
    name = f"k6_{label}.png"; shutil.copy(img, COMFY / "input" / name)
    api = kandinsky_ab.wf(name, prompt, seed, prefix)
    api["6"]["inputs"]["video_caption"] = K6_NEG
    return rw.run(api, label, timeout=3600, keep=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story_dir"); ap.add_argument("--only", default="")
    ap.add_argument("--w", type=int, default=640); ap.add_argument("--h", type=int, default=352)
    ap.add_argument("--sec", type=int, default=5); ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--shots", type=int, default=9, help="only the first N shots per scene (pass 1 = every scene moves)")
    ap.add_argument("--trim-only", action="store_true", help="only cut dark tails of existing clips")
    ap.add_argument("--keyframes-only", action="store_true",
                    help="only make the Qwen-Edit end keyframes for scene beats (run first: avoids Qwen<->LTX reloads per clip)")
    a = ap.parse_args()
    d = pathlib.Path(a.story_dir).resolve(); (d / "clips").mkdir(exist_ok=True)
    s = json.load(open(d / "story.json", encoding="utf-8-sig"))
    only = {int(x) for x in a.only.split(",") if x}
    if a.trim_only:
        for c in sorted((d / "clips").glob("s*_*.mp4")):
            if not only or int(c.stem[1:3]) in only:
                k = trim_dark_tail(c)
                if k: print(f"trim {c.name} -> {k} frames", flush=True)
        return
    if a.keyframes_only:
        for sc in s["scenes"]:
            if (only and sc["id"] not in only) or not sc.get("beats"):
                continue
            shots = [d / "scenes" / f"s{sc['id']:02d}.png"] + sorted((d / "scenes").glob(f"s{sc['id']:02d}_[b-z].png"))
            (d / "scenes" / "chain").mkdir(parents=True, exist_ok=True)
            for j, beat in enumerate(sc["beats"]):
                K = len(shots) + j + 1
                en = d / "scenes" / "chain" / f"s{sc['id']:02d}_{K}_end.png"
                if en.exists() or (d / "clips" / f"s{sc['id']:02d}_{K}.mp4").exists():
                    continue
                subprocess.run([sys.executable, str(ROOT / "scripts" / "qwen_edit.py"), str(shots[-1]), str(en),
                                "--prompt", beat["end"] + EDIT_KEEP, "--seed", str(sc["id"] * 10 + K)], check=True, capture_output=True)
                print("keyframe", en.name, flush=True)
        return
    done = 0; t0 = time.time()
    for sc in s["scenes"]:
        if only and sc["id"] not in only:
            continue
        shots = [d / "scenes" / f"s{sc['id']:02d}.png"] + sorted((d / "scenes").glob(f"s{sc['id']:02d}_[b-z].png"))
        motions = sc.get("motion", [])
        for k, img in enumerate(shots[:a.shots], 1):
            out = d / "clips" / f"s{sc['id']:02d}_{k}.mp4"
            if out.exists() or not img.exists():
                continue
            prompt = (motions[k - 1] if k - 1 < len(motions) else sc.get("image", "") + ", subtle natural motion, nearly static camera") + TAIL
            if sc.get("motion_engine") == "k6":
                res = k6_clip(img, prompt.replace(" Audio: quiet ambience, no music, no voices.", ""), sc["id"] * 10 + k,
                              f"story/{d.name}/k6_s{sc['id']:02d}_{k}", f"{d.name}_k6_{sc['id']}_{k}")
                if res.get("status") != "success":
                    print(f"FAIL k6 s{sc['id']}_{k}: {res.get('error')}", flush=True); continue
                shutil.copy(COMFY / "output" / next(o for o in res["outputs"] if o.endswith(".mp4")), out)
                done += 1; print(f"clip s{sc['id']:02d}_{k} k6 {res.get('seconds')}s", flush=True)
                continue
            name = f"mo_{d.name}_{sc['id']:02d}_{k}.png"
            shutil.copy(img, COMFY / "input" / name)
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_workflow.py"), str(WF),
                                "--set", f"31.image={name}", "--set", f"39.image={name}",
                                "--set", f"251:204.strength={0.8 if sc.get('anchor_end') else 0.0}", "--set", "251:206.strength=1.0",
                                "--set", f"251:252.value={prompt}", "--set", "251:250.value=false",
                                "--set", f"251:217.text=blurry, out of focus, overexposed, underexposed, low contrast{LTX_NEG_ADD}",
                                "--set", f"251:215.value={a.w}", "--set", f"251:216.value={a.h}",
                                "--set", f"251:198.value={a.sec}", "--set", "251:205.value=24",
                                "--set", f"251:196.noise_seed={sc['id'] * 10 + k + sc.get('seed_offset', 0)}",
                                "--set", f"68.filename_prefix=story/{d.name}/clip_s{sc['id']:02d}_{k}",
                                "--label", f"{d.name}_clip_{sc['id']}_{k}", "--timeout", "1800", "--keep-models"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            try:
                res = json.loads(r.stdout[r.stdout.index("{"):])
            except ValueError:
                res = {"status": "error", "error": r.stderr[-300:]}
            if res.get("status") != "success":
                print(f"FAIL s{sc['id']}_{k}: {res.get('error')}", flush=True); continue
            shutil.copy(COMFY / "output" / res["outputs"][0], out)
            done += 1
            cut = trim_dark_tail(out)
            print(f"clip s{sc['id']:02d}_{k} {res.get('seconds')}s (total {done}, {time.time() - t0:.0f}s)"
                  + (f" dark tail cut at frame {cut}" if cut else ""), flush=True)
            if a.max and done >= a.max:
                return
        # continuation clips (scene "beats"), chained frame-to-frame after the shot clips
        chain = d / "scenes" / "chain"
        for j, beat in enumerate(sc.get("beats", [])):
            K = len(shots) + j + 1
            out = d / "clips" / f"s{sc['id']:02d}_{K}.mp4"
            prev = d / "clips" / f"s{sc['id']:02d}_{K - 1}.mp4"
            if out.exists():
                continue
            if not prev.exists():
                print(f"skip s{sc['id']}_{K}: previous clip missing", flush=True); break
            chain.mkdir(parents=True, exist_ok=True)
            st, en = chain / f"s{sc['id']:02d}_{K}_start.png", chain / f"s{sc['id']:02d}_{K}_end.png"
            subprocess.run([FF, "-v", "error", "-y", "-sseof", "-0.2", "-i", str(prev), "-frames:v", "1", "-update", "1", str(st)], check=True)
            if not en.exists():
                subprocess.run([sys.executable, str(ROOT / "scripts" / "qwen_edit.py"), str(shots[-1]), str(en),   # the shot it continues
                                "--prompt", beat["end"] + EDIT_KEEP, "--seed", str(sc["id"] * 10 + K)], check=True,
                               capture_output=True)
            ns, ne = f"mo_{d.name}_{sc['id']:02d}_{K}_s.png", f"mo_{d.name}_{sc['id']:02d}_{K}_e.png"
            shutil.copy(st, COMFY / "input" / ns); shutil.copy(en, COMFY / "input" / ne)
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_workflow.py"), str(WF),
                                "--set", f"31.image={ns}", "--set", f"39.image={ne}",
                                "--set", "251:204.strength=0.8", "--set", "251:206.strength=1.0",
                                "--set", f"251:252.value={beat['motion'] + TAIL}", "--set", "251:250.value=false",
                                "--set", f"251:217.text=blurry, out of focus, overexposed, underexposed, low contrast{LTX_NEG_ADD}",
                                "--set", f"251:215.value={a.w}", "--set", f"251:216.value={a.h}",
                                "--set", f"251:198.value={a.sec}", "--set", "251:205.value=24",
                                "--set", f"251:196.noise_seed={sc['id'] * 10 + K + sc.get('seed_offset', 0)}",
                                "--set", f"68.filename_prefix=story/{d.name}/clip_s{sc['id']:02d}_{K}",
                                "--label", f"{d.name}_clip_{sc['id']}_{K}", "--timeout", "1800", "--keep-models"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            try:
                res = json.loads(r.stdout[r.stdout.index("{"):])
            except ValueError:
                res = {"status": "error", "error": r.stderr[-300:]}
            if res.get("status") != "success":
                print(f"FAIL s{sc['id']}_{K}: {res.get('error')}", flush=True); break
            shutil.copy(COMFY / "output" / next(o for o in res["outputs"] if o.endswith(".mp4")), out)
            done += 1
            cut = trim_dark_tail(out)
            print(f"chain s{sc['id']:02d}_{K} {res.get('seconds')}s" + (f" dark tail cut at frame {cut}" if cut else ""), flush=True)


if __name__ == "__main__":
    main()
