#define MyAppName "PulseLink Cast Studio"
#define MyAppVersion "2.4.0"
#define MyAppPublisher "PulseLink Open Studio"
#define MyAppExeName "PulseLinkCastHost.exe"

[Setup]
AppId={{B8F41C2A-9D73-4E5A-8B1A-3E92D674C109}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\PulseLinkCast
DefaultGroupName={#MyAppName}
PrivilegesRequired=admin
OutputDir=dist
OutputBaseFilename=PulseLinkCast_Windows_Setup
SetupIconFile=..\assets\app_icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "firewall"; Description: "Allow PulseLink Cast through Windows Defender Firewall (Modem/Wi-Fi LAN Ports 5959 & 5960)"; GroupDescription: "Windows Access Permissions:"

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""PulseLink Cast TCP 5959"" dir=in action=allow protocol=TCP localport=5959 profile=private,public"; Flags: runhidden; Tasks: firewall
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""PulseLink Cast UDP 5960"" dir=in action=allow protocol=UDP localport=5960 profile=private,public"; Flags: runhidden; Tasks: firewall
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
