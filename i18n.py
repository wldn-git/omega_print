# i18n.py
"""
Modul Internasionalisasi (i18n) Dwibahasa (Bahasa Indonesia & English)
untuk Omega MX Batch Printing & Dual-QC System v2.0.
Mendukung pergantian bahasa secara real-time (on-the-fly) di GUI Tkinter, Dialog, dan Web Analytics.
"""

import os
import json

TRANSLATIONS = {
    "id": {
        # --- App & Header ---
        "app_title_base": "Omega MX - Sistem Cetak Batch & QC Ganda (v2.0 API Ready)",
        "app_title_admin": "Omega MX - Sistem Cetak Batch & QC [ADMINISTRATOR - {name}]",
        "app_title_operator": "Omega MX - Sistem Cetak Batch & QC [OPERATOR - {name}]",
        "header_subtitle": " | Sistem Cetak Batch & QC Ganda (v2.0)",
        "status_ready": "SIAP",
        "status_running": "BERJALAN",
        "status_paused": "DIJEDA",
        "status_stopped": "BERHENTI",
        "status_alarm": "BAHAYA / ALARM",
        "badge_admin": "ADMIN: {name}",
        "badge_operator": "OPERATOR: {name}",
        "btn_change_pass": "Ganti Sandi",
        "btn_switch_user": "Ganti Akun",
        "footer_system_ready": "Sistem Siap",
        "footer_user": "Pengguna: {name} ({role})",

        # --- Sidebar Navigation & Hardware ---
        "nav_main": "Operasi Cetak",
        "nav_history": "Riwayat Cetak",
        "nav_conn": "Koneksi",
        "nav_logs": "Log Aktivitas",
        "nav_master": "Pengaturan Master",
        "hw_status_header": "STATUS PERANGKAT",
        "hw_printer": "Printer Omega",
        "hw_scanner_a": "Scanner Sisi A",
        "hw_scanner_b": "Scanner Sisi B",
        "hw_modbus": "Modbus I/O",
        "hw_api": "API Sistem Utama",

        # --- Tab 1: Operasi Cetak (Main) ---
        "lbl_data_source": "Sumber Data",
        "btn_select_file": "Pilih Berkas",
        "btn_fetch_api": "Tarik API",
        "lbl_no_file": "Belum ada data dipilih",
        "btn_apply": "Terapkan",
        "btn_web_analytics": "Analisis Web",
        "col_no": "No.",
        "col_sku": "Product SKU",
        "col_qr": "Coupon QR",
        "col_matl": "Material Code",
        "col_status": "Status",
        "lbl_batch_progress": "Progres Batch",
        "gauge_progress": "PROGRES",
        "gauge_boxes_done": "Kardus Selesai",
        "gauge_remaining": "Sisa: {rem}",
        "lbl_total_ok": "TOTAL OK",
        "lbl_total_ng": "TOTAL NG",
        "lbl_conveyor_queue": "Antrean Konveyor",
        "lbl_in_transit": "In Transit: {count} Box",
        "conv_head_print": "Head Print",
        "conv_dual_scanner": "Dual Scanner",
        "conv_pusher": "Pusher (DO0)",
        "btn_start_batch": "MULAI CETAK (BATCH)",
        "btn_pause": "JEDA",
        "btn_resume": "LANJUT",
        "btn_stop": "BERHENTI",
        "btn_sim_tools": "Alat Simulasi & Koreksi (Admin)",
        "chk_sim_mode": "Mode Simulasi (Tanpa Hardware)",
        "chk_auto_judge": "Auto-Scan QC (Lolos Otomatis)",
        "btn_resync_queue": "Koreksi Antrean (-1)",
        "btn_judge_ok": "JUDGE OK",
        "btn_judge_ng": "JUDGE NG",

        # --- Table Row Statuses ---
        "st_err_empty_qr": "Error: QR Kosong",
        "st_qc_ok_restored": "QC OK (Dipulihkan)",
        "st_removed_restored": "Dilepas (Dipulihkan)",
        "st_qc_ng_restored": "QC NG (Dipulihkan)",
        "st_dup_days": "Duplikat {days}H ({date})",
        "st_dup_file": "Duplikat File (No.{row})",
        "st_ready_print": "Siap Cetak",
        "st_in_queue": "Antrean Cetak",
        "st_qc_ok": "QC OK",
        "st_qc_ng": "QC NG",
        "st_removed_manual": "Dilepas Manual",

        # --- Tab 2: Riwayat Cetak (History) ---
        "hist_title": "Daftar Riwayat Cetak Batch",
        "hist_filter_frame": " Filter Tampilan Data ",
        "hist_last_20": "20 Data Terakhir",
        "hist_by_date": "Berdasarkan Tanggal:",
        "hist_date_to": " s/d ",
        "btn_show": "Tampilkan",
        "btn_export_raw_csv": "EKSPOR DATA MENTAH CSV",
        "btn_open_excel": "BUKA BERKAS EXCEL TERPILIH",
        "hcol_start": "Waktu Mulai",
        "hcol_end": "Waktu Selesai",
        "hcol_duration": "Durasi Waktu",
        "hcol_source": "Sumber Data",
        "hcol_total_data": "Total Data",
        "hcol_total_print": "Total Cetak",
        "hcol_total_ng": "Total NG",
        "hcol_ng_level": "Reprint",

        # --- Tab 3: Koneksi (Connectivity) ---
        "conn_printer_group": " Konfigurasi Printer Omega MX (TCP/IP) ",
        "btn_test_conn": "Uji Koneksi",
        "btn_save_cfg": "Simpan Konfigurasi",
        "conn_scanner_group": " Konfigurasi Dual Scanner Keyence SR (TCP/IP) ",
        "conn_s1_box": " Scanner 1 (Sisi A - Depan) ",
        "conn_s2_box": " Scanner 2 (Sisi B - Belakang) ",
        "btn_connect_s": "Hubungkan S{id}",
        "btn_disconnect_s": "Putuskan S{id}",
        "lbl_connected": "Terhubung",
        "lbl_disconnected": "Terputus",
        "lbl_scan_result": "Hasil Scan:",
        "lbl_waiting_data": "- Menunggu Data -",
        "btn_connect_both": "Hubungkan Kedua Scanner",
        "btn_disconnect_all": "Putus Semua",
        "lbl_pairing_timeout": "Timeout Pairing (ms):",
        "lbl_scanner_info": "Info: Sisi A & Sisi B wajib COCOK. Jika 1 sisi timeout/beda -> REJECT.",
        "conn_modbus_group": " Sistem Modbus I/O (DI/DO) ",
        "btn_test_modbus_tcp": "Uji Modbus TCP",
        "btn_test_modbus_rtu": "Uji Modbus RTU",
        "btn_start_io": "Mulai Monitor I/O",
        "btn_stop_io": "Hentikan Monitor",
        "btn_test_pusher": "Uji Pusher (DO 0)",
        "btn_test_alarm": "Uji Lampu Alarm (DO 1)",
        "lbl_pusher_delay": "Tunda Pusher (ms):",
        "lbl_pusher_pulse": "Durasi Dorong (ms):",
        "conn_io_map_group": " Pemetaan Alamat & Deskripsi Sinyal I/O Modbus ",
        "lbl_io_input_hdr": "INPUT (DI / Sensor Fisik Mesin ke PC):",
        "lbl_io_output_hdr": "OUTPUT (DO / Aktuator & Alarm dari PC):",
        "di0_title": "Sensor Head Print",
        "di0_desc": "Mendeteksi kedatangan kardus di head printer",
        "di1_title": "Sensor Scanner",
        "di1_desc": "Mendeteksi kardus tiba di bawah scanner Keyence",
        "di2_title": "Sensor Pusher",
        "di2_desc": "Mendeteksi kardus tepat di depan silinder rejector",
        "di3_title": "Interlock / Safety",
        "di3_desc": "Status konveyor jalan / tombol darurat (E-Stop)",
        "do0_title": "Pneumatic Pusher (Reject)",
        "do0_desc": "Silinder pendorong kardus NG (Pulsa aktif 0.5s)",
        "do1_title": "Tower Lamp MERAH (NG)",
        "do1_desc": "Alarm visual & buzzer saat terdeteksi hasil NG",
        "do2_title": "Tower Lamp KUNING",
        "do2_desc": "Indikator status siaga / jeda produksi",
        "do3_title": "Tower Lamp HIJAU",
        "do3_desc": "Indikator mesin berjalan normal & QC OK",
        "conn_api_group": " Integrasi API Sistem Utama (ERP / MES / Core Server) ",
        "chk_api_enable": "Aktifkan Integrasi API Sistem Utama",
        "lbl_api_untested": "Belum Diuji",
        "lbl_api_connecting": "Menghubungkan...",
        "lbl_api_connected": "Terhubung ({ms:.0f} ms)",
        "lbl_api_failed": "Terputus / Gagal",
        "lbl_api_proto_info": "Protokol: REST JSON Dua Arah (Client Pull/Push & Server Lokal Port 5022)",
        "lbl_api_base_url": "Base URL API:",
        "lbl_api_timeout": "Timeout (detik):",
        "lbl_api_key": "API Key / Token:",
        "btn_show_key": "Tampilkan",
        "btn_hide_key": "Sembunyikan",
        "lbl_ep_wo": "Endpoint Tarik WO:",
        "lbl_ep_batch": "Endpoint Kirim Hasil:",
        "lbl_ep_box": "Endpoint QC Box:",
        "chk_auto_sync_batch": "Kirim otomatis ringkasan produksi ke Sistem Utama saat batch selesai",
        "chk_auto_sync_box": "Kirim hasil QC real-time per kardus",
        "btn_test_api": "Uji Koneksi API",
        "btn_save_api": "Simpan Konfigurasi API",
        "btn_fetch_wo_now": "Tarik Work Order Sekarang",
        "btn_api_spec": "Spesifikasi Payload API",

        # --- Tab 5: Pengaturan Master (Master Settings) ---
        "master_title": "PENGATURAN MASTER SISTEM",
        "master_subtitle": "Pengaturan Bahasa, Hak Akses Pengguna & Masa Simpan Riwayat Data",
        "master_lang_group": " Pengaturan Bahasa Antarmuka (Language) ",
        "master_lang_lbl": "Pilih Bahasa Sistem / Select System Language:",
        "master_users_group": " Manajemen Akun Pengguna & Hak Akses ",
        "btn_add_user": "Tambah Pengguna Baru",
        "btn_edit_user": "Ubah Pengguna Terpilih",
        "btn_del_user": "Hapus Pengguna",
        "btn_refresh_users": "Segarkan Data",
        "ucol_username": "ID Pengguna",
        "ucol_name": "Nama Lengkap",
        "ucol_role": "Peran (Role)",
        "ucol_pages": "Hak Akses Halaman",
        "ucol_features": "Hak Akses Fitur",
        "pname_main": "Operasi",
        "pname_history": "Riwayat",
        "pname_conn": "Koneksi",
        "pname_logs": "Log",
        "pname_master": "Master",
        "fname_export_csv": "Ekspor CSV",
        "fname_fetch_api": "Tarik API",
        "fname_simulation_mode": "Simulasi",
        "fname_manage_users": "Kelola Akun",
        "master_ret_group": " Pengaturan Masa Simpan Riwayat (Retensi Data & Overwrite History) ",
        "master_ret_desc": "Batas waktu usia (dalam hari) untuk pengecekan otomatis kupon duplikat dan pembersihan file catatan riwayat lama.\nKupon yang sama dalam rentang hari ini akan dicegah agar tidak tercetak dua kali demi menjaga integritas produksi.",
        "lbl_retention_days": "Masa Simpan Riwayat (Hari):",
        "lbl_quick_presets": "Pilihan Cepat:",
        "btn_save_retention": "Simpan Masa Simpan",
        "lbl_maint_actions": "Tindakan Pemeliharaan Riwayat:",
        "btn_clean_logs": "Bersihkan Catatan Log Tua Sekarang",
        "btn_export_master_coupons": "Ekspor Master Kupon (.csv)",

        # --- Login Dialog & Change Password ---
        "login_win_title": "Omega MX - Login Akses Pengguna",
        "login_hdr_switch": "Ganti Akun Pengguna",
        "login_hdr_initial": "Silakan Masuk ke Sistem",
        "login_lbl_user": "ID Pengguna:",
        "login_lbl_pass": "Kata Sandi:",
        "login_chk_show": "Tampilkan Kata Sandi",
        "login_btn_submit": "MASUK",
        "login_btn_cancel": "Batal",
        "login_btn_exit": "Keluar dari Aplikasi",
        "login_security_hint": "Sistem Terproteksi | Hubungi Supervisor untuk Hak Akses",
        "login_err_empty_user": "ID Pengguna tidak boleh kosong.",
        "login_err_empty_pass": "Kata sandi tidak boleh kosong.",
        "chg_win_title": "Ubah Kata Sandi - Omega MX",
        "chg_hdr": "Ganti Kata Sandi Akun",
        "chg_lbl_account": "Pilih Akun:",
        "chg_lbl_old": "Kata Sandi Lama:",
        "chg_lbl_new": "Kata Sandi Baru:",
        "chg_lbl_conf": "Ulangi Kata Sandi:",
        "chg_btn_save": "Simpan Kata Sandi Baru",
        "chg_err_mismatch": "Konfirmasi kata sandi baru tidak cocok.",
        "chg_err_min_len": "Kata sandi baru minimal 6 karakter.",

        # --- User Management Dialog ---
        "um_title_edit": "Ubah Pengguna: {username}",
        "um_title_add": "Tambah Pengguna Baru",
        "um_hdr_edit": "Formulir Ubah Data Pengguna",
        "um_hdr_add": "Formulir Registrasi Pengguna Baru",
        "um_sub": "Tentukan identitas login, peran otorisasi, dan hak akses halaman/fitur.",
        "um_grp_identity": " Identitas Akun Pengguna ",
        "um_lbl_uname": "ID Pengguna (Username):",
        "um_lbl_perm": "(Permanen)",
        "um_lbl_fullname": "Nama Lengkap Pengguna:",
        "um_lbl_role": "Peran Pengguna (Role):",
        "um_role_op": "Operator Produksi",
        "um_role_adm": "Administrator",
        "um_lbl_pwd_new": "Kata Sandi Baru:",
        "um_lbl_pwd": "Kata Sandi (Password):",
        "um_lbl_pwd_hint": "(Kosongkan bila tidak diubah)",
        "um_lbl_pwd_conf": "Ulangi Kata Sandi:",
        "um_grp_pages": " Hak Akses Halaman Sistem (Navigasi) ",
        "um_page_main": "Operasi Cetak (Layar Kontrol & Pemantauan Batch Langsung)",
        "um_page_history": "Riwayat Cetak (Tabel Laporan & Rekapitulasi Produksi)",
        "um_page_conn": "Koneksi (Pengaturan Printer, Scanner, Modbus, dan API)",
        "um_page_logs": "Log Aktivitas (Catatan Jejak Operasional & Keamanan Sistem)",
        "um_page_master": "Pengaturan Master (Kelola Akun Pengguna & Masa Simpan Riwayat)",
        "um_grp_feats": " Hak Akses Fitur & Otoritas Operasional ",
        "um_feat_csv": "Ekspor Data Mentah CSV (Unduh Arsip Ringkasan & Kupon)",
        "um_feat_api": "Tarik Data Work Order via API Sistem Utama",
        "um_feat_sim": "Beralih ke Mode Simulasi (Pengujian Tanpa Alat Fisik)",
        "um_feat_users": "Kelola Akun Pengguna & Ubah Batas Retensi Riwayat",
        "um_btn_cancel": "Batal",
        "um_btn_save": "Simpan Pengguna",

        # --- Fetch API Work Order Dialog ---
        "wo_win_title": "Tarik Work Order dari Sistem Utama (ERP / MES)",
        "wo_hdr_title": "Integrasi API Sistem Utama - Pemilihan Work Order (SPK)",
        "fetch_target_server": "Target Server: {url}",
        "wo_lbl_preparing": "Menyiapkan koneksi...",
        "wo_btn_refresh": "Ambil Ulang Data API",
        "wo_col_id": "No. Work Order / SPK",
        "wo_col_sku": "Kode SKU",
        "wo_col_name": "Nama Produk / Deskripsi",
        "wo_col_batch": "No. Batch",
        "wo_col_qty": "Target (Box)",
        "wo_col_status": "Status",
        "wo_col_prio": "Prioritas",
        "wo_grp_detail": " Detail Work Order Terpilih ",
        "wo_lbl_select_hint": "Pilih salah satu baris Work Order di atas untuk melihat detail item dan memuat ke mesin.",
        "wo_btn_cfg": "Konfigurasi API",
        "wo_btn_excel": "Gunakan Berkas Excel (Cadangan)",
        "wo_btn_cancel": "Batal",
        "wo_btn_load": "Muat Work Order ke Antrean Produksi",
        "wo_lbl_connecting": "Menghubungi Sistem Utama via REST API...",
        "wo_lbl_found": "Ditemukan {count} Work Order aktif dari Sistem Utama.",
        "wo_lbl_empty": "Sistem Utama tidak memiliki data Work Order aktif saat ini.",
        "stat_rem": "{valid} (Sisa: {rem})",
        "stat_skip": "{valid} ({skip} Skip)",
        "lbl_modbus_ip": "Modbus IP:",
        "lbl_port": "Port:",
        "lbl_serial_settings": " Pengaturan Serial (RTU) ",
        "lbl_serial_mode": " Mode ",
        "spec_win_title": "Spesifikasi Kontrak REST API Sistem Utama (v2.0)",
        "spec_header_title": "Dokumentasi & Spesifikasi Integrasi API (Bi-directional)",
        "spec_header_sub": "Format JSON Inbound & Outbound untuk komunikasi antara Omega MX dan ERP / MES Pabrik",
        "btn_copy_spec": "Salin Spesifikasi ke Clipboard",
        "btn_close": "Tutup",
        "msg_copied": "Tersalin",
        "msg_copied_detail": "Spesifikasi kontrak API berhasil disalin ke clipboard!",
        "master_lang_desc": "Pilih bahasa tampilan untuk seluruh antarmuka aplikasi (HMI, Dialog, dan Web Analytics).",
        "btn_lang_id": "Bahasa Indonesia (IND)",
        "btn_lang_en": "English (ENG)",
    },
    "en": {
        # --- App & Header ---
        "app_title_base": "Omega MX - Batch Printing & Dual-QC System (v2.0 API Ready)",
        "app_title_admin": "Omega MX - Batch Printing & QC System [ADMINISTRATOR - {name}]",
        "app_title_operator": "Omega MX - Batch Printing & QC System [OPERATOR - {name}]",
        "header_subtitle": " | Batch Printing & Dual-QC System (v2.0)",
        "status_ready": "READY",
        "status_running": "RUNNING",
        "status_paused": "PAUSED",
        "status_stopped": "STOPPED",
        "status_alarm": "DANGER / ALARM",
        "badge_admin": "ADMIN: {name}",
        "badge_operator": "OPERATOR: {name}",
        "btn_change_pass": "Change Password",
        "btn_switch_user": "Switch User",
        "footer_system_ready": "System Ready",
        "footer_user": "User: {name} ({role})",

        # --- Sidebar Navigation & Hardware ---
        "nav_main": "Print Operations",
        "nav_history": "Print History",
        "nav_conn": "Connectivity",
        "nav_logs": "Activity Logs",
        "nav_master": "Master Settings",
        "hw_status_header": "HARDWARE STATUS",
        "hw_printer": "Omega Printer",
        "hw_scanner_a": "Scanner Side A",
        "hw_scanner_b": "Scanner Side B",
        "hw_modbus": "Modbus I/O",
        "hw_api": "Core ERP API",

        # --- Tab 1: Operasi Cetak (Main) ---
        "lbl_data_source": "Data Source",
        "btn_select_file": "Select File",
        "btn_fetch_api": "Fetch API",
        "lbl_no_file": "No data selected",
        "btn_apply": "Apply",
        "btn_web_analytics": "Web Analytics",
        "col_no": "No.",
        "col_sku": "Product SKU",
        "col_qr": "Coupon QR",
        "col_matl": "Material Code",
        "col_status": "Status",
        "lbl_batch_progress": "Batch Progress",
        "gauge_progress": "PROGRESS",
        "gauge_boxes_done": "Boxes Completed",
        "gauge_remaining": "Left: {rem}",
        "lbl_total_ok": "TOTAL OK",
        "lbl_total_ng": "TOTAL NG",
        "lbl_conveyor_queue": "Conveyor Queue",
        "lbl_in_transit": "In Transit: {count} Box",
        "conv_head_print": "Print Head",
        "conv_dual_scanner": "Dual Scanner",
        "conv_pusher": "Pusher (DO0)",
        "btn_start_batch": "START BATCH PRINT",
        "btn_pause": "PAUSE",
        "btn_resume": "RESUME",
        "btn_stop": "STOP",
        "btn_sim_tools": "Simulation & Queue Tools (Admin)",
        "chk_sim_mode": "Simulation Mode (No Hardware)",
        "chk_auto_judge": "Auto-Scan QC (Auto Pass)",
        "btn_resync_queue": "Resync Queue (-1)",
        "btn_judge_ok": "JUDGE OK",
        "btn_judge_ng": "JUDGE NG",

        # --- Table Row Statuses ---
        "st_err_empty_qr": "Error: Empty QR",
        "st_qc_ok_restored": "QC OK (Restored)",
        "st_removed_restored": "Removed (Restored)",
        "st_qc_ng_restored": "QC NG (Restored)",
        "st_dup_days": "Duplicate {days}D ({date})",
        "st_dup_file": "File Duplicate (No.{row})",
        "st_ready_print": "Ready to Print",
        "st_in_queue": "In Print Queue",
        "st_qc_ok": "QC OK",
        "st_qc_ng": "QC NG",
        "st_removed_manual": "Manually Removed",

        # --- Tab 2: Riwayat Cetak (History) ---
        "hist_title": "Batch Printing History List",
        "hist_filter_frame": " Data View Filter ",
        "hist_last_20": "Last 20 Records",
        "hist_by_date": "By Date Range:",
        "hist_date_to": " to ",
        "btn_show": "Filter",
        "btn_export_raw_csv": "EXPORT RAW DATA CSV",
        "btn_open_excel": "OPEN SELECTED EXCEL REPORT",
        "hcol_start": "Start Time",
        "hcol_end": "End Time",
        "hcol_duration": "Duration",
        "hcol_source": "Data Source",
        "hcol_total_data": "Total Data",
        "hcol_total_print": "Total Printed",
        "hcol_total_ng": "Total NG",
        "hcol_ng_level": "Reprint",

        # --- Tab 3: Koneksi (Connectivity) ---
        "conn_printer_group": " Omega MX Printer Configuration (TCP/IP) ",
        "btn_test_conn": "Test Connection",
        "btn_save_cfg": "Save Configuration",
        "conn_scanner_group": " Dual Keyence SR Scanner Configuration (TCP/IP) ",
        "conn_s1_box": " Scanner 1 (Side A - Front) ",
        "conn_s2_box": " Scanner 2 (Side B - Rear) ",
        "btn_connect_s": "Connect S{id}",
        "btn_disconnect_s": "Disconnect S{id}",
        "lbl_connected": "Connected",
        "lbl_disconnected": "Disconnected",
        "lbl_scan_result": "Scan Result:",
        "lbl_waiting_data": "- Waiting for Data -",
        "btn_connect_both": "Connect Both Scanners",
        "btn_disconnect_all": "Disconnect All",
        "lbl_pairing_timeout": "Pairing Timeout (ms):",
        "lbl_scanner_info": "Info: Side A & Side B must MATCH. If 1 side times out/differs -> REJECT.",
        "conn_modbus_group": " Modbus I/O System (DI/DO) ",
        "btn_test_modbus_tcp": "Test Modbus TCP",
        "btn_test_modbus_rtu": "Test Modbus RTU",
        "btn_start_io": "Start I/O Monitor",
        "btn_stop_io": "Stop Monitor",
        "btn_test_pusher": "Test Pusher (DO 0)",
        "btn_test_alarm": "Test Alarm Lamp (DO 1)",
        "lbl_pusher_delay": "Pusher Delay (ms):",
        "lbl_pusher_pulse": "Push Pulse (ms):",
        "conn_io_map_group": " Modbus I/O Address Mapping & Signal Description ",
        "lbl_io_input_hdr": "INPUTS (DI / Physical Machine Sensors to PC):",
        "lbl_io_output_hdr": "OUTPUTS (DO / Actuators & Alarms from PC):",
        "di0_title": "Print Head Sensor",
        "di0_desc": "Detects box arrival at the printer head",
        "di1_title": "Scanner Sensor",
        "di1_desc": "Detects box arrival under Keyence scanners",
        "di2_title": "Pusher Sensor",
        "di2_desc": "Detects box right in front of rejector cylinder",
        "di3_title": "Interlock / Safety",
        "di3_desc": "Conveyor running status / Emergency Stop (E-Stop)",
        "do0_title": "Pneumatic Pusher (Reject)",
        "do0_desc": "NG box rejector cylinder (Active pulse 0.5s)",
        "do1_title": "RED Tower Lamp (NG)",
        "do1_desc": "Visual & buzzer alarm when NG result is detected",
        "do2_title": "YELLOW Tower Lamp",
        "do2_desc": "Standby / production pause indicator",
        "do3_title": "GREEN Tower Lamp",
        "do3_desc": "Normal machine running & QC OK indicator",
        "conn_api_group": " Core System API Integration (ERP / MES / Core Server) ",
        "chk_api_enable": "Enable Core System API Integration",
        "lbl_api_untested": "Not Tested",
        "lbl_api_connecting": "Connecting...",
        "lbl_api_connected": "Connected ({ms:.0f} ms)",
        "lbl_api_failed": "Disconnected / Failed",
        "lbl_api_proto_info": "Protocol: Bi-directional REST JSON (Client Pull/Push & Local Server Port 5022)",
        "lbl_api_base_url": "API Base URL:",
        "lbl_api_timeout": "Timeout (sec):",
        "lbl_api_key": "API Key / Token:",
        "btn_show_key": "Show",
        "btn_hide_key": "Hide",
        "lbl_ep_wo": "Pull WO Endpoint:",
        "lbl_ep_batch": "Submit Batch Endpoint:",
        "lbl_ep_box": "QC Box Endpoint:",
        "chk_auto_sync_batch": "Auto-send production summary to Core System on batch completion",
        "chk_auto_sync_box": "Push real-time QC result per box",
        "btn_test_api": "Test API Connection",
        "btn_save_api": "Save API Config",
        "btn_fetch_wo_now": "Fetch Work Order Now",
        "btn_api_spec": "API Payload Specification",

        # --- Tab 5: Pengaturan Master (Master Settings) ---
        "master_title": "SYSTEM MASTER SETTINGS",
        "master_subtitle": "Interface Language, User Permissions & History Retention Settings",
        "master_lang_group": " Interface Language Settings (Bahasa) ",
        "master_lang_lbl": "Select System Language / Pilih Bahasa Sistem:",
        "master_users_group": " User Account & Permission Management ",
        "btn_add_user": "Add New User",
        "btn_edit_user": "Edit Selected User",
        "btn_del_user": "Delete User",
        "btn_refresh_users": "Refresh Data",
        "ucol_username": "User ID",
        "ucol_name": "Full Name",
        "ucol_role": "Role",
        "ucol_pages": "Page Permissions",
        "ucol_features": "Feature Permissions",
        "pname_main": "Operations",
        "pname_history": "History",
        "pname_conn": "Connectivity",
        "pname_logs": "Logs",
        "pname_master": "Master",
        "fname_export_csv": "Export CSV",
        "fname_fetch_api": "Fetch API",
        "fname_simulation_mode": "Simulation",
        "fname_manage_users": "Manage Users",
        "master_ret_group": " History Retention Settings (Duplicate Check & Log Cleanup) ",
        "master_ret_desc": "Retention period (in days) for automatic duplicate coupon checking and old log file cleanup.\nIdentical coupons within this period will be blocked from re-printing to ensure production integrity.",
        "lbl_retention_days": "Retention Period (Days):",
        "lbl_quick_presets": "Quick Presets:",
        "btn_save_retention": "Save Retention",
        "lbl_maint_actions": "History Maintenance Actions:",
        "btn_clean_logs": "Clean Up Old Log Files Now",
        "btn_export_master_coupons": "Export Master Coupons (.csv)",

        # --- Login Dialog & Change Password ---
        "login_win_title": "Omega MX - User Access Login",
        "login_hdr_switch": "Switch User Account",
        "login_hdr_initial": "Sign In to System",
        "login_lbl_user": "User ID:",
        "login_lbl_pass": "Password:",
        "login_chk_show": "Show Password",
        "login_btn_submit": "SIGN IN",
        "login_btn_cancel": "Cancel",
        "login_btn_exit": "Exit Application",
        "login_security_hint": "Protected System | Contact Supervisor for Access Rights",
        "login_err_empty_user": "User ID cannot be empty.",
        "login_err_empty_pass": "Password cannot be empty.",
        "chg_win_title": "Change Password - Omega MX",
        "chg_hdr": "Change Account Password",
        "chg_lbl_account": "Select Account:",
        "chg_lbl_old": "Current Password:",
        "chg_lbl_new": "New Password:",
        "chg_lbl_conf": "Confirm Password:",
        "chg_btn_save": "Save New Password",
        "chg_err_mismatch": "New password confirmation does not match.",
        "chg_err_min_len": "New password must be at least 6 characters.",

        # --- User Management Dialog ---
        "um_title_edit": "Edit User: {username}",
        "um_title_add": "Add New User",
        "um_hdr_edit": "Edit User Account Form",
        "um_hdr_add": "New User Registration Form",
        "um_sub": "Specify login identity, authorization role, and page/feature access rights.",
        "um_grp_identity": " User Account Identity ",
        "um_lbl_uname": "User ID (Username):",
        "um_lbl_perm": "(Permanent)",
        "um_lbl_fullname": "Full Name:",
        "um_lbl_role": "User Role:",
        "um_role_op": "Production Operator",
        "um_role_adm": "Administrator",
        "um_lbl_pwd_new": "New Password:",
        "um_lbl_pwd": "Password:",
        "um_lbl_pwd_hint": "(Leave blank to keep unchanged)",
        "um_lbl_pwd_conf": "Confirm Password:",
        "um_grp_pages": " System Page Access Rights (Navigation) ",
        "um_page_main": "Print Operations (Live Batch Control & Monitoring Screen)",
        "um_page_history": "Print History (Production Report & Summary Table)",
        "um_page_conn": "Connectivity (Printer, Scanner, Modbus, and API Settings)",
        "um_page_logs": "Activity Logs (Operational Trail & System Security Logs)",
        "um_page_master": "Master Settings (Manage User Accounts & History Retention)",
        "um_grp_feats": " Feature Access & Operational Authorities ",
        "um_feat_csv": "Export Raw Data CSV (Download Summary & Coupon Archives)",
        "um_feat_api": "Fetch Work Order Data via Core System API",
        "um_feat_sim": "Switch to Simulation Mode (Testing Without Physical Hardware)",
        "um_feat_users": "Manage User Accounts & Modify History Retention Limit",
        "um_btn_cancel": "Cancel",
        "um_btn_save": "Save User",

        # --- Fetch API Work Order Dialog ---
        "wo_win_title": "Fetch Work Orders from Core System (ERP / MES)",
        "wo_hdr_title": "Core System API Integration - Work Order Selection",
        "fetch_target_server": "Target Server: {url}",
        "wo_lbl_preparing": "Preparing connection...",
        "wo_btn_refresh": "Refresh API Data",
        "wo_col_id": "Work Order No.",
        "wo_col_sku": "SKU Code",
        "wo_col_name": "Product Name / Description",
        "wo_col_batch": "Batch No.",
        "wo_col_qty": "Target (Boxes)",
        "wo_col_status": "Status",
        "wo_col_prio": "Priority",
        "wo_grp_detail": " Selected Work Order Details ",
        "wo_lbl_select_hint": "Select a Work Order row above to view item details and load into machine.",
        "wo_btn_cfg": "API Settings",
        "wo_btn_excel": "Use Excel File (Fallback)",
        "wo_btn_cancel": "Cancel",
        "wo_btn_load": "Load Work Order to Production Queue",
        "wo_lbl_connecting": "Contacting Core System via REST API...",
        "wo_lbl_found": "Found {count} active Work Order(s) from Core System.",
        "wo_lbl_empty": "Core System has no active Work Orders at this time.",
        "stat_rem": "{valid} (Left: {rem})",
        "stat_skip": "{valid} ({skip} Skip)",
        "lbl_modbus_ip": "Modbus IP:",
        "lbl_port": "Port:",
        "lbl_serial_settings": " Serial Settings (RTU) ",
        "lbl_serial_mode": " Mode ",
        "spec_win_title": "Core System REST API Contract Specification (v2.0)",
        "spec_header_title": "Bi-directional API Integration Documentation & Specification",
        "spec_header_sub": "Inbound & Outbound JSON Format for communication between Omega MX and Factory ERP / MES",
        "btn_copy_spec": "Copy Specification to Clipboard",
        "btn_close": "Close",
        "msg_copied": "Copied",
        "msg_copied_detail": "API contract specification copied to clipboard!",
        "master_lang_desc": "Select the display language for the entire application interface (HMI, Dialogs, and Web Analytics).",
        "btn_lang_id": "Bahasa Indonesia (IND)",
        "btn_lang_en": "English (ENG)",
    }
}


