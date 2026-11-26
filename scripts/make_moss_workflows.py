"""Write MOSS-Image API workflows that mirror the official ComfyUI templates (ComfyUI >= 0.43, built-in nodes only).

  python scripts/make_moss_workflows.py   -> workflows/image_moss_{t2i,layout,edit}_api.json

t2i    : image_moss_image_t2i.json without the prompt enhancer. SFT int8 + W4A8 TE + FLUX.2 small VAE,
         SkipLayerGuidanceDiTSimple(single '22', 0-0.5), KSampler 25 steps CFG 2.5 er_sde/simple.
layout : t2i + CreateBoundingBoxes(editor_state = boxes) -> MOSSImageLayoutPrompt -> positive text (enhancer off,
         as in image_moss_image_t2i_bboxes.json). Set 25.editor_state to a list of
         {"x","y","width","height","metadata":{"type":"obj"|"text","text","desc","palette":[]}} (background first).
edit   : image_moss_image_edit.json. Edit LoRA rank 64, SLG 0-1, KSampler 30 steps CFG 4 euler/normal; image_0 (scaled
         to 1 MP, also sets the output size) + up to 2 references (41/42) given to TextEncodeMOSSImageEdit with the VAE.
"""
import copy, json, pathlib

WF = pathlib.Path(__file__).resolve().parent.parent / "workflows"
NEG = "nsfw, worst quality, bad anatomy, watermark, jpeg artifact"

base = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "moss_image_sft_int8_convrot.safetensors", "weight_dtype": "default"}},
    "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3.5_9b_w4a8_gptq.safetensors", "type": "moss_image", "device": "default"}},
    "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae_small.safetensors"}},
    "15": {"class_type": "SkipLayerGuidanceDiTSimple", "inputs": {"model": ["1", 0], "double_layers": "", "single_layers": "22",
                                                                 "start_percent": 0.0, "end_percent": 0.5}},
    "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": ""}},
    "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": NEG}},
    "6": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": 1664, "height": 928, "batch_size": 1}},
    "7": {"class_type": "KSampler", "inputs": {"model": ["15", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0],
                                               "seed": 1, "steps": 25, "cfg": 2.5, "sampler_name": "er_sde", "scheduler": "simple", "denoise": 1.0}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
    "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "moss/t2i"}},
}
json.dump(base, open(WF / "image_moss_t2i_api.json", "w", encoding="utf-8"), indent=1)

lay = copy.deepcopy(base)
lay["25"] = {"class_type": "CreateBoundingBoxes", "inputs": {"width": 1664, "height": 928, "editor_state": {"__value__": []}}}
lay["27"] = {"class_type": "MOSSImageLayoutPrompt", "inputs": {"prompt": "", "element": ["25", 2], "width": 1664, "height": 928,
                                                                "character_boxes": ""}}
lay["4"]["inputs"]["text"] = ["27", 0]
lay["26"] = {"class_type": "PreviewAny", "inputs": {"source": ["27", 0]}}
lay["9"]["inputs"]["filename_prefix"] = "moss/layout"
json.dump(lay, open(WF / "image_moss_layout_api.json", "w", encoding="utf-8"), indent=1)

ed = {
    "1": base["1"], "2": base["2"], "3": base["3"],
    "31": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": "moss_image_edit_lora_rank_64_bf16.safetensors",
                                                           "strength_model": 1.0}},
    "32": {"class_type": "SkipLayerGuidanceDiTSimple", "inputs": {"model": ["31", 0], "double_layers": "", "single_layers": "22",
                                                                 "start_percent": 0.0, "end_percent": 1.0}},
    "40": {"class_type": "LoadImage", "inputs": {"image": "moss_src.png"}},
    "41": {"class_type": "LoadImage", "inputs": {"image": "moss_ref1.png"}},
    "29": {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": ["40", 0], "upscale_method": "lanczos", "megapixels": 1.0,
                                                               "resolution_steps": 16}},
    "27": {"class_type": "GetImageSize", "inputs": {"image": ["29", 0]}},
    "28": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": ["27", 0], "height": ["27", 1], "batch_size": 1}},
    "39": {"class_type": "TextEncodeMOSSImageEdit", "inputs": {"clip": ["2", 0], "prompt": "", "edit_format": "Moss-Image-Edit",
                                                               "images.image_0": ["29", 0], "images.image_1": ["41", 0],
                                                               "image_strength": 1.0, "vae": ["3", 0]}},
    "36": {"class_type": "TextEncodeMOSSImageEdit", "inputs": {"clip": ["2", 0], "prompt": NEG, "edit_format": "Moss-Image-Edit",
                                                               "images.image_0": ["29", 0], "images.image_1": ["41", 0],
                                                               "image_strength": 1.0, "vae": ["3", 0]}},
    "37": {"class_type": "KSampler", "inputs": {"model": ["32", 0], "positive": ["39", 0], "negative": ["36", 0], "latent_image": ["28", 0],
                                                "seed": 42, "steps": 30, "cfg": 4.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}},
    "38": {"class_type": "VAEDecode", "inputs": {"samples": ["37", 0], "vae": ["3", 0]}},
    "9": {"class_type": "SaveImage", "inputs": {"images": ["38", 0], "filename_prefix": "moss/edit"}},
}
json.dump(ed, open(WF / "image_moss_edit_api.json", "w", encoding="utf-8"), indent=1)
print("wrote 3 workflows")
