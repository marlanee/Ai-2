"""Test B: Kandinsky 6.0 Lite-distill-5s image-to-video (video only) vs LTX-2.5 (story_motion.py clips) on yadam_ep5c.

  python scripts/kandinsky_ab.py motion   # 6 scenes, same first frame + same story.json motion prompt as the LTX clips
  python scripts/kandinsky_ab.py lips     # 2 dialogue shots with <S>line<E>, then our Qwen3-TTS line muxed on top
  python scripts/kandinsky_ab.py sheets   # 6-frame strips per clip: LTX row vs Kandinsky row -> _cmp_<id>.jpg
Out: test_output/story/model_ab_2611/B_kandinsky/   (results.jsonl = seconds / peak VRAM / cold flag per clip)

Settings (pack README for distilled Lite): 10 steps, CFG 1, euler/simple, 864x480, 121 frames @24 fps (5 s), Beautify off,
no MagCache (Pro only), no SR, audio VAE not loaded (it needs .pth/.pt pickles we did not download) -> video only.
"""
import json, pathlib, shutil, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import run_workflow as rw

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMFY = pathlib.Path(r"C:\AI\ComfyUI\ComfyUI")
FF = r"C:\AI\tools\ffmpeg\bin\ffmpeg.exe"
EP = ROOT / "test_output/story/yadam_ep5c"
OUT = ROOT / "test_output/story/model_ab_2611/B_kandinsky"; OUT.mkdir(parents=True, exist_ok=True)
TAIL = (" Keep the exact same characters, faces, clothes and 2D illustration art style; smooth natural motion; no new people; "
        "no text.")   # same tail as story_motion.py (its audio sentence dropped: video only here)
NEG = "Static, worst quality, low quality, ugly, deformed, melting, morphing faces, extra people, text, watermark, walking backwards"
SHOTS = [("s01", 1, 0), ("s09", 9, 0), ("s10", 10, 0), ("s11", 11, 0), ("s12", 12, 0), ("s16", 16, 0)]
LIPS = [  # (stem, image, speaker line idx in story scene, spoken text, who)
    ("lip_s05", "s05", 5, 1, "The old hunter in the indigo jacket shouts urgently at the closed door"),
    ("lip_s16", "s16", 16, 2, "The girl in the plum jeogori looks up at the kiln owner and speaks firmly"),
]


def wf(image, prompt, seed, prefix):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "Kandinsky-6.0-Lite-distill-5s-Diffusers\\transformer\\diffusion_pytorch_model.safetensors",
                                                    "weight_dtype": "default"}},
        "2": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": "qwen_2.5_vl_7b.safetensors", "clip_name2": "clip_l.safetensors",
                                                        "type": "kandinsky5", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "hunyuan_video_vae_bf16.safetensors"}},
        "5": {"class_type": "Kandinsky6TextEncode", "inputs": {"clip": ["2", 0], "video_caption": prompt, "audio_caption": ""}},
        "6": {"class_type": "Kandinsky6TextEncode", "inputs": {"clip": ["2", 0], "video_caption": NEG, "audio_caption": ""}},
        "7": {"class_type": "Kandinsky6EmptyLatent", "inputs": {"width": 864, "height": 480, "length": 121, "fps": 24.0, "batch_size": 1}},
        "8": {"class_type": "LoadImage", "inputs": {"image": image}},
        "9": {"class_type": "ImageScale", "inputs": {"image": ["8", 0], "upscale_method": "bilinear", "width": 864, "height": 480, "crop": "center"}},
        "10": {"class_type": "VAEEncode", "inputs": {"pixels": ["9", 0], "vae": ["3", 0]}},
        "11": {"class_type": "Kandinsky6ImageToVideoAudio", "inputs": {"positive": ["5", 0], "negative": ["6", 0], "empty_latent": ["7", 0],
                                                                       "reference_latent": ["10", 0]}},
        "12": {"class_type": "Kandinsky6Sampler", "inputs": {"model": ["1", 0], "seed": seed, "steps": 10, "cfg": 1.0, "sampler_name": "euler",
                                                            "scheduler": "simple", "positive": ["11", 0], "negative": ["11", 1],
                                                            "latent_image": ["11", 2], "denoise": 1.0}},
        "13": {"class_type": "Kandinsky6RemoveReferenceLatent", "inputs": {"joint_latent": ["12", 0]}},
        "14": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["13", 0], "vae": ["3", 0], "tile_size": 512, "overlap": 64,
                                                         "temporal_size": 64, "temporal_overlap": 8}},
        "18": {"class_type": "CreateVideo", "inputs": {"images": ["14", 0], "fps": 24.0, "bit_depth": 8}},
        "19": {"class_type": "SaveVideo", "inputs": {"video": ["18", 0], "filename_prefix": prefix, "format": "auto", "format.codec": "auto"}},
    }


