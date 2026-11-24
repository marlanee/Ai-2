"""Qwen-Image-2512 test: draw the alley WITH Korean signs natively (Lightning 4-step).
python scripts/q2512_alley.py [seed ...]"""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ('A narrow back alley in Seoul, Korea, around 1988, on a rainy night, retro 1980s anime-style cel illustration with '
     'soft film grain, wide 16:9 shot, no people. Wet asphalt reflects warm orange window light; rain falls in thin '
     'streaks; electric wires and a wooden utility pole; a small parked 1980s sedan at the end of the alley. On the left, '
     'a record shop with a large mint-green illuminated sign that reads "은하수레코드" in bold red Korean letters, and LP '
     'records in its window. Above it, a tall vertical white lightbox reads "다방" in pink Korean letters. In the middle, a '
     'snack bar with an orange wooden sign reading "할매분식" in red Korean letters. Further down, a small green lightbox '
     'reads "약국", and a pink lightbox reads "만화". All Korean text is large, correct and clearly legible. No English, '
     'no Chinese characters, no other text anywhere.')
N = '低分辨率，低画质，画面过饱和，人物，英文，汉字，日文，乱码文字，错误的韩文，文字模糊，扭曲'
P2 = ('A narrow back alley in Seoul, Korea, around 1988, on a rainy night, retro 1980s anime-style cel illustration with '
      'soft film grain, wide 16:9 shot, no people. Wet asphalt reflects warm orange window light; rain falls in thin '
      'streaks; electric wires and a wooden utility pole; a small parked 1980s sedan at the end of the alley. On the left, '
      'a record shop with LP records in its window and a large mint-green illuminated sign with exactly three big red '
      'Korean letters: "레코드". Above it, a tall vertical white lightbox with two pink Korean letters: "다방". In the '
      'middle, a snack bar with an orange sign with four red Korean letters: "할매분식". No other signs have text. '
      'All Korean text is large, correct and clearly legible. No English, no Chinese characters, no other text anywhere.')
if sys.argv[1:2] == ["--short"]:
    P = P2; sys.argv.pop(1)
seeds = [int(s) for s in sys.argv[1:]] or [11, 22, 33, 44]
for s in seeds:
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_workflow.py"), str(ROOT / "workflows" / "image_qwen2512_api.json"),
                        "--set", f"238:227.text={P}", "--set", f"238:228.text={N}", "--set", "238:229.value=true",
                        "--set", "238:232.width=1664", "--set", "238:232.height=928", "--set", f"238:230.seed={s}",
                        "--set", f"60.filename_prefix=q2512/alley_s{s}", "--label", f"q2512_alley_s{s}", "--timeout", "1200"],
                       capture_output=True, text=True, encoding="utf-8")
    res = json.loads(r.stdout[r.stdout.index("{"):]) if "{" in r.stdout else {"status": "error", "error": r.stderr[-500:]}
    print(s, res.get("status"), res.get("seconds"), res.get("outputs"), res.get("error"), flush=True)
print("Q2512 DONE")
