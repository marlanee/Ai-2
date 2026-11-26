"""Test C: LTX Foley LoRA (video -> audio) on our LTX-2.5 with built-in nodes only, vs current Stable Audio 3 beds.

  python scripts/foley_ab.py run       # 4 ep5c clips + whistle timing test -> <name>_foley.wav / _foley.mp4
  python scripts/foley_ab.py blind     # blind A/B per clip (foley vs sfx/sNN.flac) -> blind/A1.mp4 ... + answer.txt
Out: test_output/story/model_ab_2611/C_foley/

Graph (docs.ltx.io V2A guide, rebuilt natively): LoadVideo -> GetVideoComponents -> LTX video VAE encode -> LTXVFreezeLatent
(video kept clean = mask_video false) + LTXVEmptyLatentAudio -> LTXVConcatAVLatent -> LTX-2.5 distilled int8 + Foley LoRA
(LTX-2.3 file, strength 1.0; the guide says it is validated on 2.3 only) -> separate -> audio VAE decode -> muxed on the
original frames. Prompt style per guide: concrete sound sources, ending "No speech is present. No music is present."
"""
import json, pathlib, shutil, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import run_workflow as rw

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMFY = pathlib.Path(r"C:\AI\ComfyUI\ComfyUI")
FF = r"C:\AI\tools\ffmpeg\bin\ffmpeg.exe"
EP = ROOT / "test_output/story/yadam_ep5c"
OUT = ROOT / "test_output/story/model_ab_2611/C_foley"; OUT.mkdir(parents=True, exist_ok=True)
LORA = "ltx23_foley\\ltx-2.3-22b-lora-foley-v2a-1.0.safetensors"   # name as ComfyUI lists it on Windows
NEG = ("music, melody, song, singing, vocals, score, soundtrack, beat, rhythm bed, instrumental backing, speech, dialogue, talking, "
       "narration, tinny, thin, harsh, clipped, distorted, low bitrate")
END = " No speech is present. No music is present."
CLIPS = [
    ("footsteps", "s01_2", 1, "Two children walk slowly through deep fresh snow at night: soft crunching footsteps in snow, a light cold wind."),
    ("trap", "s09_1", 9, "An old man pries open a heavy frozen iron leg-hold trap by a creek: metallic creak and grinding of rusty iron jaws, "
                         "a sharp metal clank, snow crunching under his knees."),
    ("tiger", "s11_1", 11, "A huge tiger crouches across a frozen creek at night: deep slow heavy breathing and a low rumbling growl, faint wind."),
    ("lantern", "s10_1", 10, "A paper lantern held low by a frozen creek at night: a small candle flame flickering and softly fluttering, "
                             "quiet crackle, faint wind in bare trees."),
    ("whistle", "s01_3", 1, "In a dark snowy ravine a person whistles a signal: two short sharp whistles, a pause, then one long whistle "
                            "from far away, echoing."),
]


def wf(video, prompt, seed, prefix, audio_cfg):
    return {
        "1": {"class_type": "LoadVideo", "inputs": {"file": video}},
        "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
        "10": {"class_type": "UNETLoader", "inputs": {"unet_name": "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
                                                      "weight_dtype": "default"}},
        "11": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["10", 0], "lora_name": LORA, "strength_model": 1.0}},
        "12": {"class_type": "CLIPLoader", "inputs": {"clip_name": "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors",
                                                      "type": "ltxv", "device": "default"}},
        "13": {"class_type": "VAELoader", "inputs": {"vae_name": "ltx-2.5-video-vae-bf16.safetensors"}},
        "14": {"class_type": "VAELoader", "inputs": {"vae_name": "ltx-2.5-audio-vae-bf16.safetensors"}},
        "20": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["12", 0], "text": prompt + END}},
        "21": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["12", 0], "text": NEG}},
        "22": {"class_type": "LTXVConditioning", "inputs": {"positive": ["20", 0], "negative": ["21", 0], "frame_rate": 24.0}},
        "30": {"class_type": "VAEEncode", "inputs": {"pixels": ["2", 0], "vae": ["13", 0]}},
        "31": {"class_type": "LTXVFreezeLatent", "inputs": {"latent": ["30", 0]}},
        "32": {"class_type": "LTXVEmptyLatentAudio", "inputs": {"frames_number": 121, "frame_rate": 24.0, "batch_size": 1, "audio_vae": ["14", 0]}},
        "33": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": ["31", 0], "audio_latent": ["32", 0]}},
        "40": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "41": {"class_type": "LTXVDualCFGGuider", "inputs": {"model": ["11", 0], "positive": ["22", 0], "negative": ["22", 1],
                                                             "video_cfg": 1.0, "audio_cfg": audio_cfg}},
        "42": {"class_type": "SamplerEulerAncestral", "inputs": {"eta": 0.0, "s_noise": 1.0}},
        "43": {"class_type": "ManualSigmas", "inputs": {"sigmas": "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421"}},
        "44": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["40", 0], "guider": ["41", 0], "sampler": ["42", 0],
                                                                 "sigmas": ["43", 0], "latent_image": ["33", 0]}},
        "50": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["44", 1]}},
        "51": {"class_type": "LTXVAudioVAEDecode", "inputs": {"samples": ["50", 1], "audio_vae": ["14", 0]}},
        "52": {"class_type": "SaveAudio", "inputs": {"audio": ["51", 0], "filename_prefix": prefix}},
    }


