"""Design one fixed voice per character (Qwen3-TTS VoiceDesign) -> <dir>/voices/<key>.wav + <key>.txt (clone references).

  C:\\AI\\tts\\venv\\Scripts\\python.exe scripts/story_voices.py <story_dir>
Reads <dir>/annotate.json "voices" {key: Korean voice description}. Existing references are kept.
"""
import json, pathlib, sys, urllib.request
import librosa, numpy as np, soundfile as sf, torch
from qwen_tts import Qwen3TTSModel

REF = "그날 일은 내가 똑똑히 기억하고 있소. 비가 그렇게 쏟아지던 밤이었지. 이제 와서 숨길 것도 없으니, 처음부터 다 이야기하리다."
REF_F = "그날 일은 제가 똑똑히 기억하고 있어요. 비가 그렇게 쏟아지던 밤이었지요. 이제 와서 숨길 것도 없으니, 처음부터 다 말씀드릴게요."


def main():
    d = pathlib.Path(sys.argv[1]); out = d / "voices"; out.mkdir(exist_ok=True)
    voices = json.load(open(d / "annotate.json", encoding="utf-8"))["voices"]
    todo = {k: v for k, v in voices.items() if k != "narrator" and not (out / f"{k}.wav").exists()}
    if not todo:
        print("all voices exist"); return
    try:
        urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8188/free", data=b'{"unload_models":true,"free_memory":true}',
                                                      headers={"Content-Type": "application/json"}), timeout=10)
    except Exception:
        pass
    m = Qwen3TTSModel.from_pretrained(r"C:\AI\tts\models\Qwen3-TTS-12Hz-1.7B-VoiceDesign", device_map="cuda:0",
                                      dtype=torch.bfloat16, attn_implementation="sdpa")
    for k, desc in todo.items():
        female = any(w in desc for w in ("여성", "여자", "할머니", "어머니", "며느리", "과부", "아낙"))
        text = REF_F if female else REF
        torch.manual_seed(111)
        wavs, sr = m.generate_voice_design(text=text, language="Korean", instruct=desc)
        w, _ = librosa.effects.trim(np.asarray(wavs[0], np.float32), top_db=40)
        sf.write(out / f"{k}.wav", w / max(1e-6, np.abs(w).max()) * 0.89, sr)
        (out / f"{k}.txt").write_text(text, encoding="utf-8")
        print("voice", k, round(len(w) / sr, 1), "s |", desc, flush=True)


if __name__ == "__main__":
    main()
