"""MOSS-Image vs Qwen-Image-2512 / Qwen-Edit-2511 A/B on yadam_ep5(c) scenes -> test_output/story/moss_ab/

  python scripts/moss_ab.py qwen      # Qwen t2i (text only) + Qwen edit with character refs (current local method)
  python scripts/moss_ab.py moss      # MOSS t2i (no layout) + MOSS layout (bounding boxes)
  python scripts/moss_ab.py ref       # face consistency: MOSS edit LoRA (draft + sheet) and MOSS draft -> Qwen-Edit (sheet)
  python scripts/moss_ab.py sheet     # side-by-side _ab.jpg per scene + _ab.jpg overview
Every job is logged to moss_ab/results.jsonl (seconds, peak VRAM incl. ~1 GB desktop). The first job of each model group
runs cold (models unloaded first) and the rest warm, so cold - warm = model load/switch time.
"""
import copy, json, pathlib, shutil, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import run_workflow as rw

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMFY = pathlib.Path(r"C:\AI\ComfyUI\ComfyUI")
WF = ROOT / "workflows"
OUT = ROOT / "test_output/story/moss_ab"; OUT.mkdir(parents=True, exist_ok=True)
EP = ROOT / "test_output/story/yadam_ep5c"
W, H = 1664, 928
SEEDS = (1, 2)
STYLE = ("Korean manhwa webtoon illustration: bold tapered ink contours, flat cel colors with one shadow step, simplified "
         "painterly background with clear figure/background separation, late-Joseon setting, no text, letters or logos "
         "anywhere, single 16:9 full-bleed image, no panel borders.")
CH = {
    "chilbok": "a 62-year-old Joseon hunter with a long weathered face, heavy gray brows, short gray beard, iron-gray topknot under a "
               "dark hemp headband, faded indigo padded jeogori, charcoal baji and a patched brown vest",
    "duman": "a 9-year-old boy with round cheeks, a small mole under his left eye, a short single braid, patched ochre jeogori and gray baji",
    "yeoni": "a 13-year-old girl with an oval face, one long black braid tied with dull red cloth, faded plum jeogori and dark brown chima",
    "gwak": "a 47-year-old charcoal kiln owner with a broad square face, thin black mustache, topknot under a dark horsehair headband, "
            "deep brown padded jeogori, dark olive baji and a broad cloth sash",
}
NIGHT = "Snowy late-Joseon winter night, deep snow, falling snow, bare trees, deep blue sky."


def box(x, y, w, h, desc, kind="obj", text=""):
    return {"x": x, "y": y, "width": w, "height": h, "metadata": {"type": kind, "text": text, "desc": desc, "palette": []}}


