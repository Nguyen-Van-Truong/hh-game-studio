$blender = "D:\AI-Blender-Demo\tooling\blender-4.5.12-windows-x64\blender.exe"
$blend = "D:\AI-Blender-Demo\out\gaming_room.blend"
if (-not (Test-Path $blender)) { throw "Missing Blender: $blender" }
if (-not (Test-Path $blend)) { throw "Missing scene: $blend" }
Start-Process -FilePath $blender -ArgumentList @($blend)
