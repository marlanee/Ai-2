# Harmonize font-composited signs with Qwen-Image-Edit-2511 (keep text, repaint style), one crop at a time.
# usage: .\scripts\harmonize_signs.ps1 -In <fixed.png> -OutDir <dir> -Stage <name> -Crop "x0 y0 x1 y1" -Text "다방" -Desc "pink" [-Seeds 1,2]
param([string]$In, [string]$OutDir, [string]$Stage, [string]$Crop, [string]$Text, [string]$Desc, [int[]]$Seeds = @(1, 2), [switch]$Lit)
$repo = Split-Path $PSScriptRoot -Parent
$light = if ($Lit) { " The sign is an illuminated lightbox glowing from inside at night: keep it bright, let the letters glow and bleed light softly into the rainy air, as on a real 1980s Seoul street sign." } else { "" }
$p = "Redraw this sign so it matches the 1980s anime cel style of the rest of the picture (flat cel shading, soft painted texture, rain in front of it). The letters have clean sign-painter edges: no dripping paint, no drips, no runs, no graffiti. Keep the sign face color and the frame exactly as they are.$light Keep the Korean text $Text exactly as it is: same letters, same letter shapes, same position, same size, same $Desc color. Do not change any letter. Do not add any other text. Change nothing else."
$c = $Crop -split ' '
New-Item -ItemType Directory -Force $OutDir | Out-Null
foreach ($s in $Seeds) {
  python "$repo\scripts\qwen_edit.py" $In "$OutDir\${Stage}_s$s.png" --prompt $p --crop $c[0] $c[1] $c[2] $c[3] --seed $s --feather 12 > $null
  Write-Output "$Stage seed $s -> $OutDir\${Stage}_s$s.png"
}
