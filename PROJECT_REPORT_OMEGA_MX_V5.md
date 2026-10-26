# LAPORAN PROYEK SISTEM (PROJECT REPORT)
## OMEGA MX – BATCH PRINTING & QUALITY CONTROL SYSTEM
### Versi 5.0 Stable – Industrial Packaging Automation

---

## DAFTAR ISI
1. [Ringkasan Eksekutif (Executive Summary)](#1-ringkasan-eksekutif-executive-summary)
2. [Arsitektur Sistem (System Architecture)](#2-arsitektur-sistem-system-architecture)
   - 2.1 Pola Desain Modular (Decoupled Layered Architecture)
   - 2.2 Model Konkurensi & Multi-threading
   - 2.3 Topologi Integrasi Hardware Industri
3. [Framework & Teknologi yang Digunakan (Technology Stack)](#3-framework--teknologi-yang-digunakan-technology-stack)
4. [Fitur-Fitur Utama Sistem (Core Features)](#4-fitur-fitur-utama-sistem-core-features)
5. [Skenario Masalah Lapangan & Solusi yang Telah Diterapkan](#5-skenario-masalah-lapangan--solusi-yang-telah-diterapkan)
6. [Struktur File & Komponen Source Code](#6-struktur-file--komponen-source-code)
7. [Spesifikasi Deployment & Kompatibilitas Sistem](#7-spesifikasi-deployment--kompatibilitas-sistem)

---

## 1. RINGKASAN EKSEKUTIF (EXECUTIVE SUMMARY)

Aplikasi **Omega MX - Batch Printing & QC System** adalah perangkat lunak antarmuka mesin industri (*Human-Machine Interface / HMI*) yang dirancang khusus untuk mengelola operasional lini pengemasan benih pertanian (PT Syngenta). Sistem ini bertugas mengotomasi pencetakan stiker label (*Thermal Inkjet Omega*), inspeksi kualitas kode cetak secara *real-time* (*Dual Keyence Scanner*), pemisahan fisik produk cacat melalui aktuator pneumatik (*Modbus I/O PLC*), serta pemantauan efektivitas lini produksi secara lokal dan melalui web dashboard (*Web Analytics*).

Pada pembaruan **Versi 5.0 Stable**, aplikasi ini telah mengalami refaktorisasi arsitektur total dari struktur monolitik menjadi **arsitektur modular multi-threading**, dilengkapi sistem keamanan tingkat enterprise, ketahanan *crash recovery*, dan peremajaan antarmuka pengguna modern (*Modern Dark Sidebar HMI*) yang optimal untuk layar monitor Windows 7/10/11 di lingkungan pabrik.

---

## 2. ARSITEKTUR SISTEM (SYSTEM ARCHITECTURE)

### 2.1 Pola Desain Modular (Decoupled Layered Architecture)
Sistem dibangun dengan memisahkan logika antarmuka (*Presentation Layer*), orkestrasi bisnis (*Application Layer*), pengemudi perangkat keras (*Hardware Driver Layer*), dan persistensi data (*Persistence Layer*).

```
+-----------------------------------------------------------------------------------+
|                        PRESENTATION LAYER (HMI GUI)                               |
|  - main.py (OmegaBatchApp)                                                        |
|  - Dark Sidebar Navigation (#1e293b) & Centered Header Status Pill                |
|  - Left Pane: Batch Data Table (Treeview) & File Source Manager                   |
|  - Right Pane: Circular Arc Gauge, Conveyor Queue Canvas, Action Buttons          |
|  - Web Dashboard: Port 5022 (Chart.js / Local HTML5 Canvas)                       |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                  APPLICATION CORE ENGINE & CONCURRENCY LAYER                      |
|  - Independent Printing Worker Thread                                             |
|  - Conveyor In-Transit Queue Engine (collections.deque)                           |
|  - Dual-Scanner Verification & QC Matcher Engine                                  |
|  - Pneumatic Pusher Actuator Delay & Pulse Logic                                  |
|  - Crash-Resilient Atomic Checkpoint Engine                                       |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                     SERVICE DRIVERS & PERSISTENCE MODULES                         |
|  - printer_omega.py   : Persistent Socket Driver + Buffer Flush (CLR/RESET)       |
|  - modbus_io.py       : Modbus TCP / RTU Controller with Per-Coil Mutex Locks     |
|  - label_renderer.py  : PIL Graphic Compositor & Dynamic 2D QR Code Generator     |
|  - data_manager.py    : Atomic JSON Checkpoint, CSV Master Log, Excel Reporter    |
|  - auth_manager.py    : PBKDF2-HMAC-SHA256 Encryption & Anti-Brute-Force Guard    |
|  - analytics_server.py: Embedded Flask Server (Port 5022)                         |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                           PHYSICAL HARDWARE LAYER                                 |
|  - Thermal Inkjet Omega Printer (TCP/IP Port 6007)                                |
|  - Keyence SR-1000 Dual Scanners (TCP/IP Port 9004) - Sisi A & B                  |
|  - PLC / Modbus I/O Module (Port 502 / RS485 Serial)                              |
|  - Photoelectric Conveyor Sensors (DI)                                            |
|  - Pneumatic Rejector Solenoid Valve (DO 0)                                       |
|  - Industrial Signal Tower Lamp & Buzzer (DO 1 - 4)                               |
+-----------------------------------------------------------------------------------+
```

### 2.2 Model Konkurensi & Multi-threading
Untuk menjamin GUI Tkinter tetap responsif 60 FPS tanpa *freeze* saat berkomunikasi dengan perangkat keras berlatensi tinggi, arsitektur menggunakan **Thread Mandiri**:
1. **Main GUI Thread (Tkinter Event Loop):** Menangani render grafis, canvas gauges, interaksi operator, dan pembaruan elemen antarmuka via metode thread-safe (`root.after()`).
2. **Batch Printing Worker Thread:** Mengontrol pengiriman data cetak per item ke printer dengan jeda waktu terkontrol, memasukkan kardus ke antrean konveyor (`waiting_queue`), dan mengatur penundaan inter-box.
3. **Scanner 1 TCP Listener Thread:** Membaca *stream socket* dari Keyence Scanner 1 secara kontinu tanpa memblokir thread lain.
4. **Scanner 2 TCP Listener Thread:** Membaca *stream socket* dari Keyence Scanner 2 untuk kardus dengan label dua sisi (Sisi A & B).
5. **Modbus I/O Monitoring & Actuator Thread:** Membaca sinyal sensor optik (DI) dan memicu aktivasi solenoid silinder dorong (DO) melalui *timer delay* non-blocking.
6. **Embedded Web Server Thread (Daemon):** Menjalankan Flask microservice di latar belakang pada port `5022`.

### 2.3 Topologi Integrasi Hardware Industri

| Perangkat | Antarmuka / Protokol | Default Port / Baudrate | Fungsi Utama |
| :--- | :--- | :--- | :--- |
| **Printer TIJ Omega** | TCP/IP Socket (LAN) | `192.168.1.100 : 6007` | Mengirim data variabel SKU, Kode Kupon, Matl, dan trigger cetak stiker |
| **Keyence Scanner 1** | TCP/IP Socket (LAN) | `192.168.1.99 : 9004` | Verifikasi barcode/QR kupon sisi kiri kardus setelah keluar dari printer |
| **Keyence Scanner 2** | TCP/IP Socket (LAN) | `192.168.1.98 : 9004` | Verifikasi barcode/QR kupon sisi kanan kardus (dual-scanner mode) |
| **Modbus Controller** | Modbus TCP / RTU RS485 | `Port 502` / `COM1 9600-8-E-1` | Membaca sensor konveyor (DI) & memicu solenoid pusher rejector (DO 0) |
| **Tower Lamp & Buzzer**| Digital Output via Modbus | DO 1 (Hijau), DO 2 (Kuning), DO 3 (Merah), DO 4 (Buzzer) | Indikator visual/auditori status mesin (Normal, Warning, Alarm, Cascade NG) |

---

## 3. FRAMEWORK & TEKNOLOGI YANG DIGUNAKAN (TECHNOLOGY STACK)

- **Bahasa Pemrograman:** Python 3.10+ (Kompatibel arsitektur Windows x64).
- **GUI Engine:** `Tkinter` & `ttk` dengan konfigurasi tema native Windows 7 (`vista` / `winnative`) dan tipografi `Segoe UI`. Dilengkapi kanvas vektor kustom untuk *Circular Arc Gauge* dan *Realtime Conveyor Visualization*.
- **Komunikasi Jaringan & Serial:**
  - `socket` bawaan Python dengan konfigurasi `SO_KEEPALIVE` dan `TCP_NODELAY` untuk latensi transmisi instan ke Printer Omega dan Keyence.
  - `pymodbus (>=3.8.0)`: Penanganan protokol Modbus TCP dan Modbus RTU secara persisten.
  - `pyserial (>=3.5)`: Komunikasi serial RS-232/RS-485 ke PLC/modul relay.
- **Pengolahan & Persistensi Data:**
  - `pandas (>=2.2.0)`: Manipulasi dan agregasi dataset batch produksi.
  - `openpyxl (>=3.1.2)`: Penulisan laporan riwayat berformat resmi Microsoft Excel `.xlsx`.
  - Format CSV terindeks: Master log transaksional (`history_summary_log.csv`) dan pencegah duplikasi kupon (`printed_coupons_index.csv`).
  - Atomic JSON: Mekanisme penyimpanan konfigurasi (`config.json`) dan pemulihan insiden (`active_batch_checkpoint.json`).
- **Visualisasi & Pembuatan Label:**
  - `Pillow / PIL (>=10.0.0)`: Rendering visual label stiker, kalkulasi tata letak koordinat pixel, pemosisian logo Syngenta, Benderang, dan NK.
  - `qrcode (>=7.4.2)`: Pembuatan matriks barcode 2D QR Code secara dinamis.
- **Keamanan & Otorisasi:**
  - `hashlib.pbkdf2_hmac` (100.000 iterasi SHA-256) dengan salt kriptografis per-user (`secrets.token_hex`).
  - `hmac.compare_digest`: Validasi password *constant-time* untuk mencegah serangan *timing attack*.
- **Embedded Analytics & Reporting:**
  - `Flask (>=3.0.0)`: Web server lokal mandiri tanpa ketergantungan web server eksternal (Apache/Nginx).
  - `Chart.js`: Grafik visual web dashboard berbasis HTML5 Canvas untuk analisis OEE (*Overall Equipment Effectiveness*) dan rasio cacat (*Yield/NG Rate*).
- **Build & Deployment:**
  - `PyInstaller (>=6.0.0)`: Kompilasi kode sumber Python ke *standalone executable* (`Omega_MX_System.exe`).
  - `Inno Setup`: Pembuat installer resmi Windows lengkap dengan registrasi shortcut, hak akses administrator, dan perlindungan serial number instalasi.

---

## 4. FITUR-FITUR UTAMA SISTEM (CORE FEATURES)

1. **Smart Auto-Start & Clear Buffer Engine:**
   - Saat printer terhubung, sistem otomatis membersihkan buffer sisa cetak (`CLR` dan `RESET`) tanpa mengganggu operator.
2. **Dual-Scanner Multi-Tier QC Judgement:**
   - Mendukung inspeksi kardus satu scanner (single-side) maupun dua scanner (dual-side Sisi A & Sisi B).
   - Menganalisis ketepatan format barcode/QR terhadap data batch yang direncanakan. Jika hasil scan berbeda atau timeout, status dicatat sebagai **NG (Not Good)**.
3. **Pneumatic Rejection Synchronization:**
   - Mengintegrasikan jarak fisik konveyor (jarak scanner ke pusher ~50-80 cm) dengan penghitungan waktu tempuh (`pusher_delay` ms) dan durasi dorongan silinder (`pusher_pulse` ms). Kardus NG akan otomatis terdorong ke jalur reject tanpa menghentikan kardus OK.
4. **Crash Recovery & Checkpoint Management:**
   - Menyimpan status setiap item yang berhasil dicetak dan diinspeksi ke dalam file JSON secara *real-time*.
   - Jika listrik padam atau aplikasi tertutup paksa, saat aplikasi dibuka kembali akan muncul dialog otomatis: *"Ditemukan batch yang belum selesai, lanjutkan produksi?"* dengan seluruh counter dan antrean terpulihkan secara presisi.
5. **Automated Batch Reprinting Cycle (Siklus Cetak Ulang Kardus Cacat):**
   - Di akhir batch, sistem mendeteksi daftar kardus yang NG.
   - Operator cukup menekan *"Cetak Ulang NG"* untuk memulai Siklus 2 (atau seterusnya), mencetak hanya nomor-nomor yang cacat tanpa merusak urutan master data.
6. **Laporan Produksi Terstruktur (Automated History Excel & Master CSV):**
   - Penyimpanan arsip otomatis per folder: `history/YYYY/MM - NamaBulan/`.
   - Menghasilkan file Excel lengkap dengan penandaan warna hijau (OK) dan merah (NG), serta merangkum rekapitulasi ke master CSV.
7. **Pencegahan Kupon Duplikat (Duplicate Coupon Protection):**
   - Indeks kupon otomatis memeriksa apakah nomor kupon tertentu sudah pernah tercetak pada hari/bulan sebelumnya untuk menghindari kecurangan atau pencetakan ganda di pabrik.
8. **Interlock Alarm & Cascade NG Stop:**
   - Jika terjadi 3 kali kegagalan QC berturut-turut (*consecutive NG*), konveyor dan printer otomatis dihentikan sementara (*Interlock Pause*) serta menyalakan Tower Lamp Merah + Buzzer untuk mengundang teknisi memeriksa kebersihan *printhead* atau posisi label.
9. **Modern Combined HMI Layout (Redesain UI V5):**
   - *Dark Sidebar Navigation* (`#1e293b`) dengan 4 menu utama: **Operasi Cetak**, **Riwayat Cetak**, **Koneksi Hardware**, dan **Log Aktivitas**.
   - *System Status Pill Bar* di header: `● READY`, `● RUNNING`, `❚❚ PAUSED`, `■ STOPPED`, `▲ ALARM`.
   - Panel Kiri: Pemilihan file batch Excel/CSV, chip nama file, dan tabel antrean Treeview.
   - Panel Kanan: *Dynamic Arc Gauge* (persentase 0–100%), kartu counter Total OK & Total NG, visualisasi antrean konveyor bergerak, tombol aksi produksi, dan panel simulasi admin yang dapat dilipat (*collapsible*).
10. **Web Analytics Dashboard Terpadu:**
    - Diakses melalui peramban web pada port `5022` (`http://localhost:5022`). Menampilkan grafik tren produksi per jam, rasio perbandingan OK vs NG, dan performa throughput lini.

---

## 5. SKENARIO MASALAH LAPANGAN & SOLUSI YANG TELAH DITERAPKAN

| No | Skenario Masalah di Lapangan | Potensi Dampak | Solusi Rekayasa Teknis yang Diterapkan | Status |
| :---: | :--- | :--- | :--- | :---: |
| **1** | **UI Freezing / Macet saat Hardware Timeout**<br>Kabel LAN printer/scanner terlepas atau PLC lambat merespons. | Operator tidak bisa menekan tombol STOP, HMI Windows *"Not Responding"*. | **Arsitektur Multi-threading Terisolasi:** Seluruh panggilan socket dan serial dipindahkan ke worker thread mandiri dengan batas *timeout* ketat (2.5 detik). Pembaruan UI dilakukan secara asinkron via antrean `root.after()`. | **Selesai** |
| **2** | **Kehilangan Data saat Listrik Padam Tiba-Tiba**<br>Genset pabrik telat menyala saat batch 500 kardus sedang berjalan di nomor 250. | Data batch hilang, kupon tercetak ganda saat diulang dari awal, stok berantakan. | **Atomic JSON Checkpointing:** Tiap kardus selesai di-judge, statusnya ditulis ke file temp lalu di-*replace* atomik ke `active_batch_checkpoint.json`. Dilengkapi dialog auto-resume saat aplikasi dihidupkan kembali. | **Selesai** |
| **3** | **Reprint Cycle Stalling (Batch Tergantung di Siklus 2)**<br>Saat mencetak ulang 1 kardus NG dari 10 kardus awal, sistem menunggu 10 kardus padahal hanya 1 yang dicetak. | Batch tidak pernah selesai, file riwayat Excel tidak ter-generate, tombol selesai terkunci. | **Dinamisasi Expected Judgment Counter:** Mengubah batas target penyelesaian batch secara dinamis: jika `print_cycle > 1`, nilai `expected_total_judgments = len(items_to_print)`. | **Selesai** |
| **4** | **Konflik Akses Modbus (Deadlock & Race Condition)**<br>Thread pemantau sensor DI bertabrakan dengan thread pengaktifan silinder penolak NG (DO 0) dan lampu tower (DO 1-4). | Modbus Client crash, solenoid gagal menembak, kardus NG lolos ke gudang. | **Per-Coil Mutex Lock (`_coil_locks`):** Implementasi kunci mutex individual per alamat coil/register dan sinkronisasi lock global pada modul `modbus_io.py`. | **Selesai** |
| **5** | **Desinkronisasi Pembacaan Dual Scanner**<br>Scanner 1 (sisi A) dan Scanner 2 (sisi B) membaca pada selisih waktu beberapa ratus milidetik tergantung orientasi kardus. | Hasil scan tercampur antar kardus berbeda atau menghasilkan false-NG. | **Sliding Time-Window Buffer:** Sistem menunggu data dari kedua sisi kardus selama rentang toleransi (`dual_scan_timeout`, default 2.0 detik). Jika salah satu sisi membaca OK dalam window waktu tersebut, verifikasi disahkan. | **Selesai** |
| **6** | **Teks Angka Rusak / Leading Zeros Hilang**<br>Kode kupon berawalan angka nol (contoh: `001245`) diubah menjadi angka biasa (`1245`) oleh Excel/Treeview. | Barcode cetak tidak cocok dengan database, verifikasi QC gagal 100%. | **Penyimpanan Teks Murni (`table_items_data`):** Data baris disimpan dalam format *dictionary* string mentah asli sebelum masuk ke tabel UI, mencegah konversi otomatis tipe data angka. | **Selesai** |
| **7** | **Antarmuka Usang dan Tidak Ergonomis**<br>Layout awal berbasis tab atas terasa sempit, batas biru terasa mengganggu, dan bagian bawah layar terpotong taskbar Windows 7. | Operator kesulitan melihat status konveyor dan tombol aksi terpotong di layar pabrik. | **Redesain Mockup Gabungan:** Menghilangkan border biru tebal, menerapkan sidebar vertikal modern `#1e293b`, header status pill terpusat, layout 2 kolom (Tabel Data di kiri, Gauge & Konveyor di kanan), serta kalkulasi ukuran window responsif terhadap resolusi layar. | **Selesai** |
| **8** | **Riwayat Cetak Tidak Sinkron pada Mode Simulasi**<br>Setelah batch simulasi selesai, tabel di menu "Riwayat Cetak" kosong. | Operator / penguji mengira data tidak tersimpan. | **Auto-Refresh Navigation Hook & Auto-Judge:** Menambahkan pemanggilan `self.load_history_table()` otomatis saat tab "Riwayat Cetak" diklik, serta opsi `auto_judge_sim` untuk simulasi otomatis end-to-end tanpa klik manual. | **Selesai** |

---

## 6. STRUKTUR FILE & KOMPONEN SOURCE CODE

```
f:\ProgramPrintSygenta\project-printer-omega - W7
│
├── main.py                  # Core Engine, Orchestration, HMI Tkinter GUI (V5 Modern Layout)
├── printer_omega.py         # Socket Driver Thermal Inkjet Omega (Persistent TCP + KeepAlive)
├── modbus_io.py             # Controller Modbus TCP/RTU dengan Mutex Per-Coil (Sensors & Actuators)
├── data_manager.py          # Atomic Checkpointing, CSV History Summary, & Excel Reporter
├── label_renderer.py        # Rendering Label, Komposisi Logo (Syngenta, NK, Ben), & Matriks QR Code
├── auth_manager.py          # Keamanan: PBKDF2-HMAC-SHA256 Auth, Anti-Brute-Force & Role Management
├── login_dialog.py          # UI Dialog Login Operator, Supervisor, & Admin serta Ubah Sandi
├── analytics_server.py      # Embedded Web Service (Flask + Chart.js) untuk Dashboard Analitik Pabrik
│
├── assets/                  # Aset Gambar, Ikon (.ico), Logo Resmi, & Library JavaScript Lokal
├── data/
│   ├── config.json          # File konfigurasi parameter IP, Port, Delay Solenoid, dsb.
│   └── users.json           # Database akun terenkripsi PBKDF2
├── history/
│   ├── history_summary_log.csv    # Master log ringkasan produksi seluruh batch
│   ├── printed_coupons_index.csv  # Indeks nomor kupon terpakai (Anti-Duplikasi)
│   ├── checkpoints/               # File JSON aktif untuk pemulihan batch pasca insiden
│   └── YYYY/MM - Bulan/          # Folder arsip file Excel (.xlsx) per batch
├── logs/                    # File log teks harian operasional mesin (Auto-cleanup > 30 hari)
│
├── Jalankan_Omega_MX.bat    # Batch launcher cepat untuk lingkungan produksi
├── Omega_MX_System.spec     # Konfigurasi build PyInstaller ke .exe tunggal
└── inno setup.iss           # Skrip installer setup Windows industri
```

---

## 7. SPESIFIKASI DEPLOYMENT & KOMPATIBILITAS SISTEM

- **Sistem Operasi Target:** 
  - Windows 7 Professional / Ultimate (SP1 x64) – *Tested & Fully Supported* (menggunakan tema native `vista`/`winnative` tanpa lag).
  - Windows 10 & Windows 11 (64-bit).
- **Kebutuhan Minimum Perangkat Keras:**
  - Processor: Intel Core i3 (Generasi ke-3 ke atas) / setara.
  - RAM: 4 GB (Penggunaan memori aplikasi sangat ringan: ~65–110 MB saat operasi penuh).
  - Storage: Tersedia minimal 500 MB (untuk penyimpanan arsip log dan Excel hingga ribuan batch).
  - Network: 1 Port Ethernet LAN (dihubungkan ke Industrial Switch yang terhubung ke Printer dan Keyence Scanner) atau USB-to-RS485 Serial Converter untuk Modbus RTU.
- **Prosedur Menjalankan Aplikasi:**
  - Mode Pengembang / Source Code: Klik ganda `cmd shortcut.bat` lalu jalankan perintah `python main.py`.
  - Mode Produksi Pabrik: Klik ganda `Jalankan_Omega_MX.bat` atau jalankan shortcut executable di Desktop hasil kompilasi Inno Setup.

---
*Laporan ini mendokumentasikan seluruh arsitektur, teknologi, fitur, dan riwayat perbaikan teknis sistem hingga implementasi stabil Versi 5.0.*