class I18nManager:
    """Singleton pengelola bahasa aplikasi (ID / EN) dengan penyimpanan otomatis di config.json"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(I18nManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(base_dir, "data", "config.json")
        self.lang = self._load_lang_from_config()
        self._listeners = []

    def _load_lang_from_config(self) -> str:
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                lang = str(cfg.get("language", "id")).strip().lower()
                if lang in ("id", "en"):
                    return lang
        except Exception:
            pass
        return "id"

    def save_lang_to_config(self, lang: str):
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            cfg = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            cfg["language"] = lang
            temp_file = self.config_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
            os.replace(temp_file, self.config_file)
        except Exception as e:
            print(f"Error saving language to config.json: {e}")

    def get_lang(self) -> str:
        return self.lang

    def set_lang(self, lang: str, persist: bool = True):
        lang = str(lang).strip().lower()
        if lang not in ("id", "en"):
            lang = "id"
        self.lang = lang
        if persist:
            self.save_lang_to_config(lang)
        for cb in list(self._listeners):
            try:
                cb(self.lang)
            except Exception as e:
                print(f"Error in i18n listener: {e}")

    def toggle_lang(self) -> str:
        new_lang = "en" if self.lang == "id" else "id"
        self.set_lang(new_lang)
        return new_lang

    def add_listener(self, callback):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def t(self, key: str, **kwargs) -> str:
        lang_dict = TRANSLATIONS.get(self.lang, TRANSLATIONS["id"])
        text = lang_dict.get(key)
        if text is None:
            text = TRANSLATIONS["id"].get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text


# Global helper instance & function
i18n = I18nManager()

def tr(key: str, **kwargs) -> str:
    return i18n.t(key, **kwargs)

