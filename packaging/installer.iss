; Inno Setup script: wraps dist\PiCore into PiCore-Setup-<version>.exe
; Built by packaging\build.ps1 (needs Inno Setup 6: winget install JRSoftware.InnoSetup)

#define AppName "PiCore"
#ifndef AppVersion
  #define AppVersion "0.5.0"
#endif

[Setup]
AppId={{83D81EBE-06DA-4B86-9393-29DA8015D438}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=PiCore
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=PiCore-Setup-{#AppVersion}
SetupIconFile=picore.ico
UninstallDisplayIcon={app}\PiCore.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\PiCore\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\PiCore.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\PiCore.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PiCore.exe"; Description: "Launch PiCore"; Flags: nowait postinstall skipifsilent
