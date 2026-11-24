# GPT (Codex CLI) review of a generated image.
#   -Mode ocr      : blind transcription of every sign, syllable by syllable, no autocorrect
#   -Mode critique : audience appeal + completeness review as a YouTube lofi viewer / art director
# usage: .\scripts\codex_review.ps1 -Image a.png [-Image2 b.png] -Mode ocr|critique [-Out review.md] [-Context "..."]
# Prints GPT's answer and saves it (default: test_output/reviews/<image>_<mode>.md).
param([Parameter(Mandatory)][string]$Image, [string]$Image2, [ValidateSet('ocr', 'critique')][string]$Mode = 'ocr',
      [string]$Out, [string]$Context = '')
$repo = Split-Path $PSScriptRoot -Parent
if (-not $Out) {
  $dir = Join-Path $repo 'test_output\reviews'; New-Item -ItemType Directory -Force $dir | Out-Null
  $Out = Join-Path $dir ("{0}_{1}.md" -f [IO.Path]::GetFileNameWithoutExtension($Image), $Mode)
}
if ($Mode -eq 'ocr') {
  $q = @'
You are a strict proofreader of Korean text inside an illustration.
List EVERY piece of visible writing in the image (signs, boards, posters, plates, labels), including tiny or blurry ones.
For each: location (e.g. "top-center vertical sign"), the exact transcription syllable by syllable AS DRAWN (never autocorrect to a likely word; check whether each vowel stroke points up or down, left or right), and a verdict:
  OK = valid, correctly formed Korean syllables
  BROKEN = malformed / non-existent syllables or pseudo-letters
  FOREIGN = Latin, Chinese, Japanese or other non-Korean characters
Answer as a markdown table: | location | transcription | verdict | note |, then one line: "TOTAL: n OK, n BROKEN, n FOREIGN".
'@
} else {
  $q = @"
You are reviewing a key-art image for a Korean 1980s/90s retro lofi music YouTube channel (rainy-night city-pop / lofi, loop video background, also used as the thumbnail). $Context
Answer in Korean, honestly and specifically. Do not be polite or vague.
1. 시청자 반응: 이 채널 시청자(로파이·시티팝을 틀어 놓고 공부·작업하는 20~30대)가 썸네일로 보고 클릭하고 싶을지, 오래 틀어 둘 배경으로 좋아할지. 점수 1~10과 이유.
2. 완성도: 상업 채널에 올려도 되는 수준인지. 점수 1~10.
3. AI·합성 티: 사람이 보면 "AI가 만들었다"거나 "글자를 나중에 붙였다"고 느낄 부분을 위치와 함께 구체적으로.
4. 시대 고증: 80~90년대 한국 골목으로 어색한 요소(일본·중국풍, 현대적 디자인 등).
5. 개선 우선순위 Top 3: 무엇을 어떻게 바꾸면 점수가 가장 많이 오르는지.
마지막 줄: "SCORES: appeal=<n> completeness=<n>"
"@
}
$args2 = @('exec', '--skip-git-repo-check', '-s', 'read-only', '-i', $Image)
if ($Image2) { $args2 += @('-i', $Image2) }
$raw = @($q | & codex @args2 2>&1 | ForEach-Object { "$_" } | Where-Object { $_ -ne 'System.Management.Automation.RemoteException' })
# transcript: ... "codex" <answer> hook lines "tokens used" <n> <answer again>; keep the block after the last "codex" marker up to "tokens used"
$i = [Array]::LastIndexOf($raw, 'codex')
$j = [Array]::LastIndexOf($raw, 'tokens used')
$ans = if ($i -ge 0) {
  $end = if ($j -gt $i) { $j - 1 } else { $raw.Count - 1 }
  ($raw[($i + 1)..$end] | Where-Object { $_ -notmatch '^hook:' }) -join "`n"
} else { $raw -join "`n" }
"# codex $Mode review: $Image`n`n$ans" | Set-Content -Encoding utf8 $Out
Write-Output $ans
Write-Output "-> $Out"