SCENES = {
    "tiger": dict(kind="complex", chars=["chilbok", "duman"],
        prompt=f"At a frozen creek, {CH['chilbok']} stands on the near bank holding a paper lantern high above his head with one arm "
               f"and shielding with his other arm {CH['duman']}, who hides behind the hunter's back; across the narrow frozen creek a "
               f"huge Siberian tiger crouches low on a snowy rock ledge, head lowered, glaring at them. Exactly two people and one tiger. {NIGHT}",
        boxes=[box(0, 0, W, H, f"narrow frozen creek in a snowy ravine at night. {NIGHT}"),
               box(1130, 250, 500, 330, "a huge Siberian tiger crouching low on a snowy rock ledge across the frozen creek, head lowered, glaring"),
               box(380, 80, 520, 840, f"{CH['chilbok']}, standing on the near bank, right arm raised holding a lantern high, left arm stretched back shielding the boy"),
               box(110, 380, 310, 540, f"{CH['duman']}, hiding behind the hunter's back and peeking out, frightened"),
               box(690, 50, 170, 210, "a glowing paper lantern held high")],
        char_boxes="3, 4"),
    "wage": dict(kind="complex", chars=["yeoni", "gwak"],
        prompt=f"Pale winter morning in front of a small snowy thatched hut: {CH['yeoni']} stands firmly facing {CH['gwak']}, looking "
               f"up at him as she speaks; he is red-faced and embarrassed and holds out a string of brass coins toward her; behind them a "
               f"loose ring of villagers in white hanbok stares at him; {CH['chilbok']} stands by the hut door in the background.",
        boxes=[box(0, 0, W, H, "a small snowy thatched hut and a packed-earth yard on a pale winter morning, snow on the thatch"),
               box(0, 150, W, 560, "a loose ring of Joseon villagers in white hanbok in the background, staring at the kiln owner"),
               box(760, 180, 230, 520, f"{CH['chilbok']}, standing quietly by the hut door"),
               box(320, 260, 340, 668, f"{CH['yeoni']}, standing firmly, looking up and speaking to the man"),
               box(930, 140, 480, 788, f"{CH['gwak']}, red-faced and embarrassed, leaning forward"),
               box(860, 380, 130, 150, "a string of brass coins held out in the man's hand toward the girl")],
        char_boxes="3, 4, 5"),
    "yeoni_rock": dict(kind="single", chars=["yeoni"],
        prompt=f"Halfway up a snowy ravine at night, {CH['yeoni']} crouches alone under an overhanging snowy boulder, hugging her knees, "
               f"clutching a torn scrap of ochre cloth, staring down toward a dark frozen stream with wet eyes. Only one person. {NIGHT}",
        boxes=[box(0, 0, W, H, f"steep snowy ravine slope at night with a dark frozen stream far below. {NIGHT}"),
               box(180, 60, 960, 560, "a large overhanging snowy boulder forming a shallow shelter"),
               box(430, 360, 420, 540, f"{CH['yeoni']}, crouching under the boulder hugging her knees, clutching a torn scrap of ochre cloth, wet eyes")],
        char_boxes="3"),
    "hands_trap": dict(kind="single", chars=["chilbok"],
        prompt=f"Close-up by a frozen creek at night: the bare weathered hands of {CH['chilbok']} pry open the frost-covered iron jaws of "
               f"a tiger trap half buried in snow; a paper lantern on the snow lights his hands; his gritted face above. Only one person. {NIGHT}",
        boxes=[box(0, 0, W, H, f"snowy bank of a frozen creek at night. {NIGHT}"),
               box(720, 30, 780, 860, f"{CH['chilbok']}, kneeling and leaning over the trap, gritting his teeth"),
               box(520, 560, 560, 330, "a frost-covered iron tiger trap half buried in snow, its jaws being pried open by two bare weathered hands"),
               box(180, 540, 220, 330, "a glowing paper lantern standing on the snow")],
        char_boxes="2"),
    "thumb_trap": dict(kind="thumb", chars=[],
        prompt=f"Low close-up on a narrow snowy ravine path at night: a heavy rusted iron tiger trap with jagged open jaws, half buried in "
               f"fresh snow, fills the foreground; far up the winding path two tiny silhouettes of children (an older girl and a small boy) "
               f"walk hand in hand. {NIGHT}",
        boxes=[box(0, 0, W, H, f"narrow winding snowy ravine path between rock walls at night. {NIGHT}"),
               box(60, 420, 940, 490, "a heavy rusted iron tiger trap with jagged open jaws half buried in fresh snow, very close to the camera"),
               box(1060, 190, 190, 230, "two tiny silhouettes of children, an older girl in a plum jeogori and a small boy, walking hand in hand far up the path")],
        char_boxes=""),
    "thumb_whistle": dict(kind="thumb", chars=["chilbok"], text="짧게 두 번",
        prompt=f"YouTube thumbnail. Close-up of {CH['chilbok']} at a snowy ravine mouth at night, head turned sharply toward the dark "
               f"ravine, eyes wide, frozen, listening to a distant whistle. In the upper-left corner the Korean title text \"짧게 두 번\" "
               f"in huge bold white letters with a thick black outline. {NIGHT}",
        boxes=[box(0, 0, W, H, f"dark snowy ravine mouth at night. {NIGHT}"),
               box(50, 50, 660, 230, "huge bold white Korean title letters with a thick black outline, top-left", kind="text", text="짧게 두 번"),
               box(760, 60, 840, 868, f"{CH['chilbok']}, close-up, head turned sharply toward the dark ravine, eyes wide, frozen, listening")],
        char_boxes="3"),
}


def load(name):
    api = json.loads((WF / name).read_text(encoding="utf-8"))
    for v in api.values():
        v.pop("_meta", None)
    return api


def job(api, label, dst, first):
    res = rw.run(api, label, timeout=3600, keep=not first)
    res["cold"] = first
    with open(OUT / "results.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")
    if res["status"] != "success":
        print("FAIL", label, res.get("error"), flush=True); return False
    shutil.copy(COMFY / "output" / res["outputs"][0], dst)
    print(label, res["seconds"], "s", res["peak_vram_mb"], "MB", "(cold)" if first else "", flush=True)
    return True


def done(dst):
    return dst.exists()


