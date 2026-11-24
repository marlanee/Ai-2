"""Episode 2 '다방 창가' key art candidates with Qwen-Image-2512 (spec from test_output/strategy/retro_round2.md)."""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ('A quiet bus stop at the end of a narrow 1988 Seoul back street after the last bus, rainy night, wide 16:9, retro 1980s anime '
     'cel illustration with soft film grain, no people. A small shelter with a bench and a warm street lamp, wet asphalt with '
     'long reflections, a closed shop with its shutter down, a vending machine glowing softly, electric wires, low houses with a '
     'few lit windows, a plain round bus-stop sign with no writing. Calm, lonely but warm. Absolutely no text, no letters, '
     'no numbers anywhere.')
N = '低分辨率，低画质，画面过饱和，人物，英文，汉字，日文，乱码文字，错误的韩文，文字模糊，扭曲'
out = ROOT / "test_output" / "ep3"; out.mkdir(parents=True, exist_ok=True)
for s in [int(x) for x in sys.argv[1:]] or [71, 72, 73, 74, 75, 76]:
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_workflow.py"), str(ROOT / "workflows" / "image_qwen2512_api.json"),
                        "--set", f"238:227.text={P}", "--set", f"238:228.text={N}", "--set", "238:229.value=true",
                        "--set", "238:232.width=1664", "--set", "238:232.height=928", "--set", f"238:230.seed={s}",
                        "--set", f"60.filename_prefix=ep3/stop_s{s}", "--label", f"ep3_s{s}", "--timeout", "1200"],
                       capture_output=True, text=True, encoding="utf-8")
    res = json.loads(r.stdout[r.stdout.index("{"):]) if "{" in r.stdout else {"status": "error"}
    if res.get("status") == "success":
        src = ROOT.parent / "x"
        import shutil
        shutil.copy(pathlib.Path(r"C:\AI\ComfyUI\ComfyUI\output") / res["outputs"][0], out / f"cand_s{s}.png")
    print(s, res.get("status"), res.get("seconds"), flush=True)
print("EP3 DONE")