def gen(stem, img, prompt, seed, first):
    dst = OUT / f"{stem}_k6.mp4"
    if dst.exists():
        return first
    name = f"k6_{stem}.png"; shutil.copy(img, COMFY / "input" / name)
    res = rw.run(wf(name, prompt, seed, f"model_ab_2611/k6_{stem}"), f"k6_{stem}", timeout=3600, keep=not first)
    res["cold"] = first
    with open(OUT / "results.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")
    if res["status"] != "success":
        print("FAIL", stem, res.get("error"), flush=True); return first
    shutil.copy(COMFY / "output" / res["outputs"][0], dst)
    print(stem, res["seconds"], "s", res["peak_vram_mb"], "MB", "(cold)" if first else "", flush=True)
    return False


def motion():
    s = json.load(open(EP / "story.json", encoding="utf-8-sig")); S = {x["id"]: x for x in s["scenes"]}
    first = True
    for stem, sid, k in SHOTS:
        prompt = S[sid]["motion"][k] + TAIL
        (OUT / f"{stem}_prompt.txt").write_text(prompt, encoding="utf-8")
        shutil.copy(EP / "clips" / f"s{sid:02d}_{k + 1}.mp4", OUT / f"{stem}_ltx.mp4")
        first = gen(stem, EP / "scenes" / f"{stem}.png", prompt, 42, first)


def lips():
    s = json.load(open(EP / "story.json", encoding="utf-8-sig")); S = {x["id"]: x for x in s["scenes"]}
    rows = json.load(open(EP / "tts/lines.json", encoding="utf-8"))
    first = True
    for stem, img, sid, idx, who in LIPS:
        line = S[sid]["lines"][idx]
        spoken = line.split('"')[1] if '"' in line else line
        prompt = (f"{who}, her/his lips moving clearly with the words, saying <S>{spoken}<E>. Medium close-up, the speaker's face "
                  f"clearly visible, small natural head movement." + TAIL)
        (OUT / f"{stem}_prompt.txt").write_text(prompt, encoding="utf-8")
        first = gen(stem, EP / "scenes" / f"{img}.png", prompt, 7, first)
        v = OUT / f"{stem}_k6.mp4"
        if v.exists():   # our TTS line on top (Kandinsky audio was never decoded) -> judge mouth vs our voice
            wav = EP / "tts" / next(r["file"] for r in rows if r["scene"] == sid and r["idx"] == idx)
            subprocess.run([FF, "-v", "error", "-y", "-i", str(v), "-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                            "-c:a", "aac", "-shortest", str(OUT / f"{stem}_k6_ourtts.mp4")], check=True)


def strip(mp4, n=6, w=320):
    from PIL import Image
    d = float(subprocess.run([r"C:\AI\tools\ffmpeg\bin\ffprobe.exe", "-v", "error", "-show_entries", "format=duration", "-of",
                              "csv=p=0", str(mp4)], capture_output=True, text=True).stdout.strip())
    ims = []
    for i in range(n):
        t = d * (i + 0.5) / n
        raw = subprocess.run([FF, "-v", "error", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1", "-vf", f"scale={w}:{w * 9 // 16}",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        ims.append(Image.frombytes("RGB", (w, w * 9 // 16), raw))
    return ims


def sheets():
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf", 22)
    stems = [x[0] for x in SHOTS] + [x[0] for x in LIPS]
    for stem in stems:
        rows = [(lab, OUT / f"{stem}_{k}.mp4") for k, lab in (("ltx", "LTX-2.5 640x352"), ("k6", "Kandinsky6 Lite 864x480"))]
        rows = [(lab, p) for lab, p in rows if p.exists()]
        if not rows: continue
        sh = Image.new("RGB", (160 + 6 * 320, len(rows) * 180), (20, 20, 20)); d = ImageDraw.Draw(sh)
        for r, (lab, p) in enumerate(rows):
            d.text((8, r * 180 + 70), lab.replace(" ", "\n", 1), font=f, fill=(255, 230, 150))
            for i, im in enumerate(strip(p)):
                sh.paste(im, (160 + i * 320, r * 180))
        sh.save(OUT / f"_cmp_{stem}.jpg", quality=88)
    print("sheets done")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    {"motion": motion, "lips": lips, "sheets": sheets}[sys.argv[1]]()
