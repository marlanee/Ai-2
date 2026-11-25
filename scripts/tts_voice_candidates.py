"""Generate N takes of one designed voice (different seeds) so one can be picked as the fixed reference for cloning.

  C:\\AI\\tts\\venv\\Scripts\\python.exe scripts/tts_voice_candidates.py [--n 3]
Writes test_output/story/voice_ref/narrator_c_s<seed>.wav (+ .mp3) and ref_text.txt.
"""
import argparse, pathlib, subprocess
import librosa, numpy as np, soundfile as sf, torch
from qwen_tts import Qwen3TTSModel

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "test_output" / "story" / "voice_ref"
FF = r"C:\AI\tools\ffmpeg\bin\ffmpeg.exe"
INSTRUCT = "50대 한국 여성 라디오 낭독자. 부드럽고 포근한 중저음. 감정을 절제하면서 또박또박, 조금 느린 속도로 읽는다."
TEXT = ("오늘 들려드릴 이야기는, 조선 영조 때 충청도 어느 작은 장터에서 있었던 일입니다. "
        "비가 몹시 내리던 날이었지요. 사람들은 저마다 서둘러 집으로 돌아갔지만, 국밥집 아궁이에는 아직 불이 남아 있었습니다.")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=3); a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ref_text.txt").write_text(TEXT, encoding="utf-8")
    m = Qwen3TTSModel.from_pretrained(r"C:\AI\tts\models\Qwen3-TTS-12Hz-1.7B-VoiceDesign", device_map="cuda:0",
                                      dtype=torch.bfloat16, attn_implementation="sdpa")
    for i in range(a.n):
        seed = 100 + i * 11
        torch.manual_seed(seed)
        wavs, sr = m.generate_voice_design(text=TEXT, language="Korean", instruct=INSTRUCT)
        w, _ = librosa.effects.trim(np.asarray(wavs[0], np.float32), top_db=40)
        w = w / max(1e-6, np.abs(w).max()) * 0.89
        p = OUT / f"narrator_c_s{seed}.wav"
        sf.write(p, w, sr)
        subprocess.run([FF, "-v", "error", "-y", "-i", str(p), "-c:a", "libmp3lame", "-b:a", "160k", str(p.with_suffix(".mp3"))], check=True)
        print(p.name, round(len(w) / sr, 1), "s", flush=True)


if __name__ == "__main__":
    main()
