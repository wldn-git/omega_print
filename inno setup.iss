[Setup]
; AppId ini penting untuk update versi di masa depan biar nggak numpuk
AppId={{SMARTEK-OMEGA-MX-V5-2026}

; 1. HAK ADMIN (UAC Prompt akan muncul saat installer dibuka)
PrivilegesRequired=admin

; 2. LICENSE & README (Arahkan ke dalam folder dist)
LicenseFile=license.txt
InfoBeforeFile=readme.txt

; 3. MENGAKTIFKAN HALAMAN SERIAL NUMBER & USER INFO
UserInfoPage=yes

; Identitas Software
AppName=Omega MX Batch & QC System
AppVersion=5.0
AppPublisher=PT SMARTEK SISTEM INOVASI
AppPublisherURL=http://www.smartek.co.id/
; Install di Program Files
DefaultDirName={autopf}\Omega_MX_System
DefaultGroupName=PT SMARTEK

; Ikon & Output (Pastikan nama file ico-nya benar)
SetupIconFile=assets\setup_icon.ico
OutputBaseFilename=Omega_MX_Setup_v5
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Registry]
; Memaksa Windows untuk selalu menjalankan file .exe ini sebagai Administrator (RUNASADMIN)
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"; ValueType: string; ValueName: "{app}\Omega_MX_System.exe"; ValueData: "~ RUNASADMIN"; Flags: uninsdeletevalue

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
; Izin modifikasi folder agar penyimpanan riwayat (history) dan log sistem berjalan lancar tanpa terhalang proteksi Program Files
Name: "{app}"; Permissions: users-modify
Name: "{app}\history"; Permissions: users-modify
Name: "{app}\logs"; Permissions: users-modify

[Files]
; Pastikan path ini mengarah ke folder dist kamu
Source: "dist\Omega_MX_System\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Omega MX System"; Filename: "{app}\Omega_MX_System.exe"; WorkingDir: "{app}"; IconFilename: "{app}\assets\omega_icon.ico"
Name: "{group}\{cm:UninstallProgram,Omega MX System}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Omega MX System"; Filename: "{app}\Omega_MX_System.exe"; WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\assets\omega_icon.ico"

[Run]
Filename: "{app}\Omega_MX_System.exe"; Description: "{cm:LaunchProgram,Omega MX System}"; Flags: nowait postinstall skipifsilent

[Code]
// LOGIKA VALIDASI SERIAL NUMBER (PASCAL SCRIPT)
function CheckSerial(Serial: String): Boolean;
  begin
  // Tombol 'Next' akan otomatis menyala HANYA jika tulisan di bawah ini sama persis.
  // Tidak perlu pakai MsgBox agar tidak rewel setiap ngetik 1 huruf.
  
    if Serial = 'SMARTEK-2026-OMEGA' then
    Result := True
    else
    Result := False;
  end;