def run():
    first = True
    for name, clip, sid, prompt in CLIPS:
        for cfg in (1.0, 3.0):   # distilled model: CFG 1 is native; 3 = nearer the guide's audio guidance (6 is for the dev model)
            dst = OUT / f"{name}_cfg{cfg:g}_foley.wav"
            if dst.exists(): continue
            vn = f"foley_{clip}.mp4"; shutil.copy(EP / "clips" / f"{clip}.mp4", COMFY / "input" / vn)
            res = rw.run(wf(vn, prompt, 42, f"model_ab_2611/foley_{name}_cfg{cfg:g}", cfg), f"foley_{name}_cfg{cfg:g}", 1800, keep=not first)
            res["cold"] = first
            with open(OUT / "results.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
            if res["status"] != "success":
                print("FAIL", name, res.get("error"), flush=True)
                if first: return   # the first job decides whether the 2.3 LoRA works on 2.5 at all
                continue
            first = False
            # outputs also list LoadVideo's input preview -> take the saved audio file only
            src = COMFY / "output" / next(o for o in res["outputs"] if o.lower().endswith((".flac", ".wav", ".mp3", ".opus")))
            subprocess.run([FF, "-v", "error", "-y", "-i", str(src), "-ar", "48000", str(dst)], check=True)
            subprocess.run([FF, "-v", "error", "-y", "-i", str(EP / "clips" / f"{clip}.mp4"), "-i", str(dst), "-map", "0:v", "-map", "1:a",
                            "-c:v", "copy", "-c:a", "aac", "-shortest", str(OUT / f"{name}_cfg{cfg:g}_foley.mp4")], check=True)
            print(name, cfg, res["seconds"], "s", res["peak_vram_mb"], "MB", flush=True)


def blind():
    """Per clip: foley (best cfg chosen later by ear -> both kept) vs Stable Audio bed sfx/sNN.flac, on the same frames."""
    import random
    random.seed(2611)
    bd = OUT / "blind"; bd.mkdir(exist_ok=True)
    ans, k = [], 0
    for name, clip, sid, _ in CLIPS:
        # cfg 3 left out: on the distilled 2.5 model it gave silence (-82 dBFS) or single clipped clicks
        cands = [("LTX Foley cfg1", OUT / f"{name}_cfg1_foley.wav")]
        sa = EP / "sfx" / f"s{sid:02d}.flac"
        if name != "whistle" and sa.exists():
            cands.append(("Stable Audio 3 (현행 sfx)", sa))
        if name == "whistle":
            cands.append(("합성 휘파람(story_video cue_track)", OUT / "whistle_synth.wav"))
        cands = [c for c in cands if c[1].exists()]
        random.shuffle(cands)
        for lab, wav in cands:
            k += 1
            subprocess.run([FF, "-v", "error", "-y", "-i", str(EP / "clips" / f"{clip}.mp4"), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                            "-af", "loudnorm=I=-20:TP=-2", "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-shortest", str(bd / f"A{k}.mp4")],
                           check=True)
            ans.append(f"A{k}\t{name}\t{lab}")
    (bd / "answer.txt").write_text("\n".join(ans) + "\n", encoding="utf-8")
    print("\n".join(ans))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    {"run": run, "blind": blind}[sys.argv[1]]()
