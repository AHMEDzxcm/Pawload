; Inno Setup script: builds PalwoadSetup.exe (per-user install, no admin rights needed).
#define AppVersion GetEnv("PALWOAD_VERSION")
#if AppVersion == ""
  #define AppVersion "0.2.0"
#endif

[Setup]
AppId={{6B1F6C0E-52B4-4F3A-9C77-5A1D2F0E7A11}
AppName=Palwoad
AppVersion={#AppVersion}
AppPublisher=Palwoad contributors
AppPublisherURL=https://github.com/AHMEDzxcm/Pawload
DefaultDirName={localappdata}\Programs\Palwoad
DefaultGroupName=Palwoad
PrivilegesRequired=lowest
OutputDir=..\installer
OutputBaseFilename=PalwoadSetup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayName=Palwoad
CloseApplications=force

[Files]
Source: "..\dist\Palwoad.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\palwoad-host.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\ffmpeg.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\extension\*"; DestDir: "{app}\extension"; Flags: ignoreversion recursesubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Palwoad"; Filename: "{app}\Palwoad.exe"
Name: "{autodesktop}\Palwoad"; Filename: "{app}\Palwoad.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Registry]
; start with Windows
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Palwoad"; ValueData: """{app}\Palwoad.exe"""; Flags: uninsdeletevalue

[Run]
; let Chrome / Edge / Brave pair with Palwoad automatically
Filename: "{app}\palwoad-host.exe"; Parameters: "--register"; Flags: runhidden
Filename: "{app}\Palwoad.exe"; Description: "Start Palwoad now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\palwoad-host.exe"; Parameters: "--unregister"; Flags: runhidden; RunOnceId: "Unregister"
