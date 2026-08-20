# Export signing (M7A / T7A.3 / C13)

Exported games from `build.game` / `pack_project` / `hh-play.bat` are **unsigned**.

The pack copies `gs-player.exe`, the play snapshot (`manifest.json`, scene, scripts, input map, settings), and `run.bat`. It does **not**:

- embed or copy an editor code-signing certificate
- copy `.pfx`, `.p12`, `.cer`, `.crt`, `.pem`, `.p7b`, or `.p7c` from the project
- sign the player exe

`build.json` in the output records `"signed": false`.

This is intentional. M7A is the user’s game. Editor distribution signing is M7B and uses a different cert. Do not put the editor `.pfx` in a game folder or in the pack output.

## Optional: sign with your own key (Windows)

After a pack you can sign the copied player with a **user-supplied** certificate. Example with [SignTool](https://learn.microsoft.com/windows/win32/seccrypto/signtool) from the Windows SDK:

```
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f YOUR.pfx /p YOUR_PASSWORD gs-player.exe
```

Use your own PFX (or a token/CSP). Timestamping (`/tr`) keeps the signature valid after the cert expires.

SmartScreen / “Windows protected your PC” is expected for unsigned or newly signed binaries until reputation builds. That is not a pack bug.

## Verify a pack stayed unsigned

1. Pack a project (`build.game` or `gs-player --project … --out …`).
2. Confirm the output folder has no `.pfx` / `.cer` / editor cert files.
3. `signtool verify /pa gs-player.exe` should fail (no signature) unless you signed it yourself.
