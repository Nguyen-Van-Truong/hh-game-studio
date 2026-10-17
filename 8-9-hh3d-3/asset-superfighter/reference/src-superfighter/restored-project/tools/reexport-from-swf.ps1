# Rebuild decompile + XFL from 00-original.swf (FFDec 21.1.0)
$ErrorActionPreference = "Stop"
$here = Split-Path $PSScriptRoot -Parent
$swf = Join-Path $here "00-original.swf"
$jar = Resolve-Path (Join-Path $here "..\..\tools\ffdec.jar")
$full = Resolve-Path (Join-Path $here "..\full-ffdec-export")
$xfl = Join-Path $here "xfl-export\Superfighters"

Write-Host "Export assets -> $full"
if (Test-Path $full) { Remove-Item $full -Recurse -Force }
New-Item -ItemType Directory -Force -Path $full | Out-Null
java --enable-native-access=ALL-UNNAMED -jar $jar -onerror ignore `
  -export script,sprite,sound,image,shape,font,text,binaryData,symbolClass,button `
  $full $swf

Write-Host "Export XFL -> $xfl"
if (Test-Path $xfl) { Remove-Item $xfl -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Split-Path $xfl) | Out-Null
java --enable-native-access=ALL-UNNAMED -jar $jar -onerror ignore -format xfl:cs5.5 -export xfl $xfl $swf
Write-Host "Done. Recreate junctions if you deleted full-ffdec-export (see README-RESTORED.md)."