def qwen():
    first = True
    for sid, sc in SCENES.items():          # Qwen-Image-2512 text only (same prompt, inline character descriptions)
        for seed in SEEDS:
            dst = OUT / f"{sid}_qwen_s{seed}.png"
            if done(dst): continue
            api = load("image_qwen2512_api.json")
            rw.apply_sets(api, [f"238:227.text={sc['prompt']} {STYLE}", "238:228.text=低分辨率，低画质，肢体畸形，手指畸形，文字，字母，水印",
                                "238:229.value=true", f"238:232.width={W}", f"238:232.height={H}", f"238:230.seed={seed}",
                                f"60.filename_prefix=moss_ab/{sid}_qwen"])
            first = not job(api, f"qwen_t2i_{sid}_{seed}", dst, first) and first
    first = True
    for sid, sc in SCENES.items():          # current local method: Qwen-Edit-2511 with 1-2 character sheets
        if not sc["chars"]: continue
        for seed in SEEDS:
            dst = OUT / f"{sid}_qwenref_s{seed}.png"
            if done(dst): continue
            two = len(sc["chars"]) >= 2
            api = load("image_qwen_edit_2511_2ref_api.json" if two else "image_qwen_edit_2511_1ref_api.json")
            who = " and ".join(f"the person in image {i + 1}" for i in range(2 if two else 1))
            p = (f"Create one single unified wide 16:9 scene illustration (not a collage) featuring {who}, each exactly once, keeping "
                 f"faces, age, hair and clothing exactly as in the references. Scene: {sc['prompt']} {STYLE}")
            shutil.copy(EP / "chars" / f"{sc['chars'][0]}.png", COMFY / "input" / "ref1.png")
            sets = [f"170:151.prompt={p}", "170:168.value=true", f"170:169.seed={seed}", "41.image=ref1.png",
                    f"195.filename_prefix=moss_ab/{sid}_qwenref"]
            if two:
                shutil.copy(EP / "chars" / f"{sc['chars'][1]}.png", COMFY / "input" / "ref2.png"); sets.append("42.image=ref2.png")
            rw.apply_sets(api, sets)
            first = not job(api, f"qwen_ref_{sid}_{seed}", dst, first) and first


def moss():
    first = True
    for sid, sc in SCENES.items():
        for seed in SEEDS:
            for mode in ("t2i", "layout"):
                dst = OUT / f"{sid}_moss{mode}_s{seed}.png"
                if done(dst): continue
                api = load(f"image_moss_{mode}_api.json")
                api["7"]["inputs"]["seed"] = seed
                api["9"]["inputs"]["filename_prefix"] = f"moss_ab/{sid}_moss{mode}"
                if mode == "t2i":
                    api["4"]["inputs"]["text"] = f"{sc['prompt']} {STYLE}"
                else:
                    api["25"]["inputs"]["editor_state"] = {"__value__": sc["boxes"]}   # a bare list would be read as a link
                    api["27"]["inputs"]["prompt"] = f"{sc['prompt']} {STYLE}"
                    api["27"]["inputs"]["character_boxes"] = sc["char_boxes"]
                first = not job(api, f"moss_{mode}_{sid}_{seed}", dst, first) and first


