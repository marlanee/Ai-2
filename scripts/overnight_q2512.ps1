# Qwen-Image-2512 test: draw the alley WITH Korean signs natively (Lightning 4-step).
$repo = 'C:\Users\SSAFY\Desktop\Ai-2'; Set-Location $repo
$p = 'A narrow back alley in Seoul, Korea, around 1988, on a rainy night, retro 1980s Japanese-anime-style cel illustration with soft film grain, wide 16:9 shot, no people. Wet asphalt reflects warm orange window light; rain falls in thin streaks; electric wires and a wooden utility pole; a small parked 1980s sedan at the end of the alley. On the left, a record shop with a large mint-green illuminated sign that reads "은하수레코드" in bold red Korean letters, and LP records in its window. Above it, a tall vertical white lightbox reads "다방" in pink Korean letters. In the middle, a snack bar with an orange wooden sign reading "할매분식" in red Korean letters. Further down, a small green lightbox reads "약국", and a pink lightbox reads "만화". All Korean text is large, correct and clearly legible. No English, no Chinese characters, no other text anywhere.'
$n = '低分辨率，低画质，画面过饱和，人脸，人物，英文，汉字，日文，乱码文字，错误的韩文，文字模糊，扭曲'
foreach ($s in 11, 22, 33, 44) {
  python scripts\run_workflow.py workflows\image_qwen2512_api.json --set "238:227.text=$p" --set "238:228.text=$n" `
    --set '238:229.value=true' --set '238:232.width=1664' --set '238:232.height=928' --set "238:230.seed=$s" `
    --set "60.filename_prefix=q2512/alley_s$s" --label "q2512_alley_s$s" --timeout 1200 | Select-String '"seconds"|"status"|peak'
}
Write-Output "Q2512 DONE"
