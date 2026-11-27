# MiniMax Music 3 retry: structured instrumental "lyrics" (section tags only) so the model writes a full-length song.
$repo = 'C:\Users\SSAFY\Desktop\Ai-2'; Set-Location $repo
$lyr = "[Intro]`n`n[Instrumental]`n`n[Instrumental]`n`n[Solo]`n`n[Instrumental]`n`n[Bridge]`n`n[Instrumental]`n`n[Outro]"
$suffix = ' Fully instrumental track, no vocals, about 3 minutes long with intro, main groove, solo, and gentle outro.'
$prompts = [ordered]@{
  a = '1980s Korean city pop instrumental, lofi hip hop beat, Rhodes electric piano playing jazzy major seventh chords, warm analog tape, soft boom bap drums, smooth bassline, 75 BPM, F major, relaxing rainy night.'
  b = 'nostalgic 80s Seoul night city pop lofi, clean electric guitar licks, soft synth pads, mellow Rhodes, laid-back drums, vinyl crackle, 80 BPM, D major, smooth and consonant.'
  c = 'chill lofi instrumental, gentle piano melody, warm upright bass, brushed drums, soft rain, 70 BPM, C major, simple consonant harmony, calm and cozy.'
  d = 'retro 80s Korean ballad lofi, soft saxophone melody, Rhodes piano, gentle drums, warm bass, 72 BPM, B flat major, warm and smooth.'
}
$seed = 1100
foreach ($kv in $prompts.GetEnumerator()) {
  foreach ($i in 1..10) {
    $seed++
    python scripts\run_workflow.py workflows\music_minimax3_api.json --set "37:13.caption=$($kv.Value)$suffix" `
      --set "37:13.lyrics=$lyr" --set '37:13.max_duration=200' --set "37:38.seed=$seed" `
      --set "35.filename_prefix=mm3pool/mm3s_p$($kv.Key)_s$seed" --label "mm3s_p$($kv.Key)_s$seed" --timeout 1800 > $null
    $f = Get-ChildItem "C:\AI\ComfyUI\ComfyUI\output\mm3pool\mm3s_p$($kv.Key)_s$seed*.flac" | Select-Object -First 1
    $d = if ($f) { C:\AI\tools\ffmpeg\bin\ffprobe.exe -v error -show_entries format=duration -of csv=p=0 $f.FullName } else { 'missing' }
    Write-Output "mm3s p$($kv.Key) s$seed  $d s"
  }
}
Write-Output "MM3POOL DONE"
