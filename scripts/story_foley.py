"""Event sounds for each motion clip: LTX Foley LoRA (video -> audio), then EQ for the story mix.

  python scripts/story_foley.py <story_dir> [--only 9,11] [--force]

Per scene in annotate.json:
  "foley": "Snow crunching under an old man's knees, a heavy iron trap creaking open ..."   (all shots of the scene)
       or ["prompt for shot 1", "prompt for shot 2", ...]                                    ("" = no sound for that shot)
  "foley_model": "2.3"   optional — LTX-2.3 dev + official settings (4-5 min/clip; won sustained sounds such as a tiger's
                         breathing in the 11-26 blind test). Default LTX-2.5 distilled (~40 s/clip; won footsteps and metal).
Input clip: clips/sNN_K.mp4, or clips/_full/sNN_K.mp4 when the clip was trimmed (the graph needs the 121-frame original;
the extra audio is simply never reached by story_video). Output: sfx/foley/sNN_K.wav (48 kHz) after
  high-pass 40 Hz, low-pass 6 kHz, +6 dB at 160 Hz (listener 11-26: raw foley footsteps sounded "too bright"), peak -6 dBFS.
story_video.py mixes these over the scene ambience, time-stretched to the clip's slow-motion rate.
The whistle signal stays the synthetic cue (annotate "cues"): exact rhythm, and it beat Foley in the blind test.
"""
import argparse, json, pathlib, shutil, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import foley_ab, run_workflow as rw

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMFY = pathlib.Path(r"C:\AI\ComfyUI\ComfyUI")
FF = r"C:\AI\tools\ffmpeg\bin\ffmpeg.exe"
EQ = "highpass=f=40,lowpass=f=6000,bass=g=6:f=160"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story_dir"); ap.add_argument("--only", default=""); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    d = pathlib.Path(a.story_dir).resolve()
    ann = json.load(open(d / "annotate.json", encoding="utf-8"))
    only = {int(x) for x in a.only.split(",") if x}
    out_dir = d / "sfx" / "foley"; out_dir.mkdir(parents=True, exist_ok=True)
    first, made = True, 0
    for sc in ann["scenes"]:
        if only and sc["id"] not in only or not sc.get("foley"):
            continue
        clips = sorted((d / "clips").glob(f"s{sc['id']:02d}_*.mp4"))
        prompts = sc["foley"] if isinstance(sc["foley"], list) else [sc["foley"]] * len(clips)
        for clip, prompt in zip(clips, prompts):
            dst = out_dir / f"{clip.stem}.wav"
            if not prompt or (dst.exists() and not a.force):
                continue
            src = d / "clips" / "_full" / clip.name
            src = src if src.exists() else clip
            vn = f"foley_{d.name}_{clip.stem}.mp4"; shutil.copy(src, COMFY / "input" / vn)
            v23 = str(sc.get("foley_model", "")) == "2.3"
            api = (foley_ab.wf23 if v23 else foley_ab.wf)(vn, prompt, 42, f"story/{d.name}/foley_{clip.stem}", *([] if v23 else [1.0]))
            res = rw.run(api, f"{d.name}_foley_{clip.stem}", 3600, keep=not first)
            if res["status"] != "success":
                print("FAIL", clip.stem, res.get("error"), flush=True); continue
            first = False
            raw = COMFY / "output" / next(o for o in res["outputs"] if o.lower().endswith((".flac", ".wav", ".mp3", ".opus")))
            # EQ, then peak-normalise to -6 dBFS (story_video scales the bed again; loudness matching here would blow up
            # near-silent results into hiss)
            subprocess.run([FF, "-v", "error", "-y", "-i", str(raw), "-af", f"{EQ},alimiter=limit=0.5:level=disabled", "-ar", "48000",
                            str(dst)], check=True)
            made += 1
            print(f"foley {clip.stem} {'2.3' if v23 else '2.5'} {res['seconds']}s", flush=True)
    print(f"foley {made} new")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