def ref():
    """Faces: the MOSS t2i model has no image input, so test (a) MOSS edit LoRA: layout draft + character sheet(s);
    (b) MOSS layout draft -> Qwen-Edit-2511 (draft latent + sheet), the Exp-A route used for complex local scenes."""
    first = True
    for sid in ("tiger", "wage", "yeoni_rock", "hands_trap"):
        sc = SCENES[sid]; src = OUT / f"{sid}_mosslayout_s1.png"
        dst = OUT / f"{sid}_mossedit_s1.png"
        if src.exists() and not done(dst):
            api = load("image_moss_edit_api.json")
            shutil.copy(src, COMFY / "input" / "moss_src.png")
            shutil.copy(EP / "chars" / f"{sc['chars'][0]}.png", COMFY / "input" / "moss_ref1.png")
            names = ["the " + ("girl" if c == "yeoni" else "boy" if c == "duman" else "man") for c in sc["chars"][:2]]
            p = (f"Image 1 is the scene. Image 2 is the character sheet of {names[0]}" +
                 (f"; image 3 is the character sheet of {names[1]}" if len(sc["chars"]) > 1 else "") +
                 ". Redraw image 1 keeping its composition, poses, setting and art style, but give each of those characters exactly "
                 "the face, hair and clothes from their character sheet. Do not add people.")
            if len(sc["chars"]) > 1:
                api["42"] = {"class_type": "LoadImage", "inputs": {"image": "moss_ref2.png"}}
                shutil.copy(EP / "chars" / f"{sc['chars'][1]}.png", COMFY / "input" / "moss_ref2.png")
                for n in ("39", "36"):
                    api[n]["inputs"]["images.image_2"] = ["42", 0]
            api["39"]["inputs"]["prompt"] = p
            api["9"]["inputs"]["filename_prefix"] = f"moss_ab/{sid}_mossedit"
            first = not job(api, f"moss_edit_{sid}", dst, first) and first
    first = True
    sys.path.insert(0, str(ROOT / "scripts")); import story_images as si
    for sid in ("tiger", "wage", "yeoni_rock", "hands_trap"):
        sc = SCENES[sid]; src = OUT / f"{sid}_mosslayout_s1.png"; dst = OUT / f"{sid}_moss2qwen_s1.png"
        if not src.exists() or done(dst): continue
        api = load(si.edit_3ref_workflow().name)
        shutil.copy(src, COMFY / "input" / "ref1.png")
        shutil.copy(EP / "chars" / f"{sc['chars'][0]}.png", COMFY / "input" / "ref2.png")
        shutil.copy(EP / "chars" / f"{sc['chars'][-1]}.png", COMFY / "input" / "ref3.png")
        who = (f"the {'girl' if sc['chars'][0] == 'yeoni' else 'man'} in image 1 must have exactly the face, hair and clothes of image 2"
               + (f", and the {'boy' if sc['chars'][1] == 'duman' else 'man'} those of image 3" if len(sc["chars"]) > 1 else ""))
        rw.apply_sets(api, [f"170:151.prompt=Keep image 1's composition, poses, setting and art style exactly; {who}. Do not add people. No text.",
                            "41.image=ref1.png", "42.image=ref2.png", "43.image=ref3.png", "170:168.value=true",
                            "170:169.denoise=0.75", "170:169.seed=1", f"195.filename_prefix=moss_ab/{sid}_moss2qwen"])
        first = not job(api, f"moss2qwen_{sid}", dst, first) and first


def sheet():
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf", 26)
    cols = [("qwen", "Qwen-2512 t2i"), ("qwenref", "Qwen-Edit+시트"), ("mosst2i", "MOSS t2i"), ("mosslayout", "MOSS 레이아웃"),
            ("mossedit", "MOSS 편집+시트"), ("moss2qwen", "MOSS→Qwen-Edit")]
    tw, th = 480, 268
    rows = []
    for sid in SCENES:
        for seed in SEEDS:
            cells = [(lab, OUT / f"{sid}_{k}_s{seed}.png") for k, lab in cols]
            if any(p.exists() for _, p in cells):
                rows.append((f"{sid} s{seed}", cells))
    img = Image.new("RGB", (220 + tw * len(cols), 40 + th * len(rows)), (24, 24, 24)); d = ImageDraw.Draw(img)
    for j, (_, lab) in enumerate(cols):
        d.text((220 + j * tw + 10, 6), lab, font=f, fill=(255, 255, 255))
    for i, (name, cells) in enumerate(rows):
        y = 40 + i * th
        d.text((10, y + th // 2 - 14), name, font=f, fill=(255, 230, 150))
        for j, (_, p) in enumerate(cells):
            if p.exists():
                img.paste(Image.open(p).convert("RGB").resize((tw - 4, th - 4)), (220 + j * tw, y))
    img.save(OUT / "_ab.jpg", quality=88)
    for sid in SCENES:   # per-scene sheets at a readable size for scoring
        cells = [(lab, OUT / f"{sid}_{k}_s{s}.png") for s in SEEDS for k, lab in cols]
        cells = [(f"{lab} s{p.stem[-1]}", p) for lab, p in cells if p.exists()]
        n = len(cells); c = 3; r = (n + c - 1) // c
        sh = Image.new("RGB", (c * 832, r * 500), (24, 24, 24)); dd = ImageDraw.Draw(sh)
        for k, (lab, p) in enumerate(cells):
            x, y = (k % c) * 832, (k // c) * 500
            sh.paste(Image.open(p).convert("RGB").resize((828, 462)), (x, y + 36)); dd.text((x + 8, y + 4), lab, font=f, fill=(255, 255, 255))
        sh.save(OUT / f"_ab_{sid}.jpg", quality=88)
    print("wrote", OUT / "_ab.jpg", len(rows), "rows")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    {"qwen": qwen, "moss": moss, "ref": ref, "sheet": sheet}[sys.argv[1]]()
