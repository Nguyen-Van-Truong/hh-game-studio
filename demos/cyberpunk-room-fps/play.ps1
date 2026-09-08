$ErrorActionPreference = "Stop"
$bin = Join-Path $env:LOCALAPPDATA "HHGodotAgent\tooling\godot-4.7.1-stable\bin"
$gui = Join-Path $bin "Godot_v4.7.1-stable_win64.exe"
$proj = $PSScriptRoot
if (-not (Test-Path $gui)) { throw "Missing Godot pin: $gui" }
Write-Host "Launching Night Room FPS..."
Write-Host "WASD + mouse  |  Left click shoot  |  Esc pause  |  R restart"
Start-Process -FilePath $gui -ArgumentList @("--path", $proj, "res://scenes/main.tscn")
