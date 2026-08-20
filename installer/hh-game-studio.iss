; HH Game Studio — Inno Setup 6 (WP-M7B-1 / MASTER T7B.1)
;
; Unsigned editor distribution. Do not add SignTool= (that is M7B-2).
; Game export stays unsigned (C13) — this script never ships a .pfx.
;
; Binaries: default {#SourceRoot} = dist\ (run stage.ps1 first).
; Or compile against a release tree:
;   ISCC /DSourceRoot=..\target\release hh-game-studio.iss
;
; AppId is permanent. Changing it breaks in-place upgrade + Add/Remove Programs.

#define MyAppName "HH Game Studio"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "HH Game Studio"
#define MyAppExeName "gs-editor.exe"

#ifndef SourceRoot
  #define SourceRoot "dist"
#endif

[Setup]
; Generated once for M7B-1. Do not regenerate.
AppId={{B2E665BE-E6BF-42C7-B5F5-DA82BF9F189E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=HHGameStudio-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
MinVersion=10.0
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
VersionInfoVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes
; No SignTool / SignedUninstaller — installer and payloads stay unsigned.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceRoot}\gs-editor.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\gs-player.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\gs-cli.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\gs-mcp.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu launches the editor with no project.
; {app} has no project.json and no games\ tree, so gs-editor prints
; "usage: gs-editor <project-dir>" and opens the window on demo IR.
; User projects live outside {app} and survive uninstall.
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}"

[UninstallDelete]
; Only installer-created rollback under LocalAppData. Never user project dirs.
Type: filesandordirs; Name: "{localappdata}\HH Game Studio\rollback"
Type: dirifempty; Name: "{localappdata}\HH Game Studio"

[Code]
function RollbackDir: String;
begin
  Result := ExpandConstant('{localappdata}\HH Game Studio\rollback');
end;

procedure CopyIfExists(const Src, Dst: String);
begin
  if FileExists(Src) then
  begin
    if not FileCopy(Src, Dst, False) then
      RaiseException('Could not backup ' + Src + ' to ' + Dst);
  end;
end;

{ Keep one previous version: wipe the last rollback folder, then copy
  the four exes + Inno unins000.* from {app} before the new files land. }
procedure BackupPreviousVersion;
var
  AppDir, Dest, Note: String;
begin
  AppDir := ExpandConstant('{app}');
  if not FileExists(AppDir + '\gs-editor.exe') then
    Exit;

  Dest := RollbackDir();
  if DirExists(Dest) then
  begin
    if not DelTree(Dest, True, True, True) then
      RaiseException('Could not replace previous rollback folder: ' + Dest);
  end;
  if not ForceDirectories(Dest) then
    RaiseException('Could not create rollback folder: ' + Dest);

  CopyIfExists(AppDir + '\gs-editor.exe', Dest + '\gs-editor.exe');
  CopyIfExists(AppDir + '\gs-player.exe', Dest + '\gs-player.exe');
  CopyIfExists(AppDir + '\gs-cli.exe', Dest + '\gs-cli.exe');
  CopyIfExists(AppDir + '\gs-mcp.exe', Dest + '\gs-mcp.exe');
  CopyIfExists(AppDir + '\unins000.exe', Dest + '\unins000.exe');
  CopyIfExists(AppDir + '\unins000.dat', Dest + '\unins000.dat');
  CopyIfExists(AppDir + '\unins000.msg', Dest + '\unins000.msg');

  Note :=
    'HH Game Studio rollback (one previous version)' + #13#10 +
    'Saved before installing ' + '{#MyAppVersion}' + #13#10 +
    'Source: ' + AppDir + #13#10 + #13#10 +
    'To restore binaries: close the editor, then copy gs-*.exe from this' + #13#10 +
    'folder over the install directory. Prefer re-running the previous' + #13#10 +
    'setup exe if you still have it. There is no CDN or auto-updater.' + #13#10;
  SaveStringToFile(Dest + '\README.txt', Note, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    BackupPreviousVersion;
end;
