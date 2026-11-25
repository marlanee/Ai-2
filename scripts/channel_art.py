"""Channel art candidates (profile icon + banner background) with Qwen-Image-2512 Lightning."""
import json, pathlib, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "test_output" / "channel"; OUT.mkdir(parents=True, exist_ok=True)
N = '低分辨率，低画质，文字，字母，数字，标志，水印，乱码，人物，模糊'
JOBS = {
    "profile": (1024, 1024, 'A simple bold round emblem icon for a lofi music channel: a small vintage 1980s radio on a windowsill '
                'with a few rain drops, warm orange lamp glow and mint-green neon accent, dark navy background, centered, large '
                'simple shapes readable at tiny size, flat retro anime illustration. Absolutely no text, no letters, no numbers.'),
    "banner": (1664, 928, 'Very wide panoramic view of a rainy 1980s Seoul back alley at night, retro anime cel illustration with '
               'soft film grain, low-rise shops with warm lit windows, a mint-green record shop sign glow and an orange tearoom '
               'light, wet asphalt reflections, electric wires, calm and cozy, the central horizontal band is darker and simpler '
               'so text can sit on it. Absolutely no text, no letters, no numbers, signs are blank.'),
}
for name, (w, h, prompt) in JOBS.items():
    for s in (1, 2, 3):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_workflow.py"), str(ROOT / "workflows" / "image_qwen2512_api.json"),
                            "--set", f"238:227.text={prompt}", "--set", f"238:228.text={N}", "--set", "238:229.value=true",
                            "--set", f"238:232.width={w}", "--set", f"238:232.height={h}", "--set", f"238:230.seed={s * 7}",
                            "--set", f"60.filename_prefix=channel/{name}_s{s}", "--label", f"channel_{name}_s{s}", "--timeout", "900"],
                           capture_output=True, text=True, encoding="utf-8")
        res = json.loads(r.stdout[r.stdout.index("{"):]) if "{" in r.stdout else {"status": "error"}
        if res.get("status") == "success":
            shutil.copy(pathlib.Path(r"C:\AI\ComfyUI\ComfyUI\output") / res["outputs"][0], OUT / f"{name}_s{s}.png")
        print(name, s, res.get("status"), flush=True)
