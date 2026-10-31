; Windows kurulum dosyası (Inno Setup). GitHub Actions derler:
;   ISCC /DAppVersion=1.0.0 packaging\installer.iss
; Yönetici izni istemez; kullanıcının kendi klasörüne kurar.

#define AppName "Zaman Makinesi"
#define AppExe "ZamanMakinesi.exe"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; AppId değişirse Windows bunu ayrı bir uygulama sanar, güncelleme bozulur. Değiştirmeyin.
AppId={{8C1F6A3E-2B7D-4E59-9A41-5D3C2F7B6E10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=berkyymn
AppPublisherURL=https://github.com/berkyymn/zaman-makinesi
DefaultDirName={localappdata}\Programs\{#AppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=ZamanMakinesi-Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
; Güncellemede açık kalan eski sürüm kapatılır
CloseApplications=force
RestartApplications=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Eski sürümden kalan kütüphaneler yenileriyle karışmasın
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\ZamanMakinesi\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
; Uygulama içinden yapılan güncelleme sessiz kurulur; bitince uygulamayı "güncellendi" bilgisiyle yeniden aç
Filename: "{app}\{#AppExe}"; Parameters: "--updated"; Flags: nowait; Check: WizardSilent
