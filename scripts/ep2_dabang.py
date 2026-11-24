"""Episode 2 '다방 창가' key art candidates with Qwen-Image-2512 (spec from test_output/strategy/retro_round2.md)."""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ('Inside a cozy 1988 Seoul tearoom (dabang) at night, view from a window seat, wide 16:9, retro 1980s anime cel '
     'illustration with soft film grain, no people. A large rain-streaked window with water droplets takes the left half; '
     'through it a rainy back alley with warm shop lights and, across the alley, a glowing mint-green shop sign with three '
     'big red Korean letters "레코드". On the window table: a white coffee cup with steam on a saucer, a small glass ashtray, '
     'a sugar pot. Warm orange pendant lamp, dark wood paneling, velvet booth seat, a potted rubber plant. Calm, nostalgic, '
     'warm interior vs cool blue rainy night outside. No other text anywhere, no English, no Chinese characters.')
N = '低分辨率，低画质，画面过饱和，人物，英文，汉字，日文，乱码文字，错误的韩文，文字模糊，扭曲'
out = ROOT / "test_output" / "ep2"; out.mkdir(parents=True, exist_ok=True)
for s in [int(x) for x in sys.argv[1:]] or [61, 62, 63, 64, 65, 66]:
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_workflow.py"), str(ROOT / "workflows" / "image_qwen2512_api.json"),
                        "--set", f"238:227.text={P}", "--set", f"238:228.text={N}", "--set", "238:229.value=true",
                        "--set", "238:232.width=1664", "--set", "238:232.height=928", "--set", f"238:230.seed={s}",
                        "--set", f"60.filename_prefix=ep2/dabang_s{s}", "--label", f"ep2_s{s}", "--timeout", "1200"],
                       capture_output=True, text=True, encoding="utf-8")
    res = json.loads(r.stdout[r.stdout.index("{"):]) if "{" in r.stdout else {"status": "error"}
    if res.get("status") == "success":
        src = ROOT.parent / "x"
        import shutil
        shutil.copy(pathlib.Path(r"C:\AI\ComfyUI\ComfyUI\output") / res["outputs"][0], out / f"cand_s{s}.png")
    print(s, res.get("status"), res.get("seconds"), flush=True)
print("EP2 DONE")
