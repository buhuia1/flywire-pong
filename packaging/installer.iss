#define AppName "FlyWire Pong"
#define AppVersion "1.0.0"
[Setup]
AppId={{C3A01280-DC42-48CE-9C1F-7D522809B4FA}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppComments=Offline connectome-based Pong research demo
DefaultDirName={localappdata}\Programs\FlyWirePong
DefaultGroupName=FlyWire Pong
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\release
OutputBaseFilename=FlyWire-Pong-Setup-1.0.0-Windows-x64
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
DisableWelcomePage=yes
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=no
DisableFinishedPage=yes
UninstallDisplayIcon={app}\FlyWire-Pong.exe
CloseApplications=no
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Files]
Source: "..\dist\FlyWire-Pong\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "使用说明.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userdesktop}\果蝇 Pong"; Filename: "{app}\FlyWire-Pong.exe"; Check: not WizardSilent
Name: "{group}\果蝇 Pong"; Filename: "{app}\FlyWire-Pong.exe"
Name: "{group}\使用说明"; Filename: "{app}\使用说明.txt"

[Run]
Filename: "{app}\FlyWire-Pong.exe"; Flags: nowait skipifsilent

[UninstallRun]
Filename: "{app}\FlyWire-Pong.exe"; Parameters: "--shutdown"; Flags: runhidden; RunOnceId: "ShutdownGame"
