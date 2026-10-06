#define AppName "SIGAVI"
#define AppVersion "0.1.0"
#define AppPublisher "SIGAVI"

[Setup]
AppId={{6A8B76D3-2E2D-4C86-BF88-726E150A2A7F}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\SIGAVI
DefaultGroupName=SIGAVI
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=SIGAVI-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\SIGAVI.exe

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Files]
Source: "dist\SIGAVI.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\SIGAVI"; Filename: "{app}\SIGAVI.exe"
Name: "{autodesktop}\SIGAVI"; Filename: "{app}\SIGAVI.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SIGAVI.exe"; Description: "Abrir SIGAVI"; Flags: postinstall nowait skipifsilent
