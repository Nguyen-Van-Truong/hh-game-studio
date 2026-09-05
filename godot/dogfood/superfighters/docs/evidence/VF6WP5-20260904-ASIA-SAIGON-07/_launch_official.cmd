@echo off
cd /d D:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio
echo LAUNCH_START %DATE% %TIME% > "D:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio\godot\dogfood\superfighters\docs\evidence\VF6WP5-20260904-ASIA-SAIGON-07\_official_host.log"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio\godot\dogfood\superfighters\tests\run_bots_official.ps1" >> "D:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio\godot\dogfood\superfighters\docs\evidence\VF6WP5-20260904-ASIA-SAIGON-07\_official_host.log" 2>&1
echo HOST_EXIT=%ERRORLEVEL% >> "D:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio\godot\dogfood\superfighters\docs\evidence\VF6WP5-20260904-ASIA-SAIGON-07\_official_host.log"
echo LAUNCH_END %DATE% %TIME% >> "D:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio\godot\dogfood\superfighters\docs\evidence\VF6WP5-20260904-ASIA-SAIGON-07\_official_host.log"
