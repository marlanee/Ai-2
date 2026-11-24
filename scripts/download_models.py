"""Download approved ComfyUI models (resumable via curl). Usage: python download_models.py <models_root>"""
import subprocess, sys, pathlib, urllib.request

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\AI\ComfyUI\ComfyUI\models")
HF = "https://huggingface.co"
MODELS = [
    # (folder, url)
    ("diffusion_models", f"{HF}/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/diffusion_models/acestep_v1.5_turbo.safetensors"),
    ("text_encoders",    f"{HF}/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_0.6b_ace15.safetensors"),
    ("text_encoders",    f"{HF}/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_1.7b_ace15.safetensors"),
    ("vae",              f"{HF}/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/vae/ace_1.5_vae.safetensors"),
    ("loras",            f"{HF}/ryanontheinside/lo_fi-acestep1.5-v1/resolve/main/lo_fi-v1.safetensors"),
    ("checkpoints",      f"{HF}/Comfy-Org/stable-audio-3/resolve/main/checkpoints/stable_audio_3_medium.safetensors"),
    ("text_encoders",    f"{HF}/Comfy-Org/stable-audio-3/resolve/main/text_encoders/t5gemma_b_b_ul2.safetensors"),
    ("text_encoders",    f"{HF}/Comfy-Org/Qwen3.5/resolve/main/text_encoders/qwen3.5_2b_bf16.safetensors"),
    ("diffusion_models", f"{HF}/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_int8_convrot.safetensors"),
    ("text_encoders",    f"{HF}/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b_fp8_mixed.safetensors"),
    ("vae",              f"{HF}/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors"),
    ("upscale_models",   f"{HF}/Comfy-Org/Real-ESRGAN_repackaged/resolve/main/RealESRGAN_x4plus.safetensors"),
    ("frame_interpolation", f"{HF}/Comfy-Org/frame_interpolation/resolve/main/frame_interpolation/rife_v4.26.safetensors"),
    ("text_encoders",    f"{HF}/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"),
    ("vae",              f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors"),
    ("loras",            f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"),
    ("loras",            f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors"),
    ("diffusion_models", f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"),
    ("diffusion_models", f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"),
    ("vae",              f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan2.2_vae.safetensors"),
    ("diffusion_models", f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors"),
    ("diffusion_models", f"{HF}/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/diffusion_models/acestep_v1.5_xl_turbo_bf16.safetensors"),
    ("text_encoders",    f"{HF}/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_4b_ace15.safetensors"),
    # Qwen-Image-Edit-2511 (Apache 2.0) — native sign-text editing test
    ("diffusion_models", f"{HF}/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_2511_int8_convrot.safetensors"),
    ("text_encoders",    f"{HF}/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors"),
    ("vae",              f"{HF}/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors"),
    ("loras",            f"{HF}/lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/main/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors"),
]

def remote_size(url):
    r = urllib.request.urlopen(urllib.request.Request(url, method="HEAD"))
    return int(r.headers.get("x-linked-size") or r.headers.get("content-length") or 0)

failed = []
for folder, url in MODELS:
    name = url.rsplit("/", 1)[-1]
    dest = ROOT / folder / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    want = remote_size(url)
    if dest.exists() and dest.stat().st_size == want:
        print(f"SKIP {folder}/{name}", flush=True); continue
    print(f"GET  {folder}/{name} ({want/1024**3:.2f} GB)", flush=True)
    part = dest.with_suffix(dest.suffix + ".part")
    rc = subprocess.call(["curl.exe", "-L", "--fail", "--retry", "5", "--retry-delay", "5", "-sS", "-C", "-", "-o", str(part), url])
    if rc == 0 and part.stat().st_size == want:
        part.replace(dest); print(f"DONE {folder}/{name}", flush=True)
    else:
        failed.append(name); print(f"FAIL {folder}/{name} rc={rc}", flush=True)
print("ALL DONE" if not failed else f"FAILED: {failed}", flush=True)
