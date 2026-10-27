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
    <title>Omega MX - Management Room Production Analytics (1080p Widescreen)</title>
    <script src="/assets/chart.umd.js"></script>
    <style>
        :root {
            --bg: #eef2f6;
            --surface: #ffffff;
            --border: #dcdfe4;
            --border-light: #f1f5f9;
            --text-title: #0f172a;
            --text-body: #334155;
            --text-muted: #64748b;
            --primary: #1e3a8a;
            --accent-realtime: #0284c7;
            --accent-history: #475569;
            --ok-color: #16a34a;
            --ok-bg: #f0fdf4;
            --ok-border: #bbf7d0;
            --ng-color: #dc2626;
            --ng-bg: #fef2f2;
            --ng-border: #fecaca;
            --transit-bg: #fef9c3;
            --transit-border: #fde047;
            --transit-text: #854d0e;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }

        body {
            background-color: var(--bg);
            color: var(--text-body);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        /* Top Navbar */
        .navbar {
            background-color: #0f172a;
            color: #ffffff;
            padding: 8px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #1e293b;
            flex-shrink: 0;
        }

        .nav-brand {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .brand-icon {
            width: 26px;
            height: 26px;
            background: #2563eb;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #ffffff;
        }

        .nav-brand h1 {
            font-size: 0.98rem;
            font-weight: 700;
            letter-spacing: 0.4px;
            color: #ffffff;
        }

        .badge-dept {
            background: #1e293b;
            color: #94a3b8;
            font-size: 0.68rem;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 4px;
            border: 1px solid #334155;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .nav-right {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .btn-fullscreen {
            background: #1e293b;
            border: 1px solid #334155;
            color: #cbd5e1;
            padding: 4px 9px;
            border-radius: 4px;
            font-size: 0.72rem;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 5px;
            transition: all 0.2s ease;
        }

        .btn-fullscreen:hover {
            background: #334155;
            color: #ffffff;
        }

        .clock-display {
            font-size: 0.8rem;
            color: #cbd5e1;
            font-family: 'Consolas', monospace;
            background: #1e293b;
            padding: 4px 8px;
            border-radius: 4px;
            border: 1px solid #334155;
        }

        .badge-live {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #1e293b;
            color: #4ade80;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.72rem;
            font-weight: 700;
            border: 1px solid #334155;
            letter-spacing: 0.4px;
        }

        .dot-status {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            display: inline-block;
        }

        .dot-green { background-color: #22c55e; }
        .dot-gray  { background-color: #94a3b8; }
        .dot-amber { background-color: #f59e0b; }
        .dot-red   { background-color: #ef4444; }

        /* Widescreen 1920x1080 Dual Master Panels Layout */
        .dashboard-main {
            width: 100%;
            max-width: 1920px;
            margin: 0 auto;
            padding: 12px 18px;
            display: grid;
            grid-template-columns: 48fr 52fr;
            gap: 16px;
            align-items: stretch;
            flex: 1;
        }

        @media (max-width: 1200px) {
            .dashboard-main {
                grid-template-columns: 1fr;
            }
        }

        /* MASTER PANEL FRAMEWORK */
        .master-panel {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 5px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
        }

        .panel-realtime {
            border-top: 4px solid var(--accent-realtime);
        }

        .panel-history {
            border-top: 4px solid var(--accent-history);
        }

        /* Master Panel Header */
        .panel-header-bar {
            padding: 10px 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
        }

        .header-bar-realtime {
            background-color: #f0f9ff;
        }

        .header-bar-history {
            background-color: #f8fafc;
        }

        .panel-header-title {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.88rem;
            font-weight: 800;
            letter-spacing: 0.4px;
            text-transform: uppercase;
        }

        .header-bar-realtime .panel-header-title {
            color: #0369a1;
        }

        .header-bar-history .panel-header-title {
            color: #334155;
        }

        .panel-badge-tag {
            font-size: 0.7rem;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 3px;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }

        .tag-realtime {
            background: #e0f2fe;
            color: #0284c7;
            border: 1px solid #bae6fd;
        }

        .tag-history {
            background: #f1f5f9;
            color: #475569;
            border: 1px solid #cbd5e1;
        }

        .panel-content {
            padding: 14px 16px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            flex: 1;
        }

        /* 1. KONTEN PANEL KIRI (REAL-TIME LAPANGAN) */
        .status-box-clean {
            background: #fafbfc;
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 12px 14px;
        }

        .status-top-line {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-light);
            margin-bottom: 10px;
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 3px 12px;
            border-radius: 3px;
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.5px;
            border: 1px solid transparent;
        }

        .pill-running { background-color: #f0fdf4; color: #166534; border-color: #bbf7d0; }
        .pill-standby { background-color: #f1f5f9; color: #334155; border-color: #cbd5e1; }
        .pill-paused  { background-color: #fefce8; color: #854d0e; border-color: #fef08a; }
        .pill-stopped { background-color: #fef2f2; color: #991b1b; border-color: #fecaca; }
        .pill-offline { background-color: #f8fafc; color: #64748b; border-color: #e2e8f0; }

        .meta-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 10px;
            margin-bottom: 10px;
        }

        .meta-cell {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .meta-cell-label {
            font-size: 0.68rem;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }

        .meta-cell-val {
            font-size: 0.82rem;
            font-weight: 700;
            color: var(--text-title);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .hw-status-row {
            padding-top: 8px;
            border-top: 1px solid var(--border-light);
            display: flex;
            flex-wrap: wrap;
            gap: 14px;
            font-size: 0.72rem;
            color: var(--text-muted);
        }

        .hw-item {
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }

        .hw-val-online { font-weight: 700; color: #166534; }
        .hw-val-offline { font-weight: 700; color: #64748b; }

        /* HMI CARDS (Di dalam Panel Kiri) */
        .hmi-cards-row-top {
            display: grid;
            grid-template-columns: 1.3fr 1fr;
            gap: 12px;
        }

        .hmi-box-clean {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 12px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .hmi-header-sm {
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--text-title);
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        /* Gauge */
        .gauge-layout {
            display: flex;
            align-items: center;
            justify-content: space-around;
            padding: 2px 0 6px 0;
            gap: 10px;
        }

        .gauge-svg-wrap {
            position: relative;
            width: 150px;
            height: 80px;
            overflow: hidden;
            flex-shrink: 0;
        }

        .gauge-percent-text {
            position: absolute;
            bottom: 2px;
            left: 0;
            right: 0;
            text-align: center;
            font-size: 1.35rem;
            font-weight: 800;
            color: var(--text-title);
        }

        .gauge-subtext {
            font-size: 0.62rem;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: block;
            margin-top: -3px;
        }

        .gauge-info {
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
        }

        .gauge-counts {
            font-size: 1.4rem;
            font-weight: 800;
            color: var(--text-title);
            line-height: 1.1;
        }

        .gauge-label {
            font-size: 0.75rem;
            color: var(--text-muted);
            font-weight: 500;
            margin-top: 2px;
        }

        .gauge-sisa {
            font-size: 0.85rem;
            font-weight: 800;
            color: #0e7490;
            margin-top: 5px;
        }

        /* OK / NG */
        .ok-ng-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            height: 100%;
        }

        .counter-card {
            border-radius: 4px;
            padding: 10px 6px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
        }

        .counter-card-ok {
            background-color: var(--ok-bg);
            border: 1px solid var(--ok-border);
        }

        .counter-card-ng {
            background-color: var(--ng-bg);
            border: 1px solid var(--ng-border);
        }

        .counter-card-title {
            font-size: 0.74rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.4px;
            margin-bottom: 3px;
        }

        .counter-card-ok .counter-card-title { color: #166534; }
        .counter-card-ng .counter-card-title { color: #991b1b; }

        .counter-card-num {
            font-size: 2.1rem;
            font-weight: 800;
            line-height: 1;
        }

        .counter-card-ok .counter-card-num { color: #16a34a; }
        .counter-card-ng .counter-card-num { color: #dc2626; }

        /* Konveyor (Row Bawah Panel Kiri) */
        .badge-transit-clean {
            background-color: var(--transit-bg);
            border: 1px solid var(--transit-border);
            color: var(--transit-text);
            font-size: 0.72rem;
            font-weight: 800;
            padding: 2px 7px;
            border-radius: 3px;
        }

        .conveyor-diagram {
            position: relative;
            background: #fafbfc;
            border: 1px solid var(--border-light);
            border-radius: 4px;
            padding: 18px 14px;
            margin-top: 4px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .conveyor-track-line {
            position: absolute;
            left: 28px;
            right: 28px;
            height: 3px;
            background: #94a3b8;
            z-index: 1;
        }

        .conveyor-point {
            position: relative;
            z-index: 2;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
        }

        .node-circle-clean {
            width: 17px;
            height: 17px;
            background: #ffffff;
            border: 3px solid #64748b;
            border-radius: 50%;
            transition: all 0.2s ease;
        }

        .node-circle-clean.active {
            border-color: #0284c7;
            background: #e0f2fe;
        }

        .node-name {
            font-size: 0.7rem;
            font-weight: 700;
            color: #475569;
            white-space: nowrap;
        }

        /* 2. KONTEN PANEL KANAN (REKAPITULASI HISTORIS) */
        .kpi-row {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
        }

        .kpi-card {
            background: #fafbfc;
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 10px 12px;
        }

        .kpi-label {
            font-size: 0.68rem;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.3px;
            margin-bottom: 4px;
        }

        .kpi-val {
            font-size: 1.65rem;
            font-weight: 800;
            line-height: 1;
        }

        .charts-row {
            display: grid;
            grid-template-columns: 1.5fr 1fr;
            gap: 10px;
        }

        .chart-box-clean {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 10px 12px;
            display: flex;
            flex-direction: column;
        }

        .chart-title-sm {
            font-size: 0.76rem;
            font-weight: 700;
            color: var(--text-title);
            margin-bottom: 8px;
        }

        .chart-canvas-wrap {
            position: relative;
            flex: 1;
            min-height: 130px;
            max-height: 150px;
        }

        /* Table Box */
        .table-box-clean {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 10px 12px;
            flex: 1;
            display: flex;
            flex-direction: column;
        }

        .table-header-sm {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.76rem;
            font-weight: 700;
            color: var(--text-title);
            margin-bottom: 6px;
        }

        .table-wrap {
            overflow-y: auto;
            max-height: 180px;
            flex: 1;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.78rem;
        }

        th {
            background-color: #f8fafc;
            color: #475569;
            font-weight: 700;
            text-align: left;
            padding: 7px 10px;
            border-bottom: 2px solid var(--border);
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            position: sticky;
            top: 0;
            z-index: 5;
        }

        td {
            padding: 6px 10px;
            border-bottom: 1px solid var(--border-light);
            color: var(--text-title);
        }

        tr:nth-child(even) { background-color: #fafbfc; }

        .tag-ng-clean {
            background: #fee2e2;
            color: #b91c1c;
            padding: 1px 5px;
            border-radius: 2px;
            font-weight: 700;
            font-size: 0.68rem;
        }

        .tag-ok-clean {
            background: #dcfce7;
            color: #15803d;
            padding: 1px 5px;
            border-radius: 2px;
            font-weight: 700;
            font-size: 0.68rem;
        }

        .footer-note {
            text-align: center;
            padding: 6px 0;
            font-size: 0.7rem;
            color: var(--text-muted);
            border-top: 1px solid var(--border);
            background: #ffffff;
            flex-shrink: 0;
        }
    </style>
</head>
<body>
    <!-- Top Navigation Bar -->
    <nav class="navbar">
        <div class="nav-brand">
            <div class="brand-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                    <line x1="8" y1="21" x2="16" y2="21"></line>
                    <line x1="12" y1="17" x2="12" y2="21"></line>
                </svg>
            </div>
            <h1>OMEGA MX PRODUCTION ANALYTICS</h1>
            <span class="badge-dept">MANAGEMENT ROOM</span>
        </div>
        <div class="nav-right">
            <button class="btn-fullscreen" onclick="toggleFullScreen()" title="Tampilkan Layar Penuh">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
                </svg>
                Layar Penuh (F11)
            </button>
            <span class="clock-display" id="clockText">--:--:-- WIB</span>
            <span class="badge-live" id="badgeLive">
                <span class="dot-status dot-green" id="dotLive"></span>
                <span id="textLive">LIVE</span>
            </span>
        </div>
    </nav>

    <!-- WIDESCREEN DASHBOARD (1920x1080 FIT) -->
    <div class="dashboard-main">
        
        <!-- MASTER PANEL 1: KONDISI LAPANGAN REAL-TIME (KIRI) -->
        <section class="master-panel panel-realtime">
            <div class="panel-header-bar header-bar-realtime">
                <div class="panel-header-title">
                    <span class="dot-status dot-green"></span>
                    <span>Kondisi Lapangan Real-Time</span>
                </div>
                <span class="panel-badge-tag tag-realtime">Live Telemetri &bull; Siklus Aktif</span>
            </div>

            <div class="panel-content">
                <!-- Status Operasional & Batch Aktif -->
                <div class="status-box-clean">
                    <div class="status-top-line">
                        <span style="font-size: 0.76rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Status Operasional Mesin</span>
                        <div class="status-pill pill-standby" id="statusPill">
                            <span class="dot-status dot-amber" id="statusDot"></span>
                            <span id="statusTitle">STANDBY</span>
                        </div>
                    </div>

                    <div class="meta-grid">
                        <div class="meta-cell">
                            <span class="meta-cell-label">Work Order Aktif</span>
                            <span class="meta-cell-val" id="val_wo">-</span>
                        </div>
                        <div class="meta-cell">
                            <span class="meta-cell-label">Kode SKU / Produk</span>
                            <span class="meta-cell-val" id="val_sku">-</span>
                        </div>
                        <div class="meta-cell">
                            <span class="meta-cell-label">File Sumber Data</span>
                            <span class="meta-cell-val" id="val_file">-</span>
                        </div>
                        <div class="meta-cell">
                            <span class="meta-cell-label">Operator Bertugas</span>
                            <span class="meta-cell-val" id="val_operator">admin</span>
                        </div>
                        <div class="meta-cell">
                            <span class="meta-cell-label">Waktu Mulai Batch</span>
                            <span class="meta-cell-val" id="val_start">-</span>
                        </div>
                    </div>

                    <div class="hw-status-row">
                        <div class="hw-item">
                            <span>Printer:</span>
                            <span id="hw_printer_text" class="hw-val-offline">Offline</span>
                        </div>
                        <span>&bull;</span>
                        <div class="hw-item">
                            <span>Scanner Sisi A:</span>
                            <span id="hw_s1_text" class="hw-val-offline">Offline</span>
                        </div>
                        <span>&bull;</span>
                        <div class="hw-item">
                            <span>Scanner Sisi B:</span>
                            <span id="hw_s2_text" class="hw-val-offline">Offline</span>
                        </div>
                        <span>&bull;</span>
                        <div class="hw-item">
                            <span>Modbus I/O:</span>
                            <span id="hw_modbus_text" class="hw-val-offline">Standby</span>
                        </div>
                        <span>&bull;</span>
                        <div class="hw-item">
                            <span>API Sistem:</span>
                            <span id="hw_api_text" class="hw-val-offline">Siap</span>
                        </div>
                    </div>
                </div>

                <!-- Row 2: Card Progres Batch & Card TOTAL OK/NG -->
                <div class="hmi-cards-row-top">
                    <!-- Progres Batch -->
                    <div class="hmi-box-clean">
                        <div class="hmi-header-sm">
                            <span>Progres Batch</span>
                        </div>
                        <div class="gauge-layout">
                            <div class="gauge-svg-wrap">
                                <svg width="150" height="80" viewBox="0 0 180 95">
                                    <path d="M 20 85 A 70 70 0 0 1 160 85" fill="none" stroke="#e2e8f0" stroke-width="15" stroke-linecap="round"/>
                                    <path id="gaugePath" d="M 20 85 A 70 70 0 0 1 160 85" fill="none" stroke="#0284c7" stroke-width="15" stroke-linecap="round" stroke-dasharray="220" stroke-dashoffset="220" style="transition: stroke-dashoffset 0.4s ease;"/>
                                </svg>
                                <div class="gauge-percent-text" id="gaugePct">0%</div>
                                <span class="gauge-subtext">PROGRESS</span>
                            </div>

                            <div class="gauge-info">
                                <div class="gauge-counts">
                                    <span id="gaugeJudged">0</span> / <span id="gaugeTotal">0</span>
                                </div>
                                <span class="gauge-label">Kardus Selesai</span>
                                <div class="gauge-sisa">
                                    Sisa: <span id="gaugeSisa">0</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- TOTAL OK & TOTAL NG -->
                    <div class="hmi-box-clean">
                        <div class="ok-ng-grid">
                            <div class="counter-card counter-card-ok">
                                <div class="counter-card-title">TOTAL OK</div>
                                <div class="counter-card-num" id="countOk">0</div>
                            </div>
                            <div class="counter-card counter-card-ng">
                                <div class="counter-card-title">TOTAL NG</div>
                                <div class="counter-card-num" id="countNg">0</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Row 3: Card Antrean Konveyor In-Transit -->
                <div class="hmi-box-clean">
                    <div class="hmi-header-sm">
                        <span>Antrean Konveyor</span>
                        <span class="badge-transit-clean" id="badgeTransit">In Transit: 0 Box</span>
                    </div>

                    <div class="conveyor-diagram">
                        <div class="conveyor-track-line"></div>
                        <div class="conveyor-point">
                            <div class="node-circle-clean" id="nodeHeadPrint"></div>
                            <span class="node-name">Head Print</span>
                        </div>
                        <div class="conveyor-point">
                            <div class="node-circle-clean" id="nodeScanner"></div>
                            <span class="node-name">Dual Scanner</span>
                        </div>
                        <div class="conveyor-point">
                            <div class="node-circle-clean" id="nodePusher"></div>
                            <span class="node-name">Pusher (DO0)</span>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- MASTER PANEL 2: REKAPITULASI PRODUKSI HISTORIS (KANAN) -->
        <section class="master-panel panel-history">
            <div class="panel-header-bar header-bar-history">
                <div class="panel-header-title">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                        <line x1="16" y1="2" x2="16" y2="6"></line>
                        <line x1="8" y1="2" x2="8" y2="6"></line>
                        <line x1="3" y1="10" x2="21" y2="10"></line>
                    </svg>
                    <span>Rekapitulasi Produksi Terkumpul</span>
                </div>
                <span class="panel-badge-tag tag-history">Database &bull; 7 Hari Terakhir</span>
            </div>

            <div class="panel-content">
                <!-- 3 KPI Kumulatif -->
                <div class="kpi-row">
                    <div class="kpi-card">
                        <div class="kpi-label">Total Volume Cetak</div>
                        <div id="total_volume" class="kpi-val" style="color: #0284c7;">-</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Rata-Rata NG Level</div>
                        <div id="avg_ng" class="kpi-val" style="color: #dc2626;">-</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Total Batch Selesai</div>
                        <div id="total_batch" class="kpi-val" style="color: #16a34a;">-</div>
                    </div>
                </div>

                <!-- 2 Charts Berdampingan -->
                <div class="charts-row">
                    <div class="chart-box-clean">
                        <div class="chart-title-sm">Tren Produksi Harian (7 Hari Terakhir)</div>
                        <div class="chart-canvas-wrap">
                            <canvas id="chartLine"></canvas>
                        </div>
                    </div>
                    <div class="chart-box-clean">
                        <div class="chart-title-sm">Distribusi 5 SKU Teratas</div>
                        <div class="chart-canvas-wrap">
                            <canvas id="chartPie"></canvas>
                        </div>
                    </div>
                </div>

                <!-- Tabel Riwayat Batch Selesai -->
                <div class="table-box-clean">
                    <div class="table-header-sm">
                        <span>Riwayat Batch Produksi Terkini</span>
                        <span id="record_count" style="font-size: 0.72rem; color: var(--text-muted); font-weight: 600;">-</span>
                    </div>
                    <div class="table-wrap">
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
                                <tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 14px;">Memuat data riwayat...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </section>

    </div>

    <div class="footer-note">
        Omega MX Industrial Batch Printing & QC System v2.0 | Management Room View (1080p Optimized)
    </div>

    <script>
        let lineChartInstance = null;
        let pieChartInstance = null;

        // Fullscreen Toggle
        function toggleFullScreen() {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().catch(err => {
                    alert("Tidak dapat masuk mode layar penuh: " + err.message);
                });
            } else {
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                }
            }
        }

        // Jam Navbar
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
                document.getElementById('dotLive').className = 'dot-status dot-green';
                document.getElementById('textLive').innerText = 'LIVE';

                // Status Banner Logic (Simple, Clean, No AI text)
                const rawStatus = (s.system_status || 'READY').toUpperCase();
                const pill = document.getElementById('statusPill');
                const pDot = document.getElementById('statusDot');
                const pTitle = document.getElementById('statusTitle');

                if (rawStatus === 'RUNNING') {
                    pill.className = 'status-pill pill-running';
                    pDot.className = 'dot-status dot-green';
                    pTitle.innerText = 'RUNNING';
                } else if (rawStatus === 'PAUSED') {
                    pill.className = 'status-pill pill-paused';
                    pDot.className = 'dot-status dot-amber';
                    pTitle.innerText = 'PAUSED';
                } else if (rawStatus === 'STOPPED' || rawStatus === 'ALARM') {
                    pill.className = 'status-pill pill-stopped';
                    pDot.className = 'dot-status dot-red';
                    pTitle.innerText = 'STOPPED';
                } else {
                    pill.className = 'status-pill pill-standby';
                    pDot.className = 'dot-status dot-amber';
                    pTitle.innerText = 'STANDBY';
                }

                // Metadata Batch
                document.getElementById('val_wo').innerText = s.current_work_order || '-';
                document.getElementById('val_sku').innerText = s.current_sku || '-';
                document.getElementById('val_file').innerText = s.current_file || '-';
                document.getElementById('val_operator').innerText = s.operator || 'admin';
                document.getElementById('val_start').innerText = s.batch_start_time || '-';

                // Hardware Status Line
                const hw = s.hardware || {};
                function setHw(idText, isOnline) {
                    const txt = document.getElementById(idText);
                    if (isOnline) {
                        txt.className = 'hw-val-online';
                        txt.innerText = 'Online';
                    } else {
                        txt.className = 'hw-val-offline';
                        txt.innerText = 'Offline';
                    }
                }
                setHw('hw_printer_text', hw.printer_online);
                setHw('hw_s1_text', hw.scanner1_online);
                setHw('hw_s2_text', hw.scanner2_online);
                setHw('hw_modbus_text', hw.modbus_online);
                setHw('hw_api_text', hw.upstream_api_online);

                // Progres Batch Card
                const p = s.progress || {};
                const target = p.total_target || 0;
                const judged = p.judged || 0;
                const sisa = p.sisa !== undefined ? p.sisa : Math.max(0, target - judged);
                const pct = p.progress_percent !== undefined ? p.progress_percent : (target > 0 ? ((judged/target)*100).toFixed(1) : 0);

                document.getElementById('gaugeJudged').innerText = judged;
                document.getElementById('gaugeTotal').innerText = target;
                document.getElementById('gaugeSisa').innerText = sisa;
                document.getElementById('gaugePct').innerText = pct + '%';

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

                // Antrean Konveyor In-Transit
                const inTransit = p.in_transit || 0;
                document.getElementById('badgeTransit').innerText = `In Transit: ${inTransit} Box`;

                const nodeHp = document.getElementById('nodeHeadPrint');
                const nodeScan = document.getElementById('nodeScanner');
                const nodePush = document.getElementById('nodePusher');

                if (inTransit > 0) {
                    nodeHp.className = 'node-circle-clean active';
                    nodeScan.className = 'node-circle-clean active';
                    nodePush.className = (ngCnt > 0) ? 'node-circle-clean active' : 'node-circle-clean';
                } else {
                    nodeHp.className = 'node-circle-clean';
                    nodeScan.className = 'node-circle-clean';
                    nodePush.className = 'node-circle-clean';
                }

            } catch (err) {
                // HMI Offline
                document.getElementById('badgeLive').className = 'badge-live';
                document.getElementById('dotLive').className = 'dot-status dot-gray';
                document.getElementById('textLive').innerText = 'OFFLINE';

                const pill = document.getElementById('statusPill');
                pill.className = 'status-pill pill-offline';
                document.getElementById('statusDot').className = 'dot-status dot-gray';
                document.getElementById('statusTitle').innerText = 'OFFLINE';
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
                    document.getElementById('table_body').innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 14px;">Belum ada riwayat batch produksi tercatat.</td></tr>';
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
                            backgroundColor: 'rgba(2, 132, 199, 0.08)',
                            tension: 0.25,
                            fill: true,
                            borderWidth: 2,
                            pointBackgroundColor: '#0284c7',
                            pointRadius: 3
                        }]
                    },
                    options: { 
                        responsive: true, 
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            y: { grid: { color: '#f1f5f9' }, ticks: { font: { size: 10 } } },
                            x: { grid: { display: false }, ticks: { font: { size: 10 } } }
                        }
                    }
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
                            backgroundColor: ['#16a34a', '#eab308', '#ea580c', '#dc2626', '#8b5cf6'],
                            borderWidth: 1
                        }]
                    },
                    options: { 
                        responsive: true, 
                        maintainAspectRatio: false,
                        plugins: { 
                            legend: { 
                                position: 'right', 
                                labels: { 
                                    boxWidth: 10, 
                                    font: { size: 9 },
                                    generateLabels: function(chart) {
                                        const orig = Chart.overrides.doughnut.plugins.legend.labels.generateLabels(chart);
                                        orig.forEach(l => {
                                            if (l.text.length > 18) l.text = l.text.substring(0, 16) + '..';
                                        });
                                        return orig;
                                    }
                                } 
                            } 
                        }
                    }
                });

                function escapeHtml(text) {
                    if (!text) return '-';
                    return String(text).replace(/[&<>"']/g, function(m) {
                        return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'}[m];
                    });
                }

                // Table Data (Terbaru)
                const recent = [...data].reverse().slice(0, 8);
                const rows = recent.map(r => {
                    const ngBadge = parseInt(r.NG_Level) > 0 
                        ? `<span class="tag-ng-clean">${escapeHtml(r.NG_Level)} NG</span>` 
                        : `<span class="tag-ok-clean">0 NG</span>`;
                    return `<tr>
                        <td>${escapeHtml(r.Waktu_Selesai)}</td>
                        <td>${escapeHtml(r.Durasi)}</td>
                        <td title="${escapeHtml(r.Source)}"><b>${escapeHtml(r.Source.length > 25 ? r.Source.substring(0,23) + '..' : r.Source)}</b></td>
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
        setInterval(pollLiveStatus, 1500);

        loadHistoryData();
        setInterval(loadHistoryData, 10000);
    </script>
</body>
</html>"""
