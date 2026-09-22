# S161 ready-before-open fixture (AUTHORITY=0)

This fixture is a preparation artifact for a future supported debugger run. It starts without creating the target Event/IoCompletion handles, emits `ready`, and accepts `open` only after an external observer has attached. `snapshot`, bounded `churn N` (0..8192), explicit close, and `exit` provide deterministic lifecycle markers and an actual process exit.

Compile/run (Windows, bounded by the coordinator):

```powershell
$csc = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
& $csc /nologo /target:exe /out:$env:TEMP\hh3d-s161-fixture.exe native_fixture_s161.cs
$proc = Start-Process $env:TEMP\hh3d-s161-fixture.exe -RedirectStandardInput $env:TEMP\s161-in.txt -RedirectStandardOutput $env:TEMP\s161-out.txt -PassThru
```

The external observer must verify PID/start/executable before sending `open`. No debugger, creator attribution, leak, Godot/Blender execution, formal GT06 evidence, F13/F14 data, or acceptance is implied.
