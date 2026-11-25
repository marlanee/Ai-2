"""Qwen3-TTS Korean narration samples for the story-video pilot.

  C:\\AI\\tts\\venv\\Scripts\\python.exe scripts/tts_sample.py [script.json] [--only A,B,C]

Variants (all from the same script, joined with short pauses):
  A  CustomVoice / Sohee (preset Korean female), one voice for every line
  B  VoiceDesign, 60s male storyteller narrator + separate character voices
  C  VoiceDesign, 50s female narrator + separate character voices
Writes test_output/story/tts_sample/<variant>.wav and timing.json.
"""
import argparse, json, pathlib, time
import librosa, numpy as np, soundfile as sf, torch
from qwen_tts import Qwen3TTSModel

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODELS = pathlib.Path(r"C:\AI\tts\models")
OUT = ROOT / "test_output" / "story" / "tts_sample"

VOICES = {
    "B": {"narrator": "60대 한국 남성 이야기꾼. 낮고 따뜻하며 약간 허스키한 목소리. 옛날이야기를 들려주듯 느리고 차분하게, 문장 끝을 부드럽게 내린다.",
          "soondeok": "40대 한국 여성. 다정하지만 단단한 목소리. 걱정스러운 마음을 담아 차분하게 말한다.",
          "old_man": "70대 한국 노인 남성. 쉬고 갈라진 목소리. 지치고 낮은 톤으로 천천히 말한다."},
    "C": {"narrator": "50대 한국 여성 라디오 낭독자. 부드럽고 포근한 중저음. 감정을 절제하면서 또박또박, 조금 느린 속도로 읽는다.",
          "soondeok": "40대 한국 여성. 다정하지만 단단한 목소리. 걱정스러운 마음을 담아 차분하게 말한다.",
          "old_man": "70대 한국 노인 남성. 쉬고 갈라진 목소리. 지치고 낮은 톤으로 천천히 말한다."},
}
GAP = {"narrator": 0.55, "dialogue": 0.4}


def load(name):
    return Qwen3TTSModel.from_pretrained(str(MODELS / name), device_map="cuda:0", dtype=torch.bfloat16, attn_implementation="sdpa")


def join(chunks, roles, sr):
    out = []
    for w, r in zip(chunks, roles):
        w, _ = librosa.effects.trim(np.asarray(w, dtype=np.float32), top_db=40)   # VoiceDesign pads lines with 1-3 s of silence
        out += [w, np.zeros(int(sr * GAP["narrator" if r == "narrator" else "dialogue"]), np.float32)]
    a = np.concatenate(out)
    return a / max(1e-6, np.abs(a).max()) * 0.89   # peak -1 dBFS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script", nargs="?", default=str(OUT / "script.json"))
    ap.add_argument("--only", default="A,B,C")
    a = ap.parse_args()
    lines = json.load(open(a.script, encoding="utf-8"))["lines"]
    texts, roles = [l["text"] for l in lines], [l["role"] for l in lines]
    todo = a.only.split(",")
    timing = {}

    if "A" in todo:
        m = load("Qwen3-TTS-12Hz-1.7B-CustomVoice")
        t = time.time()
        wavs, sr = m.generate_custom_voice(text=texts, language=["Korean"] * len(texts), speaker=["Sohee"] * len(texts),
                                           instruct=["옛날이야기를 들려주듯 차분하고 따뜻하게" if r == "narrator" else "" for r in roles])
        audio = join(wavs, roles, sr); sf.write(OUT / "A_sohee.wav", audio, sr)
        timing["A"] = dict(gen_s=round(time.time() - t, 1), audio_s=round(len(audio) / sr, 1))
        print("A", timing["A"], flush=True)
        del m; torch.cuda.empty_cache()

    vd = [v for v in ("B", "C") if v in todo]
    if vd:
        m = load("Qwen3-TTS-12Hz-1.7B-VoiceDesign")
        for v in vd:
            t = time.time()
            wavs, sr = m.generate_voice_design(text=texts, language=["Korean"] * len(texts), instruct=[VOICES[v][r] for r in roles])
            audio = join(wavs, roles, sr); sf.write(OUT / f"{v}_design.wav", audio, sr)
            timing[v] = dict(gen_s=round(time.time() - t, 1), audio_s=round(len(audio) / sr, 1),
                             f0_per_line=[round(float(np.nanmedian(librosa.pyin(np.asarray(w, np.float32), fmin=70, fmax=400, sr=sr)[0])), 1) for w in wavs])
            print(v, timing[v], flush=True)
    if "D" in todo:   # fixed narrator: clone the picked reference take (config/voices.json) for every line
        v = json.load(open(ROOT / "config/voices.json", encoding="utf-8-sig"))["narrator_c"]
        m = load(v["model"])
        prompt = m.create_voice_clone_prompt(ref_audio=str(ROOT / v["ref_audio"]),
                                             ref_text=(ROOT / v["ref_text_file"]).read_text(encoding="utf-8").strip())
        t = time.time()
        wavs, sr = m.generate_voice_clone(text=texts, language=["Korean"] * len(texts), voice_clone_prompt=prompt)
        audio = join(wavs, roles, sr); sf.write(OUT / "D_clone_s111.wav", audio, sr)
        timing["D"] = dict(gen_s=round(time.time() - t, 1), audio_s=round(len(audio) / sr, 1),
                           f0_per_line=[round(float(np.nanmedian(librosa.pyin(np.asarray(w, np.float32), fmin=70, fmax=400, sr=sr)[0])), 1) for w in wavs])
        print("D", timing["D"], flush=True)
    timing["vram_peak_gb"] = round(torch.cuda.max_memory_allocated() / 1e9, 2)
    json.dump(timing, open(OUT / "timing.json", "w"), indent=1)
    print(timing)


if __name__ == "__main__":
    main()
