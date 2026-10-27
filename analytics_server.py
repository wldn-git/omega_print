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
        return """
        <!DOCTYPE html>
        <html lang="id">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Omega MX Analytics - PT SMARTEK</title>
            <script src="/assets/chart.umd.js"></script>
            <style>
                :root {
                    --primary: #1c446c;
                    --accent: #1e73be;
                    --success: #1e7e34;
                    --danger: #c0392b;
                    --warning: #f39c12;
                    --bg: #f0f2f5;
                    --card-bg: #ffffff;
                    --text: #1c446c;
                    --text-muted: #5a738e;
                }
                * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; }
                body { background-color: var(--bg); color: var(--text); padding-bottom: 40px; }
                .navbar { background: linear-gradient(135deg, #163656 0%, #1c446c 100%); color: white; padding: 18px 30px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
                .navbar h1 { font-size: 1.3rem; font-weight: 700; letter-spacing: 0.5px; }
                .badge-offline { background-color: rgba(39, 174, 96, 0.2); color: #2ecc71; padding: 6px 14px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; border: 1px solid rgba(46, 204, 113, 0.4); }
                .container { max-width: 1200px; margin: 30px auto; padding: 0 20px; }
                .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 20px; margin-bottom: 25px; }
                .card { background: var(--card-bg); border-radius: 12px; padding: 22px; box-shadow: 0 4px 15px rgba(0,0,0,0.04); border: 1px solid rgba(0,0,0,0.05); }
                .stat-title { font-size: 0.85rem; font-weight: 600; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px; }
                .stat-value { font-size: 2.2rem; font-weight: 700; }
                .val-primary { color: var(--accent); }
                .val-danger { color: var(--danger); }
                .val-success { color: var(--success); }
                .charts-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; margin-bottom: 25px; }
                @media (max-width: 900px) { .charts-grid { grid-template-columns: 1fr; } }
                .chart-title { font-size: 1.05rem; font-weight: 700; color: var(--primary); margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }
                .table-card { background: var(--card-bg); border-radius: 12px; padding: 22px; box-shadow: 0 4px 15px rgba(0,0,0,0.04); }
                table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9rem; }
                th { background-color: #f8fafc; color: var(--text-muted); font-weight: 600; text-align: left; padding: 12px 14px; border-bottom: 2px solid #edf2f7; }
                td { padding: 12px 14px; border-bottom: 1px solid #edf2f7; }
                tr:hover { background-color: #f8fafd; }
                .tag-ng { background: #fee2e2; color: #dc2626; padding: 3px 8px; border-radius: 6px; font-weight: 600; font-size: 0.8rem; }
                .tag-ok { background: #dcfce7; color: #16a34a; padding: 3px 8px; border-radius: 6px; font-weight: 600; font-size: 0.8rem; }
                .footer { text-align: center; margin-top: 30px; font-size: 0.8rem; color: var(--text-muted); }
            </style>
        </head>
        <body>
            <nav class="navbar">
                <h1>📊 OMEGA MX PRODUCTION ANALYTICS</h1>
                <span class="badge-offline">● LOCAL OFFLINE READY</span>
            </nav>
            <div class="container">
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
                                <tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Memuat riwayat...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="footer">
                    PT SMARTEK SISTEM INOVASI &copy; 2026 | Omega MX Batch & QC System V5.0
                </div>
            </div>

            <script>
                let lineChartInstance = null;
                let pieChartInstance = null;

                async function loadData() {
                    try {
                        const res = await fetch('/api/history');
                        const data = await res.json();
                        
                        if (!Array.isArray(data) || data.length === 0) {
                            document.getElementById('total_volume').innerText = "0";
                            document.getElementById('avg_ng').innerText = "0.0";
                            document.getElementById('total_batch').innerText = "0";
                            document.getElementById('table_body').innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Belum ada riwayat batch produksi tercatat.</td></tr>';
                            return;
                        }

                        const totalVol = data.reduce((s, i) => s + (parseInt(i.Total_Print) || 0), 0);
                        const totalNG = data.reduce((s, i) => s + (parseInt(i.NG_Level) || 0), 0);
                        const avgNG = data.length > 0 ? (totalNG / data.length).toFixed(2) : "0.0";

                        document.getElementById('total_volume').innerText = totalVol.toLocaleString();
                        document.getElementById('avg_ng').innerText = avgNG;
                        document.getElementById('total_batch').innerText = data.length.toLocaleString();
                        document.getElementById('record_count').innerText = data.length + " Batch";

                        // Line Chart Data
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
                                    borderColor: '#2980b9',
                                    backgroundColor: 'rgba(41, 128, 185, 0.1)',
                                    tension: 0.3,
                                    fill: true,
                                    borderWidth: 2
                                }]
                            },
                            options: { responsive: true, maintainAspectRatio: true }
                        });

                        // Pie Chart Data
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
                                    backgroundColor: ['#27ae60', '#f1c40f', '#e67e22', '#e74c3c', '#9b59b6']
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
                        console.error("Gagal load analytics:", err);
                    }
                }
                loadData();
                setInterval(loadData, 10000); // Auto-refresh tiap 10 detik
            </script>
        </body>
        </html>
        """