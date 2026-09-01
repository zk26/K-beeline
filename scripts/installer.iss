; K-Beeline 安装程序脚本（Inno Setup 6）
; 构建: & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" scripts\installer.iss
; 说明: 每用户安装（无需管理员权限），全部依赖打包在内
#define MyAppName "K-Beeline 自动化助手"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "K-Beeline"
#define MyAppExeName "KBeeline.exe"

[Setup]
AppId={{8F3A2B1C-5E7D-4A9F-B2C1-9D8E6F4A3B2C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\KBeeline
DefaultGroupName=K-Beeline
PrivilegesRequired=lowest
OutputDir=..\Output
OutputBaseFilename=KBeelineSetup
SetupIconFile=..\assets\icons\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标:";

[Files]
Source: "..\dist\KBeeline\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即运行 {#MyAppName}"; Flags: nowait postinstall skipifsilent
