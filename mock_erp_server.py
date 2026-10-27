# mock_erp_server.py
"""
SIMULATOR SERVER SISTEM UTAMA (ERP / MES MOCK SERVER)
PT SMARTEK SISTEM INOVASI - Omega MX v2.0 API Testing Tool

Jalankan script ini di terminal terpisah:
    python mock_erp_server.py

Server ini mensimulasikan ERP/MES di port 8000:
- GET  /api/v1/work-orders/active       -> Memberikan daftar Work Order aktif
- POST /api/v1/production/batch-summary  -> Menerima laporan batch selesai dari Omega MX
- POST /api/v1/production/qc-box        -> Menerima telemetri per-box dari Omega MX
- GET  /push-to-omega                   -> Menembak POST /api/v1/work-order/push ke Omega MX (Port 5022)
"""

import sys
import json
import time
import urllib.request
from flask import Flask, jsonify, request

app = Flask(__name__)

# Sample Data Work Order aktif di ERP (Format persis seperti di file Excel produksi)
SAMPLE_WORK_ORDERS = [
    {
        "work_order_id": "SPK-2026-NK6173-01",
        "sku_code": "NK 6173 BTGT",
        "sku_name": "Produk NK 6173 BTGT",
        "material_code": "NK 6173 BTGT-83IA00120",
        "batch_no": "B2610A",
        "target_qty": 10,
        "priority": "HIGH",
        "status": "READY",
        "notes": "Data riil produksi sesuai file Excel master pabrik",
        "items": [
            {
                "ProductSKU": "NK 6173 BTGT",
                "CouponCode_R1": "ECE4TUE11",
                "CouponCode_R2": "3XAHNTE9",
                "MaterialCode": "NK 6173 BTGT-83IA00130"
            },
            {
                "ProductSKU": "NK 6173 BTGT",
                "CouponCode_R1": "ECE4TUE22",
                "CouponCode_R2": "3X63GCJZ",
                "MaterialCode": "NK 6173 BTGT-83IA00131"
            },
            {
                "ProductSKU": "NK 6173 BTGT",
                "CouponCode_R1": "ECE4TUE23",
                "CouponCode_R2": "3XJHJ6AZ",
                "MaterialCode": "NK 6173 BTGT-83IA00132"
            },
            {
                "ProductSKU": "NK 6173 BTGT",
                "CouponCode_R1": "ECE4TUE24",
                "CouponCode_R2": "3XNFCFA7",
                "MaterialCode": "NK 6173 BTGT-83IA00133"
            },
            {
                "ProductSKU": "NK 6173 BTGT",
                "CouponCode_R1": "ECE4TUE25",
                "CouponCode_R2": "3XNUAMFA",
                "MaterialCode": "NK 6173 BTGT-83IA00134"
            },
            {
                "ProductSKU": "NK 6173 BTGT",
                "CouponCode_R1": "ECE4TUE26",
                "CouponCode_R2": "3XQ44F39",
                "MaterialCode": "NK 6173 BTGT-83IA00135"
            },
            {
                "ProductSKU": "NK 6173 BTGT",
                "CouponCode_R1": "ECE4TUE27",
                "CouponCode_R2": "3XNQNAMF",
                "MaterialCode": "NK 6173 BTGT-83IA00136"
            },
            {
                "ProductSKU": "NK 6173 BTGT",
                "CouponCode_R1": "ECE4TUE18",
                "CouponCode_R2": "3XPMT797",
                "MaterialCode": "NK 6172 BTGT-83IA00110"
            },
            {
                "ProductSKU": "NK 6173 BTGT",
                "CouponCode_R1": "ECE4TUE19",
                "CouponCode_R2": "3XQLM7EX",
                "MaterialCode": "NK 6172 BTGT-83IA00111"
            },
            {
                "ProductSKU": "NK 6173 BTGT",
                "CouponCode_R1": "ECE4TUE20",
                "CouponCode_R2": "3XQLM7EN",
                "MaterialCode": "NK 6172 BTGT-83IA00112"
            }
        ]
    },
    {
        "work_order_id": "SPK-2026-COF410-02",
        "sku_code": "SKU-COF-410",
        "sku_name": "Arabica Gold Blend 500gr",
        "material_code": "MAT-FOIL-B",
        "batch_no": "B2610B",
        "target_qty": 5,
        "priority": "NORMAL",
        "status": "READY",
        "notes": "Contoh batch yang serialisasi kupon R1 & R2-nya di-generate otomatis oleh mesin",
        "items": []
    }
]

@app.route('/')
def index():
    return jsonify({
        "server": "Mock ERP/MES Sistem Utama Simulator",
        "status": "ONLINE",
        "port": 8000,
        "endpoints": {
            "get_work_orders": "GET /api/v1/work-orders/active",
            "post_batch_summary": "POST /api/v1/production/batch-summary",
            "post_qc_box": "POST /api/v1/production/qc-box",
            "trigger_push_to_omega": "GET /push-to-omega (menembak WO ke Omega MX port 5022)"
        }
    })

