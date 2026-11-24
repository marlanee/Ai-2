# Overnight batch 1: SA3 music pool (headroom) + LTX 1080p loop from v1 key art (safety-net assets).
$repo = 'C:\Users\SSAFY\Desktop\Ai-2'; Set-Location $repo
$wfm = 'workflows\music_stableaudio3_medium_headroom_api.json'
$mp = '80s Korean city pop lofi, instrumental, Rhodes piano, warm tape saturation, mellow bass, soft drums, 75 BPM'
foreach ($s in 202, 303, 401, 402, 403, 404, 405, 406, 407, 408) {
  python scripts\run_workflow.py $wfm --set "52:31.value=$mp" --set '52:35.value=false' --set '52:36.value=120' `
    --set "52:3.seed=$s" --set "57.filename_prefix=pool/sa3h_s$s" --label "pool_sa3h_s$s" --timeout 600 | Select-Object -Last 1
  Write-Output "music seed $s done"
}
Copy-Item -Force test_output\keyart2\p1_s11_final_qwen.png C:\AI\ComfyUI\ComfyUI\input\keyart_v1.png
$lp = 'gentle rain falling steadily, neon sign softly flickering, light reflections shimmering on the wet ground, warm window light glowing, static camera, seamless loop, calm lofi atmosphere. Audio: soft steady rain ambience, distant drips on metal awning, no music, no voices.'
python scripts\run_workflow.py workflows\video_ltx25_flf2v_int8_api.json --set "251:252.value=$lp" --set '251:250.value=false' `
  --set '251:215.value=1920' --set '251:216.value=1088' --set '251:198.value=5' --set '251:205.value=24' `
  --set '251:196.noise_seed=1980' --set '31.image=keyart_v1.png' --set '39.image=keyart_v1.png' `
  --set '68.filename_prefix=release/ltx_v1_1080p' --label 'ltx_v1_1080p' --timeout 1800 | Select-Object -Last 1
Write-Output "BATCH1 DONE"
