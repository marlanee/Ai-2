# Harmonize font-composited signs with Qwen-Image-Edit-2511 (keep text, repaint style), one crop at a time.
# usage: .\scripts\harmonize_signs.ps1 -In <fixed.png> -OutDir <dir> -Stage <name> -Crop "x0 y0 x1 y1" -Text "다방" -Desc "pink" [-Seeds 1,2]
param([string]$In, [string]$OutDir, [string]$Stage, [string]$Crop, [string]$Text, [string]$Desc, [int[]]$Seeds = @(1, 2))
$repo = Split-Path $PSScriptRoot -Parent
$p = "Redraw this sign so it looks hand-painted in the same 1980s anime cel style as the rest of the picture, with the same soft glow, paint texture and rain in front of it. Keep the Korean text $Text exactly as it is: same letters, same position, same $Desc color. Do not change any letter. Do not add any other text. Change nothing else."
$c = $Crop -split ' '
New-Item -ItemType Directory -Force $OutDir | Out-Null
foreach ($s in $Seeds) {
  python "$repo\scripts\qwen_edit.py" $In "$OutDir\${Stage}_s$s.png" --prompt $p --crop $c[0] $c[1] $c[2] $c[3] --seed $s --feather 12 > $null
  Write-Output "$Stage seed $s -> $OutDir\${Stage}_s$s.png"
}
