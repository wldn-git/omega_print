# analytics_server.py
import os
import sys
import io
import pandas as pd
from flask import Flask, jsonify, send_from_directory, send_file, Response, request

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

        # Endpoint Ekspor Data Mentah CSV untuk Web Analytics (Mendukung Filter Fleksibel)
        @self.app.route('/api/v1/export-raw-csv', methods=['GET'])
        def export_raw_csv():
            try:
                days = request.args.get('days', type=int)
                start_date = request.args.get('start_date')
                end_date = request.args.get('end_date')

                if not os.path.exists(self.history_log_file):
                    csv_content = "Waktu_Mulai,Waktu_Selesai,Durasi,Source,Total_Data,Total_Print,Total_NG,NG_Level,Report_File\n"
                    return Response(
                        csv_content,
                        mimetype="text/csv; charset=utf-8",
                        headers={"Content-Disposition": "attachment;filename=riwayat_produksi_mentah.csv"}
                    )

                df = pd.read_csv(self.history_log_file)
                if not df.empty and 'Waktu_Selesai' in df.columns:
                    if days and days > 0:
                        cutoff_str = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
                        df = df[df['Waktu_Selesai'] >= cutoff_str]
                    elif start_date and end_date:
                        df = df[(df['Waktu_Selesai'] >= start_date) & (df['Waktu_Selesai'] <= end_date + " 23:59:59")]

                output = io.StringIO()
                df.to_csv(output, index=False, encoding='utf-8')
                csv_bytes = output.getvalue().encode('utf-8')

                return Response(
                    csv_bytes,
                    mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment;filename=riwayat_produksi_mentah.csv"}
                )
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

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
    <title>Omega MX - Analisis Produksi Ruang Manajemen (Widescreen 1080p)</title>
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

        /* Navigasi Atas */
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

        /* Widescreen 1920x1080 Dua Panel Utama */
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

        /* FRAMEWORK PANEL UTAMA */
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

        /* Header Panel Utama */
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

        /* Filter Controls Fleksibel (7D, 30D, Semua, Kustom) */
        .filter-controls-wrap {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }
        .filter-pill-group {
            display: inline-flex;
            background: #e2e8f0;
            border-radius: 6px;
            padding: 2px;
            gap: 2px;
        }
        .filter-pill-btn {
            font-family: inherit;
            font-size: 0.70rem;
            font-weight: 600;
            padding: 3px 9px;
            border-radius: 4px;
            border: none;
            background: transparent;
            color: #475569;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .filter-pill-btn:hover {
            background: #cbd5e1;
            color: #0f172a;
        }
        .filter-pill-btn.active {
            background: #ffffff;
            color: #0f172a;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
            font-weight: 700;
        }
        .custom-date-bar {
            display: flex;
            align-items: center;
            gap: 8px;
            background: #f8fafc;
            border-bottom: 1px solid var(--border-light);
            padding: 6px 14px;
            font-size: 0.74rem;
        }
        .input-date-clean {
            font-family: inherit;
            font-size: 0.72rem;
            padding: 2px 6px;
            border: 1px solid var(--border);
            border-radius: 4px;
            outline: none;
            background: #ffffff;
            color: var(--text-title);
        }
        .input-date-clean:focus {
            border-color: #0284c7;
        }
        .btn-filter-apply {
            font-family: inherit;
            font-size: 0.70rem;
            font-weight: 700;
            padding: 3px 10px;
            border: none;
            border-radius: 4px;
            background: #0284c7;
            color: #ffffff;
            cursor: pointer;
            transition: background 0.15s;
        }
        .btn-filter-apply:hover {
            background: #0369a1;
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
            border-radius: 5px;
            padding: 14px 16px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .status-top-line {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-light);
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 12px;
            border-radius: 4px;
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
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 10px;
        }

        .meta-cell {
            background: #ffffff;
            border: 1px solid var(--border-light);
            border-radius: 4px;
            padding: 9px 12px;
            display: flex;
            flex-direction: column;
            gap: 4px;
            min-width: 0;
        }

        .meta-span-3 {
            grid-column: span 3;
        }

        .meta-span-2 {
            grid-column: span 2;
        }

        .meta-cell-label {
            font-size: 0.68rem;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }

        .meta-cell-val {
            font-size: 0.85rem;
            font-weight: 700;
            color: var(--text-title);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .hw-status-row {
            padding-top: 10px;
            border-top: 1px solid var(--border-light);
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 8px;
            font-size: 0.73rem;
            color: var(--text-muted);
        }

        .hw-item {
            background: #ffffff;
            border: 1px solid var(--border-light);
            border-radius: 4px;
            padding: 7px 10px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 6px;
        }

        .hw-val-online { font-weight: 700; color: #166534; }
        .hw-val-offline { font-weight: 700; color: #64748b; }

        /* KARTU HMI */
        .hmi-cards-row-top {
            display: grid;
            grid-template-columns: 1.25fr 1fr;
            gap: 12px;
            flex: 1;
        }

        .hmi-box-clean {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 5px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .hmi-header-sm {
            font-size: 0.84rem;
            font-weight: 700;
            color: var(--text-title);
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        /* Busur Kemajuan */
        .gauge-layout {
            display: flex;
            align-items: center;
            justify-content: space-around;
            padding: 8px 0;
            gap: 12px;
            flex: 1;
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

        /* Total Lolos & Total Afkir */
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

        /* Kotak Tabel */
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
            margin-bottom: 8px;
        }

        .btn-download-csv {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            background: #f1f5f9;
            border: 1px solid #cbd5e1;
            color: #1e293b;
            padding: 3px 9px;
            border-radius: 4px;
            font-size: 0.72rem;
            font-weight: 700;
            text-decoration: none;
            transition: all 0.2s ease;
        }

        .btn-download-csv:hover {
            background: #0284c7;
            border-color: #0284c7;
            color: #ffffff;
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

        .tag-reprint-clean {
            background: #fef3c7;
            color: #b45309;
            padding: 1px 6px;
            border-radius: 2px;
            font-weight: 700;
            font-size: 0.68rem;
        }

        .tag-zero-clean {
            background: #f1f5f9;
            color: #475569;
            padding: 1px 6px;
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

        .lang-switch-group {
            display: inline-flex;
            border: 1px solid #334155;
            border-radius: 4px;
            overflow: hidden;
        }

        .lang-btn {
            background: #1e293b;
            color: #94a3b8;
            border: none;
            padding: 4px 9px;
            font-size: 0.72rem;
            font-weight: 800;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .lang-btn.active {
            background: #2563eb;
            color: #ffffff;
        }
    </style>
</head>
<body>
    <!-- Navigasi Atas -->
    <nav class="navbar">
        <div class="nav-brand">
            <h1 id="i18n_navTitle">ANALISIS PRODUKSI OMEGA MX</h1>
            <span class="badge-dept" id="i18n_navDept">RUANG MANAJEMEN</span>
        </div>
        <div class="nav-right">
            <div class="lang-switch-group" title="Pilih Bahasa / Select Language">
                <button class="lang-btn active" id="btnWebLangId" onclick="setWebLang('id')">IND</button>
                <button class="lang-btn" id="btnWebLangEn" onclick="setWebLang('en')">ENG</button>
            </div>
            <button class="btn-fullscreen" id="i18n_btnFull" onclick="toggleFullScreen()" title="Tampilkan Layar Penuh">Layar Penuh (F11)</button>
            <span class="clock-display" id="clockText">--:--:-- WIB</span>
            <span class="badge-live" id="badgeLive">
                <span class="dot-status dot-green" id="dotLive"></span>
                <span id="textLive">LANGSUNG</span>
            </span>
        </div>
    </nav>

    <!-- DASHBOARD WIDESCREEN (1920x1080 FIT) -->
    <div class="dashboard-main">
        
        <!-- PANEL UTAMA 1: KONDISI LAPANGAN TERKINI (KIRI) -->
        <section class="master-panel panel-realtime">
            <div class="panel-header-bar header-bar-realtime">
                <div class="panel-header-title">
                    <span class="dot-status dot-green"></span>
                    <span id="i18n_leftHeader">Kondisi Lapangan Terkini</span>
                </div>
                <span class="panel-badge-tag tag-realtime" id="i18n_leftBadge">Telemetri Langsung - Siklus Aktif</span>
            </div>

            <div class="panel-content">
                <!-- Status Operasional & Batch Aktif -->
                <div class="status-box-clean">
                    <div class="status-top-line">
                        <span id="i18n_lblSysOpStatus" style="font-size: 0.76rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Status Operasional Mesin</span>
                        <div class="status-pill pill-standby" id="statusPill">
                            <span class="dot-status dot-amber" id="statusDot"></span>
                            <span id="statusTitle">SIAGA</span>
                        </div>
                    </div>

                    <div class="meta-grid">
                        <div class="meta-cell meta-span-3">
                            <span class="meta-cell-label" id="i18n_lblWo">Surat Perintah Kerja (SPK)</span>
                            <span class="meta-cell-val" id="val_wo">-</span>
                        </div>
                        <div class="meta-cell meta-span-3">
                            <span class="meta-cell-label" id="i18n_lblFile">File Sumber Data</span>
                            <span class="meta-cell-val" id="val_file">-</span>
                        </div>
                        <div class="meta-cell meta-span-2">
                            <span class="meta-cell-label" id="i18n_lblSku">Kode Produk (SKU)</span>
                            <span class="meta-cell-val" id="val_sku">-</span>
                        </div>
                        <div class="meta-cell meta-span-2">
                            <span class="meta-cell-label" id="i18n_lblOp">Operator Bertugas</span>
                            <span class="meta-cell-val" id="val_operator">admin</span>
                        </div>
                        <div class="meta-cell meta-span-2">
                            <span class="meta-cell-label" id="i18n_lblStart">Waktu Mulai Batch</span>
                            <span class="meta-cell-val" id="val_start">-</span>
                        </div>
                    </div>

                    <div class="hw-status-row">
                        <div class="hw-item">
                            <span id="i18n_hwPrinter">Kepala Cetak:</span>
                            <span id="hw_printer_text" class="hw-val-offline">Terputus</span>
                        </div>
                        <div class="hw-item">
                            <span id="i18n_hwS1">Pemindai Sisi A:</span>
                            <span id="hw_s1_text" class="hw-val-offline">Terputus</span>
                        </div>
                        <div class="hw-item">
                            <span id="i18n_hwS2">Pemindai Sisi B:</span>
                            <span id="hw_s2_text" class="hw-val-offline">Terputus</span>
                        </div>
                        <div class="hw-item">
                            <span id="i18n_hwModbus">Modbus I/O:</span>
                            <span id="hw_modbus_text" class="hw-val-offline">Siaga</span>
                        </div>
                        <div class="hw-item">
                            <span id="i18n_hwApi">API Sistem Utama:</span>
                            <span id="hw_api_text" class="hw-val-offline">Siap</span>
                        </div>
                    </div>
                </div>

                <!-- Row 2: Card Kemajuan Batch & Card TOTAL LOLOS/AFKIR -->
                <div class="hmi-cards-row-top">
                    <!-- Kemajuan Batch -->
                    <div class="hmi-box-clean">
                        <div class="hmi-header-sm">
                            <span id="i18n_batchProgress">Kemajuan Batch</span>
                        </div>
                        <div class="gauge-layout">
                            <div class="gauge-svg-wrap">
                                <svg width="150" height="80" viewBox="0 0 180 95">
                                    <path d="M 20 85 A 70 70 0 0 1 160 85" fill="none" stroke="#e2e8f0" stroke-width="15" stroke-linecap="round"/>
                                    <path id="gaugePath" d="M 20 85 A 70 70 0 0 1 160 85" fill="none" stroke="#0284c7" stroke-width="15" stroke-linecap="round" stroke-dasharray="220" stroke-dashoffset="220" style="transition: stroke-dashoffset 0.4s ease;"/>
                                </svg>
                                <div class="gauge-percent-text" id="gaugePct">0%</div>
                                <span class="gauge-subtext" id="i18n_gaugeSub">KEMAJUAN</span>
                            </div>

                            <div class="gauge-info">
                                <div class="gauge-counts">
                                    <span id="gaugeJudged">0</span> / <span id="gaugeTotal">0</span>
                                                                </div>
                                <span class="gauge-label" id="i18n_boxDone">Kardus Selesai</span>
                                <div class="gauge-sisa">
                                    <span id="i18n_lblRem">Sisa:</span> <span id="gaugeSisa">0</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- TOTAL LOLOS & TOTAL AFKIR -->
                    <div class="hmi-box-clean">
                        <div class="ok-ng-grid">
                            <div class="counter-card counter-card-ok">
                                <div class="counter-card-title" id="i18n_totOk">TOTAL LOLOS</div>
                                <div class="counter-card-num" id="countOk">0</div>
                            </div>
                            <div class="counter-card counter-card-ng">
                                <div class="counter-card-title" id="i18n_totNg">TOTAL AFKIR</div>
                                <div class="counter-card-num" id="countNg">0</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- PANEL UTAMA 2: REKAPITULASI PRODUKSI TERKUMPUL (KANAN) -->
        <section class="master-panel panel-history">
            <div class="panel-header-bar header-bar-history">
                <div class="panel-header-title"><span id="i18n_rightHeader">Rekapitulasi Produksi Terkumpul</span></div>
                <div class="filter-controls-wrap">
                    <div class="filter-pill-group">
                        <button class="filter-pill-btn active" id="btnFilter7D" onclick="setHistoryFilter('7d')">7 Hari</button>
                        <button class="filter-pill-btn" id="btnFilter30D" onclick="setHistoryFilter('30d')">30 Hari</button>
                        <button class="filter-pill-btn" id="btnFilterAll" onclick="setHistoryFilter('all')">Semua</button>
                        <button class="filter-pill-btn" id="btnFilterCustom" onclick="toggleCustomRange()">Kustom</button>
                    </div>
                    <span class="panel-badge-tag tag-history" id="badgeRangeText">Basis Data: 7 Hari Terakhir</span>
                </div>
            </div>

            <!-- Baris Input Tanggal Kustom (Tersembunyi secara default, muncul saat klik Kustom) -->
            <div id="customDateRow" class="custom-date-bar" style="display: none;">
                <span id="i18n_lblDateRange" style="font-weight: 600; color: var(--text-muted);">Rentang Tanggal:</span>
                <input type="date" id="customStartDate" class="input-date-clean">
                <span id="i18n_lblDateTo" style="color: var(--text-muted);">s/d</span>
                <input type="date" id="customEndDate" class="input-date-clean">
                <button class="btn-filter-apply" id="i18n_btnApplyCustom" onclick="applyCustomDateRange()">Terapkan Filter</button>
            </div>

            <div class="panel-content">
                <!-- 3 KPI Kumulatif -->
                <div class="kpi-row">
                    <div class="kpi-card">
                        <div class="kpi-label" id="i18n_kpiVol">Total Volume Cetak</div>
                        <div id="total_volume" class="kpi-val" style="color: #0284c7;">-</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label" id="i18n_kpiNg">Rata-Rata Tingkat Afkir</div>
                        <div id="avg_ng" class="kpi-val" style="color: #dc2626;">-</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label" id="i18n_kpiBatch">Total Batch Selesai</div>
                        <div id="total_batch" class="kpi-val" style="color: #16a34a;">-</div>
                    </div>
                </div>

                <!-- 2 Grafik Berdampingan -->
                <div class="charts-row">
                    <div class="chart-box-clean">
                        <div class="chart-title-sm" id="chartLineTitle">Tren Produksi Harian (7 Hari Terakhir)</div>
                        <div class="chart-canvas-wrap">
                            <canvas id="chartLine"></canvas>
                        </div>
                    </div>
                    <div class="chart-box-clean">
                        <div class="chart-title-sm" id="i18n_chartPieTitle">Distribusi 5 Produk Teratas</div>
                        <div class="chart-canvas-wrap">
                            <canvas id="chartPie"></canvas>
                        </div>
                    </div>
                </div>

                <!-- Tabel Riwayat Batch Selesai dengan Tombol Ekspor CSV -->
                <div class="table-box-clean">
                    <div class="table-header-sm">
                        <span id="i18n_tblHeader">Riwayat Batch Produksi Terkini</span>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <a href="/api/v1/export-raw-csv?days=7" id="btnDownloadCsv" class="btn-download-csv" download="riwayat_produksi_mentah.csv" title="Unduh seluruh data riwayat dalam format CSV">Unduh Data Mentah (CSV)</a>
                            <span id="record_count" style="font-size: 0.72rem; color: var(--text-muted); font-weight: 600;">-</span>
                        </div>
                    </div>
                    <div class="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th id="i18n_thEnd">Waktu Selesai</th>
                                    <th id="i18n_thDur">Durasi</th>
                                    <th id="i18n_thSrc">File Sumber</th>
                                    <th id="i18n_thTot">Total Data</th>
                                    <th id="i18n_thPrt">Total Cetak</th>
                                    <th id="i18n_thTotNg">Total NG</th>
                                    <th id="i18n_thReprint">Reprint</th>
                                </tr>
                            </thead>
                            <tbody id="table_body">
                                <tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 14px;">Memuat data riwayat...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </section>

    </div>

    <div class="footer-note" id="i18n_footerNote">
        PT Smartek Sistem Inovasi &copy; 2026 | Sistem Percetakan Batch & Kontrol Mutu Omega MX v2.0 | Tampilan Ruang Manajemen
    </div>

    <script>
        let lineChartInstance = null;
        let pieChartInstance = null;
        let webLang = localStorage.getItem('omega_web_lang') || 'id';
        let userOverrodeWebLang = Boolean(localStorage.getItem('omega_web_lang'));
        let lastLivePayload = null;

        const WEB_I18N = {
            id: {
                navTitle: "ANALISIS PRODUKSI OMEGA MX",
                navDept: "RUANG MANAJEMEN",
                btnFull: "Layar Penuh (F11)",
                liveOnline: "LANGSUNG",
                liveOffline: "TERPUTUS",
                leftHeader: "Kondisi Lapangan Terkini",
                leftBadge: "Telemetri Langsung - Siklus Aktif",
                lblSysOpStatus: "Status Operasional Mesin",
                stRunning: "BERJALAN",
                stPaused: "DIJEDA",
                stStopped: "BERHENTI",
                stStandby: "SIAGA",
                stOffline: "TERPUTUS",
                lblWo: "Surat Perintah Kerja (SPK)",
                lblSku: "Kode Produk (SKU)",
                lblFile: "File Sumber Data",
                lblOp: "Operator Bertugas",
                lblStart: "Waktu Mulai Batch",
                hwPrinter: "Kepala Cetak:",
                hwS1: "Pemindai Sisi A:",
                hwS2: "Pemindai Sisi B:",
                hwModbus: "Modbus I/O:",
                hwApi: "API Sistem Utama:",
                hwConn: "Terhubung",
                hwDisc: "Terputus",
                hwActive: "Aktif",
                hwStandby: "Siaga",
                hwReady: "Siap",
                batchProgress: "Kemajuan Batch",
                gaugeSub: "KEMAJUAN",
                boxDone: "Kardus Selesai",
                lblRem: "Sisa:",
                totOk: "TOTAL LOLOS",
                totNg: "TOTAL AFKIR",
                convQueue: "Antrean Konveyor",
                inTransitFmt: "Dalam Lintasan: {n} Kardus",
                nodeHead: "Kepala Cetak",
                nodeScan: "Pemindai Ganda",
                nodePush: "Pendorong (DO0)",
                rightHeader: "Rekapitulasi Produksi Terkumpul",
                f7d: "7 Hari",
                f30d: "30 Hari",
                fAll: "Semua",
                fCustom: "Kustom",
                lblDateRange: "Rentang Tanggal:",
                lblDateTo: "s/d",
                btnApplyCustom: "Terapkan Filter",
                kpiVol: "Total Volume Cetak",
                kpiNg: "Rata-Rata Tingkat Afkir",
                kpiBatch: "Total Batch Selesai",
                chartPieTitle: "Distribusi 5 Produk Teratas",
                tblHeader: "Riwayat Batch Produksi Terkini",
                btnDownloadCsv: "Unduh Data Mentah (CSV)",
                thEnd: "Waktu Selesai",
                thDur: "Durasi",
                thSrc: "File Sumber",
                thTot: "Total Data",
                thPrt: "Total Cetak",
                thTotNg: "Total NG",
                thReprint: "Reprint",
                footerNote: "PT Smartek Sistem Inovasi © 2026 | Sistem Percetakan Batch & Kontrol Mutu Omega MX v2.0 | Tampilan Ruang Manajemen",
                db7d: "Basis Data: 7 Hari Terakhir",
                db30d: "Basis Data: 30 Hari Terakhir",
                dbAll: "Basis Data: Seluruh Riwayat",
                dbCustom: "Basis Data: {s} s/d {e}",
                tr7d: "Tren Produksi Harian (7 Hari Terakhir)",
                tr30d: "Tren Produksi Harian (30 Hari Terakhir)",
                trAll: "Tren Produksi Harian (Seluruh Data)",
                trCustom: "Tren Produksi Harian ({s} s/d {e})",
                noData: "Tidak Ada Data",
                volLabel: "Volume Cetak",
                emptyHist: "Belum ada riwayat batch produksi tercatat.",
                emptyRange: "Tidak ada riwayat batch produksi pada rentang tanggal ini.",
                ngSuffix: "Afkir"
            },
            en: {
                navTitle: "OMEGA MX PRODUCTION ANALYTICS",
                navDept: "MANAGEMENT ROOM",
                btnFull: "Full Screen (F11)",
                liveOnline: "LIVE",
                liveOffline: "OFFLINE",
                leftHeader: "Live Field Telemetry",
                leftBadge: "Live Telemetry - Active Cycle",
                lblSysOpStatus: "Machine Operational Status",
                stRunning: "RUNNING",
                stPaused: "PAUSED",
                stStopped: "STOPPED",
                stStandby: "STANDBY",
                stOffline: "OFFLINE",
                lblWo: "Work Order (WO)",
                lblSku: "Product Code (SKU)",
                lblFile: "Source Data File",
                lblOp: "Operator on Duty",
                lblStart: "Batch Start Time",
                hwPrinter: "Print Head:",
                hwS1: "Scanner Side A:",
                hwS2: "Scanner Side B:",
                hwModbus: "Modbus I/O:",
                hwApi: "Upstream API:",
                hwConn: "Connected",
                hwDisc: "Disconnected",
                hwActive: "Active",
                hwStandby: "Standby",
                hwReady: "Ready",
                batchProgress: "Batch Progress",
                gaugeSub: "PROGRESS",
                boxDone: "Boxes Completed",
                lblRem: "Rem:",
                totOk: "TOTAL PASSED (OK)",
                totNg: "TOTAL REJECTED (NG)",
                convQueue: "Conveyor Queue",
                inTransitFmt: "In Transit: {n} Boxes",
                nodeHead: "Print Head",
                nodeScan: "Dual Scanner",
                nodePush: "Pusher (DO0)",
                rightHeader: "Cumulative Production Summary",
                f7d: "7 Days",
                f30d: "30 Days",
                fAll: "All",
                fCustom: "Custom",
                lblDateRange: "Date Range:",
                lblDateTo: "to",
                btnApplyCustom: "Apply Filter",
                kpiVol: "Total Print Volume",
                kpiNg: "Average Reject Rate",
                kpiBatch: "Total Completed Batches",
                chartPieTitle: "Top 5 Products Distribution",
                tblHeader: "Recent Production Batch History",
                btnDownloadCsv: "Download Raw Data (CSV)",
                thEnd: "End Time",
                thDur: "Duration",
                thSrc: "Source File",
                thTot: "Total Data",
                thPrt: "Total Print",
                thTotNg: "Total NG",
                thReprint: "Reprint",
                footerNote: "PT Smartek Sistem Inovasi © 2026 | Omega MX Batch Printing & Quality Control System v2.0 | Management Room View",
                db7d: "Dataset: Last 7 Days",
                db30d: "Dataset: Last 30 Days",
                dbAll: "Dataset: All History",
                dbCustom: "Dataset: {s} to {e}",
                tr7d: "Daily Production Trend (Last 7 Days)",
                tr30d: "Daily Production Trend (Last 30 Days)",
                trAll: "Daily Production Trend (All Data)",
                trCustom: "Daily Production Trend ({s} to {e})",
                noData: "No Data",
                volLabel: "Print Volume",
                emptyHist: "No production batch history recorded yet.",
                emptyRange: "No production batch history in this date range.",
                ngSuffix: "NG"
            }
        };

        function wtr(key) {
            const d = WEB_I18N[webLang] || WEB_I18N.id;
            return d[key] || key;
        }

        function setWebLang(lang, isManual = true) {
            if (lang !== 'id' && lang !== 'en') return;
            webLang = lang;
            if (isManual) {
                userOverrodeWebLang = true;
                localStorage.setItem('omega_web_lang', lang);
            }
            document.getElementById('btnWebLangId').classList.toggle('active', lang === 'id');
            document.getElementById('btnWebLangEn').classList.toggle('active', lang === 'en');

            const mapIds = {
                i18n_navTitle: 'navTitle',
                i18n_navDept: 'navDept',
                i18n_btnFull: 'btnFull',
                i18n_leftHeader: 'leftHeader',
                i18n_leftBadge: 'leftBadge',
                i18n_lblSysOpStatus: 'lblSysOpStatus',
                i18n_lblWo: 'lblWo',
                i18n_lblSku: 'lblSku',
                i18n_lblFile: 'lblFile',
                i18n_lblOp: 'lblOp',
                i18n_lblStart: 'lblStart',
                i18n_hwPrinter: 'hwPrinter',
                i18n_hwS1: 'hwS1',
                i18n_hwS2: 'hwS2',
                i18n_hwModbus: 'hwModbus',
                i18n_hwApi: 'hwApi',
                i18n_batchProgress: 'batchProgress',
                i18n_gaugeSub: 'gaugeSub',
                i18n_boxDone: 'boxDone',
                i18n_lblRem: 'lblRem',
                i18n_totOk: 'totOk',
                i18n_totNg: 'totNg',
                i18n_convQueue: 'convQueue',
                i18n_nodeHead: 'nodeHead',
                i18n_nodeScan: 'nodeScan',
                i18n_nodePush: 'nodePush',
                i18n_rightHeader: 'rightHeader',
                btnFilter7D: 'f7d',
                btnFilter30D: 'f30d',
                btnFilterAll: 'fAll',
                btnFilterCustom: 'fCustom',
                i18n_lblDateRange: 'lblDateRange',
                i18n_lblDateTo: 'lblDateTo',
                i18n_btnApplyCustom: 'btnApplyCustom',
                i18n_kpiVol: 'kpiVol',
                i18n_kpiNg: 'kpiNg',
                i18n_kpiBatch: 'kpiBatch',
                i18n_chartPieTitle: 'chartPieTitle',
                i18n_tblHeader: 'tblHeader',
                btnDownloadCsv: 'btnDownloadCsv',
                i18n_thEnd: 'thEnd',
                i18n_thDur: 'thDur',
                i18n_thSrc: 'thSrc',
                i18n_thTot: 'thTot',
                i18n_thPrt: 'thPrt',
                i18n_thTotNg: 'thTotNg',
                i18n_thReprint: 'thReprint',
                i18n_footerNote: 'footerNote'
            };
            for (const [elId, k] of Object.entries(mapIds)) {
                const el = document.getElementById(elId);
                if (el) el.innerText = wtr(k);
            }
            if (lastLivePayload) renderLivePayload(lastLivePayload);
            renderFilteredHistory();
        }

        // Beralih Layar Penuh
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

        function renderLivePayload(s) {
            // Indikator Langsung
            document.getElementById('badgeLive').className = 'badge-live';
            document.getElementById('dotLive').className = 'dot-status dot-green';
            document.getElementById('textLive').innerText = wtr('liveOnline');

            // Status Mesin
            const rawStatus = (s.system_status || 'READY').toUpperCase();
            const pill = document.getElementById('statusPill');
            const pDot = document.getElementById('statusDot');
            const pTitle = document.getElementById('statusTitle');

            if (rawStatus === 'RUNNING') {
                pill.className = 'status-pill pill-running';
                pDot.className = 'dot-status dot-green';
                pTitle.innerText = wtr('stRunning');
            } else if (rawStatus === 'PAUSED') {
                pill.className = 'status-pill pill-paused';
                pDot.className = 'dot-status dot-amber';
                pTitle.innerText = wtr('stPaused');
            } else if (rawStatus === 'STOPPED' || rawStatus === 'ALARM') {
                pill.className = 'status-pill pill-stopped';
                pDot.className = 'dot-status dot-red';
                pTitle.innerText = wtr('stStopped');
            } else {
                pill.className = 'status-pill pill-standby';
                pDot.className = 'dot-status dot-amber';
                pTitle.innerText = wtr('stStandby');
            }

            // Metadata Batch Aktif
            document.getElementById('val_wo').innerText = s.current_work_order || '-';
            document.getElementById('val_sku').innerText = s.current_sku || '-';
            document.getElementById('val_file').innerText = s.current_file || '-';
            document.getElementById('val_operator').innerText = s.operator || 'admin';
            document.getElementById('val_start').innerText = s.batch_start_time || '-';

            // Status Koneksi Perangkat
            const hw = s.hardware || {};
            function setHw(idText, isOnline) {
                const txt = document.getElementById(idText);
                if (isOnline) {
                    txt.className = 'hw-val-online';
                    txt.innerText = wtr('hwConn');
                } else {
                    txt.className = 'hw-val-offline';
                    txt.innerText = wtr('hwDisc');
                }
            }
            setHw('hw_printer_text', hw.printer_online);
            setHw('hw_s1_text', hw.scanner1_online);
            setHw('hw_s2_text', hw.scanner2_online);
            
            // Modbus I/O
            const txtM = document.getElementById('hw_modbus_text');
            if (hw.modbus_online) {
                txtM.className = 'hw-val-online';
                txtM.innerText = wtr('hwActive');
            } else {
                txtM.className = 'hw-val-offline';
                txtM.innerText = wtr('hwStandby');
            }

            // API Sistem Utama
            const txtApi = document.getElementById('hw_api_text');
            if (hw.upstream_api_online) {
                txtApi.className = 'hw-val-online';
                txtApi.innerText = wtr('hwConn');
            } else {
                txtApi.className = 'hw-val-offline';
                txtApi.innerText = wtr('hwReady');
            }

            // Kartu Kemajuan Batch
            const p = s.progress || {};
            const cycleNum = p.print_cycle || 1;
            const elBpTitle = document.getElementById('i18n_batchProgress');
            if (elBpTitle) {
                elBpTitle.innerText = cycleNum > 1
                    ? `${wtr('batchProgress')} (Reprint #${cycleNum - 1})`
                    : wtr('batchProgress');
            }
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

            // Total Lolos & Afkir
            const okCnt = p.count_ok || 0;
            const ngCnt = p.count_ng || 0;
            document.getElementById('countOk').innerText = okCnt;
            document.getElementById('countNg').innerText = ngCnt;
        }

        // 1. POLLING STATUS LANGSUNG DARI LAPANGAN (Setiap 1.5 detik)
        async function pollLiveStatus() {
            try {
                const res = await fetch('/api/v1/status');
                if (!res.ok) throw new Error("HTTP " + res.status);
                const s = await res.json();
                lastLivePayload = s;
                if (!userOverrodeWebLang && (s.language === 'id' || s.language === 'en') && s.language !== webLang) {
                    setWebLang(s.language, false);
                    return;
                }
                renderLivePayload(s);
            } catch (err) {
                // Saat HMI Terputus
                document.getElementById('badgeLive').className = 'badge-live';
                document.getElementById('dotLive').className = 'dot-status dot-gray';
                document.getElementById('textLive').innerText = wtr('liveOffline');

                const pill = document.getElementById('statusPill');
                pill.className = 'status-pill pill-offline';
                document.getElementById('statusDot').className = 'dot-status dot-gray';
                document.getElementById('statusTitle').innerText = wtr('stOffline');
            }
        }

        // 2. MANAJEMEN DATA REKAPITULASI HISTORIS FLEKSIBEL (7D, 30D, SEMUA, KUSTOM)
        let rawHistoryData = [];
        let currentFilterMode = '7d';
        let customStartVal = '';
        let customEndVal = '';

        function setHistoryFilter(mode) {
            currentFilterMode = mode;
            ['btnFilter7D', 'btnFilter30D', 'btnFilterAll', 'btnFilterCustom'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.classList.remove('active');
            });

            const rowCustom = document.getElementById('customDateRow');
            if (mode === '7d') {
                document.getElementById('btnFilter7D').classList.add('active');
                if (rowCustom) rowCustom.style.display = 'none';
            } else if (mode === '30d') {
                document.getElementById('btnFilter30D').classList.add('active');
                if (rowCustom) rowCustom.style.display = 'none';
            } else if (mode === 'all') {
                document.getElementById('btnFilterAll').classList.add('active');
                if (rowCustom) rowCustom.style.display = 'none';
            } else if (mode === 'custom') {
                document.getElementById('btnFilterCustom').classList.add('active');
                if (rowCustom) rowCustom.style.display = 'flex';
            }
            renderFilteredHistory();
        }

        function toggleCustomRange() {
            const rowCustom = document.getElementById('customDateRow');
            if (!rowCustom) return;
            const isHidden = (rowCustom.style.display === 'none');
            if (isHidden) {
                rowCustom.style.display = 'flex';
                // Inisialisasi default tanggal jika kosong
                const now = new Date();
                const past7 = new Date();
                past7.setDate(now.getDate() - 7);
                const toIsoDate = d => d.toISOString().split('T')[0];
                if (!document.getElementById('customStartDate').value) {
                    document.getElementById('customStartDate').value = toIsoDate(past7);
                }
                if (!document.getElementById('customEndDate').value) {
                    document.getElementById('customEndDate').value = toIsoDate(now);
                }
            } else {
                rowCustom.style.display = 'none';
            }
        }

        function applyCustomDateRange() {
            const s = document.getElementById('customStartDate').value;
            const e = document.getElementById('customEndDate').value;
            if (!s || !e) {
                alert("Silakan pilih tanggal mulai dan tanggal selesai.");
                return;
            }
            if (s > e) {
                alert("Tanggal mulai tidak boleh lebih besar dari tanggal selesai.");
                return;
            }
            customStartVal = s;
            customEndVal = e;
            setHistoryFilter('custom');
        }

        async function loadHistoryData() {
            try {
                const res = await fetch('/api/history');
                const data = await res.json();
                if (Array.isArray(data)) {
                    rawHistoryData = data;
                    renderFilteredHistory();
                }
            } catch (err) {
                console.error("Gagal memuat data riwayat dari server:", err);
            }
        }

        function renderFilteredHistory() {
            if (!Array.isArray(rawHistoryData) || rawHistoryData.length === 0) {
                document.getElementById('total_volume').innerText = "0";
                document.getElementById('avg_ng').innerText = "0.0";
                document.getElementById('total_batch').innerText = "0";
                document.getElementById('record_count').innerText = "0 Batch";
                document.getElementById('table_body').innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 14px;">${wtr('emptyHist')}</td></tr>`;
                return;
            }

            const now = new Date();
            const toIsoDate = d => d.toISOString().split('T')[0];
            let filtered = [];
            let badgeText = "";
            let chartTitleText = "";
            let exportUrl = "/api/v1/export-raw-csv";

            if (currentFilterMode === '7d') {
                const past7 = new Date();
                past7.setDate(now.getDate() - 7);
                const cutoff = toIsoDate(past7);
                filtered = rawHistoryData.filter(i => (i.Waktu_Selesai || "").split(' ')[0] >= cutoff);
                badgeText = wtr('db7d');
                chartTitleText = wtr('tr7d');
                exportUrl = "/api/v1/export-raw-csv?days=7";
            } else if (currentFilterMode === '30d') {
                const past30 = new Date();
                past30.setDate(now.getDate() - 30);
                const cutoff = toIsoDate(past30);
                filtered = rawHistoryData.filter(i => (i.Waktu_Selesai || "").split(' ')[0] >= cutoff);
                badgeText = wtr('db30d');
                chartTitleText = wtr('tr30d');
                exportUrl = "/api/v1/export-raw-csv?days=30";
            } else if (currentFilterMode === 'custom') {
                filtered = rawHistoryData.filter(i => {
                    const d = (i.Waktu_Selesai || "").split(' ')[0];
                    return d >= customStartVal && d <= customEndVal;
                });
                badgeText = wtr('dbCustom').replace('{s}', customStartVal).replace('{e}', customEndVal);
                chartTitleText = wtr('trCustom').replace('{s}', customStartVal).replace('{e}', customEndVal);
                exportUrl = `/api/v1/export-raw-csv?start_date=${encodeURIComponent(customStartVal)}&end_date=${encodeURIComponent(customEndVal)}`;
            } else { // 'all'
                filtered = [...rawHistoryData];
                badgeText = wtr('dbAll');
                chartTitleText = wtr('trAll');
                exportUrl = "/api/v1/export-raw-csv";
            }

            // Update Badge & Header
            const elBadge = document.getElementById('badgeRangeText');
            if (elBadge) elBadge.innerText = badgeText;
            const elChartTitle = document.getElementById('chartLineTitle');
            if (elChartTitle) elChartTitle.innerText = chartTitleText;
            const elBtnCsv = document.getElementById('btnDownloadCsv');
            if (elBtnCsv) elBtnCsv.setAttribute('href', exportUrl);

            // Update KPI Kumulatif
            const totalVol = filtered.reduce((s, i) => s + (parseInt(i.Total_Print) || 0), 0);
            const totalNG = filtered.reduce((s, i) => s + (parseInt(i.Total_NG) || 0), 0);
            const avgNG = filtered.length > 0 ? (totalNG / filtered.length).toFixed(2) : "0.0";

            document.getElementById('total_volume').innerText = totalVol.toLocaleString();
            document.getElementById('avg_ng').innerText = avgNG;
            document.getElementById('total_batch').innerText = filtered.length.toLocaleString();
            document.getElementById('record_count').innerText = `${filtered.length} Batch`;

            // Grafik Garis Tren Harian Terfilter (Diurutkan Kronologis)
            const dates = [...new Set(filtered.map(i => (i.Waktu_Selesai || "").split(' ')[0]).filter(Boolean))].sort();
            const volData = dates.map(d => filtered.filter(i => (i.Waktu_Selesai || "").startsWith(d)).reduce((s, i) => s + (parseInt(i.Total_Print) || 0), 0));

            if (lineChartInstance) lineChartInstance.destroy();
            lineChartInstance = new Chart(document.getElementById('chartLine'), {
                type: 'line',
                data: {
                    labels: dates.length ? dates : [wtr('noData')],
                    datasets: [{
                        label: wtr('volLabel'),
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

            // Grafik Donat SKU Terfilter
            const skus = {};
            filtered.forEach(i => {
                const src = i.Source || "Other";
                skus[src] = (skus[src] || 0) + (parseInt(i.Total_Print) || 0);
            });
            const topSkus = Object.entries(skus).sort((a,b) => b[1]-a[1]).slice(0, 5);

            if (pieChartInstance) pieChartInstance.destroy();
            pieChartInstance = new Chart(document.getElementById('chartPie'), {
                type: 'doughnut',
                data: {
                    labels: topSkus.length ? topSkus.map(i => i[0]) : [wtr('noData')],
                    datasets: [{
                        data: topSkus.length ? topSkus.map(i => i[1]) : [1],
                        backgroundColor: topSkus.length ? ['#16a34a', '#eab308', '#ea580c', '#dc2626', '#8b5cf6'] : ['#e2e8f0'],
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

            // Tabel Data Riwayat Terkini Terfilter
            if (filtered.length === 0) {
                document.getElementById('table_body').innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 14px;">${wtr('emptyRange')}</td></tr>`;
            } else {
                const recent = [...filtered].reverse().slice(0, 12);
                const rows = recent.map(r => {
                    const totNgVal = parseInt(r.Total_NG) || 0;
                    const reprintVal = parseInt(r.NG_Level) || 0;
                    const totNgBadge = totNgVal > 0 
                        ? `<span class="tag-ng-clean">${totNgVal} NG</span>` 
                        : `<span class="tag-ok-clean">0 NG</span>`;
                    const reprintBadge = reprintVal > 0
                        ? `<span class="tag-reprint-clean">${reprintVal}x</span>`
                        : `<span class="tag-zero-clean">0</span>`;
                    return `<tr>
                        <td>${escapeHtml(r.Waktu_Selesai)}</td>
                        <td>${escapeHtml(r.Durasi)}</td>
                        <td title="${escapeHtml(r.Source)}"><b>${escapeHtml(r.Source.length > 25 ? r.Source.substring(0,23) + '..' : r.Source)}</b></td>
                        <td>${parseInt(r.Total_Data) || 0}</td>
                        <td>${parseInt(r.Total_Print) || 0}</td>
                        <td>${totNgBadge}</td>
                        <td>${reprintBadge}</td>
                    </tr>`;
                }).join('');
                document.getElementById('table_body').innerHTML = rows;
            }
        }

        // Inisialisasi bahasa & Interval Polling
        setWebLang(webLang, false);
        pollLiveStatus();
        setInterval(pollLiveStatus, 1500);

        loadHistoryData();
        setInterval(loadHistoryData, 10000);
    </script>
</body>
</html>"""
