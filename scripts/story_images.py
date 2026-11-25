"""Character reference sheets and scene illustrations for a story.json.

  python scripts/story_images.py <story_dir> --stage chars|scenes [--only 3,7] [--seed 1]

chars : Qwen-Image-2512 portrait per character -> <dir>/chars/<name>.png
scenes: scenes with characters -> Qwen-Image-Edit-2511 with 1-2 character refs (image1/image2) on an empty
        1664x928 latent, so faces/clothes stay consistent; scenes without characters -> Qwen-Image-2512.
        -> <dir>/scenes/sNN.png (existing files are skipped; delete to regenerate)
"""
import argparse, copy, json, pathlib, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMFY = pathlib.Path(r"C:\AI\ComfyUI\ComfyUI")
WF = ROOT / "workflows"
NEG = "低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，画面具有AI感。构图混乱。文字，字母，水印，签名"


def edit_2ref_workflow():
    """image_qwen_edit_2511_int8_api.json + second reference image + empty 16:9 latent (written once, reused)."""
    p = WF / "image_qwen_edit_2511_2ref_api.json"
    if p.exists():
        return p
    w = json.load(open(WF / "image_qwen_edit_2511_int8_api.json", encoding="utf-8"))
    w["42"] = {"class_type": "LoadImage", "inputs": {"image": "ref2.png"}}
    w["170:170"] = {"class_type": "FluxKontextImageScale", "inputs": {"image": ["42", 0]}}
    w["300"] = {"class_type": "EmptySD3LatentImage", "inputs": {"width": 1664, "height": 928, "batch_size": 1}}
    for n in ("170:151", "170:149"):
        w[n]["inputs"]["image2"] = ["170:170", 0]
    w["170:169"]["inputs"]["latent_image"] = ["300", 0]
    json.dump(w, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return p


def edit_1ref_workflow():
    p = WF / "image_qwen_edit_2511_1ref_api.json"
    if p.exists():
        return p
    w = json.load(open(WF / "image_qwen_edit_2511_int8_api.json", encoding="utf-8"))
    w["300"] = {"class_type": "EmptySD3LatentImage", "inputs": {"width": 1664, "height": 928, "batch_size": 1}}
    w["170:169"]["inputs"]["latent_image"] = ["300", 0]
    json.dump(w, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return p


def run(wf, sets, label):
    cmd = [sys.executable, str(ROOT / "scripts" / "run_workflow.py"), str(wf)]
    for k, v in sets.items():
        cmd += ["--set", f"{k}={v}"]
    r = subprocess.run(cmd + ["--label", label, "--timeout", "1800"], capture_output=True, text=True, encoding="utf-8")
    res = json.loads(r.stdout[r.stdout.index("{"):]) if "{" in r.stdout else {"status": "error", "error": r.stderr[-500:]}
    if res.get("status") != "success":
        raise SystemExit(f"{label}: {res.get('error')}")
    return COMFY / "output" / res["outputs"][0], res.get("seconds")


def t2i(prompt, w, h, seed, prefix, label):
    return run(WF / "image_qwen2512_api.json", {"238:227.text": prompt, "238:228.text": NEG, "238:229.value": "true",
               "238:232.width": w, "238:232.height": h, "238:230.seed": seed, "60.filename_prefix": prefix}, label)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story_dir"); ap.add_argument("--stage", required=True)
    ap.add_argument("--only", default=""); ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    d = pathlib.Path(a.story_dir); s = json.load(open(d / "story.json", encoding="utf-8-sig"))
    only = {x for x in a.only.split(",") if x}
    tag = d.name

    if a.stage == "chars":
        (d / "chars").mkdir(exist_ok=True)
        # plain descriptions first, then {"from": base, "edit": "..."} variants (same face, edited from the base sheet)
        for name, desc in sorted(s["characters"].items(), key=lambda kv: isinstance(kv[1], dict)):
            if (only and name not in only) or ((d / "chars" / f"{name}.png").exists() and not only):
                continue
            if isinstance(desc, dict):
                shutil.copy(d / "chars" / f"{desc['from']}.png", COMFY / "input" / "ref1.png")
                out, sec = run(WF / "image_qwen_edit_2511_int8_api.json", {"41.image": "ref1.png", "170:151.prompt": desc["edit"],
                               "170:168.value": "true", "170:169.seed": a.seed, "195.filename_prefix": f"story/{tag}/char_{name}"},
                               f"{tag}_char_{name}")
            else:
                p = (f"Waist-up portrait of a single person (head to waist only, legs not visible), normal human proportions, "
                     f"facing the viewer, neutral plain light beige background. {desc}. {s['style']}")
                out, sec = t2i(p, 1104, 1472, a.seed * 7 + 3, f"story/{tag}/char_{name}", f"{tag}_char_{name}")
            shutil.copy(out, d / "chars" / f"{name}.png"); print("char", name, sec, "s", flush=True)

    if a.stage == "scenes":
        (d / "scenes").mkdir(exist_ok=True)
        def female(c):
            desc = s["characters"].get(c, "")
            desc = desc if isinstance(desc, str) else s["characters"].get(desc.get("from", ""), "")
            return any(w in desc.lower() for w in ("woman", "girl", "bride", "widow", "mother", "daughter"))

        # continuity table (GPT 02:10, standard H): story["continuity"] = {"c1": "Transplanting season, dry stone channel, ..."};
        # a scene's "cont" key appends that block to every shot of the scene so season/water/light/props never drift.
        conts = s.get("continuity", {})

        def render(desc, chars, seed, stem):
            sid = int(stem[1:3])
            cont = conts.get(next((sc.get("cont") for sc in s["scenes"] if sc["id"] == sid), None) or "", "")
            desc = f"{desc}. Continuity: {cont}" if cont else desc
            if not chars:
                return t2i(f"{desc}. {s['style']}", 1664, 928, seed, f"story/{tag}/{stem}", f"{tag}_{stem}")
            who = " and ".join(f"the {'woman' if female(c) else 'man'} in image {i + 1}" for i, c in enumerate(chars))
            p = (f"Create one single unified wide 16:9 scene illustration (not a collage, no split panels, not a character sheet) "
                 f"featuring {who}; " + ("this is the ONLY person in the whole image, shown once, no duplicates, no second copy, "
                                          if len(chars) == 1 else "each of them appears exactly once, ") +
                 f"inside the scene's environment, keeping each character's face, "
                 f"age, hairstyle and clothing exactly the same as in the reference. Scene: {desc}. {s['style']}")
            sets = {"170:151.prompt": p, "170:168.value": "true", "170:169.seed": seed, "195.filename_prefix": f"story/{tag}/{stem}"}
            shutil.copy(d / "chars" / f"{chars[0]}.png", COMFY / "input" / "ref1.png"); sets["41.image"] = "ref1.png"
            if len(chars) == 2:
                shutil.copy(d / "chars" / f"{chars[1]}.png", COMFY / "input" / "ref2.png"); sets["42.image"] = "ref2.png"
            return run(edit_2ref_workflow() if len(chars) == 2 else edit_1ref_workflow(), sets, f"{tag}_{stem}")

        for sc in s["scenes"]:
            if only and str(sc["id"]) not in only:
                continue
            # shot 1 = "image"; extra shots from "shots" -> sNN_b.png, sNN_c.png (each may name its own chars via "shot_chars")
            jobs = [(f"s{sc['id']:02d}", sc["image"], sc["chars"][:2])]
            for j, alt in enumerate(sc.get("shots", [])[:2]):
                sch = sc.get("shot_chars", [None, None])[j] if sc.get("shot_chars") else None
                jobs.append((f"s{sc['id']:02d}_{'bc'[j]}", alt, (sch if sch is not None else sc["chars"])[:2]))
            for stem, desc, chars in jobs:
                dst = d / "scenes" / f"{stem}.png"
                if dst.exists() and not only:
                    continue
                out, sec = render(desc, chars, a.seed * 100 + sc["id"] + (7 if "_" in stem else 0), stem)
                shutil.copy(out, dst); print("scene", stem, chars, sec, "s", flush=True)


if __name__ == "__main__":
    main()
