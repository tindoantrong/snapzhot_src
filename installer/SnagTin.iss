; ============================================================================
;  SnagTin — Inno Setup script (đóng gói bản onedir thành Setup.exe)
;  Nguồn: dist\SnagTin\  (PyInstaller onedir: SnagTin.exe + _internal\)
;  Compile: ISCC.exe installer\SnagTin.iss  (hoặc qua scripts\build_installer.py)
;  Có thể override version: ISCC /DMyAppVersion=0.1.1 installer\SnagTin.iss
; ============================================================================

#ifndef MyAppVersion
  #define MyAppVersion "0.1.1"
#endif

#define MyAppName "SnagTin"
#define MyAppPublisher "SnagTin"
#define MyAppExeName "SnagTin.exe"

[Setup]
; AppId CỐ ĐỊNH — không đổi giữa các phiên bản để nâng cấp/gỡ đúng chỗ.
AppId={{A7F3C2E1-9B4D-4E5F-8A1C-2D3E4F5B6C7D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}
; Cài vào C:\Program Files\SnagTin (autopf theo quyền admin).
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Program Files cần quyền admin.
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Icon của trình cài + biểu tượng hiển thị trong Apps & Features.
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
; Nén mạnh (lzma2 + solid) → Setup.exe nhỏ dù onedir ~520MB.
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Xuất Setup.exe vào dist\ cạnh thư mục onedir.
OutputDir=..\dist
OutputBaseFilename=SnagTin-Setup-{#MyAppVersion}

[Languages]
; Default.isl luôn có sẵn trong mọi bản Inno Setup → không lỗi thiếu file.
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Toàn bộ thư mục onedir (SnagTin.exe + _internal\ deps), đệ quy.
Source: "..\dist\SnagTin\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Gỡ cài đặt {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Mời chạy app ngay sau khi cài (bỏ qua khi cài silent).
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Registry]
; Dọn giá trị autostart MỒ CÔI khi gỡ: app ghi HKCU\...\Run ValueName "snapzhot"
; (= APP_NAME). ValueType none + uninstalldeletevalue: KHÔNG tạo lúc cài, chỉ xoá lúc gỡ.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "snapzhot"; Flags: uninsdeletevalue

[UninstallDelete]
; Xoá sạch thư mục cài (kể cả file phát sinh runtime trong {app}).
; LƯU Ý: KHÔNG đụng %LOCALAPPDATA%\SnagTin (thư viện ảnh/video của user được giữ lại).
Type: filesandordirs; Name: "{app}"
