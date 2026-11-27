"""Extra LTX 1080p loop variants from the same key art (start=end frame), different seeds/motion prompts.
python scripts/ltx_variants.py keyart_name.png prefix seed:prompt_variant ..."""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = ("{motion}, light reflections shimmering on the wet asphalt, warm shop window light, static camera, seamless loop, "
        "calm lofi night atmosphere. Audio: soft steady rain ambience, distant drips on metal awning, no music, no voices.")
MOTIONS = {
    "a": "gentle rain falling steadily, neon signs softly glowing",
    "b": "rain gently intensifying then easing, ripples spreading in puddles, a faint mist drifting down the alley",
    "c": "light drizzle, raindrops dripping from the awnings, the street lamp flickering very softly, wires swaying slightly",
}
art, prefix = sys.argv[1], sys.argv[2]
for spec in sys.argv[3:]:
    seed, m = spec.split(":")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_workflow.py"), str(ROOT / "workflows" / "video_ltx25_flf2v_int8_api.json"),
                        "--set", f"251:252.value={BASE.format(motion=MOTIONS[m])}", "--set", "251:250.value=false",
                        "--set", "251:215.value=1920", "--set", "251:216.value=1088", "--set", "251:198.value=5",
                        "--set", "251:205.value=24", "--set", f"251:196.noise_seed={seed}", "--set", f"31.image={art}",
                        "--set", f"39.image={art}", "--set", f"68.filename_prefix=release/{prefix}_{m}{seed}",
                        "--label", f"{prefix}_{m}{seed}", "--timeout", "2400"], capture_output=True, text=True, encoding="utf-8")
    res = json.loads(r.stdout[r.stdout.index("{"):]) if "{" in r.stdout else {"status": "error", "error": r.stderr[-400:]}
    print(spec, res.get("status"), res.get("seconds"), res.get("outputs"), flush=True)
print("LTXVAR DONE")
