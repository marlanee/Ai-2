# Shop-window props via Qwen-Image-Edit-2511 (GPT Top-3 #2). No text allowed in the new props.
$repo = 'C:\Users\SSAFY\Desktop\Ai-2'; Set-Location $repo
$k = 'test_output\keyart2'; $o = "$k\qedit\win"; New-Item -ItemType Directory -Force $o | Out-Null
$rec = 'Inside this shop window, replace the colored round decorations with a 1980s record shop display: vinyl LP record sleeves standing in wooden bins and on shelves, a few cassette tapes, a small turntable. Album covers show only simple abstract shapes and colors, absolutely no text, letters or numbers anywhere. Keep the same 1980s anime cel style, warm interior light, window frame, door, curtain and rain. Change nothing outside the window.'
$bun = 'Inside this shop window, replace the purple and pink round decorations with a 1980s Korean snack bar interior: a stainless steel pan of red tteokbokki, skewers of fish cake in broth, steam, a small counter. Absolutely no text, letters or numbers anywhere. Keep the same 1980s anime cel style, warm light, window frame and rain. Change nothing outside the window.'
foreach ($s in 1, 2, 3) {
  python scripts\qwen_edit.py "$k\p1_s11_v3.png" "$o\rec_s$s.png" --prompt $rec --crop 240 330 590 760 --seed $s --feather 14 | Select-Object -First 1
  python scripts\qwen_edit.py "$k\p1_s11_v3.png" "$o\bun_s$s.png" --prompt $bun --crop 920 440 1100 720 --seed $s --feather 12 | Select-Object -First 1
}
Write-Output "WINDOWS DONE"
