# data_manager.py
import os
import time
import datetime
import json
import pandas as pd

class DataManager:
    def __init__(self, base_dir=None, history_dir=None, log_dir=None, data_dir=None):
        self.base_dir = base_dir if base_dir else os.path.dirname(os.path.abspath(__file__))
        self.history_dir = history_dir if history_dir else os.path.join(self.base_dir, "history")
        self.log_dir = log_dir if log_dir else os.path.join(self.base_dir, "logs")
        self.data_dir = data_dir if data_dir else os.path.join(self.base_dir, "data")
        self.checkpoint_dir = os.path.join(self.history_dir, "checkpoints")
        self.config_file = os.path.join(self.data_dir, "config.json")

        os.makedirs(self.history_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        
        self.history_log_file = os.path.join(self.history_dir, "history_summary_log.csv")
        self.coupon_index_file = os.path.join(self.history_dir, "printed_coupons_index.csv")
        self.active_checkpoint_file = os.path.join(self.checkpoint_dir, "active_batch_checkpoint.json")
        self.bulan_indo = {1:"Januari", 2:"Februari", 3:"Maret", 4:"April", 5:"Mei", 6:"Juni", 
                           7:"Juli", 8:"Agustus", 9:"September", 10:"Oktober", 11:"November", 12:"Desember"}
        self.ensure_coupon_index()

    def load_config(self):
        """Memuat konfigurasi hardware & sistem dari data/config.json"""
        if not os.path.exists(self.config_file):
            return {}
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config.json: {e}")
            return {}

    def save_config(self, config_dict):
        """Menyimpan konfigurasi hardware & sistem secara aman ke data/config.json"""
        try:
            temp_file = os.path.join(self.data_dir, f"temp_cfg_{int(time.time()*1000)}.json")
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=4)
            os.replace(temp_file, self.config_file)
            return True
        except Exception as e:
            print(f"Error saving config.json: {e}")
            return False

    def get_history_retention_days(self) -> int:
        """Mendapatkan batas masa simpan / overwrite riwayat kupon & log dari konfigurasi (default 30 hari)"""
        cfg = self.load_config()
        try:
            return max(1, int(cfg.get("history_retention_days", 30)))
        except (ValueError, TypeError):
            return 30

    def set_history_retention_days(self, days: int) -> bool:
        """Menyimpan batas masa simpan / overwrite riwayat kupon & log ke config.json"""
        try:
            days = max(1, int(days))
            cfg = self.load_config()
            cfg["history_retention_days"] = days
            return self.save_config(cfg)
        except Exception as e:
            print(f"Error setting retention days: {e}")
            return False

    def cleanup_old_logs(self, days: int = None):
        """Menghapus file txt log yang umurnya melebihi batas masa simpan (retention days)"""
        try:
            if days is None:
                days = self.get_history_retention_days()
            now_time = time.time()
            cutoff_seconds = days * 86400
            for filename in os.listdir(self.log_dir):
                filepath = os.path.join(self.log_dir, filename)
                if os.path.isfile(filepath):
                    if os.stat(filepath).st_mtime < (now_time - cutoff_seconds):
                        os.remove(filepath)
                        print(f"File log lama dihapus otomatis (> {days} hari): {filename}")
        except Exception as e: 
            print(f"Error cleanup logs: {e}")

    def export_summary_csv(self, target_filepath: str, filter_val: str = None, start_date: str = None, end_date: str = None) -> bool:
        """Mengekspor data ringkasan riwayat produksi ke file CSV mentah"""
        try:
            if filter_val:
                df = self.get_filtered_history(filter_val, start_date, end_date)
            elif os.path.exists(self.history_log_file):
                df = pd.read_csv(self.history_log_file)
            else:
                df = pd.DataFrame()

            if df.empty:
                # Tulis file kosong dengan header
                headers = ["Waktu_Mulai", "Waktu_Selesai", "Durasi", "Source", "Total_Data", "Total_Print", "NG_Level", "Report_File"]
                pd.DataFrame(columns=headers).to_csv(target_filepath, index=False, encoding='utf-8')
            else:
                df.to_csv(target_filepath, index=False, encoding='utf-8')
            return True
        except Exception as e:
            print(f"Error exporting summary CSV: {e}")
            return False

    def export_raw_coupons_csv(self, target_filepath: str) -> bool:
        """Mengekspor data mentah seluruh index kupon kardus tercetak ke file CSV"""
        try:
            self.ensure_coupon_index()
            if os.path.exists(self.coupon_index_file):
                df = pd.read_csv(self.coupon_index_file, dtype=str, keep_default_na=False)
            else:
                df = pd.DataFrame(columns=['Coupon', 'Timestamp', 'Status', 'Source_File', 'Report_File'])
            df.to_csv(target_filepath, index=False, encoding='utf-8')
            return True
        except Exception as e:
            print(f"Error exporting raw coupons CSV: {e}")
            return False

    @staticmethod
    def sanitize_field(val: str) -> str:
        """Membersihkan karakter ilegal yang dapat merusak protokol printer (| : \\r \\n)"""
        if val is None:
            return ""
        s = str(val).strip()
        # Ganti pembatas protokol dengan strip/spasi aman agar tidak terjadi protocol injection
        s = s.replace('\r', ' ').replace('\n', ' ').replace('|', '-').replace(':', '-')
        return s.strip()

    def load_source_file(self, file_path):
        """Membaca file Excel/CSV dengan tipe data string (mempertahankan leading zero seperti '00123')"""
        filename = os.path.basename(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ('.xlsx', '.xls'):
            df = pd.read_excel(file_path, dtype=str, keep_default_na=False)
        else:
            df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
        
        # Bersihkan spasi tepi tanpa mengubah teks atau angka
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip()

        return df, filename

    def get_filtered_history(self, filter_val, start_date=None, end_date=None):
        """Membaca file master log dan mem-filter datanya"""
        if not os.path.exists(self.history_log_file):
            return pd.DataFrame()
            
        try:
            df = pd.read_csv(self.history_log_file)
            df = df.sort_values(by="Waktu_Selesai", ascending=False) 
            
            if filter_val == "last_20":
                df = df.head(20)
            elif filter_val == "by_date" and start_date and end_date:
                df = df[(df['Waktu_Selesai'] >= start_date) & (df['Waktu_Selesai'] <= end_date)]
            
            return df
        except Exception as e:
            print(f"Gagal memuat tabel history: {e}")
            return pd.DataFrame()

    def _write_excel_report(self, target_path, df_summary, df_history, current_filename, print_cycle):
        """Helper menulis lembar kerja report Excel secara lengkap"""
        with pd.ExcelWriter(target_path, engine='openpyxl') as writer:
            pd.DataFrame(columns=["history print"]).to_excel(writer, index=False, startrow=0, startcol=0)
            pd.DataFrame(columns=[f"file name: {current_filename}"]).to_excel(writer, index=False, startrow=1, startcol=0)
            pd.DataFrame(columns=["summary"]).to_excel(writer, index=False, startrow=3, startcol=3)
            df_summary.to_excel(writer, index=False, startrow=4, startcol=0)
            
            current_row = 7
            for cycle in range(1, print_cycle + 1):
                df_cycle = df_history[df_history['Cycle'] == cycle].copy().drop(columns=['Cycle'])
                title = "1st PRINT" if cycle == 1 else f"Re-Print {cycle-1}"
                pd.DataFrame(columns=[title]).to_excel(writer, index=False, startrow=current_row, startcol=0)
                df_cycle.to_excel(writer, index=False, startrow=current_row+1, startcol=0)
                current_row += len(df_cycle) + 4

    def save_history_excel(self, current_filename, total_load_data, print_cycle, history_records, batch_start_time):
        """Bikin folder bulan & tahun, save Excel (dengan penanganan file lock), dan tambah ke master CSV log"""
        if not history_records: return False, "Tidak ada data history."
        
        df_history = pd.DataFrame(history_records)
        summary_data = {"Load Data": [total_load_data], "Total Print": [len(df_history)]}
        for cycle in range(1, print_cycle + 1):
            df_cycle = df_history[df_history['Cycle'] == cycle]
            prefix = "1st" if cycle == 1 else "2nd" if cycle == 2 else "3rd" if cycle == 3 else f"{cycle}th"
            summary_data[f"{prefix} OK"] = [len(df_cycle[df_cycle['Status'] == 'OK'])]
            summary_data[f"{prefix} NG"] = [len(df_cycle[df_cycle['Status'] == 'NG'])]
        
        df_summary = pd.DataFrame(summary_data)
        
        now = datetime.datetime.now()
        year_str = now.strftime('%Y')
        month_str = f"{now.month:02d} - {self.bulan_indo.get(now.month, 'Unknown')}"
        
        target_folder = os.path.join(self.history_dir, year_str, month_str)
        os.makedirs(target_folder, exist_ok=True) 
        
        timestamp_now = now.strftime('%Y%m%d_%H%M%S')
        clean_base = os.path.splitext(current_filename)[0] if current_filename and str(current_filename).strip().lower() != 'nan' else "Batch"
        clean_source = current_filename if current_filename and str(current_filename).strip().lower() != 'nan' else f"{clean_base}.xlsx"
        report_filename = f"History_{clean_base}_{timestamp_now}.xlsx"
        save_path = os.path.join(target_folder, report_filename)
        relative_report_path = os.path.join(year_str, month_str, report_filename)
        
        notice_prefix = ""
        try:
            # 1. Tulis file Excel utama dengan proteksi File Lock (PermissionError)
            try:
                self._write_excel_report(save_path, df_summary, df_history, clean_source, print_cycle)
            except PermissionError:
                # File sedang terbuka di Microsoft Excel oleh operator/user
                alt_filename = f"History_{clean_base}_{timestamp_now}_recovered_{int(time.time())}.xlsx"
                save_path = os.path.join(target_folder, alt_filename)
                relative_report_path = os.path.join(year_str, month_str, alt_filename)
                try:
                    self._write_excel_report(save_path, df_summary, df_history, clean_source, print_cycle)
                    notice_prefix = "[FILE LOCK TERATASI] File utama sedang terbuka di Excel. Dialihkan ke: "
                except Exception as ex_alt:
                    # Emergency dump ke format CSV agar hasil produksi 100% terselamatkan
                    emergency_csv = os.path.join(target_folder, f"Emergency_{clean_base}_{timestamp_now}.csv")
                    df_history.to_csv(emergency_csv, index=False)
                    return False, f"File Excel terkunci dan gagal dialihkan ({ex_alt}). File Darurat CSV tersimpan di: {emergency_csv}"

            # 2. Tulis Data Ringkasan ke CSV (Master History Log)
            try:
                waktu_mulai_dt = datetime.datetime.strptime(batch_start_time, '%Y-%m-%d %H:%M:%S')
            except Exception:
                waktu_mulai_dt = now

            waktu_selesai_dt = datetime.datetime.now()
            waktu_selesai_str = waktu_selesai_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            selisih_waktu = waktu_selesai_dt - waktu_mulai_dt
            jam, sisa = divmod(int(selisih_waktu.total_seconds()), 3600)
            menit, detik = divmod(sisa, 60)
            durasi_str = f"{jam:02d}:{menit:02d}:{detik:02d}"
            
            new_log = pd.DataFrame([{
                "Waktu_Mulai": batch_start_time, 
                "Waktu_Selesai": waktu_selesai_str, 
                "Durasi": durasi_str, 
                "Source": clean_source, 
                "Total_Data": total_load_data, 
                "Total_Print": len(df_history), 
                "NG_Level": print_cycle - 1,
                "Report_File": relative_report_path
            }])
            
            if os.path.exists(self.history_log_file):
                new_log.to_csv(self.history_log_file, mode='a', header=False, index=False)
            else:
                new_log.to_csv(self.history_log_file, index=False)
                
            # 3. Rekam kupon yang tercetak ke index pencarian cepat 30 hari
            self.record_printed_coupons(history_records, current_filename, relative_report_path)

            # 4. Hapus Checkpoint Batch Aktif karena batch berhasil selesai & tersimpan
            self.clear_batch_checkpoint()

            return True, f"{notice_prefix}{save_path}"
        except Exception as e:
            return False, str(e)

    def save_batch_checkpoint(self, checkpoint_data):
        """Menyimpan checkpoint progres batch secara aman (atomic write) ke file JSON"""
        try:
            temp_file = os.path.join(self.checkpoint_dir, f"temp_{int(time.time()*1000)}.json")
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2)
            os.replace(temp_file, self.active_checkpoint_file)
            return True
        except Exception as e:
            print(f"Error saving batch checkpoint: {e}")
            return False

    def load_batch_checkpoint(self, current_filename=None):
        """Memuat checkpoint batch aktif jika ada dan sesuai dengan file sumber"""
        if not os.path.exists(self.active_checkpoint_file):
            return None
        try:
            with open(self.active_checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not data or not data.get('is_active', False):
                return None
            if current_filename:
                src = str(data.get('source_filename', '')).strip().lower()
                cur = str(current_filename).strip().lower()
                if src != cur and os.path.basename(src) != os.path.basename(cur):
                    return None
            return data
        except Exception as e:
            print(f"Error loading batch checkpoint: {e}")
            return None

    def clear_batch_checkpoint(self):
        """Menghapus checkpoint aktif setelah batch tuntas atau direset manual"""
        try:
            if os.path.exists(self.active_checkpoint_file):
                os.remove(self.active_checkpoint_file)
            return True
        except Exception as e:
            print(f"Error clearing batch checkpoint: {e}")
            return False

    def _parse_excel_for_coupons(self, filepath, source_name='', report_rel=''):
        """Membaca file report Excel lama untuk mengekstrak kupon yang pernah tercetak"""
        coupons = []
        try:
            df = pd.read_excel(filepath, header=None, dtype=str, keep_default_na=False)
            for i, row in df.iterrows():
                if str(row[0]).strip() == 'Time Stamp' and str(row[3]).strip() == 'QR':
                    sub_df = df.iloc[i+1:].copy()
                    sub_df.columns = df.iloc[i].values
                    for _, r in sub_df.iterrows():
                        ts = str(r.get('Time Stamp', '')).strip()
                        qr = str(r.get('QR', '')).strip()
                        st = str(r.get('Status', '')).strip()
                        if qr and qr != 'nan' and not qr.startswith('QR Selesai') and ts and ts != 'nan':
                            coupons.append({
                                'Coupon': qr,
                                'Timestamp': ts,
                                'Status': st,
                                'Source_File': source_name,
                                'Report_File': report_rel
                            })
        except Exception as e:
            print(f"Error parsing {filepath}: {e}")
        return coupons

    def ensure_coupon_index(self):
        """Membangun database index CSV kupon (printed_coupons_index.csv) jika belum ada"""
        if os.path.exists(self.coupon_index_file):
            return

        coupons = []
        if os.path.exists(self.history_log_file):
            try:
                sum_df = pd.read_csv(self.history_log_file, dtype=str, keep_default_na=False)
                for _, row in sum_df.iterrows():
                    p = os.path.join(self.history_dir, str(row.get('Report_File', '')))
                    if os.path.exists(p):
                        coupons.extend(self._parse_excel_for_coupons(
                            p, str(row.get('Source', '')), str(row.get('Report_File', ''))
                        ))
            except Exception as e:
                print(f"Error building coupon index: {e}")

        df_idx = pd.DataFrame(coupons, columns=['Coupon', 'Timestamp', 'Status', 'Source_File', 'Report_File'])
        df_idx.to_csv(self.coupon_index_file, index=False)

    def record_single_coupon(self, coupon, timestamp=None, status="Printed", source_file="", report_file=""):
        """Menambahkan satu kupon yang baru saja diterima printer ke database index CSV secara real-time"""
        coupon = str(coupon).strip()
        if not coupon or coupon == 'nan' or coupon.startswith('QR Selesai'):
            return

        ts = timestamp if timestamp else datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_row = pd.DataFrame([{
            'Coupon': coupon,
            'Timestamp': ts,
            'Status': status,
            'Source_File': source_file,
            'Report_File': report_file
        }])

        self.ensure_coupon_index()
        try:
            is_empty_or_new = not os.path.exists(self.coupon_index_file) or os.stat(self.coupon_index_file).st_size == 0
            new_row.to_csv(self.coupon_index_file, mode='a', header=is_empty_or_new, index=False)
        except Exception as e:
            print(f"Error recording single coupon: {e}")

    def record_printed_coupons(self, history_records, current_filename, report_relative_path):
        """Menambahkan kupon yang baru saja dicetak ke database index CSV (jika belum tercatat)"""
        if not history_records:
            return

        new_entries = []
        for r in history_records:
            qr = str(r.get('QR', '')).strip()
            ts = str(r.get('Time Stamp', '')).strip()
            st = str(r.get('Status', '')).strip()
            if qr and qr != 'nan' and not qr.startswith('QR Selesai'):
                new_entries.append({
                    'Coupon': qr,
                    'Timestamp': ts if ts else datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'Status': st,
                    'Source_File': current_filename,
                    'Report_File': report_relative_path
                })

        if not new_entries:
            return

        df_new = pd.DataFrame(new_entries, columns=['Coupon', 'Timestamp', 'Status', 'Source_File', 'Report_File'])
        self.ensure_coupon_index()
        is_empty_or_new = not os.path.exists(self.coupon_index_file) or os.stat(self.coupon_index_file).st_size == 0
        df_new.to_csv(self.coupon_index_file, mode='a', header=is_empty_or_new, index=False)

    def get_coupons_in_last_days(self, days=30):
        """
        Mendapatkan semua kupon yang pernah tercetak dalam N hari terakhir.
        Mengembalikan dictionary: { coupon_code: { 'timestamp': ..., 'source': ..., 'report': ..., 'status': ... } }
        """
        self.ensure_coupon_index()
        if not os.path.exists(self.coupon_index_file):
            return {}

        try:
            df = pd.read_csv(self.coupon_index_file, dtype=str, keep_default_na=False)
            if df.empty or 'Timestamp' not in df.columns or 'Coupon' not in df.columns:
                return {}

            df['dt'] = pd.to_datetime(df['Timestamp'], errors='coerce')
            cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
            recent_df = df[df['dt'] >= cutoff]

            result = {}
            for _, r in recent_df.iterrows():
                code = str(r['Coupon']).strip()
                if code and code != 'nan':
                    result[code] = {
                        'timestamp': str(r.get('Timestamp', '')),
                        'source': str(r.get('Source_File', '')),
                        'report': str(r.get('Report_File', '')),
                        'status': str(r.get('Status', ''))
                    }
            return result
        except Exception as e:
            print(f"Error reading coupon index: {e}")
            return {}