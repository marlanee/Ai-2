"""Narrate every line of a story.json with the fixed cloned narrator voice (config/voices.json).

  C:\\AI\\tts\\venv\\Scripts\\python.exe scripts/story_tts.py <story_dir> [--voice narrator_c]
Writes <story_dir>/tts/sNN_LL.wav (silence-trimmed) and <story_dir>/tts/lines.json with durations.
Existing wavs are kept (resumable); delete one to regenerate it.
"""
import argparse, json, pathlib, time
import librosa, numpy as np, soundfile as sf, torch
from qwen_tts import Qwen3TTSModel

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("story_dir"); ap.add_argument("--voice", default="narrator_c")
    ap.add_argument("--batch", type=int, default=6)
    a = ap.parse_args()
    d = pathlib.Path(a.story_dir); out = d / "tts"; out.mkdir(exist_ok=True)
    story = json.load(open(d / "story.json", encoding="utf-8-sig"))
    v = json.load(open(ROOT / "config/voices.json", encoding="utf-8-sig"))[a.voice]
    items = [(s["id"], i, t) for s in story["scenes"] for i, t in enumerate(s["lines"])]
    todo = [x for x in items if not (out / f"s{x[0]:02d}_{x[1]:02d}.wav").exists()]
    if todo:
        # ComfyUI may still hold LTX/Qwen models (story_motion uses --keep-models); on a 16 GB card the TTS model then
        # spills into shared memory and crawls. Ask ComfyUI to unload first.
        try:
            import urllib.request
            urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8188/free", data=b'{"unload_models":true,"free_memory":true}',
                                                          headers={"Content-Type": "application/json"}), timeout=10)
        except Exception:
            pass
        m = Qwen3TTSModel.from_pretrained(str(pathlib.Path(r"C:\AI\tts\models") / v["model"]), device_map="cuda:0",
                                          dtype=torch.bfloat16, attn_implementation="sdpa")
        prompts = {"narrator": m.create_voice_clone_prompt(ref_audio=str(ROOT / v["ref_audio"]),
                                                            ref_text=(ROOT / v["ref_text_file"]).read_text(encoding="utf-8").strip())}
        # character voices: annotate.json speakers per line + voices/<key>.wav references (story_voices.py)
        spk = {}
        if (d / "annotate.json").exists():
            ann = {x["id"]: x["speakers"] for x in json.load(open(d / "annotate.json", encoding="utf-8"))["scenes"]}
            for sid, i, t in items:
                k = (ann.get(sid) or [])[i] if i < len(ann.get(sid) or []) else "narrator"
                if k != "narrator" and (d / "voices" / f"{k}.wav").exists():
                    spk[(sid, i)] = k
                    if k not in prompts:
                        prompts[k] = m.create_voice_clone_prompt(ref_audio=str(d / "voices" / f"{k}.wav"),
                                                                 ref_text=(d / "voices" / f"{k}.txt").read_text(encoding="utf-8").strip())
        t0 = time.time()
        for who, pr in prompts.items():
            group = [x for x in todo if spk.get((x[0], x[1]), "narrator") == who]
            for k in range(0, len(group), a.batch):
                chunk = group[k:k + a.batch]
                # quotes are for subtitles; the voice reads the words only
                wavs, sr = m.generate_voice_clone(text=[t.replace('"', "").replace("“", "").replace("”", "") for _, _, t in chunk],
                                                  language=["Korean"] * len(chunk), voice_clone_prompt=pr)
                for (sid, i, t), w in zip(chunk, wavs):
                    w, _ = librosa.effects.trim(np.asarray(w, np.float32), top_db=40)
                    sf.write(out / f"s{sid:02d}_{i:02d}.wav", w, sr)
                print(f"{who}: {k + len(chunk)}/{len(group)} lines, {time.time() - t0:.0f}s", flush=True)
    rows = []
    for sid, i, t in items:
        info = sf.info(out / f"s{sid:02d}_{i:02d}.wav")
        rows.append(dict(scene=sid, idx=i, text=t, file=f"s{sid:02d}_{i:02d}.wav", dur=round(info.duration, 3),
                         chars_per_s=round(len(t.replace(" ", "")) / info.duration, 2)))
    json.dump(rows, open(out / "lines.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tot = sum(r["dur"] for r in rows)
    print(f"total speech {tot:.0f}s ({tot / 60:.1f} min), {len(rows)} lines")
    for r in rows:   # flag likely truncation or babble
        if r["chars_per_s"] < 3 or r["chars_per_s"] > 9:
            print("CHECK", r["file"], r["chars_per_s"], r["text"][:40])


if __name__ == "__main__":
    main()
