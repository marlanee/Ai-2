# MiniMax Music 3 test: same captions as the preferred SA3 prompt variants, instrumental, 150 s, 2 seeds each.
$repo = 'C:\Users\SSAFY\Desktop\Ai-2'; Set-Location $repo
$prompts = [ordered]@{
  a = '1980s Korean city pop instrumental, lofi hip hop beat, Rhodes electric piano playing jazzy major seventh chords, warm analog tape, soft boom bap drums, smooth bassline, 75 BPM, F major, relaxing rainy night'
  b = 'nostalgic 80s Seoul night city pop lofi, clean electric guitar licks, soft synth pads, mellow Rhodes, laid-back drums, vinyl crackle, 80 BPM, D major, instrumental, smooth and consonant'
  c = 'chill lofi instrumental, gentle piano melody, warm upright bass, brushed drums, soft rain, 70 BPM, C major, simple consonant harmony, calm and cozy, no vocals'
  d = 'retro 80s Korean ballad lofi, soft saxophone melody, Rhodes piano, gentle drums, warm bass, 72 BPM, B flat major, warm and smooth, instrumental'
}
$seed = 900
foreach ($kv in $prompts.GetEnumerator()) {
  foreach ($i in 1, 2) {
    $seed++
    python scripts\run_workflow.py workflows\music_minimax3_api.json --set "37:13.caption=$($kv.Value)" `
      --set '37:13.lyrics=[Instrumental]' --set '37:13.max_duration=150' --set "37:38.seed=$seed" `
      --set "35.filename_prefix=mm3/mm3_p$($kv.Key)_s$seed" --label "mm3_p$($kv.Key)_s$seed" --timeout 1800 | Select-Object -Last 12
    Write-Output "mm3 p$($kv.Key) s$seed"
  }
}
Write-Output "MM3 DONE"
