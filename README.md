# Omega MX - Batch Printing & Quality Control System (v5.0 Stable)

Aplikasi HMI (*Human Machine Interface*) kustom berbasis Python untuk otomasi lini pengemasan dan pencetakan batch (*Thermal Inkjet Omega*), terintegrasi dengan inspeksi *Dual Scanner Keyence* (QC Barcode/QR Verification), penolakan pneumatik *Modbus I/O*, serta *Web Analytics Dashboard*.

---

## 🚀 Cara Menjalankan Aplikasi (Quick Start)

### **Metode 1: Otomatis (1-Klik via Batch File)**
1. Pastikan di komputer sudah terinstal **Python 3.10+** (Centang *"Add Python to PATH"* saat instalasi).
2. Unduh atau clone repositori ini:
   ```bash
   git clone https://github.com/wldn-git/omega_print.git
   cd omega_print
   ```
3. Klik ganda file:
   ```cmd
   Jalankan_Omega_MX.bat
   ```
   > **Catatan:** Pada saat pertama kali dijalankan di komputer baru, skrip launcher ini akan secara otomatis:
   > - Membuat virtual environment (`venv`)
   > - Menginstal semua pustaka dependensi dari `requirements.txt`
   > - Menginisialisasi direktori data dan akun default
   > - Membuka aplikasi secara langsung.

---

### **Metode 2: Manual via Terminal / Command Prompt**
```bash
# 1. Buat dan aktifkan virtual environment
python -m venv venv
venv\Scripts\activate

# 2. Instal seluruh dependensi
pip install -r requirements.txt

# 3. Jalankan aplikasi utama
python main.py
```

---

## 🔑 Akun Login Default Sistem
Saat aplikasi pertama kali dijalankan, sistem otomatis membuat akun otentikasi awal:
* **Administrator:**
  * Username: `admin`
  * Password: `admin123`
* **Operator:**
  * Username: `operator`
  * Password: `operator123`

*(Kata sandi dapat diubah sewaktu-waktu melalui menu Akun di dalam aplikasi)*

---

## 📊 Akses Web Analytics Dashboard
Setelah aplikasi berjalan, buka peramban web pada komputer yang sama:
* URL: `http://localhost:5022`

---

## 📖 Dokumentasi Lengkap Proyek
Silakan baca laporan teknis lengkap pada:
- **Format Markdown:** [`PROJECT_REPORT_OMEGA_MX_V5.md`](PROJECT_REPORT_OMEGA_MX_V5.md)
- **Format Teks:** [`PROJECT_REPORT_OMEGA_MX_V5.txt`](PROJECT_REPORT_OMEGA_MX_V5.txt)
