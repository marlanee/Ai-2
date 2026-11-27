# Batch 3: music pool from the user-preferred prompt variants (pa..pd), 5 seeds each.
$repo = 'C:\Users\SSAFY\Desktop\Ai-2'; Set-Location $repo
$prompts = [ordered]@{
  a = '1980s Korean city pop instrumental, lofi hip hop beat, Rhodes electric piano playing jazzy major seventh chords, warm analog tape, soft boom bap drums, smooth bassline, 75 BPM, F major, relaxing rainy night'
  b = 'nostalgic 80s Seoul night city pop lofi, clean electric guitar licks, soft synth pads, mellow Rhodes, laid-back drums, vinyl crackle, 80 BPM, D major, instrumental, smooth and consonant'
  c = 'chill lofi instrumental, gentle piano melody, warm upright bass, brushed drums, soft rain, 70 BPM, C major, simple consonant harmony, calm and cozy, no vocals'
  d = 'retro 80s Korean ballad lofi, soft saxophone melody, Rhodes piano, gentle drums, warm bass, 72 BPM, B flat major, warm and smooth, instrumental'
}
$seed = 1000
foreach ($i in 1..12) {
  foreach ($kv in $prompts.GetEnumerator()) {
    $seed++
    python scripts\run_workflow.py workflows\music_stableaudio3_medium_headroom_api.json --set "52:31.value=$($kv.Value)" `
      --set '52:35.value=false' --set '52:36.value=120' --set "52:3.seed=$seed" `
      --set "57.filename_prefix=pool2/sa3h_p$($kv.Key)_s$seed" --label "pool2_p$($kv.Key)_s$seed" --timeout 900 > $null
    Write-Output "p$($kv.Key) s$seed"
  }
}
Write-Output "BATCH4 DONE"
