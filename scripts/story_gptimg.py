"""GPT image generation for key shots + approval -> automatic LoRA dataset collection.

  python scripts/story_gptimg.py gen     <story_dir> [--only s01,s11,thumb] [--force]
  python scripts/story_gptimg.py approve <story_dir> s01 s11 [--by claude|user]
  python scripts/story_gptimg.py collect <story_dir>          (re-sync every approved shot of this story)
  python scripts/story_gptimg.py status  <story_dir>

Which shots go to GPT (codex image_gen via the baoyu codex-imagegen wrapper; uses the codex subscription quota):
  story.json "gpt": ["thumb", "s01", "s11", ...] — thumbnail, opening, multi-character key scenes. Everything else stays
  local (story_images.py scenes -> stylize with a GPT shot as the style anchor).
Prompt per stem: scene "gpt_prompt" (shot 1) / "gpt_shots" {"b": ...} (extra shots) override, else the local description.
  "thumb": story["thumb"]["gpt_prompt"] + story["thumb"]["chars"].
Style: <dir>/style_bible.md, else config/style_bible_yadam.md. Character refs: chars/<name>.png (up to 3, in order).
Output: scenes/gpt/<stem>.png (GPT original, never overwritten by local edits) -> copied to scenes/<stem>.png
  (thumb -> scenes/gpt/thumb.png only). The replaced image is kept in scenes/_old/.

Approval = a human or Claude looked at the GPT original and it matches the story and the style. Approved shots are copied
automatically to the style-LoRA dataset C:/AI/train/data/style_gpt/ (<story>_<stem>.png + caption .txt with the trigger
word), deduplicated by content hash, listed in manifest.json; style_gpt.toml is (re)written for musubi-tuner.
Only unedited GPT originals are collected (a sha1 mismatch with the approval record = edited after approval -> skipped).
"""
import argparse, hashlib, json, pathlib, shutil, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
WRAP = pathlib.Path(r"C:\AI\skills_eval\baoyu-skills\skills\baoyu-image-gen\scripts\codex-imagegen\main.ts")
LORA = pathlib.Path(r"C:\AI\train\data\style_gpt")
TRIG = "nyadam style, Korean manhwa webtoon illustration"


def sha1(p):
    return hashlib.sha1(pathlib.Path(p).read_bytes()).hexdigest()


def load(d):
    return json.load(open(d / "story.json", encoding="utf-8-sig"))


def shot_spec(s, stem):
    """stem -> (description, [char names])"""
    if stem == "thumb":
        th = s.get("thumb", {})
        return th.get("gpt_prompt") or th.get("image", ""), th.get("chars", [])
    sid, k = int(stem[1:3]), stem[4:] if "_" in stem else ""
    sc = next(x for x in s["scenes"] if x["id"] == sid)
    if not k:
        return sc.get("gpt_prompt") or sc["image"], sc.get("gpt_chars", sc["chars"])
    j = "bc".index(k)
    desc = sc.get("gpt_shots", {}).get(k) or sc.get("shots", [""] * 3)[j]
    chars = (sc.get("shot_chars") or [None, None])[j]
    return desc, chars if chars is not None else sc["chars"]


def prompt_for(d, s, stem):
    desc, chars = shot_spec(s, stem)
    bible = (d / "style_bible.md") if (d / "style_bible.md").exists() else ROOT / "config" / "style_bible_yadam.md"
    roster = []
    for i, c in enumerate(chars[:3], 1):
        cd = s["characters"].get(c, "")
        cd = cd if isinstance(cd, str) else s["characters"].get(cd.get("from", ""), "")
        roster.append(f"- {c} (reference image {i}): {cd}")
    n = len(chars)
    who = (f"Characters ({n}; each appears exactly once, faces/clothes exactly as in the reference sheets):\n" + "\n".join(roster)
           if n else "")
    kind = ("YouTube thumbnail key art: one strong, readable moment, large faces, leave the upper-left third calm and "
            "uncluttered for a title to be added later (do NOT draw any text)" if stem == "thumb" else "story scene")
    return (f"Create ONE 16:9 full-bleed illustration ({kind}; no panel borders, absolutely no text, letters or logos). "
            f"Follow this style bible exactly:\n\n{bible.read_text(encoding='utf-8')}\n\n{who}\n\nScene: {desc}\n").strip() + "\n", chars


