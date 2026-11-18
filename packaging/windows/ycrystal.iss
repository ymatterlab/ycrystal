; Inno Setup 6 script of the graphical Windows installer of Ycrystal (x64).
;
; Built by packaging\windows\build.ps1 after PyInstaller, which passes the defines below;
; see docs\development\windows-installer.md. It installs the PyInstaller folder: no
; Python, Git, or PowerShell is needed on the user's computer. POV-Ray for Windows is
; not included; the installer says so when it does not find it.
;
; Coexistence with an installation from source (scripts\install-windows.ps1 and
; "ycrystal --install-desktop"): every identity here differs from that one's.
;   Start-menu shortcut  "Ycrystal"                     source: "Ycrystal (development)"
;   AppUserModelID       YMatterLab.Ycrystal.App        source: YMatterLab.Ycrystal
;   file type (ProgID)   YMatterLab.Ycrystal.Project    source: Ycrystal.Project
;   icon                 inside Ycrystal.exe            source: %LOCALAPPDATA%\Y-Matter Lab\Ycrystal\ycrystal.ico
; Uninstalling removes only this installation's files, shortcuts, and registry values;
; the ".ycrystal" default value only while it still names this file type ([Code]).
; Ycrystal's settings (HKCU\Software\Y-Matter Lab\Ycrystal) are shared and kept.
; tests\test_windows_installer.py checks these values against the Python code.

#ifndef AppVersion
  #define AppVersion "0.0.0.dev0"
#endif
#ifndef AppVersionNumeric
  #define AppVersionNumeric "0.0.0.0"
#endif
#ifndef BundleDir
  #define BundleDir "..\..\dist\windows\Ycrystal"
#endif
#ifndef IconFile
  #define IconFile "..\..\build\windows\ycrystal.ico"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist\windows"
#endif

#define AppUserModelId "YMatterLab.Ycrystal.App"
#define ProgId "YMatterLab.Ycrystal.Project"

[Setup]
; Fixed for every version: Windows recognises updates and the uninstaller by it.
AppId={{96A7291E-332A-4D2A-ACAD-E2489153A771}
AppName=Ycrystal
AppVersion={#AppVersion}
AppVerName=Ycrystal {#AppVersion}
AppPublisher=Y-Matter Lab
AppPublisherURL=https://github.com/ymatterlab/ycrystal
AppSupportURL=https://github.com/ymatterlab/ycrystal/issues
AppUpdatesURL=https://github.com/ymatterlab/ycrystal/releases
VersionInfoVersion={#AppVersionNumeric}
VersionInfoProductName=Ycrystal
VersionInfoDescription=Ycrystal installer
; For the current user without administrator rights by default; the wizard offers an
; installation for all users (Program Files) to administrators.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
DefaultDirName={autopf}\Ycrystal
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\Ycrystal.exe
UninstallDisplayName=Ycrystal
LicenseFile=..\..\LICENSE
OutputDir={#OutputDir}
OutputBaseFilename=Ycrystal-{#AppVersion}-windows-x64-setup
Compression=lzma2/max
SolidCompression=yes
ChangesAssociations=yes
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "fileassoc"; Description: "Open .ycrystal projects with Ycrystal"; GroupDescription: "File types:"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Ycrystal"; Filename: "{app}\Ycrystal.exe"; WorkingDir: "{userdocs}"; Comment: "Prepare crystal-structure figures and render them with POV-Ray"; AppUserModelID: "{#AppUserModelId}"
Name: "{autodesktop}\Ycrystal"; Filename: "{app}\Ycrystal.exe"; WorkingDir: "{userdocs}"; AppUserModelID: "{#AppUserModelId}"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\{#ProgId}"; ValueType: string; ValueName: ""; ValueData: "Ycrystal project"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\{#ProgId}"; ValueType: string; ValueName: "AppUserModelID"; ValueData: "{#AppUserModelId}"; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\{#ProgId}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\Ycrystal.exe,0"; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Ycrystal.exe"" ""%1"""; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\.ycrystal\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
; No uninstall flag: [Code] removes this value only while it names this file type.
Root: HKA; Subkey: "Software\Classes\.ycrystal"; ValueType: string; ValueName: ""; ValueData: "{#ProgId}"; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\Applications\Ycrystal.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "Ycrystal"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\Applications\Ycrystal.exe\SupportedTypes"; ValueType: string; ValueName: ".ycrystal"; ValueData: ""; Tasks: fileassoc

[Run]
Filename: "{app}\Ycrystal.exe"; Description: "{cm:LaunchProgram,Ycrystal}"; Flags: nowait postinstall skipifsilent
Filename: "https://www.povray.org/download/"; Description: "Open the download page of POV-Ray for Windows (needed to render images)"; Flags: postinstall shellexec skipifsilent unchecked; Check: not PovrayFound

[Code]
var
  PovrayPage: TOutputMsgWizardPage;

{ The same places as ycrystal.render.povray.windows_engine_candidates: the folder that
  POV-Ray for Windows 3.7 records in the registry ("Home"), then Program Files. The
  program itself searches again at every start; this only informs the user. }
function PovrayIn(Home: String): Boolean;
begin
  Result := (Home <> '') and FileExists(AddBackslash(Home) + 'bin\pvengine64.exe');
end;

function PovrayFound: Boolean;
var
  Home: String;
begin
  Result := False;
  if RegQueryStringValue(HKCU, 'Software\POV-Ray\v3.7\Windows', 'Home', Home) and PovrayIn(Home) then
    Result := True
  else if RegQueryStringValue(HKLM64, 'Software\POV-Ray\v3.7\Windows', 'Home', Home) and PovrayIn(Home) then
    Result := True
  else if RegQueryStringValue(HKLM32, 'Software\POV-Ray\v3.7\Windows', 'Home', Home) and PovrayIn(Home) then
    Result := True
  else
    Result := PovrayIn(ExpandConstant('{commonpf64}\POV-Ray\v3.7'));
end;

procedure InitializeWizard;
begin
  if not PovrayFound then
    PovrayPage := CreateOutputMsgPage(wpSelectTasks,
      'POV-Ray for Windows', 'Ycrystal renders its images with POV-Ray for Windows 3.7.',
      'POV-Ray for Windows 3.7 was not found on this computer. Ycrystal opens, shows, '
      + 'and exports structures without it, but needs it for previews and images.' + #13#10#13#10
      + 'Install it afterwards from https://www.povray.org/download/ (the installer '
      + '"povwin-3.7-agpl3-setup.exe"), or in a terminal with:' + #13#10
      + '    winget install --id PersistenceOfVisionRaytracer.POVRay --exact' + #13#10#13#10
      + 'Then start POV-Ray for Windows once, answer its question about its editor (No, '
      + 'then untick Options > Other Settings > Use Editor), and close it. Ycrystal finds '
      + 'it by itself.');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Value: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if RegQueryStringValue(HKA, 'Software\Classes\.ycrystal', '', Value) and (Value = '{#ProgId}') then
      RegDeleteValue(HKA, 'Software\Classes\.ycrystal', '');
    RegDeleteKeyIfEmpty(HKA, 'Software\Classes\.ycrystal\OpenWithProgids');
    RegDeleteKeyIfEmpty(HKA, 'Software\Classes\.ycrystal');
    RegDeleteKeyIfEmpty(HKA, 'Software\Classes\Applications\Ycrystal.exe\SupportedTypes');
  end;
end;
