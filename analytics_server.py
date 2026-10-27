# analytics_server.py
import os
import sys
import pandas as pd
from flask import Flask, jsonify, send_from_directory

def get_base_dir():
    try:
        return sys._MEIPASS
    except Exception:
        return os.path.dirname(os.path.abspath(__file__))

class AnalyticsServer:
    def __init__(self, history_log_file=None, app_status_callback=None, work_order_callback=None, history_csv=None):
        self.history_log_file = history_log_file or history_csv or "data/history_log.csv"
        self.app_status_callback = app_status_callback
        self.work_order_callback = work_order_callback
        self.assets_dir = os.path.join(get_base_dir(), "assets")
        self.app = Flask(__name__)
        self.setup_routes()

    def setup_routes(self):
        @self.app.route('/')
        def home():
            return self.get_html_template()

        @self.app.route('/assets/<path:filename>')
        def serve_assets(filename):
            return send_from_directory(self.assets_dir, filename)

        @self.app.route('/api/history')
        def get_history():
            try:
                if not os.path.exists(self.history_log_file):
                    return jsonify([])
                df = pd.read_csv(self.history_log_file)
                if df.empty:
                    return jsonify([])
                df = df.fillna("")
                return jsonify(df.to_dict(orient='records'))
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)})

        # === ENDPOINTS REST API V1 UNTUK SISTEM UTAMA ===
        @self.app.route('/api/v1/health', methods=['GET'])
        def api_health():
            return jsonify({
                "status": "healthy",
                "system": "Omega MX Batch & QC System",
                "version": "2.0-API",
                "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
            })

        @self.app.route('/api/v1/status', methods=['GET'])
        def api_status():
            try:
                if self.app_status_callback:
                    data = self.app_status_callback()
                    return jsonify(data)
                return jsonify({"status": "online", "message": "Omega MX server active"})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/api/v1/history', methods=['GET'])
        def api_v1_history():
            return get_history()

        from flask import request
        @self.app.route('/api/v1/work-order/push', methods=['POST'])
        def api_push_work_order():
            try:
                payload = request.get_json(silent=True)
                if not payload:
                    return jsonify({"status": "error", "message": "Body payload JSON tidak valid atau kosong"}), 400

                if self.work_order_callback:
                    ok, msg = self.work_order_callback(payload)
                    if ok:
                        return jsonify({"status": "success", "message": msg})
                    return jsonify({"status": "error", "message": msg}), 422

                return jsonify({"status": "error", "message": "Handler callback work order tidak terpasang"}), 503
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

    def run(self, port=5022):
        self.app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    def get_html_template(self):
        return """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Omega MX - Management Room Production Analytics</title>
    <script src="/assets/chart.umd.js"></script>
    <style>
        :root {
            --primary: #0f172a;
            --primary-light: #1e293b;
            --accent: #2563eb;
            --accent-hover: #1d4ed8;
            --success: #16a34a;
            --success-bg: #f0fdf4;
            --success-border: #86efac;
            --danger: #dc2626;
            --danger-bg: #fef2f2;
            --danger-border: #fca5a5;
            --warning: #d97706;
            --warning-bg: #fef3c7;
            --warning-border: #fde68a;
            --bg: #f1f5f9;
            --card-bg: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border-subtle: #e2e8f0;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
        }

        body {
            background-color: var(--bg);
            color: var(--text-main);
            padding-bottom: 50px;
        }

        /* Top Navbar */
        .navbar {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #ffffff;
            padding: 14px 28px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.12);
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }

        .nav-brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .brand-icon {
            width: 32px;
            height: 32px;
            background: #2563eb;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #ffffff;
        }

        .nav-brand h1 {
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: 0.5px;
            color: #f8fafc;
        }

        .nav-brand .badge-dept {
            background: rgba(37, 99, 235, 0.25);
            color: #93c5fd;
            font-size: 0.72rem;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
            border: 1px solid rgba(147, 197, 253, 0.3);
            text-transform: uppercase;
            letter-spacing: 0.8px;
        }

        .nav-right {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .clock-display {
            font-size: 0.85rem;
            color: #94a3b8;
            font-family: 'Consolas', monospace;
            background: rgba(0, 0, 0, 0.2);
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }

        .badge-live {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(22, 163, 74, 0.2);
            color: #4ade80;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 700;
            border: 1px solid rgba(74, 222, 128, 0.4);
            letter-spacing: 0.5px;
        }

        .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }

        .dot-green { background-color: #22c55e; }
        .dot-amber { background-color: #f59e0b; }
        .dot-red   { background-color: #ef4444; }
        .dot-gray  { background-color: #94a3b8; }

        .dot-pulse {
            animation: pulse-dot 1.5s infinite ease-in-out;
        }

        @keyframes pulse-dot {
            0% { transform: scale(0.95); opacity: 0.8; }
            50% { transform: scale(1.3); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.8; }
        }

        .container {
            max-width: 1280px;
            margin: 24px auto;
            padding: 0 20px;
        }

        /* Section Headings */
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
        }

        .section-title {
            font-size: 0.95rem;
            font-weight: 700;
            color: #334155;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .section-title svg {
            width: 18px;
            height: 18px;
            stroke: #2563eb;
        }

        .section-badge {
            font-size: 0.75rem;
            color: var(--text-muted);
            background: #e2e8f0;
            padding: 3px 8px;
            border-radius: 4px;
            font-weight: 600;
        }

        /* 1. STATUS LINE PRODUKSI REAL-TIME */
        .live-status-card {
            background: #ffffff;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.04);
            border: 1px solid var(--border-subtle);
            margin-bottom: 20px;
        }

        .live-status-banner {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 14px 18px;
            border-radius: 10px;
            margin-bottom: 16px;
            transition: all 0.3s ease;
        }

        /* State Banner Themes */
        .banner-running {
            background: linear-gradient(90deg, #ecfdf5 0%, #f0fdf4 100%);
            border: 1px solid #a7f3d0;
        }
        .banner-standby {
            background: linear-gradient(90deg, #f0f9ff 0%, #f8fafc 100%);
            border: 1px solid #bae6fd;
        }
        .banner-paused {
            background: linear-gradient(90deg, #fffbeb 0%, #fefce8 100%);
            border: 1px solid #fde68a;
        }
        .banner-stopped {
            background: linear-gradient(90deg, #fef2f2 0%, #fff1f2 100%);
            border: 1px solid #fca5a5;
        }
        .banner-offline {
            background: #f1f5f9;
            border: 1px solid #cbd5e1;
        }

        .status-pill-large {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            font-size: 1.1rem;
            font-weight: 800;
            letter-spacing: 0.5px;
        }

        .pill-running { color: #047857; }
        .pill-standby { color: #0369a1; }
        .pill-paused  { color: #b45309; }
        .pill-stopped { color: #b91c1c; }
        .pill-offline { color: #475569; }

        .live-meta-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            padding-top: 4px;
            border-top: 1px solid #f1f5f9;
        }

        .meta-item {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }

        .meta-label {
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
        }

        .meta-value {
            font-size: 0.95rem;
            font-weight: 700;
            color: var(--text-main);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        /* Hardware Indicators Grid */
        .hw-strip {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-top: 14px;
            padding-top: 14px;
            border-top: 1px dashed var(--border-subtle);
        }

        .hw-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.78rem;
            font-weight: 600;
            color: #334155;
        }

        /* 2. GRID CARD HMI (PROGRES BATCH, TOTAL OK, TOTAL NG, ANTREAN KONVEYOR) */
        .hmi-cards-grid {
            display: grid;
            grid-template-columns: 1.3fr 1.1fr 1.6fr;
            gap: 20px;
            margin-bottom: 24px;
        }

        @media (max-width: 1024px) {
            .hmi-cards-grid {
                grid-template-columns: 1fr;
            }
        }

        /* Card Progres Batch */
        .hmi-card {
            background: #ffffff;
            border-radius: 12px;
            padding: 18px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.04);
            border: 1px solid var(--border-subtle);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .hmi-card-title {
            font-size: 0.88rem;
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .gauge-container {
            display: flex;
            align-items: center;
            justify-content: space-around;
            padding: 8px 0;
            gap: 12px;
        }

        .gauge-svg-wrap {
            position: relative;
            width: 170px;
            height: 90px;
            overflow: hidden;
            flex-shrink: 0;
        }

        .gauge-percent-text {
            position: absolute;
            bottom: 4px;
            left: 0;
            right: 0;
            text-align: center;
            font-size: 1.45rem;
            font-weight: 800;
            color: #1e293b;
        }

        .gauge-subtext {
            font-size: 0.65rem;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            display: block;
            margin-top: -2px;
        }

        .gauge-right-info {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
        }

        .gauge-counter-big {
            font-size: 1.55rem;
            font-weight: 800;
            color: #0f172a;
            line-height: 1.1;
        }

        .gauge-count-label {
            font-size: 0.8rem;
            color: #64748b;
            font-weight: 600;
            margin-top: 4px;
        }

        .gauge-sisa {
            font-size: 0.95rem;
            font-weight: 800;
            color: #0284c7;
            margin-top: 8px;
        }

        /* Card Counters OK / NG (Side-by-side) */
        .counters-split {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            height: 100%;
        }

        .counter-box {
            border-radius: 10px;
            padding: 14px 12px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            border: 1px solid transparent;
            transition: transform 0.2s;
        }

        .counter-box:hover {
            transform: translateY(-2px);
        }

        .box-ok {
            background-color: var(--success-bg);
            border-color: var(--success-border);
        }

        .box-ng {
            background-color: var(--danger-bg);
            border-color: var(--danger-border);
        }

        .counter-box-title {
            font-size: 0.78rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 5px;
        }

        .box-ok .counter-box-title { color: #15803d; }
        .box-ng .counter-box-title { color: #b91c1c; }

        .counter-number {
            font-size: 2.5rem;
            font-weight: 800;
            line-height: 1;
        }

        .box-ok .counter-number { color: #16a34a; }
        .box-ng .counter-number { color: #dc2626; }

        .counter-ratio {
            font-size: 0.72rem;
            margin-top: 6px;
            font-weight: 600;
            color: #64748b;
        }

        /* Card Antrean Konveyor In-Transit */
        .conveyor-box {
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            height: 100%;
        }

        .badge-transit {
            background-color: var(--warning-bg);
            color: #b45309;
            font-size: 0.78rem;
            font-weight: 800;
            padding: 3px 10px;
            border-radius: 6px;
            border: 1px solid var(--warning-border);
        }

        .conveyor-track {
            position: relative;
            background: #f8fafc;
            border: 1px solid var(--border-subtle);
            border-radius: 10px;
            padding: 24px 16px;
            margin: 12px 0;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .conveyor-line {
            position: absolute;
            left: 30px;
            right: 30px;
            height: 4px;
            background: #cbd5e1;
            z-index: 1;
        }

        .conveyor-node {
            position: relative;
            z-index: 2;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
        }

        .node-circle {
            width: 22px;
            height: 22px;
            background: #ffffff;
            border: 3px solid #64748b;
            border-radius: 50%;
            transition: all 0.3s;
        }

        .node-circle.active {
            border-color: #2563eb;
            background: #dbeafe;
            box-shadow: 0 0 10px rgba(37, 99, 235, 0.5);
        }

        .node-label {
            font-size: 0.75rem;
            font-weight: 700;
            color: #475569;
            white-space: nowrap;
        }

        .transit-status-msg {
            font-size: 0.8rem;
            color: var(--text-muted);
            text-align: center;
            background: #f8fafc;
            padding: 6px 12px;
            border-radius: 6px;
            border: 1px solid #edf2f7;
            font-weight: 600;
        }

        /* 3. REKAPITULASI & TREN HISTORIS */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }

        .card {
            background: var(--card-bg);
            border-radius: 12px;
            padding: 22px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.04);
            border: 1px solid var(--border-subtle);
        }

        .stat-title {
            font-size: 0.82rem;
            font-weight: 700;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 8px;
            letter-spacing: 0.5px;
        }

        .stat-value {
            font-size: 2.2rem;
            font-weight: 800;
            line-height: 1.1;
        }

        .val-primary { color: #0284c7; }
        .val-danger { color: var(--danger); }
        .val-success { color: var(--success); }

        .charts-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
            margin-bottom: 24px;
        }

        @media (max-width: 900px) {
            .charts-grid { grid-template-columns: 1fr; }
        }

        .chart-title {
            font-size: 0.95rem;
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .table-card {
            background: var(--card-bg);
            border-radius: 12px;
            padding: 22px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.04);
            border: 1px solid var(--border-subtle);
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 0.88rem;
        }

        th {
            background-color: #f8fafc;
            color: #475569;
            font-weight: 700;
            text-align: left;
            padding: 12px 14px;
            border-bottom: 2px solid #e2e8f0;
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }

        td {
            padding: 12px 14px;
            border-bottom: 1px solid #f1f5f9;
        }

        tr:hover { background-color: #f8fafd; }

        .tag-ng {
            background: #fee2e2;
            color: #dc2626;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.78rem;
            display: inline-block;
        }

        .tag-ok {
            background: #dcfce7;
            color: #16a34a;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.78rem;
            display: inline-block;
        }

        .footer {
            text-align: center;
            margin-top: 36px;
            font-size: 0.8rem;
            color: #94a3b8;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <!-- Top Navigation Bar -->
    <nav class="navbar">
        <div class="nav-brand">
            <div class="brand-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                    <line x1="8" y1="21" x2="16" y2="21"></line>
                    <line x1="12" y1="17" x2="12" y2="21"></line>
                </svg>
            </div>
            <h1>OMEGA MX PRODUCTION ANALYTICS</h1>
            <span class="badge-dept">MANAGEMENT ROOM</span>
        </div>
        <div class="nav-right">
            <span class="clock-display" id="clockText">--:--:-- WIB</span>
            <span class="badge-live" id="badgeLive">
                <span class="dot dot-green dot-pulse" id="dotLive"></span>
                <span id="textLive">LIVE MONITORING</span>
            </span>
        </div>
    </nav>

    <div class="container">
        <!-- SECTION 1: LIVE FACTORY FLOOR STATUS -->
        <div class="section-header">
            <div class="section-title">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
                </svg>
                Status Real-Time Kondisi Lapangan
            </div>
            <span class="section-badge" id="badgeUpdateStatus">Sinkronisasi: Setiap 1.5s</span>
        </div>

        <div class="live-status-card">
            <!-- Dynamic State Banner -->
            <div class="live-status-banner banner-standby" id="statusBanner">
                <div class="status-pill-large pill-standby" id="statusPill">
                    <span class="dot dot-amber" id="statusDot"></span>
                    <span id="statusTitle">STANDBY - SIAP OPERASI</span>
                </div>
                <div style="font-size: 0.82rem; font-weight: 600; color: #475569;" id="statusSubinfo">
                    Menunggu operator memuat penugasan SPK
                </div>
            </div>

            <!-- Metadata Active Batch -->
            <div class="live-meta-grid">
                <div class="meta-item">
                    <span class="meta-label">Work Order Aktif</span>
                    <span class="meta-value" id="val_wo">Tidak ada batch</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Kode SKU / Produk</span>
                    <span class="meta-value" id="val_sku">-</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">File / Sumber Data</span>
                    <span class="meta-value" id="val_file">-</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Operator Bertugas</span>
                    <span class="meta-value" id="val_operator">Administrator</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Waktu Mulai Batch</span>
                    <span class="meta-value" id="val_start">-</span>
                </div>
            </div>

            <!-- Hardware Strip -->
            <div class="hw-strip">
                <span class="hw-badge">
                    <span class="dot dot-gray" id="hw_printer_dot"></span>
                    Printer Omega MX: <span id="hw_printer_text" style="font-weight: 700; margin-left: 2px;">Offline</span>
                </span>
                <span class="hw-badge">
                    <span class="dot dot-gray" id="hw_s1_dot"></span>
                    Keyence Scanner Sisi A: <span id="hw_s1_text" style="font-weight: 700; margin-left: 2px;">Offline</span>
                </span>
                <span class="hw-badge">
                    <span class="dot dot-gray" id="hw_s2_dot"></span>
                    Keyence Scanner Sisi B: <span id="hw_s2_text" style="font-weight: 700; margin-left: 2px;">Offline</span>
                </span>
                <span class="hw-badge">
                    <span class="dot dot-gray" id="hw_modbus_dot"></span>
                    Modbus I/O System: <span id="hw_modbus_text" style="font-weight: 700; margin-left: 2px;">Standby</span>
                </span>
                <span class="hw-badge">
                    <span class="dot dot-gray" id="hw_api_dot"></span>
                    API Sistem Utama: <span id="hw_api_text" style="font-weight: 700; margin-left: 2px;">Siap</span>
                </span>
            </div>
        </div>

        <!-- SECTION 2: CARDS SEPERTI DI HMI (PROGRES BATCH, OK/NG, ANTREAN KONVEYOR) -->
        <div class="hmi-cards-grid">
            <!-- Card 1: Progres Batch -->
            <div class="hmi-card">
                <div class="hmi-card-title">
                    <span>Progres Batch</span>
                    <span style="font-size: 0.72rem; color: #64748b; font-weight: 600;">Siklus Produksi</span>
                </div>
                <div class="gauge-container">
                    <!-- SVG Semicircular Gauge -->
                    <div class="gauge-svg-wrap">
                        <svg width="170" height="90" viewBox="0 0 180 95">
                            <!-- Background Arc -->
                            <path d="M 20 85 A 70 70 0 0 1 160 85" fill="none" stroke="#e2e8f0" stroke-width="16" stroke-linecap="round"/>
                            <!-- Progress Arc -->
                            <path id="gaugePath" d="M 20 85 A 70 70 0 0 1 160 85" fill="none" stroke="#0284c7" stroke-width="16" stroke-linecap="round" stroke-dasharray="220" stroke-dashoffset="220" style="transition: stroke-dashoffset 0.5s ease;"/>
                        </svg>
                        <div class="gauge-percent-text" id="gaugePct">0%</div>
                        <span class="gauge-subtext">PROGRESS</span>
                    </div>

                    <div class="gauge-right-info">
                        <div class="gauge-counter-big">
                            <span id="gaugeJudged">0</span> / <span id="gaugeTotal">0</span>
                        </div>
                        <span class="gauge-count-label">Kardus Selesai</span>
                        <div class="gauge-sisa">
                            Sisa: <span id="gaugeSisa">0</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Card 2: Counters OK & NG (Side-by-side) -->
            <div class="hmi-card">
                <div class="hmi-card-title">
                    <span>Hasil Inspeksi Dual-QC</span>
                    <span id="ngRateBadge" style="font-size: 0.72rem; font-weight: 700; color: #64748b; background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">Afkir: 0.0%</span>
                </div>
                <div class="counters-split">
                    <!-- Box TOTAL OK -->
                    <div class="counter-box box-ok">
                        <div class="counter-box-title">
                            <span class="dot dot-green"></span>
                            TOTAL OK
                        </div>
                        <div class="counter-number" id="countOk">0</div>
                        <div class="counter-ratio">Lolos Standar</div>
                    </div>

                    <!-- Box TOTAL NG -->
                    <div class="counter-box box-ng">
                        <div class="counter-box-title">
                            <span class="dot dot-red"></span>
                            TOTAL NG
                        </div>
                        <div class="counter-number" id="countNg">0</div>
                        <div class="counter-ratio">Kardus Ditolak</div>
                    </div>
                </div>
            </div>

            <!-- Card 3: Antrean Konveyor In-Transit -->
            <div class="hmi-card conveyor-box">
                <div class="hmi-card-title">
                    <span>Antrean Konveyor</span>
                    <span class="badge-transit" id="badgeTransit">In Transit: 0 Box</span>
                </div>

                <!-- Visual Alur Fisik Konveyor -->
                <div class="conveyor-track">
                    <div class="conveyor-line"></div>
                    <!-- Node 1: Head Print -->
                    <div class="conveyor-node">
                        <div class="node-circle" id="nodeHeadPrint"></div>
                        <span class="node-label">Head Print</span>
                    </div>
                    <!-- Node 2: Dual Scanner -->
                    <div class="conveyor-node">
                        <div class="node-circle" id="nodeScanner"></div>
                        <span class="node-label">Dual Scanner</span>
                    </div>
                    <!-- Node 3: Pusher Solenoid -->
                    <div class="conveyor-node">
                        <div class="node-circle" id="nodePusher"></div>
                        <span class="node-label">Pusher (DO0)</span>
                    </div>
                </div>

                <div class="transit-status-msg" id="transitStatusText">
                    Konveyor bersih, tidak ada kardus tertahan di antara printer dan sensor scanner.
                </div>
            </div>
        </div>

        <!-- SECTION 3: REKAPITULASI HISTORIS MANAJEMEN -->
        <div class="section-header">
            <div class="section-title">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 3v18h18"></path>
                    <path d="M18.7 8l-5.1 5.2-2.8-2.7L7 14.3"></path>
                </svg>
                Rekapitulasi Produksi & Analisis Historis
            </div>
            <span class="section-badge">Akumulasi Database</span>
        </div>

        <div class="stats-grid">
            <div class="card">
                <div class="stat-title">Total Volume Cetak</div>
                <div id="total_volume" class="stat-value val-primary">-</div>
            </div>
            <div class="card">
                <div class="stat-title">Rata-Rata NG Level</div>
                <div id="avg_ng" class="stat-value val-danger">-</div>
            </div>
            <div class="card">
                <div class="stat-title">Total Batch Selesai</div>
                <div id="total_batch" class="stat-value val-success">-</div>
            </div>
        </div>

        <div class="charts-grid">
            <div class="card">
                <div class="chart-title">
                    <span>Tren Produksi Harian (7 Hari Terakhir)</span>
                </div>
                <canvas id="chartLine" height="130"></canvas>
            </div>
            <div class="card">
                <div class="chart-title">
                    <span>Distribusi 5 SKU Teratas</span>
                </div>
                <canvas id="chartPie" height="130"></canvas>
            </div>
        </div>

        <div class="table-card">
            <div class="chart-title">
                <span>Riwayat Batch Produksi Terkini</span>
                <span id="record_count" style="font-size: 0.85rem; font-weight: 400; color: var(--text-muted);">0 Batch</span>
            </div>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>Waktu Selesai</th>
                            <th>Durasi</th>
                            <th>File Sumber</th>
                            <th>Total Data</th>
                            <th>Total Print</th>
                            <th>NG Level</th>
                        </tr>
                    </thead>
                    <tbody id="table_body">
                        <tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 24px;">Memuat riwayat produksi...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="footer">
            PT SMARTEK SISTEM INOVASI &copy; 2026 | Omega MX Industrial Batch Printing & Dual-QC System v2.0
        </div>
    </div>

    <script>
        let lineChartInstance = null;
        let pieChartInstance = null;

        // Jam Real-Time Navbar
        function updateClock() {
            const now = new Date();
            const h = String(now.getHours()).padStart(2, '0');
            const m = String(now.getMinutes()).padStart(2, '0');
            const s = String(now.getSeconds()).padStart(2, '0');
            document.getElementById('clockText').innerText = `${h}:${m}:${s} WIB`;
        }
        setInterval(updateClock, 1000);
        updateClock();

        // 1. LIVE POLLING STATUS LAPANGAN (Setiap 1.5 detik)
        async function pollLiveStatus() {
            try {
                const res = await fetch('/api/v1/status');
                if (!res.ok) throw new Error("HTTP " + res.status);
                const s = await res.json();

                // Live Badge
                document.getElementById('badgeLive').className = 'badge-live';
                document.getElementById('dotLive').className = 'dot dot-green dot-pulse';
                document.getElementById('textLive').innerText = 'LIVE MONITORING';

                // Status Banner Logic
                const rawStatus = (s.system_status || 'READY').toUpperCase();
                const banner = document.getElementById('statusBanner');
                const pill = document.getElementById('statusPill');
                const pDot = document.getElementById('statusDot');
                const pTitle = document.getElementById('statusTitle');
                const pSub = document.getElementById('statusSubinfo');

                if (rawStatus === 'RUNNING') {
                    banner.className = 'live-status-banner banner-running';
                    pill.className = 'status-pill-large pill-running';
                    pDot.className = 'dot dot-green dot-pulse';
                    pTitle.innerText = 'MESIN RUNNING (MEMPRODUKSI)';
                    pSub.innerText = 'Sedang mengeksekusi pencetakan dan inspeksi dual scanner';
                } else if (rawStatus === 'PAUSED') {
                    banner.className = 'live-status-banner banner-paused';
                    pill.className = 'status-pill-large pill-paused';
                    pDot.className = 'dot dot-amber';
                    pTitle.innerText = 'PRODUKSI DIJEDA (PAUSED)';
                    pSub.innerText = 'Operator menghentikan sementara proses pencetakan';
                } else if (rawStatus === 'STOPPED' || rawStatus === 'ALARM') {
                    banner.className = 'live-status-banner banner-stopped';
                    pill.className = 'status-pill-large pill-stopped';
                    pDot.className = 'dot dot-red';
                    pTitle.innerText = 'MESIN STOP / ALARM';
                    pSub.innerText = 'Kondisi mesin terhenti atau terjadi interlock';
                } else {
                    banner.className = 'live-status-banner banner-standby';
                    pill.className = 'status-pill-large pill-standby';
                    pDot.className = 'dot dot-amber';
                    pTitle.innerText = 'STANDBY - SIAP OPERASI';
                    pSub.innerText = 'Mesin standby menunggu penugasan batch baru dari operator atau ERP';
                }

                // Metadata Batch
                document.getElementById('val_wo').innerText = s.current_work_order || '-';
                document.getElementById('val_sku').innerText = s.current_sku || '-';
                document.getElementById('val_file').innerText = s.current_file || '-';
                document.getElementById('val_operator').innerText = s.operator || 'Admin';
                document.getElementById('val_start').innerText = s.batch_start_time || '-';

                // Hardware Status Indicators
                const hw = s.hardware || {};
                function setHw(idDot, idText, isOnline, label) {
                    const dot = document.getElementById(idDot);
                    const txt = document.getElementById(idText);
                    if (isOnline) {
                        dot.className = 'dot dot-green';
                        txt.innerText = 'Online';
                        txt.style.color = '#15803d';
                    } else {
                        dot.className = 'dot dot-gray';
                        txt.innerText = 'Offline';
                        txt.style.color = '#64748b';
                    }
                }
                setHw('hw_printer_dot', 'hw_printer_text', hw.printer_online);
                setHw('hw_s1_dot', 'hw_s1_text', hw.scanner1_online);
                setHw('hw_s2_dot', 'hw_s2_text', hw.scanner2_online);
                setHw('hw_modbus_dot', 'hw_modbus_text', hw.modbus_online);
                setHw('hw_api_dot', 'hw_api_text', hw.upstream_api_online);

                // Progres Batch Card (Gauge SVG Arc Calculation)
                const p = s.progress || {};
                const target = p.total_target || 0;
                const judged = p.judged || 0;
                const sisa = p.sisa !== undefined ? p.sisa : Math.max(0, target - judged);
                const pct = p.progress_percent !== undefined ? p.progress_percent : (target > 0 ? ((judged/target)*100).toFixed(1) : 0);

                document.getElementById('gaugeJudged').innerText = judged;
                document.getElementById('gaugeTotal').innerText = target;
                document.getElementById('gaugeSisa').innerText = sisa;
                document.getElementById('gaugePct').innerText = pct + '%';

                // Semi-circle perimeter ~ 220
                const maxDash = 220;
                const offset = maxDash - Math.min(100, Math.max(0, pct)) * (maxDash / 100);
                const gPath = document.getElementById('gaugePath');
                gPath.style.strokeDashoffset = offset;
                if (pct >= 100) {
                    gPath.setAttribute('stroke', '#16a34a');
                } else if (rawStatus === 'RUNNING') {
                    gPath.setAttribute('stroke', '#0284c7');
                } else {
                    gPath.setAttribute('stroke', '#94a3b8');
                }

                // Counters OK & NG
                const okCnt = p.count_ok || 0;
                const ngCnt = p.count_ng || 0;
                document.getElementById('countOk').innerText = okCnt;
                document.getElementById('countNg').innerText = ngCnt;

                const totalJudged = okCnt + ngCnt;
                const ngRate = totalJudged > 0 ? ((ngCnt / totalJudged) * 100).toFixed(1) : '0.0';
                document.getElementById('ngRateBadge').innerText = 'Afkir: ' + ngRate + '%';

                // Antrean Konveyor In-Transit
                const inTransit = p.in_transit || 0;
                document.getElementById('badgeTransit').innerText = `In Transit: ${inTransit} Box`;

                const nodeHp = document.getElementById('nodeHeadPrint');
                const nodeScan = document.getElementById('nodeScanner');
                const nodePush = document.getElementById('nodePusher');
                const tText = document.getElementById('transitStatusText');

                if (inTransit > 0) {
                    nodeHp.className = 'node-circle active';
                    nodeScan.className = 'node-circle active';
                    nodePush.className = (ngCnt > 0) ? 'node-circle active' : 'node-circle';
                    tText.innerText = `${inTransit} kardus sedang mengalir di atas konveyor menuju sensor Keyence.`;
                    tText.style.color = '#b45309';
                } else {
                    nodeHp.className = 'node-circle';
                    nodeScan.className = 'node-circle';
                    nodePush.className = 'node-circle';
                    tText.innerText = 'Konveyor bersih, tidak ada kardus tertahan di antara printer dan sensor scanner.';
                    tText.style.color = '#64748b';
                }

            } catch (err) {
                // HMI Offline / Tidak merespons
                document.getElementById('badgeLive').className = 'badge-live';
                document.getElementById('badgeLive').style.borderColor = '#cbd5e1';
                document.getElementById('dotLive').className = 'dot dot-gray';
                document.getElementById('textLive').innerText = 'HMI OFFLINE';

                const banner = document.getElementById('statusBanner');
                banner.className = 'live-status-banner banner-offline';
                document.getElementById('statusPill').className = 'status-pill-large pill-offline';
                document.getElementById('statusDot').className = 'dot dot-gray';
                document.getElementById('statusTitle').innerText = 'KONEKSI HMI TERPUTUS';
                document.getElementById('statusSubinfo').innerText = 'Tidak dapat menghubungi service controller Omega MX di port 5022';
            }
        }

        // 2. LOAD HISTORICAL ANALYTICS DATA (Setiap 10 detik)
        async function loadHistoryData() {
            try {
                const res = await fetch('/api/history');
                const data = await res.json();
                
                if (!Array.isArray(data) || data.length === 0) {
                    document.getElementById('total_volume').innerText = "0";
                    document.getElementById('avg_ng').innerText = "0.0";
                    document.getElementById('total_batch').innerText = "0";
                    document.getElementById('table_body').innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 24px;">Belum ada riwayat batch produksi tercatat.</td></tr>';
                    return;
                }

                const totalVol = data.reduce((s, i) => s + (parseInt(i.Total_Print) || 0), 0);
                const totalNG = data.reduce((s, i) => s + (parseInt(i.NG_Level) || 0), 0);
                const avgNG = data.length > 0 ? (totalNG / data.length).toFixed(2) : "0.0";

                document.getElementById('total_volume').innerText = totalVol.toLocaleString();
                document.getElementById('avg_ng').innerText = avgNG;
                document.getElementById('total_batch').innerText = data.length.toLocaleString();
                document.getElementById('record_count').innerText = data.length + " Batch";

                // Line Chart
                const dates = [...new Set(data.map(i => (i.Waktu_Selesai || "").split(' ')[0]).filter(Boolean))].slice(-7);
                const volData = dates.map(d => data.filter(i => (i.Waktu_Selesai || "").startsWith(d)).reduce((s, i) => s + (parseInt(i.Total_Print) || 0), 0));

                if (lineChartInstance) lineChartInstance.destroy();
                lineChartInstance = new Chart(document.getElementById('chartLine'), {
                    type: 'line',
                    data: {
                        labels: dates.length ? dates : ['Hari Ini'],
                        datasets: [{
                            label: 'Volume Cetak',
                            data: volData.length ? volData : [0],
                            borderColor: '#0284c7',
                            backgroundColor: 'rgba(2, 132, 199, 0.1)',
                            tension: 0.35,
                            fill: true,
                            borderWidth: 2.5,
                            pointBackgroundColor: '#0284c7',
                            pointRadius: 4
                        }]
                    },
                    options: { responsive: true, maintainAspectRatio: true }
                });

                // Doughnut Chart
                const skus = {};
                data.forEach(i => {
                    const src = i.Source || "Unknown";
                    skus[src] = (skus[src] || 0) + (parseInt(i.Total_Print) || 0);
                });
                const topSkus = Object.entries(skus).sort((a,b) => b[1]-a[1]).slice(0, 5);

                if (pieChartInstance) pieChartInstance.destroy();
                pieChartInstance = new Chart(document.getElementById('chartPie'), {
                    type: 'doughnut',
                    data: {
                        labels: topSkus.map(i => i[0]),
                        datasets: [{
                            data: topSkus.map(i => i[1]),
                            backgroundColor: ['#16a34a', '#eab308', '#ea580c', '#dc2626', '#8b5cf6']
                        }]
                    },
                    options: { responsive: true, maintainAspectRatio: true }
                });

                function escapeHtml(text) {
                    if (!text) return '-';
                    return String(text).replace(/[&<>"']/g, function(m) {
                        return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'}[m];
                    });
                }

                // Table Data (10 Terbaru)
                const recent = [...data].reverse().slice(0, 10);
                const rows = recent.map(r => {
                    const ngBadge = parseInt(r.NG_Level) > 0 
                        ? `<span class="tag-ng">${escapeHtml(r.NG_Level)} NG</span>` 
                        : `<span class="tag-ok">0 NG</span>`;
                    return `<tr>
                        <td>${escapeHtml(r.Waktu_Selesai)}</td>
                        <td>${escapeHtml(r.Durasi)}</td>
                        <td><b>${escapeHtml(r.Source)}</b></td>
                        <td>${parseInt(r.Total_Data) || 0}</td>
                        <td>${parseInt(r.Total_Print) || 0}</td>
                        <td>${ngBadge}</td>
                    </tr>`;
                }).join('');
                document.getElementById('table_body').innerHTML = rows;

            } catch (err) {
                console.error("Gagal load history analytics:", err);
            }
        }

        // Inisialisasi & Polling Interval
        pollLiveStatus();
        setInterval(pollLiveStatus, 1500); // Live status setiap 1.5 detik

        loadHistoryData();
        setInterval(loadHistoryData, 10000); // Data riwayat setiap 10 detik
    </script>
</body>
</html>"""