def gen(d, s, stem, force=False):
    out = d / "scenes" / "gpt" / f"{stem}.png"
    if out.exists() and not force:
        return "exists"
    prompt, chars = prompt_for(d, s, stem)
    (d / "scenes" / "gpt").mkdir(parents=True, exist_ok=True)
    pf = d / "scenes" / "gpt" / f"{stem}.prompt.md"; pf.write_text(prompt, encoding="utf-8")
    tmp = d / "scenes" / "gpt" / f"_{stem}.png"
    cmd = ["npx.cmd" if sys.platform == "win32" else "npx", "-y", "bun", str(WRAP), "--image", str(tmp),
           "--prompt-file", str(pf), "--aspect", "16:9", "--timeout", "600000", "--retries", "1",
           "--cache-dir", str(d / "scenes" / "gpt" / ".cache"), "--log-file", str(d / "scenes" / "gpt" / "gen_log.jsonl")]
    for c in chars[:3]:
        cmd += ["--ref", str(d / "chars" / f"{c}.png")]
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    line = next((l for l in reversed((r.stdout or "").splitlines()) if l.startswith("{")), "{}")
    res = json.loads(line)
    if res.get("status") != "ok" or not tmp.exists():
        return f"FAIL {res.get('error_kind', '')} {res.get('error', (r.stderr or '')[-300:])}"
    tmp.replace(out)
    if stem != "thumb":
        dst = d / "scenes" / f"{stem}.png"
        if dst.exists():
            (d / "scenes" / "_old").mkdir(exist_ok=True)
            shutil.copy(dst, d / "scenes" / "_old" / f"{stem}_{time.strftime('%H%M%S')}.png")
        shutil.copy(out, dst)
        for c in (d / "clips").glob(f"{stem.split('_')[0]}_{'1' if '_' not in stem else 'bc'.index(stem[4]) + 2}.mp4"):
            c.unlink()   # old motion clip no longer matches the new still
    return f"ok {round(time.time() - t)}s"


def approvals(d):
    p = d / "review" / "gpt_approved.json"
    return json.load(open(p, encoding="utf-8")) if p.exists() else {}


def collect(d, s):
    """Copy every approved, unedited GPT original of this story into the LoRA dataset (idempotent)."""
    from PIL import Image
    LORA.mkdir(parents=True, exist_ok=True)
    mf = LORA / "manifest.json"
    man = json.load(open(mf, encoding="utf-8")) if mf.exists() else {}
    added, skipped = [], []
    for stem, ap in approvals(d).items():
        src = d / "scenes" / "gpt" / f"{stem}.png"
        if not src.exists() or sha1(src) != ap["sha1"]:
            skipped.append(f"{stem}(changed/missing)"); continue
        if ap["sha1"] in man:
            continue
        name = f"{d.name}_{stem}"
        im = Image.open(src).convert("RGB"); im.thumbnail((1344, 768)); im.save(LORA / f"{name}.png")
        (LORA / f"{name}.txt").write_text(f"{TRIG}. {ap['caption']}", encoding="utf-8")
        man[ap["sha1"]] = dict(file=f"{name}.png", story=d.name, stem=stem, by=ap["by"], at=ap["at"], src=str(src))
        added.append(stem)
    json.dump(man, open(mf, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    (LORA.parent / "style_gpt.toml").write_text(
        f'[general]\nresolution = [1024, 576]\ncaption_extension = ".txt"\nbatch_size = 1\nenable_bucket = true\n'
        f'bucket_no_upscale = false\n\n[[datasets]]\nimage_directory = "{LORA.as_posix()}"\n'
        f'cache_directory = "{(LORA.parent / "style_gpt_cache").as_posix()}"\nnum_repeats = 1\n', encoding="utf-8")
    return added, skipped, len(man)


def caption(s, stem):
    desc, chars = shot_spec(s, stem)
    for c in chars:   # names mean nothing to the LoRA: replace with a short visual tag
        cd = s["characters"].get(c, "")
        cd = cd if isinstance(cd, str) else ""
        tag = cd.split(" with ")[0].replace("A ", "a ").replace("An ", "an ") if cd else c
        desc = desc.replace(c, tag, 1).replace(c, "they")
    return " ".join(desc.split()).strip(" .")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gen", "approve", "collect", "status"]); ap.add_argument("story_dir")
    ap.add_argument("stems", nargs="*"); ap.add_argument("--only", default=""); ap.add_argument("--force", action="store_true")
    ap.add_argument("--by", default="claude")
    a = ap.parse_args()
    d = pathlib.Path(a.story_dir).resolve(); s = load(d)
    if a.cmd == "gen":
        stems = [x for x in a.only.split(",") if x] or s.get("gpt", [])
        for st in stems:
            print(st, gen(d, s, st, a.force), flush=True)
    elif a.cmd == "approve":
        apv = approvals(d); (d / "review").mkdir(exist_ok=True)
        for st in a.stems:
            src = d / "scenes" / "gpt" / f"{st}.png"
            if not src.exists():
                print(st, "no GPT original -> not approvable"); continue
            apv[st] = dict(sha1=sha1(src), caption=caption(s, st), by=a.by, at=time.strftime("%Y-%m-%d %H:%M"))
        json.dump(apv, open(d / "review" / "gpt_approved.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        added, skipped, n = collect(d, s)
        print(f"approved {a.stems}; LoRA dataset +{len(added)} {added} skipped {skipped} -> {n} images in {LORA}")
    elif a.cmd == "collect":
        added, skipped, n = collect(d, s)
        print(f"lora_collect +{len(added)} {added} skipped {skipped} -> {n} images")
    else:
        apv = approvals(d)
        for st in s.get("gpt", []):
            p = d / "scenes" / "gpt" / f"{st}.png"
            print(st, "drawn" if p.exists() else "-", "approved" if st in apv else "")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