@app.route('/api/v1/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "system": "ERP Core Simulator",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route('/api/v1/work-orders/active', methods=['GET'])
def get_work_orders():
    auth_header = request.headers.get("Authorization", "Tidak ada token")
    print(f"\n[MOCK ERP] >>> GET /api/v1/work-orders/active dipanggil oleh Omega MX!")
    print(f"[MOCK ERP] Header Auth: {auth_header}")
    print(f"[MOCK ERP] Mengirimkan {len(SAMPLE_WORK_ORDERS)} Work Order ke Omega MX...")
    return jsonify({
        "status": "success",
        "total": len(SAMPLE_WORK_ORDERS),
        "data": SAMPLE_WORK_ORDERS
    }), 200

@app.route('/api/v1/production/batch-summary', methods=['POST'])
def receive_batch_summary():
    data = request.get_json(silent=True) or {}
    print(f"\n[MOCK ERP] <<< POST /api/v1/production/batch-summary DITERIMA DARI OMEGA MX!")
    print(f"[MOCK ERP] Work Order ID : {data.get('work_order_id')}")
    print(f"[MOCK ERP] Total Target   : {data.get('total_target')}")
    print(f"[MOCK ERP] Total OK       : {data.get('total_ok')}")
    print(f"[MOCK ERP] Total NG       : {data.get('total_ng')} (Afkir: {data.get('ng_rate_pct')}%)")
    print(f"[MOCK ERP] Operator       : {data.get('operator')}")
    print(f"[MOCK ERP] Durasi Batch   : {data.get('batch_start_time')} s/d {data.get('batch_end_time')}")
    print(f"[MOCK ERP] Payload Lengkap: {json.dumps(data, indent=2)}")
    return jsonify({
        "status": "success",
        "message": f"Batch {data.get('work_order_id')} berhasil direkam dan ditutup di ERP.",
        "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }), 200

@app.route('/api/v1/production/qc-box', methods=['POST'])
def receive_qc_box():
    data = request.get_json(silent=True) or {}
    print(f"[MOCK ERP TELEMETRI] Box #{data.get('box_no')} | SKU: {data.get('sku')} | QR: {data.get('qr')} | Status: {data.get('status')} | S1: {data.get('scanner1')} | S2: {data.get('scanner2')}")
    return jsonify({"status": "received"}), 200

@app.route('/push-to-omega', methods=['GET', 'POST'])
def push_sample_to_omega():
    """Endpoint bantuan untuk menguji Sistem Utama me-push SPK ke Omega MX (Port 5022)"""
    omega_push_url = "http://127.0.0.1:5022/api/v1/work-order/push"
    new_spk = {
        "work_order_id": f"PUSH-{int(time.time())}",
        "sku_code": "SKU-URGENT-99",
        "sku_name": "Emergency Batch Priority 1",
        "material_code": "MAT-URGENT",
        "batch_no": "EXP-URG",
        "target_qty": 3,
        "items": [
            {"No": 1, "SKU": "SKU-URGENT-99", "QR": "URG001", "Material Code": "MAT-URGENT"},
            {"No": 2, "SKU": "SKU-URGENT-99", "QR": "URG002", "Material Code": "MAT-URGENT"},
            {"No": 3, "SKU": "SKU-URGENT-99", "QR": "URG003", "Material Code": "MAT-URGENT"}
        ]
    }
    try:
        body = json.dumps(new_spk).encode('utf-8')
        req = urllib.request.Request(omega_push_url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=3) as resp:
            resp_txt = resp.read().decode('utf-8')
            return jsonify({
                "status": "pushed_successfully",
                "target_omega": omega_push_url,
                "payload": new_spk,
                "omega_response": json.loads(resp_txt)
            })
    except Exception as e:
        return jsonify({
            "status": "failed_to_push",
            "error": str(e),
            "tips": "Pastikan aplikasi main.py Omega MX sedang running di port 5022!"
        }), 500

if __name__ == '__main__':
    print("=" * 65)
    print("  SIMULATOR SISTEM UTAMA (ERP / MES MOCK SERVER) - PORT 8000")
    print("  PT SMARTEK SISTEM INOVASI - Omega MX v2.0")
    print("=" * 65)
    print("Endpoint aktif:")
    print("  • GET  http://127.0.0.1:8000/api/v1/work-orders/active")
    print("  • POST http://127.0.0.1:8000/api/v1/production/batch-summary")
    print("  • POST http://127.0.0.1:8000/api/v1/production/qc-box")
    print("  • GET  http://127.0.0.1:8000/push-to-omega (Test Push ke HMI)")
    print("-" * 65)
    print("Server siap menerima request dari HMI Omega MX...\n")
    app.run(host='0.0.0.0', port=8000, debug=False)
