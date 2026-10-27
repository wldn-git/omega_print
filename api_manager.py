# api_manager.py
"""
Modul Integrasi API Sistem Utama (ERP / MES / Core Server) untuk Omega MX.
Mendukung komunikasi dua arah:
1. Inbound (Tarik Data): Mengambil Work Order, SKU, QR Kupon, dan Material Code dari Sistem Utama.
2. Outbound (Kirim Data): Mengirimkan hasil QC per box dan ringkasan batch produksi ke Sistem Utama.
"""

import json
import time
import threading
import urllib.request
import urllib.error
import urllib.parse
import pandas as pd

class APIManager:
    def __init__(self, config=None):
        self.config = config if config else {}
        self.last_sync_status = "Idle"
        self.last_sync_time = None
        self.last_error = None
        self.is_connected = False
        self._lock = threading.Lock()

    def update_config(self, config_dict):
        with self._lock:
            self.config.update(config_dict)

    def _build_headers(self, api_key=None):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "OmegaMX-HMI/v2.0"
        }
        key = api_key if api_key is not None else self.config.get("api_key", "")
        if key and key.strip():
            # Jika api_key berawalan Bearer, gunakan langsung, jika tidak tambahkan Bearer
            if key.startswith("Bearer "):
                headers["Authorization"] = key.strip()
            else:
                headers["Authorization"] = f"Bearer {key.strip()}"
                headers["X-API-Key"] = key.strip()
        return headers

    def test_connection(self, base_url=None, api_key=None, timeout=None):
        """
        Menguji konektivitas ke Sistem Utama (Health Check atau ping endpoint).
        Return: (success: bool, message: str, latency_ms: float)
        """
        url = (base_url or self.config.get("api_base_url", "")).strip().rstrip("/")
        if not url:
            return False, "Base URL API belum diisi.", 0.0

        t_out = float(timeout or self.config.get("api_timeout", 5))
        headers = self._build_headers(api_key)

        # Coba cek beberapa kemungkinan endpoint health check standar
        candidates = [
            f"{url}/health",
            f"{url}/ping",
            f"{url}/status",
            f"{url}"
        ]

        t0 = time.time()
        last_msg = ""
        for target in candidates:
            try:
                req = urllib.request.Request(target, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=t_out) as resp:
                    latency = round((time.time() - t0) * 1000, 1)
                    status_code = resp.getcode()
                    if 200 <= status_code < 300:
                        self.is_connected = True
                        return True, f"Koneksi Berhasil! (HTTP {status_code}, Respon {latency} ms)", latency
            except urllib.error.HTTPError as e:
                # Jika 401/403, berarti server merespons tapi auth salah
                latency = round((time.time() - t0) * 1000, 1)
                if e.code in (401, 403):
                    return False, f"Server Terhubung tapi Otentikasi Gagal (HTTP {e.code}: {e.reason}). Periksa API Key.", latency
                elif e.code == 404:
                    # Endpoint kandidat tidak ada, coba kandidat berikutnya
                    last_msg = f"HTTP {e.code}: {e.reason}"
                    continue
                else:
                    return False, f"Server merespons error (HTTP {e.code}: {e.reason})", latency
            except urllib.error.URLError as e:
                latency = round((time.time() - t0) * 1000, 1)
                return False, f"Gagal menghubungi server ({e.reason}). Periksa IP/URL dan jaringan LAN.", latency
            except Exception as e:
                latency = round((time.time() - t0) * 1000, 1)
                return False, f"Error: {str(e)}", latency

        return False, f"Host merespons tapi endpoint health check tidak ditemukan ({last_msg}).", round((time.time() - t0) * 1000, 1)

    def fetch_active_work_orders(self, base_url=None, endpoint=None, api_key=None, timeout=None):
        """
        Mengambil daftar Work Order / Batch Produksi aktif dari Sistem Utama.
        Return: (success: bool, work_orders: list, message: str)
        """
        b_url = (base_url or self.config.get("api_base_url", "")).strip().rstrip("/")
        ep = (endpoint or self.config.get("api_endpoint_work_orders", "/work-orders/active")).strip()
        if not ep.startswith("/"):
            ep = "/" + ep
        full_url = f"{b_url}{ep}"

        t_out = float(timeout or self.config.get("api_timeout", 5))
        headers = self._build_headers(api_key)

        try:
            req = urllib.request.Request(full_url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=t_out) as resp:
                data_raw = resp.read().decode("utf-8")
                json_data = json.loads(data_raw)

                # Mendukung beragam wrapper format standar API
                if isinstance(json_data, dict):
                    # { "status": "success", "data": [ ... ] }
                    orders = json_data.get("data") or json_data.get("work_orders") or json_data.get("orders") or [json_data]
                elif isinstance(json_data, list):
                    orders = json_data
                else:
                    orders = []

                self.last_sync_status = "Sukses"
                self.last_sync_time = time.strftime("%Y-%m-%d %H:%M:%S")
                return True, orders, f"Berhasil menarik {len(orders)} Work Order dari Sistem Utama."
        except urllib.error.HTTPError as e:
            err = f"HTTP Error {e.code}: {e.reason}"
            self.last_error = err
            return False, [], err
        except urllib.error.URLError as e:
            err = f"URL Error: {e.reason}"
            self.last_error = err
            return False, [], err
        except Exception as e:
            err = f"Gagal mengambil Work Order: {str(e)}"
            self.last_error = err
            return False, [], err

    def parse_work_order_to_dataframe(self, work_order):
        """
        Mengonversi objek Work Order JSON menjadi pandas DataFrame yang siap
        diproses oleh modul percetakan Omega MX (mempertahankan tipe data string murni).
        
        Format item yang didukung:
        - work_order berisi list 'items' / 'details' / 'coupons'
        - atau work_order adalah list baris data itu sendiri
        """
        items = []
        hdr_sku = ""
        hdr_matl = ""
        hdr_batch = ""

        if isinstance(work_order, dict):
            hdr_sku = str(work_order.get("sku_code") or work_order.get("sku") or work_order.get("product_sku") or "SKU01").strip()
            hdr_matl = str(work_order.get("material_code") or work_order.get("matl") or work_order.get("matl_code") or "MAT01").strip()
            hdr_batch = str(work_order.get("batch_no") or work_order.get("batch") or "B001").strip()

            # Cek kemungkinan array item
            if "items" in work_order and isinstance(work_order["items"], list) and len(work_order["items"]) > 0:
                items = work_order["items"]
            elif "details" in work_order and isinstance(work_order["details"], list) and len(work_order["details"]) > 0:
                items = work_order["details"]
            elif "coupons" in work_order and isinstance(work_order["coupons"], list) and len(work_order["coupons"]) > 0:
                for idx, c in enumerate(work_order["coupons"], start=1):
                    qr_val = c.get("qr", c.get("coupon", "")) if isinstance(c, dict) else str(c)
                    items.append({
                        "No": idx,
                        "SKU": str(c.get("sku", hdr_sku) if isinstance(c, dict) else hdr_sku),
                        "QR": str(qr_val),
                        "Material Code": str(c.get("material_code", hdr_matl) if isinstance(c, dict) else hdr_matl)
                    })
            else:
                # Fallback: Work Order hanya menyertakan header target_qty (misal 10 box)
                # Mesin meng-generate serialisasi kupon QR otomatis (mendukung CouponCode_R1 & CouponCode_R2)
                try:
                    qty = int(work_order.get("target_qty") or work_order.get("qty") or 10)
                except Exception:
                    qty = 10
                for idx in range(1, qty + 1):
                    items.append({
                        "ProductSKU": hdr_sku,
                        "CouponCode_R1": f"{hdr_sku}-{hdr_batch}-R1-{idx:04d}",
                        "CouponCode_R2": f"{hdr_sku}-{hdr_batch}-R2-{idx:04d}",
                        "MaterialCode": hdr_matl
                    })
        elif isinstance(work_order, list):
            items = work_order

        if not items:
            return pd.DataFrame(), "Data item kosong pada Work Order terpilih."

        # Konversi langsung ke pandas DataFrame dengan mempertahankan nama-nama kolom asli (seperti di Excel: ProductSKU, CouponCode_R1, CouponCode_R2, MaterialCode)
        df = pd.DataFrame(items, dtype=str)
        
        # Bersihkan spasi tepi dan pastikan string murni (mencegah leading zeroes hilang)
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip()

        return df, f"Berhasil memuat {len(df)} item dari Work Order."

    def send_batch_summary(self, payload, base_url=None, endpoint=None, api_key=None, timeout=None):
        """
        Mengirimkan laporan ringkasan batch produksi (Batch Report) ke Sistem Utama setelah selesai.
        Return: (success: bool, message: str)
        """
        b_url = (base_url or self.config.get("api_base_url", "")).strip().rstrip("/")
        ep = (endpoint or self.config.get("api_endpoint_submit_batch", "/production/batch-summary")).strip()
        if not ep.startswith("/"):
            ep = "/" + ep
        full_url = f"{b_url}{ep}"

        t_out = float(timeout or self.config.get("api_timeout", 8))
        headers = self._build_headers(api_key)

        try:
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(full_url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=t_out) as resp:
                resp_text = resp.read().decode("utf-8")
                return True, f"Laporan Batch berhasil terkirim ke Sistem Utama (HTTP {resp.getcode()})."
        except urllib.error.HTTPError as e:
            return False, f"Gagal kirim batch (HTTP {e.code}: {e.reason})"
        except urllib.error.URLError as e:
            return False, f"Gagal menghubungi server Sistem Utama: {e.reason}"
        except Exception as e:
            return False, f"Error kirim batch: {str(e)}"

    def send_box_qc(self, box_data, base_url=None, endpoint=None, api_key=None, timeout=None):
        """
        Mengirimkan hasil inspeksi QC satu kardus (Real-time telemetry) ke Sistem Utama.
        Biasanya dijalankan di background thread agar tidak membebani siklus pencetakan.
        """
        b_url = (base_url or self.config.get("api_base_url", "")).strip().rstrip("/")
        ep = (endpoint or self.config.get("api_endpoint_submit_box", "/production/qc-box")).strip()
        if not ep.startswith("/"):
            ep = "/" + ep
        full_url = f"{b_url}{ep}"

        t_out = float(timeout or self.config.get("api_timeout", 3))
        headers = self._build_headers(api_key)

        try:
            body = json.dumps(box_data).encode("utf-8")
            req = urllib.request.Request(full_url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=t_out) as resp:
                return True, f"QC box terkirim (HTTP {resp.getcode()})"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_api_documentation_markdown():
        """Menghasilkan dokumentasi kontrak REST API lengkap untuk IT / Developer Sistem Utama"""
        return """# PANDUAN SPESIFIKASI KONTRAK REST API OMEGA MX (v2.0)

Dokumen ini menjelaskan spesifikasi antarmuka pemrograman aplikasi (REST API) 
untuk integrasi dua arah antara **Omega MX Batch & QC System** dengan **Sistem Utama (ERP / MES / Core Server)**.

---

## 1. ALUR KOMUNIKASI (DATA FLOW)

```
+---------------------+                      +---------------------+
|    SISTEM UTAMA     |                      |   OMEGA MX SYSTEM   |
|     (ERP / MES)     |                      |     (HMI Lini)      |
+---------------------+                      +---------------------+
           │                                            │
           │  1. GET /work-orders/active                │
           │◄───────────────────────────────────────────┤ (Tarik SPK/Batch)
           │  2. Return JSON list work orders           │
           ├───────────────────────────────────────────►│ (Muat ke tabel)
           │                                            │
           │                                            │ [Cetak & QC Dual-Scan]
           │                                            │
           │  3. POST /production/qc-box (Opsional)     │
           │◄───────────────────────────────────────────┤ (Realtime telemetry)
           │                                            │
           │  4. POST /production/batch-summary         │
           │◄───────────────────────────────────────────┤ (Kirim laporan akhir)
           │  5. Return 200 OK                          │
           ├───────────────────────────────────────────►│
```

---

## 2. INBOUND: SISTEM UTAMA -> OMEGA MX (TARIK WORK ORDER)

### Endpoint: `GET /work-orders/active`
Dipanggil oleh Omega MX saat operator menekan tombol **"Tarik Data dari API"** di HMI.

#### Headers:
```http
Accept: application/json
Authorization: Bearer <API_KEY_ANDA>
X-API-Key: <API_KEY_ANDA>
```

#### Contoh Format Respons JSON yang Diharapkan:
```json
{
  "status": "success",
  "data": [
    {
      "work_order_id": "WO-2026-00105",
      "batch_no": "BCH-SYN-9981",
      "product_name": "BENIH JAGUNG NK 212",
      "sku": "NK212-KG05",
      "material_code": "MAT-08912-A",
      "total_target": 500,
      "items": [
        {
          "no": 1,
          "sku": "NK212-KG05",
          "qr": "SYN2026000001",
          "material_code": "MAT-08912-A"
        },
        {
          "no": 2,
          "sku": "NK212-KG05",
          "qr": "SYN2026000002",
          "material_code": "MAT-08912-A"
        }
      ]
    }
  ]
}
```

---

## 3. OUTBOUND: OMEGA MX -> SISTEM UTAMA (KIRIM HASIL BATCH)

### Endpoint: `POST /production/batch-summary`
Dipanggil otomatis oleh Omega MX di latar belakang saat sebuah batch selesai diproses dan di-QC.

#### Headers:
```http
Content-Type: application/json
Authorization: Bearer <API_KEY_ANDA>
```

#### Contoh Payload JSON yang Dikirim Omega MX:
```json
{
  "source": "WO-2026-00105",
  "batch_start_time": "2026-10-27 08:30:00",
  "batch_end_time": "2026-10-27 09:15:22",
  "duration": "00:45:22",
  "total_load_data": 500,
  "total_printed": 500,
  "total_ok": 498,
  "total_ng": 2,
  "ng_level": 0,
  "operator": "operator",
  "system_version": "v2.0-API",
  "records": [
    {
      "no": 1,
      "sku": "NK212-KG05",
      "qr": "SYN2026000001",
      "material_code": "MAT-08912-A",
      "status": "OK",
      "scanner1": "SYN2026000001",
      "scanner2": "SYN2026000001",
      "cycle": 1,
      "timestamp": "2026-10-27 08:30:15"
    },
    {
      "no": 2,
      "sku": "NK212-KG05",
      "qr": "SYN2026000002",
      "material_code": "MAT-08912-A",
      "status": "NG",
      "scanner1": "NOREAD",
      "scanner2": "SYN2026000002",
      "cycle": 1,
      "timestamp": "2026-10-27 08:30:20"
    }
  ]
}
```

---

## 4. LOCAL EMBEDDED API SERVER OMEGA MX (Port 5022)

Omega MX juga menyediakan endpoint lokal yang dapat diakses oleh Sistem Utama di jaringan pabrik:
- `GET http://<IP_PC_OMEGA>:5022/api/v1/status` : Mengambil status real-time mesin & batch berjalan.
- `GET http://<IP_PC_OMEGA>:5022/api/v1/history` : Mengambil riwayat produksi master.
- `POST http://<IP_PC_OMEGA>:5022/api/v1/work-order/push` : Menerima penugasan batch baru langsung dari Sistem Utama.
"""
