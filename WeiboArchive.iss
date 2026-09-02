; ============================================================
;  WeiboArchive 微博归档工具 - Windows 一键安装包 (Inno Setup 6)
;  编译: tools\innosetup\ISCC.exe WeiboArchive.iss
;  产物: dist\WeiboArchive-Setup-1.3.2.exe
; ============================================================
#define MyAppName "WeiboArchive 微博归档工具"
#define MyAppVersion "1.3.2"
#define MyAppExeName "WeiboArchive.exe"
#define MyAppPublisher "WeiboArchive"

[Setup]
AppId={{8F2A1B3C-4D5E-4F60-9A7B-2C3D4E5F6A7B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\WeiboArchive
DefaultGroupName=WeiboArchive
DisableProgramGroupPage=yes
DisableDirPage=no
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=WeiboArchive-Setup-{#MyAppVersion}
SetupIconFile=build\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
