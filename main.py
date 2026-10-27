import os
import time
import socket
import threading
import datetime
import sys
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from collections import deque

# Library Pihak Ketiga (Hanya yang dipakai oleh UI)
from PIL import ImageTk, Image # ImageDraw & ImageFont sudah dihapus
from tkcalendar import DateEntry 
# pandas, qrcode, dan serial SUDAH DIHAPUS TOTAL dari sini!

# --- IMPORT MODUL CUSTOM KAMU ---
from analytics_server import AnalyticsServer 
from label_renderer import LabelRenderer
from printer_omega import OmegaPrinter
from modbus_io import ModbusController
from data_manager import DataManager
from auth_manager import AuthManager
from login_dialog import LoginDialog, ChangePasswordDialog
from api_manager import APIManager
# --------------------------------

def resource_path(relative_path):
    """ Mendapatkan path absolut ke resource, berfungsi untuk dev dan PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class NotebookCompat:
    """Wrapper kompatibilitas agar pemanggilan self.notebook tetap berfungsi mulus dengan sidebar kustom"""
    def __init__(self, app):
        self.app = app

    def tab(self, tab_frame, state="normal"):
        nav_id = self.app.tab_to_nav.get(tab_frame)
        if nav_id:
            hidden = getattr(self.app, '_hidden_navs', set())
            if state == "hidden":
                hidden.add(nav_id)
            else:
                hidden.discard(nav_id)
            self.app._repack_nav_buttons(hidden)

    def select(self, tab_frame=None):
        if tab_frame is None:
            return str(getattr(self.app, 'active_tab', ''))
        nav_id = self.app.tab_to_nav.get(tab_frame)
        if nav_id:
            self.app.switch_nav(nav_id)

class OmegaBatchApp:
    def __init__(self, root):
        self.renderer = LabelRenderer() # <--- TAMBAHAN BARU (Inisiasi Sang Seniman)
        self.printer = OmegaPrinter()# <--- TAMBAHAN BARU (Inisiasi Sang Eksekutor)
        self.modbus = ModbusController()
        self.data_manager = DataManager()
        self.auth_manager = AuthManager()
        self.api_manager = APIManager() # <--- Integrasi API Sistem Utama (v2.0)
        self.current_user = None
        # --- FIX IKON TASKBAR (AppUserModelID) ---
        try:
            from ctypes import windll
            # ID ini bebas, formatnya: Perusahaan.Produk.Subproduk.Versi
            myappid = 'PT_SMARTEK.OmegaMX.System.v.2.0' 
            windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            print(f"Gagal mengatur AppUserModelID: {e}")
            
        self.root = root
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.title("Omega MX - Batch Printing & Dual-QC System (v2.0 API Ready)")
        
        # ... kode iconbitmap yang sudah ada ...
        try:
            self.root.iconbitmap(resource_path("assets/omega_icon.ico"))
        except: pass
        
        # --- TAMBAHKAN KODE IKON DI SINI ---
        try:
            # Menggunakan resource_path agar file .ico ditemukan saat jadi .exe
            icon_path = resource_path("assets/omega_icon.ico")
            self.root.iconbitmap(icon_path)
        except Exception as e:
            print(f"Gagal memuat ikon jendela: {e}")
        
        # --- Window Setup ---
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Ukuran jendela responsif agar footer & logo tidak terpotong oleh taskbar Windows
        app_width = min(1250, screen_width - 20)
        app_height = min(710, screen_height - 65)
        x_pos = max(0, int((screen_width - app_width) / 2))
        y_pos = max(0, int((screen_height - 65 - app_height) / 2))
        self.root.geometry(f"{app_width}x{app_height}+{x_pos}+{y_pos}")
        
        # --- Konfigurasi Tema Windows 7 (Vista / Aero Theme & Segoe UI) ---
        self.style = ttk.Style()
        try:
            if "vista" in self.style.theme_names():
                self.style.theme_use("vista")
            elif "winnative" in self.style.theme_names():
                self.style.theme_use("winnative")
        except Exception:
            pass

        self.style.configure(".", font=("Segoe UI", 9))
        self.style.configure("TLabelframe.Label", font=("Segoe UI", 9, "bold"), foreground="#1c446c")
        self.style.configure("TNotebook.Tab", font=("Segoe UI", 9))
        self.style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        self.style.configure("Treeview", font=("Segoe UI", 9), rowheight=21)
        
        # Bersihkan log tua saat aplikasi jalan
        self.data_manager.cleanup_old_logs()
        
        # Ambil path dari Data Manager agar fungsi text log & web analytics di main.py tetap jalan
        self.history_dir = self.data_manager.history_dir
        self.log_dir = self.data_manager.log_dir
        self.history_log_file = self.data_manager.history_log_file
        
        # --- Core Variables ---
        self.df = None
        self.preview_img = None
        self.is_simulation = tk.BooleanVar(value=True) 
        self.auto_judge_sim = tk.BooleanVar(value=True) 
        self.history_filter = tk.StringVar(value="last_20") # Default Filter GUI
        self.current_filename = ""
        self.total_load_data = 0
        self.batch_start_time = ""
        
        # --- Core Variables statistik ---
        self.stat_total = tk.StringVar(value="0")
        self.stat_ok = tk.StringVar(value="0")
        self.stat_ng = tk.StringVar(value="0")
        self.stat_progress = tk.StringVar(value="0 %")
        
        # Variabel counter internal
        self.count_ok = 0
        self.count_ng = 0
        
        # --- Queue & Tracking Variables ---
        self.waiting_queue = deque() 
        self.ng_list = []            
        self.is_printing = False    
        self.batch_completed = False 
        self.history_records = []
        self.print_cycle = 1 
        self.consecutive_ng_count = 0
        self.cascade_warning_active = False 
        self.pause_requested = False
        self.max_queue_transit = 3  # Bentang 1.4 m dengan box 60 cm memuat maksimal 2-3 kardus in-transit 
        self.printer_connected = False
        self.modbus_connected = False
        self.active_tab = None
        self.active_nav = None
        self._hidden_navs = set() 
        
        # --- Hardware Connection Variables ---
        self.conn_mode = tk.StringVar(value="TCP")
        self.ip_addr = tk.StringVar(value="192.168.1.100") 
        self.ip_port = tk.StringVar(value="6007")
        self.com_port = tk.StringVar()
        self.baudrate = tk.StringVar(value="9600")
        
        # --- Dual Keyence Scanners (TCP/IP) ---
        self.scanner1_ip = tk.StringVar(value="192.168.1.99") 
        self.scanner1_port = tk.StringVar(value="9004")
        self.scanner1_socket = None
        self.is_listening1 = False
        self.last_scan_result1 = tk.StringVar(value="- Menunggu Data -")
        
        self.scanner2_ip = tk.StringVar(value="192.168.1.98") 
        self.scanner2_port = tk.StringVar(value="9004")
        self.scanner2_socket = None
        self.is_listening2 = False
        self.last_scan_result2 = tk.StringVar(value="- Menunggu Data -")
        
        # Buffer hasil scan per box untuk verifikasi 2 sisi (Sisi A & B)
        self.current_box_scans = {"side1": None, "side2": None}
        self.dual_scan_timeout_var = tk.StringVar(value="2000") # Default 2.0 detik
        self._dual_scan_timer_id = None

        # Variabel Penolakan Pneumatik & Timing Rejector (Solusi 4)
        self.ng_boxes_waiting_reject = deque()
        self.last_scanner_sensor_state = False
        self.last_sensor_fall_time = 0
        self.interlock_alarm_active = False
        self.pusher_delay_var = tk.StringVar(value="2000") # Default 2000 ms (tunda tempuh 50cm ke pusher 80cm)
        self.pusher_pulse_var = tk.StringVar(value="500")  # Default 500 ms durasi pulsa dorong solenoid DO 0

        # Variabel Checkpoint & Recovery Batch (Solusi 5)
        self.resumed_checkpoint = None
        self.checkpoint_judged_map = {}

        # Penyimpanan data baris asli sebagai teks murni (mencegah Treeview merusak leading zeroes seperti '00123')
        self.table_items_data = {}
        self.modbus_fail_count = 0
        self.modbus_alarm_active = False
        
        # Kompatibilitas Legacy
        self.scanner_ip = self.scanner1_ip 
        self.scanner_port = self.scanner1_port
        self.scanner_socket = None
        self.is_listening = False
        self.last_scan_result = self.last_scan_result1
                
        # Modbus Specific Variables TCP
        self.modbus_ip = tk.StringVar(value="127.0.0.1")
        self.modbus_port = tk.StringVar(value="502")
        # Modbus Specific Variables Serial Settings 
        self.modbus_com = tk.StringVar(value="COM1")
        self.modbus_baud = tk.StringVar(value="9600")
        self.modbus_databits = tk.StringVar(value="8")
        self.modbus_parity = tk.StringVar(value="Even")
        self.modbus_stopbits = tk.StringVar(value="1")
        self.modbus_serial_mode = tk.StringVar(value="RTU") # RTU atau ASCII
        self.slave_id = tk.IntVar(value=1)
                
        self.is_io_running = False # Flag monitoring
        
        # --- API Integration Variables (v2.0) ---
        self.api_enabled = tk.BooleanVar(value=True)
        self.api_base_url = tk.StringVar(value="http://192.168.1.50:8000/api/v1")
        self.api_key = tk.StringVar(value="")
        self.api_endpoint_work_orders = tk.StringVar(value="/work-orders/active")
        self.api_endpoint_submit_batch = tk.StringVar(value="/production/batch-summary")
        self.api_endpoint_submit_box = tk.StringVar(value="/production/qc-box")
        self.api_timeout = tk.StringVar(value="5")
        self.api_auto_sync_batch = tk.BooleanVar(value=True)
        self.api_auto_sync_box = tk.BooleanVar(value=False)
        self.api_status_text = tk.StringVar(value="○ Belum Diuji")
        self.current_work_order_id = ""
        self.active_sys_status = "READY"
        
        # --- Layout Coordinates ---
        self.coords = {
            "qr":   {"x": tk.StringVar(value="450"),   "y": tk.StringVar(value="3"),   "w": tk.StringVar(value="271"), "h": tk.StringVar(value="271")},
            "txt_kupon": {"x": tk.StringVar(value="60"), "y": tk.StringVar(value="165"), "w": tk.StringVar(value="22"), "h": tk.StringVar(value="0")},
            "sku":  {"x": tk.StringVar(value="200"), "y": tk.StringVar(value="120"),  "w": tk.StringVar(value="36"),  "h": tk.StringVar(value="0")},
            "matl": {"x": tk.StringVar(value="40"), "y": tk.StringVar(value="215"), "w": tk.StringVar(value="22"),  "h": tk.StringVar(value="0")},
            "syn":  {"x": tk.StringVar(value="310"), "y": tk.StringVar(value="40"),  "w": tk.StringVar(value="170"), "h": tk.StringVar(value="42")},
            "ben":  {"x": tk.StringVar(value="40"), "y": tk.StringVar(value="40"), "w": tk.StringVar(value="220"),  "h": tk.StringVar(value="50")},
            "nk":  {"x": tk.StringVar(value="40"), "y": tk.StringVar(value="90"), "w": tk.StringVar(value="140"),  "h": tk.StringVar(value="75")},
        }
        self.sel_qr, self.sel_sku, self.sel_matl = tk.StringVar(), tk.StringVar(), tk.StringVar()

        # Muat konfigurasi tersimpan dari data/config.json (S3)
        self.load_hardware_config()

        self.setup_ui()
        self.log_msg("Aplikasi Omega MX Designer & QC System dimulai (v2.0 API Ready).")

        # Memulai Embedded REST API & Analytics Server (Port 5022) di background thread
        self.start_api_server()

        # Sembunyikan window utama dan tampilkan Login Dialog di awal
        self.root.withdraw()
        LoginDialog(self.root, self.auth_manager, on_login_success=self.on_initial_login_success, is_switch_user=False)

    # ==========================================
    # 1. USER INTERFACE (UI) SETUP & AUTH
    # ==========================================
    def setup_ui(self):
        # --- FOOTER / STATUS BAR (Dipack lebih dulu di BOTTOM agar selalu terlihat dan tidak terdorong) ---
        footer_frame = ttk.Frame(self.root)
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(2, 6))

        # 1. Muat Logo Smartek di sebelah KIRI (Bottom-Left)
        try:
            logo_path = resource_path("assets/smartek_text.png")
            img_open = Image.open(logo_path)
            aspect_ratio = img_open.width / img_open.height
            new_height = 20
            new_width = int(new_height * aspect_ratio)
            img_resized = img_open.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            self.footer_logo = ImageTk.PhotoImage(img_resized)
            logo_label = tk.Label(footer_frame, image=self.footer_logo)
            logo_label.pack(side=tk.LEFT, padx=(0, 10)) 
        except Exception as e:
            print(f"Gagal memuat logo footer: {e}")

        # 2. Tampilkan Label Versi di sebelah logo Smartek (Kiri Bawah)
        ttk.Label(footer_frame, text="© 2026 SMARTEK SOFTWARE | Developed by WLDN | Version 2.0 API Ready", font=("Segoe UI", 8, "italic")).pack(side=tk.LEFT)

        # 3. Status Sistem & User Aktif di sebelah Kanan Bawah
        self.lbl_footer_user = ttk.Label(footer_frame, text="User: -", font=("Segoe UI", 8, "italic"), foreground="#333333")
        self.lbl_footer_user.pack(side=tk.RIGHT, padx=12)

        ttk.Label(footer_frame, text="● System Ready", font=("Segoe UI", 8, "bold"), foreground="#1e7e34").pack(side=tk.RIGHT, padx=5)

        # --- TOP HEADER BAR (Dark Slate #1e293b) ---
        self.top_bar = tk.Frame(self.root, bg="#1e293b", height=42)
        self.top_bar.pack(side=tk.TOP, fill=tk.X)

        # Subtle bottom divider
        divider_top = tk.Frame(self.root, bg="#334155", height=1)
        divider_top.pack(side=tk.TOP, fill=tk.X)

        # Brand on left
        brand_frame = tk.Frame(self.top_bar, bg="#1e293b")
        brand_frame.pack(side=tk.LEFT, padx=14, pady=5)
        tk.Label(brand_frame, text="Ω OMEGA MX", font=("Segoe UI", 11, "bold"), fg="#ffffff", bg="#1e293b").pack(side=tk.LEFT)
        tk.Label(brand_frame, text=" | Batch Printing & Dual-QC System (v2.0 API)", font=("Segoe UI", 9), fg="#94a3b8", bg="#1e293b").pack(side=tk.LEFT)

        # Live System Status Pill in Center
        self.lbl_system_status_pill = tk.Label(
            self.top_bar, text="● READY", font=("Segoe UI", 9, "bold"),
            fg="#10b981", bg="#064e3b", relief="solid", bd=1, padx=14, pady=2
        )
        self.lbl_system_status_pill.pack(side=tk.LEFT, expand=True)

        # User Profile & Action buttons on Right
        user_frame = tk.Frame(self.top_bar, bg="#1e293b")
        user_frame.pack(side=tk.RIGHT, padx=12, pady=5)

        self.lbl_user_badge = tk.Label(user_frame, text="OPERATOR", font=("Segoe UI", 8, "bold"), fg="#ffffff", bg="#1e73be",
                                       relief="solid", bd=1, highlightbackground="#0f172a", padx=10, pady=2)
        self.lbl_user_badge.pack(side=tk.LEFT, padx=5)

        btn_chg_pass = tk.Button(user_frame, text="Ganti Password", font=("Segoe UI", 8),
                                 bg="#334155", fg="#ffffff", activebackground="#475569", activeforeground="#ffffff",
                                 relief="flat", bd=0, padx=8, pady=3, cursor="hand2", command=self.open_change_password)
        btn_chg_pass.pack(side=tk.LEFT, padx=3)

        btn_logout = tk.Button(user_frame, text="Ganti User", font=("Segoe UI", 8, "bold"),
                               bg="#be123c", fg="#ffffff", activebackground="#e11d48", activeforeground="#ffffff",
                               relief="flat", bd=0, padx=10, pady=3, cursor="hand2", command=self.request_switch_user)
        btn_logout.pack(side=tk.LEFT, padx=3)

        # --- BODY CONTAINER (SIDEBAR KIRI + KONTEN UTAMA) ---
        self.body_frame = tk.Frame(self.root, bg="#f1f5f9")
        self.body_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # 1. Sidebar Kiri (Navigasi & Hardware Indicators)
        self.sidebar_frame = tk.Frame(self.body_frame, bg="#1e293b", width=168)
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar_frame.pack_propagate(False)

        # 2. Kontainer Konten (Stack Frame dengan Grid)
        self.content_container = tk.Frame(self.body_frame, bg="#f1f5f9")
        self.content_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.content_container.rowconfigure(0, weight=1)
        self.content_container.columnconfigure(0, weight=1)

        # 4 Tab Halaman
        self.tab_main = tk.Frame(self.content_container, bg="#f1f5f9")
        self.tab_history = tk.Frame(self.content_container, bg="#f1f5f9", padx=10, pady=8)
        self.tab_connectivity = tk.Frame(self.content_container, bg="#f1f5f9", padx=10, pady=8)
        self.tab_logs = tk.Frame(self.content_container, bg="#f1f5f9", padx=10, pady=8)

        for tab in (self.tab_main, self.tab_history, self.tab_connectivity, self.tab_logs):
            tab.grid(row=0, column=0, sticky="nsew")

        # Inisialisasi Navigasi Sidebar
        self.nav_items_order = ["main", "history", "conn", "logs"]
        self.nav_tab_map = {
            "main": self.tab_main,
            "history": self.tab_history,
            "conn": self.tab_connectivity,
            "logs": self.tab_logs
        }
        self.tab_to_nav = {v: k for k, v in self.nav_tab_map.items()}
        self.nav_btns = {}

        nav_labels = [
            ("main", "🖶  Operasi Cetak"),
            ("history", "🕒  Riwayat Cetak"),
            ("conn", "⚙  Koneksi"),
            ("logs", "📋  Log Aktivitas")
        ]

        self.f_nav_list = tk.Frame(self.sidebar_frame, bg="#1e293b")
        self.f_nav_list.pack(side=tk.TOP, fill=tk.X, pady=(6, 0))

        for nid, title in nav_labels:
            btn = tk.Label(self.f_nav_list, text=title, font=("Segoe UI", 9),
                           fg="#94a3b8", bg="#1e293b", anchor="w", padx=14, pady=10, cursor="hand2")
            btn.bind("<Button-1>", lambda e, n=nid: self.switch_nav(n))
            btn.bind("<Enter>", lambda e, n=nid: self._on_nav_hover(n, True))
            btn.bind("<Leave>", lambda e, n=nid: self._on_nav_hover(n, False))
            self.nav_btns[nid] = btn

        self._repack_nav_buttons()

        # Panel Status Hardware di Bagian Bawah Sidebar
        f_hw = tk.Frame(self.sidebar_frame, bg="#0f172a", padx=10, pady=10)
        f_hw.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Label(f_hw, text="STATUS HARDWARE", font=("Segoe UI", 7, "bold"), fg="#64748b", bg="#0f172a").pack(anchor="w", pady=(0, 4))

        # Hardware indicator rows
        r_p = tk.Frame(f_hw, bg="#0f172a"); r_p.pack(fill=tk.X, pady=1)
        self.lbl_hw_printer = tk.Label(r_p, text="●", font=("Segoe UI", 9), fg="#64748b", bg="#0f172a")
        self.lbl_hw_printer.pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(r_p, text="Printer Omega", font=("Segoe UI", 8), fg="#cbd5e1", bg="#0f172a").pack(side=tk.LEFT)

        r_s1 = tk.Frame(f_hw, bg="#0f172a"); r_s1.pack(fill=tk.X, pady=1)
        self.lbl_hw_scanner1 = tk.Label(r_s1, text="●", font=("Segoe UI", 9), fg="#ef4444", bg="#0f172a")
        self.lbl_hw_scanner1.pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(r_s1, text="Scanner Sisi A", font=("Segoe UI", 8), fg="#cbd5e1", bg="#0f172a").pack(side=tk.LEFT)

        r_s2 = tk.Frame(f_hw, bg="#0f172a"); r_s2.pack(fill=tk.X, pady=1)
        self.lbl_hw_scanner2 = tk.Label(r_s2, text="●", font=("Segoe UI", 9), fg="#ef4444", bg="#0f172a")
        self.lbl_hw_scanner2.pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(r_s2, text="Scanner Sisi B", font=("Segoe UI", 8), fg="#cbd5e1", bg="#0f172a").pack(side=tk.LEFT)

        r_m = tk.Frame(f_hw, bg="#0f172a"); r_m.pack(fill=tk.X, pady=1)
        self.lbl_hw_modbus = tk.Label(r_m, text="●", font=("Segoe UI", 9), fg="#64748b", bg="#0f172a")
        self.lbl_hw_modbus.pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(r_m, text="Modbus I/O", font=("Segoe UI", 8), fg="#cbd5e1", bg="#0f172a").pack(side=tk.LEFT)

        r_api = tk.Frame(f_hw, bg="#0f172a"); r_api.pack(fill=tk.X, pady=1)
        self.lbl_hw_api = tk.Label(r_api, text="●", font=("Segoe UI", 9), fg="#10b981", bg="#0f172a")
        self.lbl_hw_api.pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(r_api, text="API Sistem Utama", font=("Segoe UI", 8), fg="#cbd5e1", bg="#0f172a").pack(side=tk.LEFT)

        tk.Label(f_hw, text="v2.0 API Ready", font=("Segoe UI", 7), fg="#475569", bg="#0f172a").pack(anchor="w", pady=(6, 0))

        # Objek Kompatibilitas Notebook
        self.notebook = NotebookCompat(self)
        self.switch_nav("main")

        self.build_logs_tab()
        self.build_main_tab()
        self.build_history_tab()
        self.build_connectivity_tab()
        self.load_hardware_config()
        self.update_hardware_indicators()

    def switch_nav(self, nav_id):
        """Beralih tab halaman melalui klik tombol navigasi sidebar"""
        if nav_id not in self.nav_tab_map:
            return
        self.active_nav = nav_id
        target_tab = self.nav_tab_map[nav_id]
        target_tab.tkraise()
        self.active_tab = target_tab

        for nid, btn in self.nav_btns.items():
            if nid == nav_id:
                btn.config(bg="#334155", fg="#ffffff", font=("Segoe UI", 9, "bold"))
            else:
                btn.config(bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 9, "normal"))

        if nav_id == "history":
            self.load_history_table()

    def _on_nav_hover(self, nav_id, is_enter):
        """Efek hover kursor pada navigasi sidebar"""
        btn = self.nav_btns.get(nav_id)
        if not btn:
            return
        if nav_id == getattr(self, 'active_nav', None):
            return
        if is_enter:
            btn.config(bg="#2d3748", fg="#ffffff")
        else:
            btn.config(bg="#1e293b", fg="#94a3b8")

    def _repack_nav_buttons(self, hidden_keys=None):
        """Menyusun ulang tombol navigasi sesuai hak akses peran"""
        if hidden_keys is None:
            hidden_keys = getattr(self, '_hidden_navs', set())
        else:
            self._hidden_navs = hidden_keys

        for nid in self.nav_items_order:
            btn = self.nav_btns.get(nid)
            if btn:
                if nid in hidden_keys:
                    btn.pack_forget()
                else:
                    btn.pack(fill=tk.X, pady=1)

    def set_system_status(self, status):
        """Update indikator pill status sistem di bagian tengah top bar secara thread-safe"""
        self.active_sys_status = status.upper()
        def _apply():
            if not hasattr(self, 'lbl_system_status_pill'):
                return
            s = status.upper()
            if s == "RUNNING":
                self.lbl_system_status_pill.config(text="● RUNNING", fg="#34d399", bg="#064e3b")
            elif s == "PAUSED":
                self.lbl_system_status_pill.config(text="❚❚ PAUSED", fg="#fbbf24", bg="#78350f")
            elif s == "STOPPED":
                self.lbl_system_status_pill.config(text="■ STOPPED", fg="#94a3b8", bg="#334155")
            elif s == "ALARM":
                self.lbl_system_status_pill.config(text="▲ ALARM", fg="#f87171", bg="#7f1d1d")
            else:
                self.lbl_system_status_pill.config(text="● READY", fg="#10b981", bg="#064e3b")
        if threading.current_thread() is threading.main_thread():
            _apply()
        else:
            try:
                self.root.after(0, _apply)
            except Exception:
                pass

    def update_hardware_indicators(self):
        """Update live status dot hardware & API di sidebar secara thread-safe"""
        def _upd():
            # Scanner 1
            if hasattr(self, 'lbl_hw_scanner1'):
                col1 = "#10b981" if getattr(self, 'is_listening1', False) else "#ef4444"
                self.lbl_hw_scanner1.config(fg=col1)
            # Scanner 2
            if hasattr(self, 'lbl_hw_scanner2'):
                col2 = "#10b981" if getattr(self, 'is_listening2', False) else "#ef4444"
                self.lbl_hw_scanner2.config(fg=col2)
            # Printer
            if hasattr(self, 'lbl_hw_printer'):
                is_sim = getattr(self, 'is_simulation', None) and self.is_simulation.get()
                is_conn = getattr(self, 'printer_connected', False)
                col_p = "#10b981" if (is_sim or is_conn) else "#64748b"
                self.lbl_hw_printer.config(fg=col_p)
            # Modbus
            if hasattr(self, 'lbl_hw_modbus'):
                col_m = "#10b981" if getattr(self, 'modbus_connected', False) else "#64748b"
                self.lbl_hw_modbus.config(fg=col_m)
            # API Sistem Utama
            if hasattr(self, 'lbl_hw_api'):
                if not getattr(self, 'api_enabled', None) or not self.api_enabled.get():
                    col_api = "#64748b" # Abu-abu jika non-aktif
                elif getattr(self.api_manager, 'is_connected', False):
                    col_api = "#10b981" # Hijau jika online
                else:
                    col_api = "#f59e0b" # Kuning jika aktif tapi belum/sedang dicek
                self.lbl_hw_api.config(fg=col_api)
        if threading.current_thread() is threading.main_thread():
            _upd()
        else:
            try:
                self.root.after(0, _upd)
            except Exception:
                pass

    # ==========================================
    # MANAJEMEN OTORITAS & SESI USER
    # ==========================================
    def apply_user_permissions(self):
        """Menerapkan batasan otoritas berdasarkan peran (Admin vs Operator)"""
        if not self.current_user:
            return

        role = self.current_user.get("role", "operator")
        username = self.current_user.get("username", "operator")
        name = self.current_user.get("name", username)

        # 1. Update Judul Jendela & Header Badge
        if role == "admin":
            badge_text = f"ADMIN: {name}"
            badge_bg = "#d97706"
            self.root.title(f"Omega MX - Batch Printing & QC System [ADMINISTRATOR - {name}]")
        else:
            badge_text = f"OPERATOR: {name}"
            badge_bg = "#1e73be"
            self.root.title(f"Omega MX - Batch Printing & QC System [OPERATOR - {name}]")

        if hasattr(self, 'lbl_user_badge'):
            self.lbl_user_badge.config(text=badge_text, bg=badge_bg)

        if hasattr(self, 'lbl_footer_user'):
            self.lbl_footer_user.config(text=f"User: {name} ({role.upper()})")

        # 2. Otoritas Tab & Fitur
        if role == "operator":
            # Sembunyikan Tab Connectivity Settings untuk Operator
            try:
                self.notebook.tab(self.tab_connectivity, state="hidden")
            except Exception as e:
                print(f"Error hiding connectivity tab: {e}")

            # Kunci Mode Simulasi (Operator wajib mode Hardware Produksi)
            if hasattr(self, 'chk_simulation'):
                self.is_simulation.set(False)
                self.chk_simulation.config(state="disabled")
            if hasattr(self, 'chk_auto_judge'):
                self.chk_auto_judge.config(state="disabled")

            # Sembunyikan Card Simulator (Hanya untuk Admin / Dev)
            if hasattr(self, 'card_sim'):
                self.card_sim.pack_forget()

            # Jika saat ini berada di tab Connectivity, kembalikan ke tab Print Operation
            try:
                if str(getattr(self, 'active_tab', '')) == str(self.tab_connectivity):
                    self.switch_nav("main")
            except Exception:
                pass

        else: # Role == 'admin'
            # Tampilkan kembali Tab Connectivity Settings untuk Admin
            try:
                self.notebook.tab(self.tab_connectivity, state="normal")
            except Exception as e:
                print(f"Error showing connectivity tab: {e}")

            # Buka kunci Mode Simulasi
            if hasattr(self, 'chk_simulation'):
                self.chk_simulation.config(state="normal")
            if hasattr(self, 'chk_auto_judge'):
                self.chk_auto_judge.config(state="normal")

            # Tampilkan kembali Card Simulator jika belum terpasang
            if hasattr(self, 'card_sim') and not self.card_sim.winfo_manager():
                self.card_sim.pack(fill=tk.X, pady=(4, 0))

    def on_initial_login_success(self, user_info):
        """Dipanggil saat login awal berhasil"""
        self.current_user = user_info
        self.apply_user_permissions()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.log_msg(f"[AUTH] Login berhasil sebagai '{user_info.get('username')}' ({user_info.get('role').upper()}).")

    def request_switch_user(self):
        """Meminta ganti akun / switch user saat aplikasi berjalan"""
        if self.is_printing:
            messagebox.showwarning(
                "Peringatan",
                "Proses Batch Printing sedang berjalan!\nHarap hentikan (STOP) Batch sebelum ganti user.",
                parent=self.root
            )
            return

        LoginDialog(self.root, self.auth_manager, on_login_success=self.on_switch_user_success, is_switch_user=True)

    def on_switch_user_success(self, user_info):
        """Dipanggil saat switch user berhasil"""
        prev_user = self.current_user.get("username", "Unknown") if self.current_user else "Unknown"
        self.current_user = user_info
        self.apply_user_permissions()
        self.log_msg(f"[AUTH] Pengguna berganti dari '{prev_user}' ke '{user_info.get('username')}' ({user_info.get('role').upper()}).")

    def open_change_password(self):
        """Membuka dialog ubah password"""
        if not self.current_user:
            return
        ChangePasswordDialog(self.root, self.auth_manager, self.current_user)

    def build_main_tab(self):
        """Membangun tab Operasi Cetak dengan layout 2 kolom: Kiri (Data & Tabel) | Kanan (Metrik & Kontrol)"""
        # Container 2 Kolom
        main_panes = tk.Frame(self.tab_main, bg="#f1f5f9", padx=10, pady=8)
        main_panes.pack(fill=tk.BOTH, expand=True)

        # ==========================================
        # KOLOM KIRI: SUMBER DATA & TABEL UTAMA
        # ==========================================
        left_pane = tk.Frame(main_panes, bg="#f1f5f9")
        left_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        # Card 1: Sumber Data & Pemetaan Kolom
        card_src = tk.Frame(left_pane, bg="#ffffff", relief="solid", bd=1, highlightbackground="#cbd5e1", padx=10, pady=7)
        card_src.pack(fill=tk.X, pady=(0, 6))

        tk.Label(card_src, text="Sumber Data", font=("Segoe UI", 9, "bold"), fg="#1e293b", bg="#ffffff").pack(side=tk.LEFT, padx=(0, 8))
        
        btn_load = tk.Button(card_src, text="📂 Load File", font=("Segoe UI", 8, "bold"),
                             bg="#f8fafc", fg="#1e293b", relief="solid", bd=1, padx=8, pady=3,
                             cursor="hand2", command=self.load_file)
        btn_load.pack(side=tk.LEFT, padx=(0, 4))

        btn_api = tk.Button(card_src, text="☁ Tarik API", font=("Segoe UI", 8, "bold"),
                            bg="#eff6ff", fg="#1d4ed8", activebackground="#dbeafe", activeforeground="#1e40af",
                            relief="solid", bd=1, highlightbackground="#93c5fd", padx=8, pady=3,
                            cursor="hand2", command=self.open_fetch_api_dialog)
        btn_api.pack(side=tk.LEFT, padx=(0, 8))

        self.lbl_file_chip = tk.Label(card_src, text="Belum ada data dipilih", font=("Segoe UI", 8),
                                      fg="#0f766e", bg="#ccfbf1", relief="solid", bd=1, padx=8, pady=2)
        self.lbl_file_chip.pack(side=tk.LEFT, padx=(0, 10))

        # Dropdowns Mapping
        tk.Label(card_src, text="SKU:", font=("Segoe UI", 8), fg="#64748b", bg="#ffffff").pack(side=tk.LEFT, padx=(4, 2))
        self.cb_sku = ttk.Combobox(card_src, textvariable=self.sel_sku, state="readonly", width=11)
        self.cb_sku.pack(side=tk.LEFT, padx=(0, 4))

        tk.Label(card_src, text="QR:", font=("Segoe UI", 8), fg="#64748b", bg="#ffffff").pack(side=tk.LEFT, padx=(4, 2))
        self.cb_qr = ttk.Combobox(card_src, textvariable=self.sel_qr, state="readonly", width=11)
        self.cb_qr.pack(side=tk.LEFT, padx=(0, 4))

        tk.Label(card_src, text="Matl:", font=("Segoe UI", 8), fg="#64748b", bg="#ffffff").pack(side=tk.LEFT, padx=(4, 2))
        self.cb_matl = ttk.Combobox(card_src, textvariable=self.sel_matl, state="readonly", width=11)
        self.cb_matl.pack(side=tk.LEFT, padx=(0, 4))

        btn_apply = tk.Button(card_src, text="Apply", font=("Segoe UI", 8, "bold"),
                              bg="#f8fafc", fg="#1e293b", relief="solid", bd=1, padx=8, pady=2,
                              cursor="hand2", command=self.update_table)
        btn_apply.pack(side=tk.LEFT, padx=6)

        # Tombol Web Analytics di sisi kanan atas
        self.btn_web_ana = tk.Button(card_src, text="Web Analytics ↗", font=("Segoe UI", 8, "bold"),
                                     bg="#eff6ff", fg="#2563eb", activebackground="#dbeafe", activeforeground="#1d4ed8",
                                     relief="solid", bd=1, highlightbackground="#bfdbfe", padx=10, pady=2,
                                     cursor="hand2", command=self.open_web_analytics)
        self.btn_web_ana.pack(side=tk.RIGHT)

        # Card 2: Tabel Data Full-Width dengan Scrollbar
        card_table = tk.Frame(left_pane, bg="#ffffff", relief="solid", bd=1, highlightbackground="#cbd5e1")
        card_table.pack(fill=tk.BOTH, expand=True)

        cols = ("no", "sku", "kupon", "matl", "status")
        self.tree = ttk.Treeview(card_table, columns=cols, show='headings', height=12)
        self.tree.heading("no", text="No.")
        self.tree.heading("sku", text="Product SKU")
        self.tree.heading("kupon", text="Coupon QR")
        self.tree.heading("matl", text="Material Code")
        self.tree.heading("status", text="Status")
        self.tree.column("no", width=45, anchor=tk.CENTER)
        self.tree.column("sku", width=190)
        self.tree.column("kupon", width=260)
        self.tree.column("matl", width=160)
        self.tree.column("status", width=140, anchor=tk.CENTER)

        sb_tree = ttk.Scrollbar(card_table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb_tree.set)
        sb_tree.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree.tag_configure('waiting', background='#fffbeb', foreground='#92400e')
        self.tree.tag_configure('ok', background='#f0fdf4', foreground='#166534')
        self.tree.tag_configure('ng', background='#fef2f2', foreground='#991b1b')
        self.tree.tag_configure('duplicate', background='#fff1f2', foreground='#9f1239')

        # ==========================================
        # KOLOM KANAN: METRIK, GAUGE & KONTROL BATCH
        # ==========================================
        right_pane = tk.Frame(main_panes, bg="#f1f5f9", width=310)
        right_pane.pack(side=tk.RIGHT, fill=tk.Y)
        right_pane.pack_propagate(False)

        # Card 1: Batch Progress Ring Gauge
        card_progress = tk.Frame(right_pane, bg="#ffffff", relief="solid", bd=1, highlightbackground="#cbd5e1", padx=8, pady=6)
        card_progress.pack(fill=tk.X, pady=(0, 6))
        tk.Label(card_progress, text="Progres Batch", font=("Segoe UI", 9, "bold"), fg="#1e293b", bg="#ffffff").pack(anchor="w")

        self.canvas_gauge = tk.Canvas(card_progress, width=280, height=95, bg="#ffffff", highlightthickness=0)
        self.canvas_gauge.pack()
        self.draw_progress_gauge(0, 0, 0)

        # Card 2: Counters OK / NG (Side by Side)
        card_counters = tk.Frame(right_pane, bg="#f1f5f9")
        card_counters.pack(fill=tk.X, pady=(0, 6))

        card_ok = tk.Frame(card_counters, bg="#f0fdf4", relief="solid", bd=1, highlightbackground="#86efac", padx=8, pady=6)
        card_ok.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(0, 3))
        tk.Label(card_ok, text="TOTAL OK", font=("Segoe UI", 8, "bold"), fg="#15803d", bg="#f0fdf4").pack()
        tk.Label(card_ok, textvariable=self.stat_ok, font=("Segoe UI", 20, "bold"), fg="#16a34a", bg="#f0fdf4").pack()

        card_ng = tk.Frame(card_counters, bg="#fef2f2", relief="solid", bd=1, highlightbackground="#fca5a5", padx=8, pady=6)
        card_ng.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=(3, 0))
        tk.Label(card_ng, text="TOTAL NG", font=("Segoe UI", 8, "bold"), fg="#b91c1c", bg="#fef2f2").pack()
        tk.Label(card_ng, textvariable=self.stat_ng, font=("Segoe UI", 20, "bold"), fg="#dc2626", bg="#fef2f2").pack()

        # Card 3: Visualisasi Antrean Konveyor In-Transit
        card_queue = tk.Frame(right_pane, bg="#ffffff", relief="solid", bd=1, highlightbackground="#cbd5e1", padx=8, pady=6)
        card_queue.pack(fill=tk.X, pady=(0, 6))

        f_q_header = tk.Frame(card_queue, bg="#ffffff")
        f_q_header.pack(fill=tk.X)
        tk.Label(f_q_header, text="Antrean Konveyor", font=("Segoe UI", 9, "bold"), fg="#1e293b", bg="#ffffff").pack(side=tk.LEFT)
        self.lbl_queue_count = tk.Label(f_q_header, text="In Transit: 0 Box", font=("Segoe UI", 8, "bold"), fg="#b45309", bg="#fef3c7", padx=6, pady=1)
        self.lbl_queue_count.pack(side=tk.RIGHT)

        self.canvas_conveyor = tk.Canvas(card_queue, width=280, height=52, bg="#ffffff", highlightthickness=0)
        self.canvas_conveyor.pack(pady=(4, 0))
        self.draw_conveyor(0)

        # Card 4: Tombol Aksi Batch Utama
        card_action = tk.Frame(right_pane, bg="#ffffff", relief="solid", bd=1, highlightbackground="#cbd5e1", padx=8, pady=8)
        card_action.pack(fill=tk.X, pady=(0, 6))

        self.btn_batch_print = tk.Button(card_action, text="▶  MULAI CETAK (BATCH)",
                                         font=("Segoe UI", 10, "bold"), bg="#16a34a", fg="#ffffff",
                                         activebackground="#15803d", activeforeground="#ffffff",
                                         relief="flat", bd=0, pady=8, cursor="hand2",
                                         command=self.run_batch_print)
        self.btn_batch_print.pack(fill=tk.X, pady=(0, 6))

        f_action_sub = tk.Frame(card_action, bg="#ffffff")
        f_action_sub.pack(fill=tk.X)

        self.btn_pause_print = tk.Button(f_action_sub, text="❚❚  JEDA",
                                         font=("Segoe UI", 9, "bold"), bg="#d97706", fg="#ffffff",
                                         activebackground="#b45309", activeforeground="#ffffff",
                                         relief="flat", bd=0, pady=6, cursor="hand2",
                                         command=self.toggle_pause_batch, state="disabled")
        self.btn_pause_print.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 3))

        self.btn_stop_print = tk.Button(f_action_sub, text="■  STOP",
                                        font=("Segoe UI", 9, "bold"), bg="#dc2626", fg="#ffffff",
                                        activebackground="#b91c1c", activeforeground="#ffffff",
                                        relief="flat", bd=0, pady=6, cursor="hand2",
                                        command=self.stop_batch_print, state="disabled")
        self.btn_stop_print.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(3, 0))

        # Card 5: Alat Simulasi & Koreksi Antrean (Admin Only - Collapsible)
        self.card_sim = tk.Frame(right_pane, bg="#ffffff", relief="solid", bd=1, highlightbackground="#cbd5e1", padx=8, pady=6)
        self.card_sim.pack(fill=tk.X)

        self.sim_expanded = False
        self.btn_toggle_sim = tk.Button(self.card_sim, text="▸ Alat Simulasi & Koreksi (Admin)",
                                        font=("Segoe UI", 8), fg="#475569", bg="#ffffff",
                                        relief="flat", bd=0, anchor="w", cursor="hand2",
                                        command=self.toggle_sim_panel)
        self.btn_toggle_sim.pack(fill=tk.X)

        self.f_sim_body = tk.Frame(self.card_sim, bg="#ffffff", pady=4)

        self.chk_simulation = ttk.Checkbutton(self.f_sim_body, text="Simulasi Mode (No Hardware)", variable=self.is_simulation)
        self.chk_simulation.pack(anchor="w", pady=2)

        self.chk_auto_judge = ttk.Checkbutton(self.f_sim_body, text="Auto-Scan QC (Lolos Otomatis)", variable=self.auto_judge_sim)
        self.chk_auto_judge.pack(anchor="w", pady=2)

        self.btn_resync_queue = ttk.Button(self.f_sim_body, text="Koreksi Antrean (-1)", command=self.manual_resync_queue)
        self.btn_resync_queue.pack(fill=tk.X, pady=2)

        f_j = tk.Frame(self.f_sim_body, bg="#ffffff")
        f_j.pack(fill=tk.X, pady=2)
        self.btn_judge_ok = ttk.Button(f_j, text="JUDGE OK", command=lambda: self.simulate_judge(True))
        self.btn_judge_ok.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.btn_judge_ng = ttk.Button(f_j, text="JUDGE NG", command=lambda: self.simulate_judge(False))
        self.btn_judge_ng.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(2, 0))

    def toggle_sim_panel(self):
        """Buka / tutup panel alat simulasi & koreksi admin"""
        if getattr(self, 'sim_expanded', False):
            self.f_sim_body.pack_forget()
            self.btn_toggle_sim.config(text="▸ Alat Simulasi & Koreksi (Admin)")
            self.sim_expanded = False
        else:
            self.f_sim_body.pack(fill=tk.X, pady=(4, 0))
            self.btn_toggle_sim.config(text="▾ Alat Simulasi & Koreksi (Admin)")
            self.sim_expanded = True

    def draw_progress_gauge(self, processed, total, percent):
        """Menggambar visualisasi arc ring gauge progres batch secara responsif"""
        if not hasattr(self, 'canvas_gauge'):
            return
        c = self.canvas_gauge
        c.delete("all")
        bbox = (30, 10, 150, 130)
        c.create_arc(bbox, start=180, extent=-180, style="arc", outline="#e2e8f0", width=12)
        extent = -180 * (min(max(percent, 0), 100) / 100.0)
        c.create_arc(bbox, start=180, extent=extent, style="arc", outline="#2563eb", width=12)

        c.create_text(90, 58, text=f"{percent}%", font=("Segoe UI", 16, "bold"), fill="#1e293b")
        c.create_text(90, 78, text="PROGRESS", font=("Segoe UI", 7, "bold"), fill="#64748b")

        c.create_text(215, 30, text=f"{processed} / {total}", font=("Segoe UI", 13, "bold"), fill="#1e293b")
        c.create_text(215, 48, text="Kardus Selesai", font=("Segoe UI", 8), fill="#64748b")
        remaining = max(0, total - processed)
        c.create_text(215, 68, text=f"Sisa: {remaining}", font=("Segoe UI", 9, "bold"), fill="#0f766e")

    def draw_conveyor(self, count):
        """Menggambar visualisasi lintasan konveyor dan kardus in-transit"""
        if not hasattr(self, 'canvas_conveyor'):
            return
        c = self.canvas_conveyor
        c.delete("all")
        c.create_line(20, 26, 260, 26, fill="#94a3b8", width=4)
        for rx in (20, 60, 100, 140, 180, 220, 260):
            c.create_oval(rx-4, 23, rx+4, 31, fill="#cbd5e1", outline="#64748b")

        c.create_text(50, 42, text="Head Print", font=("Segoe UI", 7), fill="#64748b")
        c.create_text(140, 42, text="Dual Scanner", font=("Segoe UI", 7), fill="#64748b")
        c.create_text(230, 42, text="Pusher (DO0)", font=("Segoe UI", 7), fill="#64748b")

        stations = [(50, 14), (140, 14), (230, 14)]
        for i in range(min(count, 3)):
            bx, by = stations[i]
            c.create_rectangle(bx-14, by-10, bx+14, by+10, fill="#f59e0b", outline="#b45309", width=1)
            c.create_text(bx, by, text="BOX", font=("Segoe UI", 7, "bold"), fill="#ffffff")

    def build_history_tab(self):
        title_frame = ttk.Frame(self.tab_history)
        title_frame.pack(fill=tk.X, pady=5)
        ttk.Label(title_frame, text="Daftar Histori Batch Printing", font=("Segoe UI", 11, "bold"), foreground="#1c446c").pack(side=tk.LEFT)
        
        # --- UI FILTER KALENDER ---
        filter_frame = ttk.LabelFrame(self.tab_history, text=" Filter Tampilan Data ", padding="5")
        filter_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(filter_frame, text="20 Data Terakhir", variable=self.history_filter, value="last_20", command=self.toggle_date_filter).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(filter_frame, text="Berdasarkan Tanggal:", variable=self.history_filter, value="by_date", command=self.toggle_date_filter).pack(side=tk.LEFT, padx=10)
        
        # Widget Kalender (Default disabled sampai Radio by_date dipilih)
        self.cal_start = DateEntry(filter_frame, width=12, background='#1c446c', foreground='white', borderwidth=2, date_pattern='y-mm-dd', state='disabled', font=("Segoe UI", 9))
        self.cal_start.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(filter_frame, text=" s/d ").pack(side=tk.LEFT)
        
        self.cal_end = DateEntry(filter_frame, width=12, background='#1c446c', foreground='white', borderwidth=2, date_pattern='y-mm-dd', state='disabled', font=("Segoe UI", 9))
        self.cal_end.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(filter_frame, text="Tampilkan", command=self.load_history_table).pack(side=tk.LEFT, padx=15)

        # --- TOMBOL AKSI HISTORI (Dipack BOTTOM terlebih dahulu) ---
        btn_frame = ttk.Frame(self.tab_history)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(4, 2))
        ttk.Button(btn_frame, text="BUKA FILE EXCEL TERPILIH", command=self.open_selected_history).pack(side=tk.RIGHT)

        # --- TABEL DATA HISTORI ---
        self.hist_tree = ttk.Treeview(self.tab_history, 
                                      columns=("waktu_mulai", "waktu_selesai", "durasi", "file_src", "load", "total_print", "ng_level", "file_rep"), 
                                      displaycolumns=("waktu_mulai", "waktu_selesai", "durasi", "file_src", "load", "total_print", "ng_level"),
                                      show='headings', height=10)
                                      
        self.hist_tree.heading("waktu_mulai", text="Waktu Mulai")
        self.hist_tree.heading("waktu_selesai", text="Waktu Selesai")
        self.hist_tree.heading("durasi", text="Durasi Waktu")
        self.hist_tree.heading("file_src", text="Source Data Excel")
        self.hist_tree.heading("load", text="Total Data")
        self.hist_tree.heading("total_print", text="Total Print")
        self.hist_tree.heading("ng_level", text="NG Level")
        
        self.hist_tree.column("waktu_mulai", width=140, anchor=tk.CENTER)
        self.hist_tree.column("waktu_selesai", width=140, anchor=tk.CENTER)
        self.hist_tree.column("durasi", width=100, anchor=tk.CENTER)
        self.hist_tree.column("file_src", width=250)
        self.hist_tree.column("load", width=90, anchor=tk.CENTER)
        self.hist_tree.column("total_print", width=90, anchor=tk.CENTER)
        self.hist_tree.column("ng_level", width=90, anchor=tk.CENTER)
        
        self.hist_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(4, 4))
        
        self.load_history_table()

            
    def load_hardware_config(self):
        """Memuat konfigurasi hardware & API yang tersimpan dari data/config.json (S3)"""
        cfg = self.data_manager.load_config()
        if not cfg:
            return
        try:
            # Printer
            if "printer_ip" in cfg: self.ip_addr.set(cfg["printer_ip"])
            if "printer_port" in cfg: self.ip_port.set(cfg["printer_port"])
            if "com_port" in cfg: self.com_port.set(cfg["com_port"])
            if "baudrate" in cfg: self.baudrate.set(cfg["baudrate"])
            
            # Scanners
            if "scanner1_ip" in cfg: self.scanner1_ip.set(cfg["scanner1_ip"])
            if "scanner1_port" in cfg: self.scanner1_port.set(cfg["scanner1_port"])
            if "scanner2_ip" in cfg: self.scanner2_ip.set(cfg["scanner2_ip"])
            if "scanner2_port" in cfg: self.scanner2_port.set(cfg["scanner2_port"])
            if "dual_scan_timeout" in cfg: self.dual_scan_timeout_var.set(str(cfg["dual_scan_timeout"]))
            
            # Pusher / Rejector
            if "pusher_delay" in cfg: self.pusher_delay_var.set(str(cfg["pusher_delay"]))
            if "pusher_pulse" in cfg: self.pusher_pulse_var.set(str(cfg["pusher_pulse"]))
            
            # Modbus
            if "modbus_mode" in cfg and hasattr(self, 'modbus_mode'):
                self.modbus_mode.set(cfg["modbus_mode"])
                self.on_modbus_mode_change(None)
            if "modbus_ip" in cfg: self.modbus_ip.set(cfg["modbus_ip"])
            if "modbus_port" in cfg: self.modbus_port.set(cfg["modbus_port"])
            if "modbus_com" in cfg: self.modbus_com.set(cfg["modbus_com"])
            if "modbus_baud" in cfg: self.modbus_baud.set(cfg["modbus_baud"])
            if "modbus_databits" in cfg: self.modbus_databits.set(cfg["modbus_databits"])
            if "modbus_parity" in cfg: self.modbus_parity.set(cfg["modbus_parity"])
            if "modbus_stopbits" in cfg: self.modbus_stopbits.set(cfg["modbus_stopbits"])
            if "modbus_serial_mode" in cfg: self.modbus_serial_mode.set(cfg["modbus_serial_mode"])
            if "slave_id" in cfg: self.slave_id.set(int(cfg["slave_id"]))

            # API Sistem Utama (v2.0)
            if "api_enabled" in cfg: self.api_enabled.set(bool(cfg["api_enabled"]))
            if "api_base_url" in cfg: self.api_base_url.set(str(cfg["api_base_url"]))
            if "api_key" in cfg: self.api_key.set(str(cfg["api_key"]))
            if "api_endpoint_work_orders" in cfg: self.api_endpoint_work_orders.set(str(cfg["api_endpoint_work_orders"]))
            if "api_endpoint_submit_batch" in cfg: self.api_endpoint_submit_batch.set(str(cfg["api_endpoint_submit_batch"]))
            if "api_endpoint_submit_box" in cfg: self.api_endpoint_submit_box.set(str(cfg["api_endpoint_submit_box"]))
            if "api_timeout" in cfg: self.api_timeout.set(str(cfg["api_timeout"]))
            if "api_auto_sync_batch" in cfg: self.api_auto_sync_batch.set(bool(cfg["api_auto_sync_batch"]))
            if "api_auto_sync_box" in cfg: self.api_auto_sync_box.set(bool(cfg["api_auto_sync_box"]))
            if hasattr(self, 'api_manager'):
                self.api_manager.update_config(cfg)
        except Exception as e:
            print(f"Error applying config: {e}")

    def save_hardware_config(self, show_msg=False):
        """Menyimpan konfigurasi hardware & API ke data/config.json (S3)"""
        cfg = {
            "printer_ip": self.ip_addr.get(),
            "printer_port": self.ip_port.get(),
            "com_port": self.com_port.get(),
            "baudrate": self.baudrate.get(),
            "scanner1_ip": self.scanner1_ip.get(),
            "scanner1_port": self.scanner1_port.get(),
            "scanner2_ip": self.scanner2_ip.get(),
            "scanner2_port": self.scanner2_port.get(),
            "dual_scan_timeout": self.dual_scan_timeout_var.get(),
            "pusher_delay": self.pusher_delay_var.get(),
            "pusher_pulse": self.pusher_pulse_var.get(),
            "modbus_mode": self.modbus_mode.get() if hasattr(self, 'modbus_mode') else "TCP",
            "modbus_ip": self.modbus_ip.get(),
            "modbus_port": self.modbus_port.get(),
            "modbus_com": self.modbus_com.get(),
            "modbus_baud": self.modbus_baud.get(),
            "modbus_databits": self.modbus_databits.get(),
            "modbus_parity": self.modbus_parity.get(),
            "modbus_stopbits": self.modbus_stopbits.get(),
            "modbus_serial_mode": self.modbus_serial_mode.get(),
            "slave_id": self.slave_id.get(),
            "api_enabled": self.api_enabled.get(),
            "api_base_url": self.api_base_url.get(),
            "api_key": self.api_key.get(),
            "api_endpoint_work_orders": self.api_endpoint_work_orders.get(),
            "api_endpoint_submit_batch": self.api_endpoint_submit_batch.get(),
            "api_endpoint_submit_box": self.api_endpoint_submit_box.get(),
            "api_timeout": self.api_timeout.get(),
            "api_auto_sync_batch": self.api_auto_sync_batch.get(),
            "api_auto_sync_box": self.api_auto_sync_box.get()
        }
        success = self.data_manager.save_config(cfg)
        if hasattr(self, 'api_manager'):
            self.api_manager.update_config(cfg)
        if show_msg:
            if success:
                messagebox.showinfo("Konfigurasi Tersimpan", "Konfigurasi hardware & API berhasil disimpan ke data/config.json!", parent=self.root)
                self.log_msg("Konfigurasi hardware & API berhasil disimpan ke file data/config.json.")
            else:
                messagebox.showerror("Error", "Gagal menyimpan konfigurasi hardware.", parent=self.root)
        return success

    def build_connectivity_tab(self):
        # Buat scrollable container di tab_connectivity agar seluruh section (Printer, Scanner, Modbus, API) dapat diakses nyaman di semua resolusi monitor
        canvas = tk.Canvas(self.tab_connectivity, bg="#f1f5f9", highlightthickness=0)
        v_scroll = ttk.Scrollbar(self.tab_connectivity, orient="vertical", command=canvas.yview)
        scroll_content = ttk.Frame(canvas)

        scroll_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas_window = canvas.create_window((0, 0), window=scroll_content, anchor="nw")

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event):
            if str(getattr(self, 'active_nav', '')) == "conn":
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.tab_connectivity.bind_all("<MouseWheel>", _on_mousewheel)

        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas.configure(yscrollcommand=v_scroll.set)

        # --- 1. PRINTER GROUP ---
        p_frame = ttk.LabelFrame(scroll_content, text=" Konfigurasi Printer Omega MX (TCP/IP) ", padding="12")
        p_frame.pack(fill=tk.X, pady=(2, 6))
        ttk.Label(p_frame, text="IP:").grid(row=0, column=0)
        ttk.Entry(p_frame, textvariable=self.ip_addr, width=15).grid(row=0, column=1, padx=5)
        ttk.Label(p_frame, text="Port:").grid(row=0, column=2)
        ttk.Entry(p_frame, textvariable=self.ip_port, width=7).grid(row=0, column=3, padx=5)
        ttk.Button(p_frame, text="Test Connection", command=self.test_tcp).grid(row=0, column=4, padx=10)
        ttk.Button(p_frame, text="Simpan Konfigurasi", command=lambda: self.save_hardware_config(show_msg=True)).grid(row=0, column=5, padx=5)
       
        # --- 2. DUAL SCANNER GROUP ---
        s_frame = ttk.LabelFrame(scroll_content, text=" Konfigurasi Dual Scanner Keyence SR (TCP/IP) ", padding="10")
        s_frame.pack(fill=tk.X, pady=(0, 6))

        # Baris Atas: 2 Card Berdampingan (Scanner 1 & Scanner 2)
        grid_scanners = ttk.Frame(s_frame)
        grid_scanners.pack(fill=tk.X, expand=True)
        grid_scanners.columnconfigure(0, weight=1)
        grid_scanners.columnconfigure(1, weight=1)

        # === SCANNER 1 (SISI A) ===
        box_s1 = ttk.LabelFrame(grid_scanners, text=" Scanner 1 (Sisi A - Depan) ", padding="8")
        box_s1.grid(row=0, column=0, padx=(0, 5), sticky="nsew")
        
        f_s1_net = ttk.Frame(box_s1)
        f_s1_net.pack(fill=tk.X, pady=2)
        ttk.Label(f_s1_net, text="IP:").pack(side=tk.LEFT)
        ttk.Entry(f_s1_net, textvariable=self.scanner1_ip, width=14).pack(side=tk.LEFT, padx=3)
        ttk.Label(f_s1_net, text="Port:").pack(side=tk.LEFT, padx=(5, 0))
        ttk.Entry(f_s1_net, textvariable=self.scanner1_port, width=6).pack(side=tk.LEFT, padx=3)
        self.btn_conn_s1 = ttk.Button(f_s1_net, text="Connect S1", command=lambda: self.toggle_scanner(1))
        self.btn_conn_s1.pack(side=tk.LEFT, padx=5)
        self.lbl_status_s1 = tk.Label(f_s1_net, text="○ Terputus", fg="#c0392b", font=("Segoe UI", 8, "bold"))
        self.lbl_status_s1.pack(side=tk.LEFT, padx=5)
        
        f_s1_mon = ttk.Frame(box_s1)
        f_s1_mon.pack(fill=tk.X, pady=3)
        ttk.Label(f_s1_mon, text="Hasil Scan:").pack(side=tk.LEFT)
        self.ent_scan_monitor1 = ttk.Entry(f_s1_mon, textvariable=self.last_scan_result1, state='readonly')
        self.ent_scan_monitor1.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

        # === SCANNER 2 (SISI B) ===
        box_s2 = ttk.LabelFrame(grid_scanners, text=" Scanner 2 (Sisi B - Belakang) ", padding="8")
        box_s2.grid(row=0, column=1, padx=(5, 0), sticky="nsew")
        
        f_s2_net = ttk.Frame(box_s2)
        f_s2_net.pack(fill=tk.X, pady=2)
        ttk.Label(f_s2_net, text="IP:").pack(side=tk.LEFT)
        ttk.Entry(f_s2_net, textvariable=self.scanner2_ip, width=14).pack(side=tk.LEFT, padx=3)
        ttk.Label(f_s2_net, text="Port:").pack(side=tk.LEFT, padx=(5, 0))
        ttk.Entry(f_s2_net, textvariable=self.scanner2_port, width=6).pack(side=tk.LEFT, padx=3)
        self.btn_conn_s2 = ttk.Button(f_s2_net, text="Connect S2", command=lambda: self.toggle_scanner(2))
        self.btn_conn_s2.pack(side=tk.LEFT, padx=5)
        self.lbl_status_s2 = tk.Label(f_s2_net, text="○ Terputus", fg="#c0392b", font=("Segoe UI", 8, "bold"))
        self.lbl_status_s2.pack(side=tk.LEFT, padx=5)
        
        f_s2_mon = ttk.Frame(box_s2)
        f_s2_mon.pack(fill=tk.X, pady=3)
        ttk.Label(f_s2_mon, text="Hasil Scan:").pack(side=tk.LEFT)
        self.ent_scan_monitor2 = ttk.Entry(f_s2_mon, textvariable=self.last_scan_result2, state='readonly')
        self.ent_scan_monitor2.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

        # Baris Bawah: Tombol Cepat Hubungkan Semua, Timeout Pairing & Info Logika
        f_s_footer = ttk.Frame(s_frame)
        f_s_footer.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(f_s_footer, text="Hubungkan Kedua Scanner", command=self.connect_all_scanners).pack(side=tk.LEFT, padx=3)
        ttk.Button(f_s_footer, text="Putus Semua", command=self.disconnect_all_scanners).pack(side=tk.LEFT, padx=3)
        
        ttk.Label(f_s_footer, text="Timeout Pairing (ms):").pack(side=tk.LEFT, padx=(12, 2))
        ttk.Entry(f_s_footer, textvariable=self.dual_scan_timeout_var, width=6).pack(side=tk.LEFT, padx=2)

        ttk.Label(
            f_s_footer, 
            text="Info: Sisi A & Sisi B wajib MATCH. Jika 1 sisi timeout/beda -> REJECT.",
            font=("Segoe UI", 8, "italic"),
            foreground="#444444"
        ).pack(side=tk.RIGHT, padx=5)

        # --- 3. MODBUS I/O GROUP ---
        self.io_frame = ttk.LabelFrame(scroll_content, text=" Modbus I/O System (DI/DO) ", padding="12")
        self.io_frame.pack(fill=tk.X, pady=(0, 6))

        # Header: Mode & Slave ID
        header_f = ttk.Frame(self.io_frame)
        header_f.pack(fill=tk.X, pady=(0, 4))
        
        ttk.Label(header_f, text="Mode:").pack(side=tk.LEFT)
        self.modbus_mode = ttk.Combobox(header_f, values=["TCP", "RTU"], width=7, state="readonly")
        self.modbus_mode.set("TCP")
        self.modbus_mode.pack(side=tk.LEFT, padx=5)
        self.modbus_mode.bind("<<ComboboxSelected>>", self.on_modbus_mode_change)

        ttk.Label(header_f, text="Slave ID:").pack(side=tk.LEFT, padx=10)
        ttk.Entry(header_f, textvariable=self.slave_id, width=5).pack(side=tk.LEFT)

        # Container untuk Dynamic Settings (TCP vs RTU)
        self.modbus_settings_container = ttk.Frame(self.io_frame)
        self.modbus_settings_container.pack(fill=tk.X, pady=6)
        
        # Area Tombol Aksi I/O (Start Monitor & Test)
        action_bar = ttk.Frame(self.io_frame)
        action_bar.pack(fill=tk.X, pady=(2, 6))

        self.btn_io_connect = ttk.Button(action_bar, text="Start Monitor I/O", command=self.toggle_io_monitoring)
        self.btn_io_connect.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_test_reject = ttk.Button(action_bar, text="Test Pusher (DO 0)", command=self.manual_test_rejector)
        self.btn_test_reject.pack(side=tk.LEFT, padx=5)

        self.btn_test_alarm = ttk.Button(action_bar, text="Test Alarm Lamp (DO 1)", command=self.manual_test_alarm)
        self.btn_test_alarm.pack(side=tk.LEFT, padx=5)

        ttk.Label(action_bar, text="Delay Pusher (ms):").pack(side=tk.LEFT, padx=(15, 2))
        ttk.Entry(action_bar, textvariable=self.pusher_delay_var, width=6).pack(side=tk.LEFT, padx=2)

        ttk.Label(action_bar, text="Durasi Dorong (ms):").pack(side=tk.LEFT, padx=(8, 2))
        ttk.Entry(action_bar, textvariable=self.pusher_pulse_var, width=5).pack(side=tk.LEFT, padx=2)

        # --- PEMETAAN DAN DESKRIPSI ALAMAT I/O (DI / DO) ---
        mapping_frame = ttk.LabelFrame(self.io_frame, text=" Pemetaan Alamat & Deskripsi Sinyal I/O Modbus ", padding="8")
        mapping_frame.pack(fill=tk.X, pady=(2, 0))

        col_input = ttk.Frame(mapping_frame)
        col_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 15))

        col_output = ttk.Frame(mapping_frame)
        col_output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(15, 5))

        # Header Kolom
        ttk.Label(col_input, text="INPUT (DI / Sensor Fisik Mesin ke PC):", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(0, 4))
        ttk.Label(col_output, text="OUTPUT (DO / Aktuator & Alarm dari PC):", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(0, 4))

        self.di_leds = []
        self.do_leds = []

        di_data = [
            ("I0", "10001", "Sensor Head Print", "Mendeteksi kedatangan box di head printer"),
            ("I1", "10002", "Sensor Scanner", "Mendeteksi box tiba di bawah scanner Keyence"),
            ("I2", "10003", "Sensor Pusher", "Mendeteksi box tepat di depan silinder rejector"),
            ("I3", "10004", "Interlock / Safety", "Status konveyor jalan / tombol darurat (E-Stop)")
        ]

        do_data = [
            ("O0", "00001", "Pneumatic Pusher (Reject)", "Silinder pendorong box NG (Pulsa aktif 0.5s)"),
            ("O1", "00002", "Tower Lamp MERAH (NG)", "Alarm visual & buzzer saat terdeteksi hasil NG"),
            ("O2", "00003", "Tower Lamp KUNING", "Indikator status standby / jeda produksi"),
            ("O3", "00004", "Tower Lamp HIJAU", "Indikator mesin running normal & QC OK")
        ]

        for code, addr, title, desc in di_data:
            r = ttk.Frame(col_input)
            r.pack(fill=tk.X, pady=1)
            led = tk.Frame(r, width=13, height=13, bg="grey", highlightthickness=1)
            led.pack(side=tk.LEFT, padx=(0, 6))
            self.di_leds.append(led)
            ttk.Label(r, text=f"[{code}] {addr} :", font=("Consolas", 8, "bold"), width=14).pack(side=tk.LEFT)
            ttk.Label(r, text=f"{title}", font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
            ttk.Label(r, text=f" — {desc}", font=("Segoe UI", 8, "italic"), foreground="#555555").pack(side=tk.LEFT)

        for code, addr, title, desc in do_data:
            r = ttk.Frame(col_output)
            r.pack(fill=tk.X, pady=1)
            led = tk.Frame(r, width=13, height=13, bg="grey", highlightthickness=1)
            led.pack(side=tk.LEFT, padx=(0, 6))
            self.do_leds.append(led)
            ttk.Label(r, text=f"[{code}] {addr} :", font=("Consolas", 8, "bold"), width=14).pack(side=tk.LEFT)
            ttk.Label(r, text=f"{title}", font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
            ttk.Label(r, text=f" — {desc}", font=("Segoe UI", 8, "italic"), foreground="#555555").pack(side=tk.LEFT)

        # Panggil fungsi pertama kali untuk set view TCP
        self.on_modbus_mode_change(None)

        # --- 4. INTEGRASI API SISTEM UTAMA (ERP / MES / CLOUD) ---
        self.api_frame = ttk.LabelFrame(scroll_content, text=" Integrasi API Sistem Utama (ERP / MES / Core Server) ", padding="12")
        self.api_frame.pack(fill=tk.X, pady=(0, 8))

        # Baris Header: Toggle Enable + Indikator Status Koneksi
        api_header = ttk.Frame(self.api_frame)
        api_header.pack(fill=tk.X, pady=(0, 8))

        self.chk_api_enable = ttk.Checkbutton(
            api_header,
            text="Aktifkan Integrasi API Sistem Utama",
            variable=self.api_enabled,
            command=self._on_api_enable_toggle
        )
        self.chk_api_enable.pack(side=tk.LEFT)

        self.lbl_api_status = tk.Label(
            api_header,
            textvariable=self.api_status_text,
            font=("Segoe UI", 8, "bold"),
            fg="#64748b",
            bg="#f1f5f9",
            padx=8,
            pady=2,
            relief="solid",
            bd=1
        )
        self.lbl_api_status.pack(side=tk.LEFT, padx=12)

        lbl_api_mode_info = ttk.Label(
            api_header,
            text="Protokol: REST JSON Bi-directional (Client Pull/Push & Embedded Server Port 5022)",
            font=("Segoe UI", 8, "italic"),
            foreground="#555555"
        )
        lbl_api_mode_info.pack(side=tk.RIGHT)

        # Baris 1: Base URL API & Timeout
        row_url = ttk.Frame(self.api_frame)
        row_url.pack(fill=tk.X, pady=2)
        ttk.Label(row_url, text="Base URL API:", width=18).pack(side=tk.LEFT)
        self.ent_api_url = ttk.Entry(row_url, textvariable=self.api_base_url, width=50)
        self.ent_api_url.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(row_url, text="Timeout (detik):").pack(side=tk.LEFT)
        self.ent_api_timeout = ttk.Entry(row_url, textvariable=self.api_timeout, width=6)
        self.ent_api_timeout.pack(side=tk.LEFT, padx=5)

        # Baris 2: API Key / Bearer Token & Toggle Show/Hide
        row_key = ttk.Frame(self.api_frame)
        row_key.pack(fill=tk.X, pady=2)
        ttk.Label(row_key, text="API Key / Token:", width=18).pack(side=tk.LEFT)
        self.ent_api_key = ttk.Entry(row_key, textvariable=self.api_key, width=50, show="●")
        self.ent_api_key.pack(side=tk.LEFT, padx=(0, 6))

        self.var_show_api_key = tk.BooleanVar(value=False)
        def _toggle_key_vis():
            if self.var_show_api_key.get():
                self.ent_api_key.config(show="")
                btn_key_vis.config(text="Sembunyikan")
            else:
                self.ent_api_key.config(show="●")
                btn_key_vis.config(text="Tampilkan")

        btn_key_vis = tk.Button(
            row_key, text="Tampilkan", font=("Segoe UI", 8),
            relief="groove", bd=1, padx=6, pady=1, cursor="hand2",
            command=lambda: [self.var_show_api_key.set(not self.var_show_api_key.get()), _toggle_key_vis()]
        )
        btn_key_vis.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row_key, text="(Header: Bearer Token / X-API-Key)", font=("Segoe UI", 8, "italic"), foreground="#64748b").pack(side=tk.LEFT)

        # Baris 3: Endpoints (Inbound: Work Orders | Outbound: Batch Summary)
        row_ep = ttk.Frame(self.api_frame)
        row_ep.pack(fill=tk.X, pady=2)
        ttk.Label(row_ep, text="Endpoint Tarik WO:", width=18).pack(side=tk.LEFT)
        self.ent_ep_wo = ttk.Entry(row_ep, textvariable=self.api_endpoint_work_orders, width=22)
        self.ent_ep_wo.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(row_ep, text="Endpoint Kirim Hasil:").pack(side=tk.LEFT)
        self.ent_ep_batch = ttk.Entry(row_ep, textvariable=self.api_endpoint_submit_batch, width=26)
        self.ent_ep_batch.pack(side=tk.LEFT, padx=5)

        ttk.Label(row_ep, text="Endpoint QC Box:").pack(side=tk.LEFT, padx=(10, 2))
        self.ent_ep_box = ttk.Entry(row_ep, textvariable=self.api_endpoint_submit_box, width=20)
        self.ent_ep_box.pack(side=tk.LEFT, padx=3)

        # Baris 4: Opsi Otomasi & Telemetry
        row_opts = ttk.Frame(self.api_frame)
        row_opts.pack(fill=tk.X, pady=(5, 8))

        ttk.Checkbutton(
            row_opts,
            text="Auto-kirim ringkasan produksi ke Sistem Utama saat batch selesai",
            variable=self.api_auto_sync_batch
        ).pack(side=tk.LEFT, padx=(0, 15))

        ttk.Checkbutton(
            row_opts,
            text="Push hasil QC real-time per box",
            variable=self.api_auto_sync_box
        ).pack(side=tk.LEFT)

        # Baris 5: Action Buttons (Test, Simpan, Preview, Spesifikasi)
        row_actions = ttk.Frame(self.api_frame)
        row_actions.pack(fill=tk.X, pady=(4, 2))

        btn_test_api = ttk.Button(row_actions, text="Test Koneksi API", command=self.test_api_connection)
        btn_test_api.pack(side=tk.LEFT, padx=(0, 6))

        btn_save_api = ttk.Button(row_actions, text="Simpan Konfigurasi API", command=lambda: self.save_hardware_config(show_msg=True))
        btn_save_api.pack(side=tk.LEFT, padx=6)

        btn_sample_api = ttk.Button(row_actions, text="Tarik Work Order Sekarang", command=self.open_fetch_api_dialog)
        btn_sample_api.pack(side=tk.LEFT, padx=6)

        btn_schema_api = ttk.Button(row_actions, text="📖 Spesifikasi Payload API", command=self.open_api_contract_dialog)
        btn_schema_api.pack(side=tk.RIGHT, padx=6)
        
        # --- INFO DEVELOPER ---
        dev_frame = ttk.Frame(scroll_content)
        dev_frame.pack(fill=tk.X, pady=(4, 0))
        ttk.Separator(dev_frame, orient='horizontal').pack(fill=tk.X, pady=4)
        ttk.Label(dev_frame, text="PT SMARTEK SISTEM INOVASI  |  Industrial Automation & Software Solutions  |  Developer: WLDN  |  v2.0 API Ready", font=("Segoe UI", 8, "italic"), foreground="#555555").pack(pady=2)
           
    def build_logs_tab(self):
        log_frame = ttk.Frame(self.tab_logs)
        log_frame.pack(fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text = tk.Text(log_frame, yscrollcommand=scrollbar.set, state=tk.DISABLED, bg="#1a1a1a", fg="#3cd070", font=("Consolas", 9), relief="sunken", bd=1)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)

    # ==========================================
    # 2. LOGGER, CLEANUP & HISTORY MANAGEMENT
    # ==========================================
    def log_msg(self, message):
        """Menulis pesan ke tab Activity Log, CMD, dan File txt Harian secara Thread-Safe dengan Audit User (T6)"""
        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        user_prefix = ""
        if hasattr(self, 'current_user') and self.current_user and isinstance(self.current_user, dict):
            uname = self.current_user.get("username")
            if uname:
                user_prefix = f"[{uname}] "
        full_msg = f"[{date_str} {time_str}] {user_prefix}{message}\n"
        
        # Eksekusi pembaruan widget GUI di Main Thread agar thread-safe
        def _write_gui():
            try:
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, full_msg)
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)
            except Exception:
                pass

        if threading.current_thread() is threading.main_thread():
            _write_gui()
        else:
            try:
                self.root.after(0, _write_gui)
            except Exception:
                pass

        print(full_msg.strip())
        
        # --- SIMPAN ACTIVITY LOG KE FILE HARIAN ---
        log_file_path = os.path.join(self.log_dir, f"activity_log_{date_str}.txt")
        try:
            with open(log_file_path, "a", encoding="utf-8") as f:
                f.write(full_msg)
        except Exception: pass

    def toggle_date_filter(self):
        """Fungsi yang dipanggil saat Radio Button Filter diganti"""
        if self.history_filter.get() == "by_date":
            self.cal_start.config(state='normal')
            self.cal_end.config(state='normal')
        else:
            self.cal_start.config(state='disabled')
            self.cal_end.config(state='disabled')
            self.load_history_table() # Langsung refresh kalau pilih 20 Terakhir
    
    def load_history_table(self):
        for item in self.hist_tree.get_children(): self.hist_tree.delete(item)
        
        start_date = self.cal_start.get() + " 00:00:00" if self.history_filter.get() == "by_date" else None
        end_date = self.cal_end.get() + " 23:59:59" if self.history_filter.get() == "by_date" else None
        
        df = self.data_manager.get_filtered_history(self.history_filter.get(), start_date, end_date)
        
        if not df.empty:
            for _, row in df.iterrows():
                self.hist_tree.insert("", tk.END, values=(
                    row["Waktu_Mulai"], row["Waktu_Selesai"], row.get("Durasi", "-"), 
                    row["Source"], row["Total_Data"], row["Total_Print"], 
                    row["NG_Level"], row["Report_File"]
                ))

    def open_selected_history(self):
        selected = self.hist_tree.selection()
        if not selected:
            return messagebox.showwarning("Peringatan", "Pilih salah satu riwayat di tabel terlebih dahulu.")
        
        # Index ke-7 adalah "Report_File" yang berisi Relative Path
        report_relative_path = str(self.hist_tree.item(selected[0])['values'][7])
        full_path = os.path.abspath(os.path.join(self.history_dir, report_relative_path))
        if not full_path.startswith(os.path.abspath(self.history_dir)):
            return messagebox.showerror("Error", "Akses path tidak valid!")
        
        if os.path.exists(full_path):
            self.log_msg(f"Membuka file excel report: {report_relative_path}")
            os.startfile(full_path)
        else:
            messagebox.showerror("Error", f"File tidak ditemukan:\n{full_path}")

    # ==========================================
    # 3. DATA MANAGEMENT (Load & Table)
    # ==========================================
    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel/CSV", "*.xlsx *.xls *.csv")])
        if file_path:
            try:
                self.df, self.current_filename = self.data_manager.load_source_file(file_path)
                
                self.total_load_data = len(self.df)
                self.stat_total.set(str(self.total_load_data)) 
                if hasattr(self, 'lbl_file_chip'):
                    self.lbl_file_chip.config(text=self.current_filename)
                if hasattr(self, 'draw_progress_gauge'):
                    self.draw_progress_gauge(0, self.total_load_data, 0) 

                # Cek apakah ada Checkpoint Batch yang belum tuntas untuk file ini (Solusi 5)
                chk = self.data_manager.load_batch_checkpoint(self.current_filename)
                if chk and chk.get('is_active') and chk.get('current_judgments', 0) > 0:
                    judged_cnt = chk.get('current_judgments', 0)
                    total_v = chk.get('total_valid_print_data', self.total_load_data)
                    msg_cp = (
                        f"Ditemukan sesi produksi yang belum selesai untuk file:\n{self.current_filename}\n\n"
                        f"Progres terakhir: {judged_cnt} dari {total_v} kardus telah selesai diinspeksi.\n"
                        f"Waktu mulai sesi: {chk.get('batch_start_time', '-')}\n\n"
                        f"Apakah Anda ingin MELANJUTKAN (RESUME) dari posisi terakhir?\n\n"
                        f"- [YES] = Lanjutkan (Data kardus sebelumnya dipulihkan, cetak dilanjutkan mulai sisa kardus)\n"
                        f"- [NO]  = Reset / Mulai Baru dari awal (Batalkan checkpoint sebelumnya)"
                    )
                    if messagebox.askyesno("Checkpoint Produksi Terdeteksi", msg_cp):
                        self.resumed_checkpoint = chk
                        self.checkpoint_judged_map = chk.get('judged_indices', {})
                        self.log_msg(f"[CHECKPOINT] Melanjutkan batch: {judged_cnt} kardus telah selesai di sesi sebelumnya.")
                    else:
                        self.data_manager.clear_batch_checkpoint()
                        self.resumed_checkpoint = None
                        self.checkpoint_judged_map = {}
                        self.reset_stats()
                        self.log_msg("[CHECKPOINT] Checkpoint lama dibatalkan oleh operator. Memulai batch dari awal.")
                else:
                    self.resumed_checkpoint = None
                    self.checkpoint_judged_map = {}
                    self.reset_stats() 
                
                cols = self.df.columns.tolist()
                self.cb_sku['values'] = cols
                self.cb_qr['values'] = cols
                self.cb_matl['values'] = cols
                if len(cols) >= 3:
                    self.sel_sku.set(cols[0]); self.sel_qr.set(cols[1]); self.sel_matl.set(cols[2])
                
                self.update_table()
                self.log_msg(f"Berhasil load file: {self.current_filename} ({self.total_load_data} data)")
                
                # --- LOGIKA BARU: Pemanasan Printer di Belakang Layar ---
                threading.Thread(target=self.auto_start_printer, daemon=True).start()
                
                if not (getattr(self, 'is_listening1', False) or getattr(self, 'is_listening2', False)): 
                    ans = messagebox.askyesno("Load Sukses", f"Data ({self.total_load_data} baris) dimuat.\nHubungkan Scanner Keyence (Dual Scanner) sekarang?")
                    if ans: self.connect_all_scanners()
                        
            except Exception as e: 
                messagebox.showerror("Error", str(e))
                self.log_msg(f"ERROR Load File: {str(e)}")

    def auto_start_printer(self):
        """Membangunkan mesin saat Load File berhasil (Berjalan di background thread - S6)"""
        self.is_auto_starting = True
        try:
            self.log_msg("-> [Auto-Start] Mengecek status printer di belakang layar...")
            stat_reply = self.send_and_read("STATUS")
            
            # PERBAIKAN: Deteksi STATUS|0 sebagai STOP
            if stat_reply and ("STOP" in stat_reply.upper() or "STATUS|0" in stat_reply):
                self.log_msg("   [!] Printer posisi STOP. Mengirim perintah START...")
                self.send_and_read("START")
                time.sleep(1)
            else:
                self.log_msg(f"   [V] Printer sudah posisi PLAY/RUN. (Reply: {stat_reply})")
                time.sleep(0.5)
                
            if not getattr(self, 'is_printing', False):
                self.log_msg("-> [Auto-Start] Mereset Counter Print (RESET|2)...")
                self.send_and_read("RESET|2")
        finally:
            self.is_auto_starting = False

    def update_table(self):
        if self.df is None: return
        self.table_items_data.clear()
        for item in self.tree.get_children(): self.tree.delete(item)
        c_sku, c_qr, c_matl = self.sel_sku.get(), self.sel_qr.get(), self.sel_matl.get()
        if all(c in self.df.columns for c in [c_sku, c_qr, c_matl]):
            # Pengecekan data riwayat cetak 30 hari terakhir
            past_coupons = self.data_manager.get_coupons_in_last_days(days=30)
            seen_in_current_file = {}
            dup_30d_count = 0
            dup_file_count = 0

            for idx, (_, row) in enumerate(self.df.iterrows(), start=1):
                raw_sku = self.data_manager.sanitize_field(row[c_sku])
                raw_qr  = self.data_manager.sanitize_field(row[c_qr])
                raw_mat = self.data_manager.sanitize_field(row[c_matl])
                idx_str = str(idx)

                # Prioritas 0: Cek jika QR kosong atau bernilai 'nan'
                if not raw_qr or raw_qr.lower() == 'nan':
                    status_str = "Error: QR Kosong"
                    tag = ('duplicate',)
                    dup_file_count += 1
                # Prioritas 1: Sesi checkpoint yang di-resume
                elif self.resumed_checkpoint and idx_str in self.checkpoint_judged_map:
                    j_info = self.checkpoint_judged_map[idx_str]
                    j_status = j_info.get("status", "OK")
                    if j_status == "OK":
                        status_str = "QC OK (Dipulihkan)"
                        tag = ('ok',)
                    elif j_status == "REMOVED":
                        status_str = "Dilepas (Dipulihkan)"
                        tag = ('ng',)
                    else:
                        status_str = "QC NG (Dipulihkan)"
                        tag = ('ng',)
                elif raw_qr in past_coupons:
                    past_info = past_coupons[raw_qr]
                    ts_date = past_info.get('timestamp', '')[:10]
                    status_str = f"Duplikat 30H ({ts_date})"
                    tag = ('duplicate',)
                    dup_30d_count += 1
                elif raw_qr in seen_in_current_file:
                    first_row = seen_in_current_file[raw_qr]
                    status_str = f"Duplikat File (No.{first_row})"
                    tag = ('duplicate',)
                    dup_file_count += 1
                else:
                    seen_in_current_file[raw_qr] = idx
                    status_str = "Siap Cetak"
                    tag = ()

                item_id = self.tree.insert("", tk.END, values=(idx, raw_sku, raw_qr, raw_mat, status_str), tags=tag)
                # Simpan teks asli tanpa konversi angka agar leading zeroes (00123) 100% aman
                self.table_items_data[item_id] = {
                    'no': idx,
                    'sku': raw_sku,
                    'qr': raw_qr,
                    'mat': raw_mat,
                    'status': status_str
                }

            total_duplicate = dup_30d_count + dup_file_count
            valid_count = len(self.df) - total_duplicate
            self.total_valid_print_data = valid_count

            if self.resumed_checkpoint:
                self.history_records = list(self.resumed_checkpoint.get('history_records', []))
                self.count_ok = self.resumed_checkpoint.get('stat_ok', 0)
                self.count_ng = self.resumed_checkpoint.get('stat_ng', 0)
                self.current_judgments = self.resumed_checkpoint.get('current_judgments', 0)
                self.batch_start_time = self.resumed_checkpoint.get('batch_start_time', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                self.print_cycle = self.resumed_checkpoint.get('print_cycle', 1)
                self.stat_ok.set(str(self.count_ok))
                self.stat_ng.set(str(self.count_ng))
                remaining_count = max(0, valid_count - self.current_judgments)
                self.stat_total.set(f"{valid_count} (Sisa: {remaining_count})")
                self.log_msg(f"[CHECKPOINT] Status dipulihkan: OK={self.count_ok}, NG={self.count_ng}. Sisa kardus siap cetak: {remaining_count} data.")
            elif total_duplicate > 0:
                self.stat_total.set(f"{valid_count} ({total_duplicate} Skip)")
                warn_msg = f"Ditemukan {total_duplicate} data kupon duplikat!\n"
                if dup_30d_count > 0:
                    warn_msg += f"- {dup_30d_count} kupon pernah dicetak dalam 30 hari terakhir.\n"
                if dup_file_count > 0:
                    warn_msg += f"- {dup_file_count} kupon duplikat di dalam file ini sendiri.\n"
                warn_msg += f"\nData duplikat telah ditandai (warna merah muda) dan otomatis DILEWATI (tidak dicetak).\nSiap dicetak: {valid_count} dari {len(self.df)} baris."
                
                self.log_msg(f"[VALIDASI] Selesai: {total_duplicate} duplikat dilewati ({dup_30d_count} dari 30 hari terakhir, {dup_file_count} internal file). Siap dicetak: {valid_count} data.")
                messagebox.showwarning("Peringatan Duplikasi Kupon", warn_msg)
            else:
                self.stat_total.set(str(len(self.df)))
                self.log_msg(f"[VALIDASI] Selesai: Semua {len(self.df)} kupon unik & valid (tidak ada duplikasi dalam 30 hari terakhir).")

    # ==========================================
    # 4. GRAPHICS & RENDER (Preview & PDF)
    # ==========================================
    def generate_label_preview(self):
        selected = self.tree.selection()
        txt_sku, txt_qr, txt_matl = ("SKU-S", "QR-S", "MAT-S") if not selected else [str(x) for x in self.tree.item(selected[0])['values'][1:4]]
        
        # Minta "Sang Seniman" untuk menggambar preview
        self.preview_img, p_w, p_h = self.renderer.generate_preview(txt_sku, txt_qr, txt_matl, self.coords)
        
        # Update canvas di UI
        self.canvas_preview.config(width=p_w, height=p_h)
        self.canvas_preview.create_image(p_w // 2, p_h // 2, image=self.preview_img)

    def export_test_pdf(self):
        self.log_msg("Mengekspor layout ke PDF...")
        selected = self.tree.selection()
        if not selected:
            return messagebox.showwarning("Peringatan", "Pilih data di tabel dulu untuk di-export!")
            
        val = self.tree.item(selected[0])['values']
        txt_sku, txt_qr, txt_matl = str(val[1]), str(val[2]), str(val[3])

        # Minta "Sang Seniman" untuk membuat PDF
        pdf_path = self.renderer.export_pdf(txt_sku, txt_qr, txt_matl, self.coords)
        
        messagebox.showinfo("Sukses", f"File siap di-print!\nTersimpan di: {pdf_path}")
        try: 
            os.startfile(os.path.abspath(pdf_path))
        except: 
            pass
        
    # ==========================================
    # 5. BATCH QUEUE & LOGIC
    # ==========================================
    # ==========================================
    # KONEKSI PRINTER OMEGA (Wrapper)
    # ==========================================
    def test_tcp(self):
        """Uji koneksi printer secara non-blocking di worker thread (S2)"""
        if self.is_simulation.get():
            self.log_msg("Test Koneksi Omega MX (Mode Simulasi) - OK")
            messagebox.showinfo("OK", "Printer Online (Mode Simulasi)!", parent=self.root)
        else:
            ip = self.ip_addr.get().strip()
            port = self.ip_port.get().strip()
            self.log_msg(f"Menguji koneksi ke Printer Omega MX ({ip}:{port})...")
            def _worker_test():
                success, msg = self.printer.test_connection(ip, port)
                def _on_done():
                    if success:
                        self.log_msg("Test Koneksi Omega MX (Aktual) - Berhasil")
                        messagebox.showinfo("OK", f"Printer Online!\n{msg}", parent=self.root)
                    else:
                        self.log_msg(f"Test Koneksi Omega MX Gagal: {msg}")
                        messagebox.showerror("Gagal", f"Printer Offline:\n{msg}", parent=self.root)
                self.root.after(0, _on_done)
            threading.Thread(target=_worker_test, daemon=True).start()
       
    def check_is_simulation(self):
        """Pemeriksaan status mode simulasi secara thread-safe"""
        try:
            return bool(self.is_simulation.get())
        except Exception:
            return True

    def check_is_auto_judge_sim(self):
        """Pemeriksaan status auto-scan mode simulasi secara thread-safe"""
        try:
            return bool(getattr(self, 'auto_judge_sim', None) and self.auto_judge_sim.get())
        except Exception:
            return False

    def send_and_read(self, message):
        """Meneruskan pesan ke modul printer_omega.py dengan penanganan mode simulasi"""
        is_sim = self.check_is_simulation()

        if is_sim:
            cmd = message.strip()
            if cmd == "STATUS":
                return "STATUS|1,PLAY"
            elif cmd == "CSTATUS":
                return f"CSTATUS|{getattr(self, 'current_judgments', 0)},0"
            return "OK"

        try:
            ip = self.ip_addr.get()
            port = self.ip_port.get()
        except Exception:
            ip = "192.168.1.100"
            port = "6007"

        reply = self.printer.send_and_read(ip, port, message)
        
        if reply.startswith("ERROR_CONN:"):
            self.log_msg(f"ERROR KONEKSI PRINTER: {reply}")
            return None
        return reply

    def get_current_print_count(self):
        """Meneruskan permintaan hitungan ke modul printer_omega.py"""
        try:
            is_sim = bool(self.is_simulation.get())
        except Exception:
            is_sim = True

        if is_sim:
            return getattr(self, 'current_judgments', 0)

        try:
            ip = self.ip_addr.get()
            port = self.ip_port.get()
        except Exception:
            ip = "192.168.1.100"
            port = "6007"

        return self.printer.get_current_print_count(ip, port) 
  
    def run_batch_print(self):
        if getattr(self, 'is_printing', False):
            return messagebox.showwarning("Sedang Berjalan", "Proses cetak batch sedang berlangsung!")

        all_items = self.tree.get_children()
        if not all_items: return messagebox.showwarning("!", "Tabel Kosong!")

        # Filter hanya data yang BUKAN duplikat dan BELUM pernah selesai di-judge (Solusi 5 Checkpoint)
        items_to_print = [
            it for it in all_items 
            if 'duplicate' not in self.tree.item(it, 'tags')
            and 'ok' not in self.tree.item(it, 'tags')
            and 'ng' not in self.tree.item(it, 'tags')
        ]

        if not items_to_print:
            return messagebox.showwarning("Peringatan", "Semua data telah selesai dicetak & diinspeksi atau merupakan duplikat.")

        dup_count = len(all_items) - len(items_to_print)
        confirm_msg = f"Mulai cetak {len(items_to_print)} data?"
        if self.resumed_checkpoint:
            confirm_msg = f"Lanjutkan cetak {len(items_to_print)} data tersisa?\n({self.current_judgments} data kardus sebelumnya telah tercatat selesai)"
        elif dup_count > 0:
            confirm_msg += f"\n({dup_count} data kupon duplikat otomatis dilewati/skip)"

        if not self.is_simulation.get() and not (getattr(self, 'is_listening1', False) or getattr(self, 'is_listening2', False)):
            if messagebox.askyesno("Scanner Terputus", "Scanner Keyence belum terhubung!\nHubungkan kedua scanner sekarang?"):
                # Koneksi berjalan di background; batch dilanjutkan otomatis bila kedua scanner berhasil terhubung
                self.connect_all_scanners(on_finished=lambda ok: self.run_batch_print() if ok else None)
                return
            elif not messagebox.askyesno("Peringatan", "Mencetak TANPA Scanner (Mode Manual). Lanjutkan?"): return
        
        if not messagebox.askyesno("Batch", confirm_msg) : return

        self.waiting_queue.clear()
        self.ng_boxes_waiting_reject.clear()
        
        if not self.resumed_checkpoint:
            self.ng_list.clear()
            self.history_records.clear() 
            self.print_cycle = 1         
            self.count_ok = 0
            self.count_ng = 0
            self.current_judgments = 0
            self.batch_start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for item in items_to_print:
                self.tree.item(item, tags=())
        else:
            # Bangun ulang ng_list dari sesi sebelumnya agar box NG lama tetap bisa di-reprint (K2)
            self.ng_list = [it for it in all_items if 'ng' in self.tree.item(it, 'tags')]
            if self.ng_list:
                self.log_msg(f"[CHECKPOINT] {len(self.ng_list)} kardus NG dari sesi sebelumnya dimasukkan kembali ke antrean reprint.")
            self.log_msg(f"-> Melanjutkan batch: {self.current_judgments} riwayat kardus sebelumnya dipertahankan.")

        self.expected_total_judgments = getattr(self, 'total_valid_print_data', len(all_items))
        self.is_printing = True
        self.stop_requested = False
        self.pause_requested = False
        self.consecutive_ng_count = 0
        self.cascade_warning_active = False

        # Inisialisasi / perbarui checkpoint lokal (Solusi 5)
        self.save_current_checkpoint()
        
        # Update status tombol UI & Indikator Sistem
        if hasattr(self, 'btn_batch_print'): self.btn_batch_print.config(state="disabled")
        if hasattr(self, 'btn_stop_print'): self.btn_stop_print.config(state="normal")
        if hasattr(self, 'btn_pause_print'): self.btn_pause_print.config(text="PAUSE", state="normal")
        self.set_system_status("RUNNING")

        if self.resumed_checkpoint:
            self.log_msg(f"=== MELANJUTKAN BATCH PRINTING ({len(items_to_print)} DATA TERSISA DARI TOTAL {self.expected_total_judgments}) ===")
        else:
            self.log_msg(f"=== MEMULAI BATCH PRINTING ({len(items_to_print)} DATA) ===")
            if dup_count > 0:
                self.log_msg(f"-> INFO: {dup_count} data duplikat tidak dikirim ke printer.")
        
        # Jalankan loop cetak di Background Thread agar GUI tetap mulus dan responsif
        threading.Thread(target=self._worker_batch_print, args=(list(items_to_print),), daemon=True).start()

    def toggle_pause_batch(self):
        """Toggle jeda / lanjut batch printing oleh operator"""
        if not getattr(self, 'is_printing', False):
            return

        if not getattr(self, 'pause_requested', False):
            self.pause_requested = True
            self.log_msg("-> [PAUSE] Operator menjeda pengiriman batch printing...")
            if not self.is_simulation.get():
                self.send_and_read("STOP")
        else:
            self.pause_requested = False
            self.log_msg("-> [RESUME] Melanjutkan pengiriman batch printing...")
            if not self.is_simulation.get():
                self.send_and_read("START")

        self._sync_pause_button_ui()

    def _sync_pause_button_ui(self):
        """Sinkronisasi teks tombol PAUSE/RESUME di GUI secara thread-safe"""
        def _upd():
            if hasattr(self, 'btn_pause_print'):
                if getattr(self, 'pause_requested', False):
                    self.btn_pause_print.config(text="RESUME", state="normal")
                    self.set_system_status("PAUSED")
                else:
                    self.btn_pause_print.config(text="PAUSE", state="normal" if getattr(self, 'is_printing', False) else "disabled")
                    self.set_system_status("RUNNING" if getattr(self, 'is_printing', False) else "READY")
        if threading.current_thread() is threading.main_thread():
            _upd()
        else:
            try:
                self.root.after(0, _upd)
            except Exception:
                pass

    def stop_batch_print(self):
        """Meminta penghentian proses cetak batch oleh operator"""
        if getattr(self, 'is_printing', False):
            if messagebox.askyesno("Konfirmasi Stop", "Hentikan pengiriman antrean cetak batch ke printer?"):
                self.stop_requested = True
                self.pause_requested = False
                self._cancel_dual_scan_timer()
                self.current_box_scans = {"side1": None, "side2": None}
                self.ng_boxes_waiting_reject.clear()
                self.log_msg("-> [STOP] Operator menghentikan proses cetak batch.")
                self.save_current_checkpoint()
                self.send_and_read("STOP")
                self.set_system_status("STOPPED")
                self._sync_pause_button_ui()

    def _restore_print_buttons(self):
        """Mengembalikan status tombol print di GUI"""
        def _res():
            if hasattr(self, 'btn_batch_print'): self.btn_batch_print.config(state="normal")
            if hasattr(self, 'btn_stop_print'): self.btn_stop_print.config(state="disabled")
            if hasattr(self, 'btn_pause_print'): self.btn_pause_print.config(text="PAUSE", state="disabled")
            self.set_system_status("READY")
        if threading.current_thread() is threading.main_thread():
            _res()
        else:
            try:
                self.root.after(0, _res)
            except Exception:
                pass

    def _worker_batch_print(self, items_to_print):
        """Looping pencetakan batch di background thread dengan Flow Control (Backpressure) & Auto-Recovery"""
        try:
            self.batch_completed = False
            if self.print_cycle > 1:
                # Saat Reprint Cycle, target scan hanya sejumlah kardus yang di-reprint pada cycle ini
                self.expected_total_judgments = len(items_to_print)
                self.current_judgments = 0
            elif getattr(self, 'resumed_checkpoint', None):
                # Saat Resume Checkpoint Cycle 1, target scan adalah total valid print data
                self.expected_total_judgments = getattr(self, 'total_valid_print_data', len(items_to_print))
            else:
                # Cycle 1 Baru
                self.expected_total_judgments = getattr(self, 'total_valid_print_data', len(items_to_print))
                self.current_judgments = 0

            # Eksekusi pemanasan / start mesin
            self.send_and_read("CLR")
            self.send_and_read("RESET|2")
            self.send_and_read("START")
            self.log_msg("-> [!] Trigger START dikirim (Mesin running).")
            time.sleep(0.5)

            for idx, item in enumerate(items_to_print):
                # 1. Backpressure Control: Tunggu jika antrean in-transit sudah mencapai batas maksimum (mencegah overflow buffer)
                max_queue = getattr(self, 'max_queue_transit', 10)
                while len(self.waiting_queue) >= max_queue:
                    if getattr(self, 'stop_requested', False):
                        break
                    time.sleep(0.15)

                # 2. Pause Handling: Tunggu selama status pause aktif
                while getattr(self, 'pause_requested', False):
                    if getattr(self, 'stop_requested', False):
                        break
                    time.sleep(0.2)

                if getattr(self, 'stop_requested', False):
                    self.log_msg("-> Pengiriman data dihentikan sebelum selesai.")
                    break

                # Ambil data dari cache asli string (mencegah thread violation Tkinter & mempertahankan '00123')
                row_data = self.table_items_data.get(item)
                if row_data:
                    item_no = row_data['no']
                    txt_sku = row_data['sku']
                    txt_qr  = row_data['qr']
                    txt_mat = row_data['mat']
                else:
                    val = self.tree.item(item)['values']
                    item_no = val[0]
                    txt_sku = str(val[1])
                    txt_qr  = str(val[2])
                    txt_mat = str(val[3])

                # 3. Kirim MFD ke Printer dengan Auto-Retry & Auto-Pause jika jaringan terputus
                mfd_payload = f"MFD|SKU01:{txt_sku}|QRC02:{txt_qr}|MAT03:{txt_mat}\r\n"
                send_success = False
                max_retries = 3

                for attempt in range(1, max_retries + 1):
                    if getattr(self, 'stop_requested', False):
                        break
                    reply = self.send_and_read(mfd_payload)
                    if reply is not None and not reply.startswith("ERROR_CONN:") and not reply.startswith("ERR") and "ERROR" not in reply.upper():
                        send_success = True
                        break
                    else:
                        err_detail = reply if reply else "No Reply"
                        self.log_msg(f"[PRINTER] Upaya {attempt}/{max_retries} kirim No.{item_no} gagal ({err_detail}). Menghubungkan ulang...")
                        time.sleep(1.0)

                # Jika tetap gagal setelah 3x percobaan, lakukan Auto-Pause dan beri notifikasi ke operator
                if not send_success:
                    if getattr(self, 'stop_requested', False):
                        break
                    self.log_msg(f"[ALARM PRINTER] Komunikasi ke printer terputus pada data No.{item_no}! Batch otomatis di-PAUSE.")
                    self.pause_requested = True
                    self._sync_pause_button_ui()

                    def _ask_reconnect(no=item_no, sku=txt_sku):
                        ans = messagebox.askretrycancel(
                            "Komunikasi Printer Terputus",
                            f"Gagal mengirim data No.{no} ({sku}) ke Printer Omega MX!\n"
                            f"Koneksi jaringan LAN/TCP ke {self.ip_addr.get()}:{self.ip_port.get()} terputus.\n\n"
                            f"Periksa kabel LAN atau daya printer, lalu klik 'Retry' untuk mencoba lagi, "
                            f"atau 'Cancel' untuk menghentikan batch.",
                            parent=self.root
                        )
                        if ans:
                            self.pause_requested = False
                        else:
                            self.stop_requested = True
                            self.pause_requested = False
                        self._sync_pause_button_ui()

                    try:
                        self.root.after(100, _ask_reconnect)
                    except Exception:
                        pass

                    # Tunggu sampai operator memutuskan Retry atau Stop
                    while getattr(self, 'pause_requested', False):
                        time.sleep(0.3)

                    if getattr(self, 'stop_requested', False):
                        break

                    # Coba kirim ulang satu kali
                    reply = self.send_and_read(mfd_payload)
                    if reply is None or reply.startswith("ERROR_CONN:") or reply.startswith("ERR") or "ERROR" in reply.upper():
                        self.log_msg(f"[ERROR FATAL] Tetap gagal mengirim data No.{item_no} (Respon: {reply}). Menghentikan batch.")
                        break

                # 4. Tambahkan ke waiting_queue software HANYA setelah data berhasil diterima printer!
                # Catat kupon ke database duplikat secara real-time (T1) agar aman dari crash/listrik padam
                self.data_manager.record_single_coupon(txt_qr, source_file=self.current_filename)
                def _add_to_queue(it=item):
                    try:
                        self.tree.item(it, tags=('waiting',))
                        self.tree.set(it, "status", "Antrean Cetak")
                        self.waiting_queue.append(it)
                        self.update_queue_ui()
                    except Exception:
                        pass
                try:
                    self.root.after(0, _add_to_queue)
                except Exception:
                    pass

                self.log_msg(f"-> Data {txt_sku} terkirim ({idx+1}/{self.expected_total_judgments})")
                
                # Simulasi Auto-Scan QC otomatis bila Mode Simulasi & Auto-Scan aktif
                if self.check_is_simulation() and self.check_is_auto_judge_sim():
                    def _auto_judge():
                        time.sleep(0.6)
                        if self.waiting_queue and not getattr(self, 'stop_requested', False):
                            try:
                                self.root.after(0, lambda: self.simulate_judge(True))
                            except Exception:
                                pass
                    threading.Thread(target=_auto_judge, daemon=True).start()

                time.sleep(0.4) # Jeda antar-cetak terkontrol

            if not getattr(self, 'stop_requested', False):
                self.log_msg("-> Semua antrean masuk. Mengirim Dummy Data ke Layar...")
                dummy_payload = "MFD|SKU01:COMPLETE|QRC02:QR Selesai|MAT03:xxxxxxxxx\r\n"
                self.send_and_read(dummy_payload)
                self.log_msg("INFO: Menunggu proses Scan/Judgement selesai...")

                # Di mode simulasi auto-scan, selesaikan sisa kardus di lintasan sampai antrean tuntas
                if self.check_is_simulation() and self.check_is_auto_judge_sim():
                    while self.waiting_queue and not getattr(self, 'stop_requested', False):
                        time.sleep(0.6)
                        if self.waiting_queue:
                            try:
                                self.root.after(0, lambda: self.simulate_judge(True))
                            except Exception:
                                pass

        except Exception as e:
            self.log_msg(f"ERROR saat proses cetak batch: {e}")
        finally:
            self.is_printing = False
            self.pause_requested = False
            try:
                self.root.after(0, self._restore_print_buttons)
            except Exception:
                pass

    def do_printing_loop(self, items_to_print):
        """Wrapper kompatibilitas untuk memulai worker batch"""
        self.is_printing = True
        self.stop_requested = False
        self.pause_requested = False
        if hasattr(self, 'btn_batch_print'): self.btn_batch_print.config(state="disabled")
        if hasattr(self, 'btn_stop_print'): self.btn_stop_print.config(state="normal")
        if hasattr(self, 'btn_pause_print'): self.btn_pause_print.config(text="PAUSE", state="normal")
        threading.Thread(target=self._worker_batch_print, args=(list(items_to_print),), daemon=True).start()

    def update_queue_ui(self):
        def _upd():
            q_len = len(self.waiting_queue)
            if hasattr(self, 'lbl_queue_count'):
                self.lbl_queue_count.config(text=f"In Transit: {q_len} Box")
            if hasattr(self, 'draw_conveyor'):
                self.draw_conveyor(q_len)
        if threading.current_thread() is threading.main_thread():
            _upd()
        else:
            try:
                self.root.after(0, _upd)
            except Exception:
                pass

    # ==========================================
    # 6. DUAL SCANNER LISTENER & QC LOGIC (KEYENCE SR)
    # ==========================================
    def update_scanner_ui_status(self, scanner_id):
        """Update label status dan teks tombol connect untuk Scanner 1 atau 2 (Thread-Safe)"""
        def _update():
            is_conn = (self.is_listening1 if scanner_id == 1 else self.is_listening2)
            btn = getattr(self, f"btn_conn_s{scanner_id}", None)
            lbl = getattr(self, f"lbl_status_s{scanner_id}", None)
            if btn:
                btn.config(text=f"Disconnect S{scanner_id}" if is_conn else f"Connect S{scanner_id}")
            if lbl:
                lbl.config(
                    text="● Terhubung" if is_conn else "○ Terputus",
                    fg="#1e7e34" if is_conn else "#c0392b"
                )
            self.is_listening = bool(self.is_listening1 or self.is_listening2)
            if hasattr(self, 'update_hardware_indicators'):
                self.update_hardware_indicators()

        if threading.current_thread() is threading.main_thread():
            _update()
        else:
            try:
                self.root.after(0, _update)
            except Exception:
                pass

    def toggle_scanner(self, scanner_id):
        is_conn = (self.is_listening1 if scanner_id == 1 else self.is_listening2)
        if is_conn:
            self.disconnect_scanner(scanner_id)
        else:
            threading.Thread(target=lambda: self.connect_scanner(scanner_id), daemon=True).start()

    def connect_scanner(self, scanner_id=1, silent=False):
        """Menghubungkan Scanner Keyence berdasarkan ID (1 = Sisi A, 2 = Sisi B)"""
        is_conn = (self.is_listening1 if scanner_id == 1 else self.is_listening2)
        if is_conn: return True

        ip_var = self.scanner1_ip if scanner_id == 1 else self.scanner2_ip
        port_var = self.scanner1_port if scanner_id == 1 else self.scanner2_port
        side_name = "Sisi A" if scanner_id == 1 else "Sisi B"

        if self.is_simulation.get():
            if scanner_id == 1: 
                self.is_listening1 = True
            else: 
                self.is_listening2 = True
            self.update_scanner_ui_status(scanner_id)
            self.log_msg(f"Scanner {scanner_id} ({side_name}) terhubung (Mode Simulasi).")
            if not silent:
                self.root.after(0, lambda: messagebox.showinfo(f"Scanner {scanner_id} OK", f"Scanner {scanner_id} ({side_name}) Terhubung (SIMULASI).", parent=self.root))
            return True

        try:
            old_sock = self.scanner1_socket if scanner_id == 1 else self.scanner2_socket
            if old_sock:
                try: old_sock.close()
                except Exception: pass

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.settimeout(2.5)
            sock.connect((ip_var.get().strip(), int(port_var.get().strip())))
            sock.settimeout(1.0) # Non-blocking timeout agar thread responsif saat kabel dicabut (T2)

            if scanner_id == 1:
                self.scanner1_socket = sock
                self.scanner_socket = sock
                self.is_listening1 = True
            else:
                self.scanner2_socket = sock
                self.is_listening2 = True

            self.update_scanner_ui_status(scanner_id)
            threading.Thread(target=self.listen_to_scanner, args=(scanner_id,), daemon=True).start()
            self.log_msg(f"Scanner {scanner_id} ({side_name} - {ip_var.get()}:{port_var.get()}) Aktual Terhubung.")
            if not silent:
                self.root.after(0, lambda: messagebox.showinfo(f"Scanner {scanner_id} OK", f"Scanner {scanner_id} ({side_name}) Aktual Terhubung!", parent=self.root))
            return True
        except Exception as e:
            if scanner_id == 1: self.is_listening1 = False
            else: self.is_listening2 = False
            self.update_scanner_ui_status(scanner_id)
            self.log_msg(f"Gagal koneksi Scanner {scanner_id} ({side_name}): {e}")
            if not silent:
                self.root.after(0, lambda: messagebox.showerror("Gagal", f"Tidak bisa terhubung ke Scanner {scanner_id} ({side_name}).\n\nError: {e}", parent=self.root))
            return False

    def disconnect_scanner(self, scanner_id):
        """Memutus koneksi Scanner Keyence 1 atau 2"""
        side_name = "Sisi A" if scanner_id == 1 else "Sisi B"
        if scanner_id == 1:
            self.is_listening1 = False
            if self.scanner1_socket:
                try: self.scanner1_socket.close()
                except Exception: pass
                self.scanner1_socket = None
        else:
            self.is_listening2 = False
            if self.scanner2_socket:
                try: self.scanner2_socket.close()
                except Exception: pass
                self.scanner2_socket = None
        self.update_scanner_ui_status(scanner_id)
        self.log_msg(f"Scanner {scanner_id} ({side_name}) diputuskan.")

    def connect_all_scanners(self, on_finished=None):
        """Menghubungkan kedua scanner Keyence (Scanner 1 & Scanner 2) di worker thread (S2).
        on_finished(ok: bool) dipanggil di main thread setelah dialog hasil ditutup."""
        self.log_msg("Menghubungkan kedua scanner Keyence...")
        def _worker_connect():
            s1_ok = self.connect_scanner(1, silent=True)
            s2_ok = self.connect_scanner(2, silent=True)
            def _on_done():
                if s1_ok and s2_ok:
                    messagebox.showinfo("Dual Scanner OK", "Kedua Scanner Keyence (Sisi A & Sisi B) Berhasil Terhubung!", parent=self.root)
                elif s1_ok and not s2_ok:
                    messagebox.showwarning("Sebagian Terhubung", "Scanner 1 (Sisi A) Terhubung, tetapi Scanner 2 (Sisi B) Gagal!", parent=self.root)
                elif not s1_ok and s2_ok:
                    messagebox.showwarning("Sebagian Terhubung", "Scanner 2 (Sisi B) Terhubung, tetapi Scanner 1 (Sisi A) Gagal!", parent=self.root)
                else:
                    messagebox.showerror("Gagal", "Kedua Scanner Gagal Terhubung! Periksa kabel LAN, IP & Port masing-masing scanner.", parent=self.root)
                if on_finished:
                    on_finished(bool(s1_ok and s2_ok))
            self.root.after(0, _on_done)
        threading.Thread(target=_worker_connect, daemon=True).start()

    def disconnect_all_scanners(self):
        """Memutus kedua scanner Keyence"""
        self.disconnect_scanner(1)
        self.disconnect_scanner(2)
        messagebox.showinfo("Scanner Disconnected", "Kedua Scanner telah diputuskan.", parent=self.root)

    def listen_to_scanner(self, scanner_id):
        """Mendengarkan data scanner dengan buffer akumulasi dan timeout non-blocking (T2)"""
        buffer = ""
        sock = self.scanner1_socket if scanner_id == 1 else self.scanner2_socket
        side_name = "Sisi A" if scanner_id == 1 else "Sisi B"
        while (self.is_listening1 if scanner_id == 1 else self.is_listening2):
            try:
                if not sock: break
                try:
                    chunk = sock.recv(1024)
                except (socket.timeout, TimeoutError):
                    continue # Polling timeout 1.0s normal: lanjut cek loop is_listening

                if not chunk:
                    self.log_msg(f"Koneksi Scanner {scanner_id} ({side_name}) Terputus (remote host close).")
                    if scanner_id == 1: self.is_listening1 = False
                    else: self.is_listening2 = False
                    self.update_scanner_ui_status(scanner_id)
                    break
                
                buffer += chunk.decode('utf-8', errors='ignore')
                
                # Standar Keyence menggunakan terminasi \r, \n, atau \r\n
                while '\r' in buffer or '\n' in buffer:
                    buffer = buffer.replace('\r\n', '\n').replace('\r', '\n')
                    parts = buffer.split('\n', 1)
                    barcode = parts[0].strip()
                    buffer = parts[1] if len(parts) > 1 else ""
                    
                    if barcode:
                        # Kirim ke UI thread secara aman tanpa closure late-binding
                        self.root.after(0, lambda sid=scanner_id, b=barcode: self.process_scanned_data(sid, b))
            except Exception as e:
                is_active = (self.is_listening1 if scanner_id == 1 else self.is_listening2)
                if is_active:
                    self.log_msg(f"Koneksi Scanner {scanner_id} ({side_name}) Terputus: {e}")
                if scanner_id == 1: self.is_listening1 = False
                else: self.is_listening2 = False
                self.update_scanner_ui_status(scanner_id)
                break

    def _cancel_dual_scan_timer(self):
        """Membatalkan timer timeout pairing dual-scanner jika sedang aktif"""
        if hasattr(self, '_dual_scan_timer_id') and self._dual_scan_timer_id is not None:
            try:
                self.root.after_cancel(self._dual_scan_timer_id)
            except Exception:
                pass
            self._dual_scan_timer_id = None

    def _on_dual_scan_timeout(self):
        """
        Dipanggil saat salah satu scanner membaca barcode namun scanner sisi pasangannya
        tidak merespons dalam batas waktu timeout pairing (mencegah deadlock & cross-matching).
        """
        self._dual_scan_timer_id = None
        if not self.waiting_queue:
            self.current_box_scans = {"side1": None, "side2": None}
            return

        s1 = self.current_box_scans.get("side1")
        s2 = self.current_box_scans.get("side2")

        if s1 is None and s2 is None:
            return

        missing_side = "Sisi B (Scanner 2)" if s2 is None else "Sisi A (Scanner 1)"
        present_side = "Sisi A (Scanner 1)" if s1 is not None else "Sisi B (Scanner 2)"
        present_val = s1 if s1 is not None else s2
        
        self.log_msg(f"[DUAL-SCAN TIMEOUT] {missing_side} tidak merespons! (Hanya {present_side} terdeteksi: '{present_val}'). Box dinilai NG.")

        s1_val = s1 if s1 is not None else "(Timeout / No Read)"
        s2_val = s2 if s2 is not None else "(Timeout / No Read)"
        self.current_box_scans = {"side1": None, "side2": None}

        # Keputusan: NG karena salah satu sisi tidak terbaca
        self.simulate_judge(is_ok=False, side1_val=s1_val, side2_val=s2_val)

    def process_scanned_data(self, scanner_id, scanned_text):
        """Memproses data masuk dari Scanner 1 atau 2 dan sinkronisasi dual-scan"""
        scanned_text = str(scanned_text).strip()
        side_name = "Sisi A" if scanner_id == 1 else "Sisi B"
        other_id = 2 if scanner_id == 1 else 1
        other_name = "Sisi B" if scanner_id == 1 else "Sisi A"
        side_key = f"side{scanner_id}"
        other_key = f"side{other_id}"

        # 1. Update Monitor di Tab Connectivity
        if scanner_id == 1:
            self.last_scan_result1.set(scanned_text)
            self.last_scan_result.set(scanned_text)
        else:
            self.last_scan_result2.set(scanned_text)
            
        # 2. Logika QC jika ada box di queue
        if not self.waiting_queue: 
            self.log_msg(f"SCANNER {scanner_id} ({side_name}) IDLE: '{scanned_text}'")
            return
            
        self.log_msg(f"-> Scanner {scanner_id} ({side_name}) Read: '{scanned_text}'")
        
        # 3. Mode Inspeksi: Apakah kedua scanner aktif atau hanya satu (komisioning)?
        dual_active = bool(self.is_listening1 and self.is_listening2)
        
        if dual_active:
            # Proteksi Overrun: Jika sisi ini SUDAH memiliki data yang belum berpasangan,
            # berarti kardus sebelumnya terlewat oleh sisi pasangannya, dan kardus baru sudah tiba di sisi ini!
            if self.current_box_scans[side_key] is not None:
                self.log_msg(f"[DUAL-SCAN OVERRUN] {side_name} menerima kardus baru sebelum {other_name} merespons kardus sebelumnya. Menyelesaikan kardus sebelumnya sebagai NG.")
                self._cancel_dual_scan_timer()
                prev_val = self.current_box_scans[side_key]
                self.current_box_scans = {"side1": None, "side2": None}
                if scanner_id == 1:
                    self.simulate_judge(is_ok=False, side1_val=prev_val, side2_val="(Terlewat / No Read)")
                else:
                    self.simulate_judge(is_ok=False, side1_val="(Terlewat / No Read)", side2_val=prev_val)
                
                if not self.waiting_queue:
                    return

            # Simpan hasil scan ke sisi yang bersangkutan
            self.current_box_scans[side_key] = scanned_text

            # Cek apakah sisi pasangannya SUDAH ada di buffer
            if self.current_box_scans[other_key] is not None:
                # KEDUA SISI LENGKAP: Batalkan timer timeout & evaluasi pencocokan
                self._cancel_dual_scan_timer()
                item_id = self.waiting_queue[0]
                row_data = self.table_items_data.get(item_id)
                expected_qr = row_data['qr'].strip() if row_data else str(self.tree.item(item_id)['values'][2]).strip()
                s1 = str(self.current_box_scans["side1"]).strip()
                s2 = str(self.current_box_scans["side2"]).strip()
                self.current_box_scans = {"side1": None, "side2": None} # reset buffer untuk box berikutnya
                
                # Standar Keyence Error Strings
                keyence_errors = ["ERROR", "-ERROR-", "NG", "NOREAD", "NO-READ"]
                is_s1_err = (s1.upper() in keyence_errors)
                is_s2_err = (s2.upper() in keyence_errors)
                
                is_s1_ok = (not is_s1_err) and (s1 == expected_qr)
                is_s2_ok = (not is_s2_err) and (s2 == expected_qr)
                is_both_ok = (is_s1_ok and is_s2_ok)
                
                self.simulate_judge(is_ok=is_both_ok, side1_val=s1, side2_val=s2)
            else:
                # SISI PERTAMA MASUK: Pasang timer timeout menunggu sisi pasangannya
                self._cancel_dual_scan_timer()
                try:
                    timeout_ms = int(self.dual_scan_timeout_var.get().strip())
                except Exception:
                    timeout_ms = 2000
                self._dual_scan_timer_id = self.root.after(timeout_ms, self._on_dual_scan_timeout)
        else:
            # Single-scanner mode fallback (misal saat testing hanya 1 unit aktif)
            self._cancel_dual_scan_timer()
            item_id = self.waiting_queue[0]
            row_data = self.table_items_data.get(item_id)
            expected_qr = row_data['qr'].strip() if row_data else str(self.tree.item(item_id)['values'][2]).strip()
            val_scanned = scanned_text
            self.current_box_scans = {"side1": None, "side2": None}
            keyence_errors = ["ERROR", "-ERROR-", "NG", "NOREAD", "NO-READ"]
            is_err = (val_scanned.upper() in keyence_errors)
            is_ok = (not is_err) and (val_scanned == expected_qr)
            if scanner_id == 1:
                self.simulate_judge(is_ok=is_ok, side1_val=val_scanned, side2_val="(Scanner 2 Non-Aktif)")
            else:
                self.simulate_judge(is_ok=is_ok, side1_val="(Scanner 1 Non-Aktif)", side2_val=val_scanned)

    def simulate_judge(self, is_ok, side1_val=None, side2_val=None):
        """Mengevaluasi hasil inspeksi QC dan memutuskan OK atau Rejector Solenoid"""
        if not self.waiting_queue: return
        self._cancel_dual_scan_timer()
        item_id = self.waiting_queue.popleft()
        self.current_box_scans = {"side1": None, "side2": None} # Reset buffer jika ada sisa
        row_data = self.table_items_data.get(item_id)
        if row_data:
            box_no  = row_data['no']
            box_sku = row_data['sku']
            box_qr  = row_data['qr']
            box_mat = row_data['mat']
        else:
            val = self.tree.item(item_id)['values']
            box_no  = val[0]
            box_sku = str(val[1])
            box_qr  = str(val[2])
            box_mat = str(val[3])
        
        s1_str = str(side1_val) if side1_val is not None else ("OK" if is_ok else "NG")
        s2_str = str(side2_val) if side2_val is not None else ("OK" if is_ok else "NG")
        
        self.history_records.append({
            "Cycle": self.print_cycle,
            "Time Stamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "No": box_no, "SKU": box_sku, "QR": box_qr, "Matl Code": box_mat,
            "Status": "OK" if is_ok else "NG",
            "Scanner 1": s1_str,
            "Scanner 2": s2_str
        })
        
        if is_ok:
            self.consecutive_ng_count = 0
            self.cascade_warning_active = False
            self.count_ok += 1 
            if side1_val is not None or side2_val is not None:
                self.log_msg(f"[OK] No.{box_no} (S1: {s1_str} | S2: {s2_str})")
            else:
                self.log_msg(f"[OK] No.{box_no}")
            self.tree.item(item_id, tags=('ok',))
            self.tree.set(item_id, "status", "QC OK")
        else:
            self.count_ng += 1 
            self.consecutive_ng_count += 1
            if side1_val is not None or side2_val is not None:
                self.log_msg(f"[NG] No.{box_no} (S1: {s1_str} | S2: {s2_str})")
            else:
                self.log_msg(f"[NG] No.{box_no}")
            self.tree.item(item_id, tags=('ng',))
            self.tree.set(item_id, "status", "QC NG")
            self.schedule_box_rejection(box_no)
            self.ng_list.append(item_id) 
            
            # Deteksi potensi Cascade NG akibat pergeseran antrean fisik
            if self.consecutive_ng_count >= 3:
                self._warn_cascade_ng()
        
        self.update_live_stats()
        self.update_queue_ui()
        
        # TINGKATKAN COUNTER JUDGEMENT
        self.current_judgments += 1

        # Rekam ke mapping checkpoint & simpan ke disk secara incremental (Solusi 5)
        self.checkpoint_judged_map[str(box_no)] = {
            "status": "OK" if is_ok else "NG",
            "s1": s1_str,
            "s2": s2_str,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.save_current_checkpoint()
        
        # Kirim hasil QC real-time ke Sistem Utama via REST API (v2.0)
        if getattr(self, 'api_auto_sync_box', None) and self.api_auto_sync_box.get() and hasattr(self, 'api_manager'):
            box_payload = {
                "work_order_id": getattr(self, 'current_work_order_id', getattr(self, 'current_filename', '')),
                "box_no": box_no,
                "sku": box_sku,
                "qr": box_qr,
                "matl_code": box_mat,
                "status": "OK" if is_ok else "NG",
                "scanner1": s1_str,
                "scanner2": s2_str,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            b_url = self.api_base_url.get().strip() if hasattr(self, 'api_base_url') else None
            ep = self.api_endpoint_submit_box.get().strip() if hasattr(self, 'api_endpoint_submit_box') else None
            key = self.api_key.get().strip() if hasattr(self, 'api_key') else None
            try:
                tout = float(self.api_timeout.get().strip())
            except Exception:
                tout = 3.0
            threading.Thread(
                target=self.api_manager.send_box_qc,
                args=(box_payload, b_url, ep, key, tout),
                daemon=True
            ).start()
        
        # JIKA JUMLAH SCAN == JUMLAH DATA YANG DIKIRIM (LOAD)
        if self.current_judgments >= self.expected_total_judgments:
            self.finalize_batch()

    def manual_resync_queue(self, skip_confirm=False):
        """
        Koreksi antrean manual jika kardus fisik diangkat/jatuh sebelum scanner,
        mencegah desinkronisasi antrean FIFO (Cascade NG).
        """
        if not self.waiting_queue:
            if not skip_confirm:
                messagebox.showinfo("Antrean Kosong", "Tidak ada kardus dalam antrean transit (Queue: 0).")
            return False

        item_id = self.waiting_queue[0]
        row_data = self.table_items_data.get(item_id)
        if row_data:
            val = [row_data['no'], row_data['sku'], row_data['qr'], row_data['mat']]
        else:
            val = self.tree.item(item_id)['values']
        box_no = val[0]
        box_sku = val[1]

        if not skip_confirm:
            ans = messagebox.askyesno(
                "Koreksi Antrean Kardus",
                f"Keluarkan kardus No.{box_no} ({box_sku}) dari antrean software?\n\n"
                f"Gunakan fitur ini jika kardus fisik terjatuh/diambil dari konveyor sebelum mencapai scanner, "
                f"agar antrean data software kembali sinkron dengan kardus fisik berikutnya."
            )
            if not ans:
                return False

        # Keluarkan kardus terdepan dari queue
        self._cancel_dual_scan_timer()
        self.waiting_queue.popleft()
        self.current_box_scans = {"side1": None, "side2": None}
        self.consecutive_ng_count = 0  # Reset alarm cascade NG
        self.cascade_warning_active = False

        # Tandai di tabel dan riwayat
        self.count_ng += 1
        self.ng_list.append(item_id)
        self.tree.item(item_id, tags=('ng',))
        self.tree.set(item_id, "status", "Dilepas Manual")
        
        self.history_records.append({
            "Cycle": self.print_cycle,
            "Time Stamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "No": val[0], "SKU": val[1], "QR": val[2], "Matl Code": val[3],
            "Status": "REMOVED",
            "Scanner 1": "(Dilepas Manual)",
            "Scanner 2": "(Dilepas Manual)"
        })

        self.log_msg(f"[RESYNC] Kardus No.{box_no} ({box_sku}) dikeluarkan dari antrean software (Koreksi Desinkronisasi).")
        self.update_live_stats()
        self.update_queue_ui()

        # Update penghitungan judgment batch
        self.current_judgments += 1

        # Rekam ke mapping checkpoint & simpan ke disk (Solusi 5)
        self.checkpoint_judged_map[str(val[0])] = {
            "status": "REMOVED",
            "s1": "(Dilepas Manual)",
            "s2": "(Dilepas Manual)",
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.save_current_checkpoint()

        if self.current_judgments >= self.expected_total_judgments:
            self.finalize_batch()

        return True

    def _warn_cascade_ng(self):
        """Mendeteksi potensi Queue Desynchronization (Cascade NG) saat terjadi 3x NG beruntun"""
        if self.cascade_warning_active:
            return
        self.cascade_warning_active = True
        self.set_system_status("ALARM")
        self.log_msg(f"[ALARM DESINKRONISASI] Terdeteksi {self.consecutive_ng_count}x NG berturut-turut! Kemungkinan terjadi pergeseran antrean fisik/software.")
        
        def _show_dialog():
            try:
                ans = messagebox.askyesno(
                    "Peringatan: Potensi Desinkronisasi Antrean",
                    f"Terdeteksi {self.consecutive_ng_count}x status NG berturut-turut pada scanner!\n\n"
                    "Kemungkinan penyebab:\n"
                    "1. Ada kardus fisik yang terjatuh atau diangkat operator sebelum scanner.\n"
                    "2. Antrean data software bergeser (Queue Desync).\n\n"
                    "Apakah Anda ingin mengeluarkan 1 data terdepan (Koreksi Antrean -1) sekarang agar antrean kembali sinkron?\n"
                    "(Pilih 'No' jika Anda ingin memeriksa barcode fisik terlebih dahulu)",
                    parent=self.root
                )
                if ans:
                    self.manual_resync_queue(skip_confirm=True)
            finally:
                self.cascade_warning_active = False
                if getattr(self, 'is_printing', False):
                    self.set_system_status("RUNNING")
                else:
                    self.set_system_status("READY")

        self.root.after(100, _show_dialog)

    def finalize_batch(self):
        """Verifikasi akhir setelah semua ter-scan (dijalankan di background thread - S2)"""
        self.log_msg("-> Seluruh data telah di-Scan! Memvalidasi CSTATUS printer di background...")
        def _worker_finalize():
            time.sleep(1) # Jeda agar mesin sempat update memori CSTATUS nya
            current_count = self.get_current_print_count()
            if current_count >= self.expected_total_judgments:
                self.log_msg(f"   [V] PRINTER MATCH! (CSTATUS: {current_count} == Load: {self.expected_total_judgments})")
            else:
                self.log_msg(f"   [!] WARNING: CSTATUS Mesin ({current_count}) lebih kecil dari target ({self.expected_total_judgments}).")
            self.batch_completed = True
            self.root.after(0, self.check_completion)

        threading.Thread(target=_worker_finalize, daemon=True).start()

    def check_completion(self):
        if self.batch_completed and len(self.waiting_queue) == 0:
            if len(self.ng_list) > 0:
                ans = messagebox.askyesno("Reprint NG", f"Terdapat {len(self.ng_list)} NG (Reject).\nKlik YES untuk REPRINT.", parent=self.root)
                if ans:
                    self.print_cycle += 1 
                    self.log_msg(f"=== MEMULAI RE-PRINT CYCLE {self.print_cycle} ===")
                    
                    items_to_reprint = list(self.ng_list)
                    self.ng_list.clear()
                    
                    # --- EKSEKUSI REPRINT KILAT ---
                    self.send_and_read("CLR")
                    self.send_and_read("RESET|2")
                    # ------------------------------
                    
                    self.do_printing_loop(items_to_reprint)
                else:
                    self.log_msg("Proses Re-print dibatalkan.")
                    self.generate_history_excel() 
            else:
                self.log_msg("=== BATCH SELESAI 100% SUKSES ===")
                messagebox.showinfo("Sukses", "Semua data telah dicetak dan QC OK.", parent=self.root)
                self.generate_history_excel() 

    # ==========================================
    # 7. EXPORT EXCEL HISTORY & SMART FOLDER
    # ==========================================
    def generate_history_excel(self):
        if not self.history_records: return
        self.log_msg("Menyusun file Report Print History (Excel) di background thread (S2)...")
        
        target_total = getattr(self, 'total_valid_print_data', self.total_load_data)
        current_fn = self.current_filename
        cycle = self.print_cycle
        records = list(self.history_records)
        start_time = self.batch_start_time

        def _worker_save():
            success, msg_or_path = self.data_manager.save_history_excel(
                current_fn, target_total, cycle, records, start_time
            )
            def _on_done():
                if success:
                    self.log_msg(f"History tersimpan di: {msg_or_path}")
                    self.load_history_table()

                    # Reset status checkpoint aktif karena batch berhasil dituntaskan (Solusi 5)
                    self.resumed_checkpoint = None
                    self.checkpoint_judged_map = {}
                    self.data_manager.clear_batch_checkpoint()

                    # Kirim ringkasan produksi batch ke Sistem Utama via REST API (v2.0)
                    if getattr(self, 'api_auto_sync_batch', None) and self.api_auto_sync_batch.get() and hasattr(self, 'api_manager'):
                        batch_summary = {
                            "work_order_id": getattr(self, 'current_work_order_id', getattr(self, 'current_filename', '')),
                            "source_filename": current_fn,
                            "batch_start_time": start_time,
                            "batch_end_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "total_target": target_total,
                            "total_judged": getattr(self, 'current_judgments', len(records)),
                            "total_ok": self.count_ok,
                            "total_ng": self.count_ng,
                            "ng_rate_pct": round((self.count_ng / max(1, (self.count_ok + self.count_ng))) * 100, 2),
                            "operator": self.current_user.get("username", "Admin") if hasattr(self, 'current_user') and self.current_user else "Admin",
                            "records_count": len(records)
                        }
                        b_url = self.api_base_url.get().strip() if hasattr(self, 'api_base_url') else None
                        ep = self.api_endpoint_submit_batch.get().strip() if hasattr(self, 'api_endpoint_submit_batch') else None
                        key = self.api_key.get().strip() if hasattr(self, 'api_key') else None
                        try:
                            tout = float(self.api_timeout.get().strip())
                        except Exception:
                            tout = 5.0
                        def _send_batch_api():
                            ok, res = self.api_manager.send_batch_summary(
                                batch_summary,
                                base_url=b_url,
                                endpoint=ep,
                                api_key=key,
                                timeout=tout
                            )
                            if ok:
                                self.log_msg(f"[API] Sukses sinkronisasi ringkasan batch ke Sistem Utama.")
                            else:
                                self.log_msg(f"[API WARNING] Gagal sinkronisasi batch ke Sistem Utama: {res}")
                        threading.Thread(target=_send_batch_api, daemon=True).start()

                    # --- STOP & CLR SETELAH HISTORY TERSIMPAN DI BACKGROUND ---
                    def _printer_cleanup():
                        self.log_msg("-> Membersihkan memory/cache (CLR)...")
                        self.send_and_read("CLR")
                        time.sleep(0.5)
                        self.log_msg("-> Menampilkan Dummy Data (Standby)...")
                        dummy_payload = "MFD|SKU01:STANDBY|QRC02:QR Selesai|MAT03:xxxxxxxxx\r\n"
                        self.send_and_read(dummy_payload)
                        self.log_msg("-> Mematikan Mode Print (STOP)...")
                        self.send_and_read("STOP")
                    threading.Thread(target=_printer_cleanup, daemon=True).start()

                    messagebox.showinfo("Report Tersimpan", "History telah disimpan di tab Print History.", parent=self.root)
                else:
                    self.log_msg(f"ERROR Export Excel: {msg_or_path}")
            self.root.after(0, _on_done)

        threading.Thread(target=_worker_save, daemon=True).start()

    def save_current_checkpoint(self):
        """Menyimpan progres batch saat ini ke storage lokal secara incremental (Solusi 5)"""
        if not getattr(self, 'current_filename', None):
            return
        try:
            target_total = getattr(self, 'total_valid_print_data', self.total_load_data)
            cp_data = {
                "source_filename": self.current_filename,
                "batch_start_time": self.batch_start_time,
                "print_cycle": self.print_cycle,
                "total_load_data": self.total_load_data,
                "total_valid_print_data": target_total,
                "current_judgments": self.current_judgments,
                "stat_ok": self.count_ok,
                "stat_ng": self.count_ng,
                "judged_indices": self.checkpoint_judged_map,
                "history_records": list(self.history_records),
                "is_active": True,
                "last_updated": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            self.data_manager.save_batch_checkpoint(cp_data)
        except Exception as e:
            print(f"Error saving checkpoint: {e}")

    def schedule_box_rejection(self, box_no):
        """Mendaftarkan kardus NG ke antrean penolakan pusher (sinkronisasi sensor lepas + delay 80cm)"""
        self.ng_boxes_waiting_reject.append({
            "box_no": box_no,
            "timestamp": time.time()
        })
        self.log_msg(f"-> Kardus No.{box_no} (NG): Terdaftar. Menunggu ekor kardus lepas dari sensor scanner...")
        
        # Fallback jika monitoring Modbus I/O tidak aktif atau dalam Mode Simulasi:
        if not getattr(self, 'is_io_running', False) or self.is_simulation.get():
            try:
                delay_ms = int(self.pusher_delay_var.get().strip())
            except Exception:
                delay_ms = 2000
            # Estimasi waktu kardus 60cm melintas keluar scanner (~2.4s) + delay pusher (~2.0s ke 80cm)
            total_fallback_ms = 2400 + delay_ms
            self.log_msg(f"-> [FALLBACK TIMING] Jadwal pemicuan pusher: {total_fallback_ms} ms (Simulasi / Sensor Non-Aktif).")
            try:
                self.root.after(total_fallback_ms, self._execute_rejection_pusher)
            except Exception:
                pass

    def trigger_rejector(self):
        """Memicu penolakan langsung (kompatibilitas & manual)"""
        self._execute_rejection_pusher()

    def _execute_rejection_pusher(self):
        """Mengeksekusi silinder pneumatik pusher (DO 0) & Tower Lamp Merah (DO 1) saat kardus tiba tepat di rejector"""
        slave = self.slave_id.get()
        try:
            pulse_sec = float(self.pusher_pulse_var.get().strip()) / 1000.0
        except Exception:
            pulse_sec = 0.5

        if self.is_simulation.get():
            self.log_msg(f"-> [SIMULASI] PUSHER STROKE! Silinder DO 0 mendorong kardus NG (Durasi pulsa: {pulse_sec*1000:.0f} ms).")
            if hasattr(self, 'do_leds') and len(self.do_leds) >= 2:
                self.do_leds[0].config(bg="#ff0000")
                self.do_leds[1].config(bg="#ff0000")
                try:
                    self.root.after(int(pulse_sec * 1000), lambda: [
                        self.do_leds[0].config(bg="grey"),
                        self.do_leds[1].config(bg="grey")
                    ])
                except Exception:
                    pass
            return

        mode = self.modbus_mode.get()
        self.log_msg(f"-> [AKTUAL] PUSHER STROKE ({mode})! Memicu Solenoid DO 0 ({pulse_sec}s) & Tower Lamp Merah DO 1...")
        def _on_pusher_done(ok, msg):
            if not ok:
                self.log_msg(f"[PERINGATAN PUSHER] Gagal memicu Solenoid Pusher DO 0! ({msg})")

        try:
            if mode == "TCP":
                ip = self.modbus_ip.get()
                port = self.modbus_port.get()
                self.modbus.pulse_coil_tcp(ip, port, address=0, duration=pulse_sec, slave_id=slave, on_complete=_on_pusher_done)
                self.modbus.pulse_coil_tcp(ip, port, address=1, duration=1.5, slave_id=slave)
            else:
                com = self.modbus_com.get()
                baud = self.modbus_baud.get()
                parity = self.modbus_parity.get()
                stopbits = self.modbus_stopbits.get()
                databits = self.modbus_databits.get()
                self.modbus.pulse_coil_rtu(com, baud, parity, stopbits, databits, address=0, duration=pulse_sec, slave_id=slave, on_complete=_on_pusher_done)
                self.modbus.pulse_coil_rtu(com, baud, parity, stopbits, databits, address=1, duration=1.5, slave_id=slave)
        except Exception as e:
            self.log_msg(f"ERROR saat memicu rejector: {e}")

    def manual_test_rejector(self):
        """Tombol uji coba manual rejector & alarm langsung ke Modbus Slave"""
        mode = self.modbus_mode.get()
        slave = self.slave_id.get()
        self.log_msg(f"-> [TEST MANUAL] Menguji pulsa Coil Modbus (DO 0 Rejector & DO 1 Alarm) ke mode {mode}...")

        # Visual feedback langsung di GUI LED
        if hasattr(self, 'do_leds') and len(self.do_leds) >= 2:
            self.do_leds[0].config(bg="#ffcc00")
            self.do_leds[1].config(bg="#ff0000")
            self.root.after(800, lambda: [
                self.do_leds[0].config(bg="grey"),
                self.do_leds[1].config(bg="grey")
            ])

        success = False
        msg = ""

        try:
            if mode == "TCP":
                ip = self.modbus_ip.get()
                port = self.modbus_port.get()
                # Test tulis Coil 0 (Solenoid)
                ok0, msg0 = self.modbus.write_coil_tcp(ip, port, address=0, value=True, slave_id=slave)
                ok1, msg1 = self.modbus.write_coil_tcp(ip, port, address=1, value=True, slave_id=slave)
                
                # Kembalikan ke OFF setelah jeda sebentar
                def _turn_off():
                    time.sleep(0.6)
                    self.modbus.write_coil_tcp(ip, port, address=0, value=False, slave_id=slave)
                    self.modbus.write_coil_tcp(ip, port, address=1, value=False, slave_id=slave)
                threading.Thread(target=_turn_off, daemon=True).start()
                
                success = ok0 and ok1
                msg = msg0 if not ok0 else (msg1 if not ok1 else "Pulsa Coil 0 (Rejector) & Coil 1 (Alarm) berhasil dikirim!")
            else:
                com = self.modbus_com.get()
                baud = self.modbus_baud.get()
                parity = self.modbus_parity.get()
                stopbits = self.modbus_stopbits.get()
                databits = self.modbus_databits.get()
                ok0, msg0 = self.modbus.write_coil_rtu(com, baud, parity, stopbits, databits, address=0, value=True, slave_id=slave)
                ok1, msg1 = self.modbus.write_coil_rtu(com, baud, parity, stopbits, databits, address=1, value=True, slave_id=slave)
                
                def _turn_off_rtu():
                    time.sleep(0.6)
                    self.modbus.write_coil_rtu(com, baud, parity, stopbits, databits, address=0, value=False, slave_id=slave)
                    self.modbus.write_coil_rtu(com, baud, parity, stopbits, databits, address=1, value=False, slave_id=slave)
                threading.Thread(target=_turn_off_rtu, daemon=True).start()

                success = ok0 and ok1
                msg = msg0 if not ok0 else (msg1 if not ok1 else "Pulsa Coil 0 & 1 RTU berhasil dikirim!")

            if success:
                self.log_msg(f"✓ Test Modbus DO Berhasil: {msg}")
                messagebox.showinfo(
                    "Test Rejector Berhasil",
                    f"{msg}\n\n"
                    "📌 PENTING PADA MODBUS SLAVE SIMULATOR:\n"
                    "Pastikan di aplikasi simulator Anda membuka tampilan:\n"
                    "-> '01: COIL STATUS' (Function 01 / Coils 00001 & 00002),\n"
                    "BUKAN 'Holding Registers' (karena Holding Register adalah tabel angka 16-bit, bukan saklar ON/OFF bit)."
                )
            else:
                self.log_msg(f"❌ Test Modbus DO Gagal: {msg}")
                messagebox.showerror("Test Rejector Gagal", f"Gagal mengirim sinyal ke Modbus Slave:\n{msg}")

        except Exception as e:
            self.log_msg(f"❌ Exception Test Rejector: {e}")
            messagebox.showerror("Error", f"Terjadi kesalahan:\n{e}")

    def manual_test_alarm(self):
        """Tombol uji coba manual Tower Lamp Merah / Alarm (DO 1)"""
        mode = self.modbus_mode.get()
        slave = self.slave_id.get()
        self.log_msg(f"-> [TEST MANUAL] Menguji pulsa Tower Lamp Merah (DO 1 Alarm) ke mode {mode}...")

        # Visual feedback di GUI
        if hasattr(self, 'do_leds') and len(self.do_leds) >= 2:
            self.do_leds[1].config(bg="#ff0000")
            self.root.after(1000, lambda: self.do_leds[1].config(bg="grey"))

        try:
            if mode == "TCP":
                ip = self.modbus_ip.get()
                port = self.modbus_port.get()
                self.modbus.pulse_coil_tcp(ip, port, address=1, duration=1.0, slave_id=slave)
            else:
                com = self.modbus_com.get()
                baud = self.modbus_baud.get()
                parity = self.modbus_parity.get()
                stopbits = self.modbus_stopbits.get()
                databits = self.modbus_databits.get()
                self.modbus.pulse_coil_rtu(com, baud, parity, stopbits, databits, address=1, duration=1.0, slave_id=slave)

            self.log_msg("✓ Pulsa Tower Lamp Merah (DO 1) berhasil dikirim (durasi 1.0 detik).")
            messagebox.showinfo("Test Alarm Lampu", "Sinyal pulsa Tower Lamp Merah / Alarm (DO 1) berhasil dikirim ke Modbus!")
        except Exception as e:
            self.log_msg(f"❌ Error test alarm: {e}")
            messagebox.showerror("Error", f"Gagal mengirim sinyal alarm:\n{e}")

    # ==========================================
    # 8. LIVE STATUS DASHBOARD
    # ==========================================
    
    def reset_stats(self):
        self.count_ok = 0
        self.count_ng = 0
        self.stat_ok.set("0")
        self.stat_ng.set("0")
        self.stat_progress.set("0 %")
        if hasattr(self, 'draw_progress_gauge'):
            self.draw_progress_gauge(0, getattr(self, 'total_load_data', 0), 0)

    def update_live_stats(self):
        def _upd():
            target_total = getattr(self, 'total_valid_print_data', self.total_load_data)
            total = target_total if target_total > 0 else 1
            processed = self.count_ok + self.count_ng
            percent = int((processed / total) * 100)
            self.stat_ok.set(str(self.count_ok))
            self.stat_ng.set(str(self.count_ng))
            self.stat_progress.set(f"{percent} %")
            if hasattr(self, 'draw_progress_gauge'):
                self.draw_progress_gauge(processed, target_total, percent)
        if threading.current_thread() is threading.main_thread():
            _upd()
        else:
            self.root.after(0, _upd)
        
    #=========================
    # 9. MODBUS AREA
    #=========================
    def on_modbus_mode_change(self, event):
        """ Logika untuk mengganti tampilan setting Modbus (TCP vs RTU) """
        for widget in self.modbus_settings_container.winfo_children():
            widget.destroy()

        mode = self.modbus_mode.get()
        
        if mode == "TCP":
            f = ttk.Frame(self.modbus_settings_container)
            f.pack(fill=tk.X)
            ttk.Label(f, text="Modbus IP:").pack(side=tk.LEFT)
            ttk.Entry(f, textvariable=self.modbus_ip, width=15).pack(side=tk.LEFT, padx=5)
            ttk.Label(f, text="Port:").pack(side=tk.LEFT)
            ttk.Entry(f, textvariable=self.modbus_port, width=7).pack(side=tk.LEFT, padx=5)
            ttk.Button(f, text="Test Modbus TCP", command=self.test_modbus_connection).pack(side=tk.LEFT, padx=10)
        
        else: # MODE RTU (SERIAL SETTINGS)
            # Frame utama Serial Settings
            s_frame = ttk.LabelFrame(self.modbus_settings_container, text=" Serial Settings ", padding="10")
            s_frame.pack(fill=tk.X, pady=5)

            # Baris 1: COM Port
            ttk.Combobox(s_frame, textvariable=self.modbus_com, 
                         values=["COM1", "COM2", "COM3", "COM4", "COM5"], width=40).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=5)

            # Baris 2: Baudrate & Mode
            ttk.Combobox(s_frame, textvariable=self.modbus_baud, 
                         values=["4800", "9600", "19200", "38400", "115200"], width=15).grid(row=1, column=0, sticky=tk.W, pady=2)
            
            m_frame = ttk.LabelFrame(s_frame, text=" Mode ")
            m_frame.grid(row=1, column=1, rowspan=2, padx=10, sticky=tk.NW)
            ttk.Radiobutton(m_frame, text="RTU", variable=self.modbus_serial_mode, value="RTU").pack(side=tk.LEFT, padx=5)
            ttk.Radiobutton(m_frame, text="ASCII", variable=self.modbus_serial_mode, value="ASCII").pack(side=tk.LEFT, padx=5)

            # Baris 3: Data Bits
            ttk.Combobox(s_frame, textvariable=self.modbus_databits, 
                         values=["7", "8"], width=15).grid(row=2, column=0, sticky=tk.W, pady=2)

            # Baris 4: Parity
            ttk.Combobox(s_frame, textvariable=self.modbus_parity, 
                         values=["None", "Even", "Odd", "Mark", "Space"], width=15).grid(row=3, column=0, sticky=tk.W, pady=2)

            # Baris 5: Stop Bits & Button
            ttk.Combobox(s_frame, textvariable=self.modbus_stopbits, 
                         values=["1", "1.5", "2"], width=15).grid(row=4, column=0, sticky=tk.W, pady=2)
            
            ttk.Button(s_frame, text="Test Modbus RTU", command=self.test_modbus_rtu).grid(row=4, column=1, padx=10, sticky=tk.E)

    def test_modbus_connection(self):
        """Mencoba koneksi ke Modbus Slave Simulator secara non-blocking di worker thread (S2)"""
        ip = self.modbus_ip.get().strip()
        port = self.modbus_port.get().strip()
        slave = self.slave_id.get()
        self.log_msg(f"Mencoba koneksi Modbus ke {ip}:{port}...")
        def _worker_mb():
            success, msg = self.modbus.test_tcp(ip, port, slave)
            def _on_done():
                if success:
                    self.log_msg(f"Modbus Berhasil! {msg}")
                    messagebox.showinfo("Modbus Success", msg, parent=self.root)
                else:
                    self.log_msg(msg)
                    messagebox.showerror("Modbus Error", msg, parent=self.root)
            self.root.after(0, _on_done)
        threading.Thread(target=_worker_mb, daemon=True).start()
            
    def test_modbus_rtu(self):
        """Mencoba koneksi RTU secara non-blocking di worker thread (S2)"""
        com = self.modbus_com.get()
        baud = self.modbus_baud.get()
        parity = self.modbus_parity.get()
        stopbits = self.modbus_stopbits.get()
        databits = self.modbus_databits.get()
        slave = self.slave_id.get()
        self.log_msg(f"Mencoba koneksi RTU via {com}...")
        def _worker_rtu():
            success, msg = self.modbus.test_rtu(com, baud, parity, stopbits, databits, slave)
            def _on_done():
                if success:
                    self.log_msg(f"RTU OK! {msg}")
                    messagebox.showinfo("RTU OK", msg, parent=self.root)
                else:
                    self.log_msg(msg)
                    messagebox.showerror("RTU Error", msg, parent=self.root)
            self.root.after(0, _on_done)
        threading.Thread(target=_worker_rtu, daemon=True).start()
               
#------------------- modbus DI DO
    def toggle_io_monitoring(self):
        """Aktifkan/Matikan pemantauan I/O"""
        if not hasattr(self, 'is_io_running'): self.is_io_running = False
        
        if not self.is_io_running:
            self.is_io_running = True
            self.btn_io_connect.config(text="Stop Monitor")
            threading.Thread(target=self.io_monitor_loop, daemon=True).start()
        else:
            self.is_io_running = False
            self.btn_io_connect.config(text="Start Monitor")
            # Tutup koneksi persistent Modbus agar port dilepas
            self.modbus.close_all()

    def io_monitor_loop(self):
        """Looping I/O yang meminta data bersih dari modbus_io.py (Thread-safe snapshot - S1)"""
        mode = self.modbus_mode.get()
        slave = self.slave_id.get()
        ip = self.modbus_ip.get().strip()
        port = self.modbus_port.get().strip()
        com = self.modbus_com.get().strip()
        baud = self.modbus_baud.get().strip()
        parity = self.modbus_parity.get().strip()
        stopbits = self.modbus_stopbits.get().strip()
        databits = self.modbus_databits.get().strip()
        self.log_msg(f"Monitoring I/O started ({mode})...")
        
        while self.is_io_running:
            if mode == "TCP":
                success, di_bits, do_bits, err = self.modbus.read_io_tcp(
                    ip, port, slave
                )
            else:
                success, di_bits, do_bits, err = self.modbus.read_io_rtu(
                    com, baud, parity, stopbits, databits, slave
                )
                
            if success:
                self.modbus_fail_count = 0
                if getattr(self, 'modbus_alarm_active', False):
                    self.modbus_alarm_active = False
                    self.log_msg("[MODBUS] Komunikasi I/O Modbus pulih kembali normal.")
                # Update LED di GUI (Harus via main thread / root.after)
                try:
                    self.root.after(0, lambda d=di_bits, o=do_bits: self.update_led_ui(d, o))
                except Exception:
                    pass
                # Analisis Trailing Edge Sensor Scanner & Interlock Safety
                self._process_di_signals(di_bits)
            else:
                self.modbus_fail_count += 1
                if self.modbus_fail_count >= 3:
                    # Fail-Safe: Jika I/O terputus saat cetak, interlock safety & rejector tidak bisa dijamin!
                    if getattr(self, 'is_printing', False) and not self.is_simulation.get():
                        if not getattr(self, 'modbus_alarm_active', False):
                            self.modbus_alarm_active = True
                            self.interlock_alarm_active = True
                            self.pause_requested = True
                            self.log_msg(f"[ALARM KRITIS MODBUS] Komunikasi I/O terputus {self.modbus_fail_count}x berturut-turut ({err})! Batch otomatis di-PAUSE (Fail-Safe).")
                            self._sync_pause_button_ui()
                print(f"[MODBUS] {err}")
                
            time.sleep(0.08) # Polling presisi tinggi untuk deteksi transisi sensor

    def _process_di_signals(self, di_bits):
        """Memproses sinyal digital input (Sensor Scanner, Safety Interlock, Debounce)"""
        # 1. Pengecekan Interlock Safety / Tekanan Angin Drop (DI 3)
        is_safety_ok = di_bits[3]
        if not is_safety_ok and getattr(self, 'is_printing', False) and not self.is_simulation.get():
            if not getattr(self, 'interlock_alarm_active', False):
                self.interlock_alarm_active = True
                self.log_msg("[ALARM INTERLOCK] Tekanan Angin Drop / E-Stop Aktif (DI 3 OFF)! Batch di-PAUSE otomatis.")
                self.pause_requested = True
                self._sync_pause_button_ui()
        elif is_safety_ok:
            self.interlock_alarm_active = False

        # 2. Deteksi Trailing Edge Sensor Scanner (DI 1: True -> False / "Sudah tidak terdeteksi")
        # Menandakan ekor kardus 60 cm baru saja lepas dari area scanner
        curr_scanner_sensor = di_bits[1]
        prev_scanner_sensor = getattr(self, 'last_scanner_sensor_state', False)
        now = time.time()

        # Deteksi transisi falling edge dengan debounce filter (min 200 ms)
        if prev_scanner_sensor and not curr_scanner_sensor:
            if (now - getattr(self, 'last_sensor_fall_time', 0)) > 0.2:
                self.last_sensor_fall_time = now
                self.log_msg("-> [SENSOR SCANNER] Ekor kardus lepas dari area scanner (sudah tidak terdeteksi).")

                # Watchdog Scanner (T2): Jika kardus fisik lepas dari scanner tapi kedua scanner tidak membaca apa pun (No Read)
                if getattr(self, 'is_printing', False) and self.waiting_queue:
                    s1 = self.current_box_scans.get("side1")
                    s2 = self.current_box_scans.get("side2")
                    if s1 is None and s2 is None:
                        self.log_msg("[SCANNER WATCHDOG] Kardus terdeteksi lewat tapi kedua scanner TIDAK membaca barcode (No Read). Menilai NG otomatis.")
                        try:
                            self.root.after(0, lambda: self.simulate_judge(is_ok=False, side1_val="(No Read)", side2_val="(No Read)"))
                        except Exception as ex_w:
                            print(f"Error scanner watchdog simulate judge: {ex_w}")

                # Cek apakah ada kardus NG dalam antrean yang menunggu dorongan pusher
                if self.ng_boxes_waiting_reject:
                    target_box = self.ng_boxes_waiting_reject.popleft()
                    box_no = target_box.get("box_no", "?")
                    try:
                        delay_ms = int(self.pusher_delay_var.get().strip())
                    except Exception:
                        delay_ms = 2000
                    self.log_msg(f"-> Kardus No.{box_no} (NG): Menghitung tunda gerak {delay_ms} ms menuju silinder pusher 80 cm...")
                    try:
                        self.root.after(delay_ms, self._execute_rejection_pusher)
                    except Exception:
                        pass

        self.last_scanner_sensor_state = curr_scanner_sensor

    def update_led_ui(self, di_bits, do_bits):
        """Mengubah warna kotak LED di GUI berdasarkan status bit"""
        # DI LED (Discrete Inputs)
        for i in range(4):
            # Jika bit bernilai True/1, warna Hijau, jika False/0, warna Abu-abu
            color = "#00ff00" if di_bits[i] else "grey" 
            self.di_leds[i].config(bg=color)

        # DO LED (Coils)
        for i in range(4):
            # Jika bit bernilai True/1, warna Oranye/Kuning, jika False/0, warna Abu-abu
            color = "#ffcc00" if do_bits[i] else "grey"
            self.do_leds[i].config(bg=color)
    
    # ==================
    # WEB ANALITIK
    # ==================
    def open_web_analytics(self):
        """ Menjalankan Flask Server lewat modul terpisah """
        if not os.path.exists(self.history_log_file):
            return messagebox.showwarning("Data Kosong", "Belum ada histori produksi.")
        
        if not hasattr(self, 'flask_instance'):
            # Buat instance dari class di file sebelah
            self.flask_instance = AnalyticsServer(self.history_log_file)
            self.flask_thread = threading.Thread(
                target=lambda: self.flask_instance.run(port=5022), 
                daemon=True
            )
            self.flask_thread.start()
            self.log_msg("Memulai Web Server di port 5022 (Modular Mode)...")
            self.root.after(1500, lambda: [
                self.log_msg("Membuka Dashboard Analitik."),
                webbrowser.open("http://127.0.0.1:5022")
            ])
            return

        self.log_msg("Membuka Dashboard Analitik.")
        webbrowser.open("http://127.0.0.1:5022")

    # ==========================================
    # 6. INTEGRASI REST API SISTEM UTAMA (v2.0)
    # ==========================================
    def _on_api_enable_toggle(self):
        """Handler saat checkbox aktifasi integrasi API diubah oleh operator"""
        is_en = bool(self.api_enabled.get())
        if hasattr(self, 'api_manager'):
            self.api_manager.config["api_enabled"] = is_en
        self.update_hardware_indicators()
        status_str = "Diaktifkan" if is_en else "Dinonaktifkan"
        self.log_msg(f"[API] Integrasi API Sistem Utama {status_str}.")

    def test_api_connection(self):
        """Uji koneksi ping / health-check HTTP ke Sistem Utama secara non-blocking (S2)"""
        base_url = self.api_base_url.get().strip()
        api_key = self.api_key.get().strip()
        try:
            timeout_sec = float(self.api_timeout.get().strip())
        except Exception:
            timeout_sec = 5.0

        self.api_status_text.set("⟳ Menghubungkan...")
        if hasattr(self, 'lbl_api_status'):
            self.lbl_api_status.config(fg="#f59e0b", bg="#fef3c7")
        self.log_msg(f"[API] Menguji koneksi HTTP ke Sistem Utama: {base_url}...")

        def _worker():
            success, msg, latency = self.api_manager.test_connection(base_url, api_key, timeout_sec)
            def _on_done():
                if success:
                    self.api_status_text.set(f"● Online ({latency:.0f} ms)")
                    if hasattr(self, 'lbl_api_status'):
                        self.lbl_api_status.config(fg="#10b981", bg="#ecfdf5")
                    self.log_msg(f"[API] Terhubung ke Sistem Utama! Latensi: {latency:.1f} ms. {msg}")
                    messagebox.showinfo(
                        "Koneksi API Berhasil",
                        f"Berhasil terhubung ke Sistem Utama!\n\n"
                        f"Base URL: {base_url}\n"
                        f"Latensi Jaringan: {latency:.1f} ms\n"
                        f"Respon: {msg}",
                        parent=self.root
                    )
                else:
                    self.api_status_text.set("○ Offline / Gagal")
                    if hasattr(self, 'lbl_api_status'):
                        self.lbl_api_status.config(fg="#ef4444", bg="#fef2f2")
                    self.log_msg(f"[API GAGAL] {msg}")
                    messagebox.showerror(
                        "Koneksi API Gagal",
                        f"Tidak dapat menjangkau Sistem Utama:\n\n{msg}\n\n"
                        f"Tips:\n"
                        f"- Pastikan server ERP / MES aktif di port yang benar.\n"
                        f"- Periksa kabel LAN atau rute jaringan ke host {base_url}.\n"
                        f"- Jika server belum online, gunakan opsi 'Load File' Excel sebagai cadangan.",
                        parent=self.root
                    )
                self.update_hardware_indicators()
            self.root.after(0, _on_done)

        threading.Thread(target=_worker, daemon=True).start()

    def start_api_server(self):
        """Menjalankan Embedded REST API & Analytics Server (Port 5022) di background thread"""
        try:
            if not hasattr(self, 'flask_instance'):
                self.flask_instance = AnalyticsServer(
                    history_log_file=self.history_log_file,
                    app_status_callback=self.get_system_status_dict,
                    work_order_callback=self.on_work_order_pushed
                )
                self.flask_thread = threading.Thread(
                    target=lambda: self.flask_instance.run(port=5022),
                    daemon=True
                )
                self.flask_thread.start()
                self.log_msg("[API SERVER] Embedded REST API & Analytics Server berjalan di http://0.0.0.0:5022")
        except Exception as e:
            self.log_msg(f"[API SERVER WARNING] Inisialisasi API server: {e}")

    def get_system_status_dict(self):
        """Data telemetri mesin real-time yang disajikan untuk Sistem Utama via GET /api/v1/status"""
        try:
            is_sim = self.check_is_simulation()
            target_total = getattr(self, 'total_valid_print_data', getattr(self, 'total_load_data', 0))
            judged = getattr(self, 'current_judgments', 0)
            pct = round((judged / max(1, target_total)) * 100, 1) if target_total > 0 else 0.0

            return {
                "system_status": getattr(self, 'active_sys_status', 'READY'),
                "mode_simulasi": is_sim,
                "current_work_order": getattr(self, 'current_work_order_id', ''),
                "current_file": getattr(self, 'current_filename', ''),
                "batch_start_time": getattr(self, 'batch_start_time', '-'),
                "progress": {
                    "total_target": target_total,
                    "judged": judged,
                    "count_ok": getattr(self, 'count_ok', 0),
                    "count_ng": getattr(self, 'count_ng', 0),
                    "progress_percent": pct
                },
                "hardware": {
                    "printer_online": is_sim or getattr(self, 'printer_connected', False),
                    "scanner1_online": getattr(self, 'is_listening1', False),
                    "scanner2_online": getattr(self, 'is_listening2', False),
                    "modbus_online": getattr(self, 'modbus_connected', False),
                    "upstream_api_online": getattr(self.api_manager, 'is_connected', False)
                },
                "operator": self.current_user.get("username", "Admin") if hasattr(self, 'current_user') and self.current_user else "Admin",
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    def on_work_order_pushed(self, payload):
        """Handler saat Sistem Utama mengirim POST /api/v1/work-order/push ke Omega MX"""
        def _handle_push():
            wo_id = payload.get("work_order_id", "Unknown")
            sku = payload.get("sku_code", "")
            qty = payload.get("target_qty", len(payload.get("items", [])))
            msg = (
                f"Sistem Utama (ERP / MES) me-push Work Order baru ke mesin ini!\n\n"
                f"• No. Work Order: {wo_id}\n"
                f"• SKU: {sku}\n"
                f"• Target Produksi: {qty} Box\n\n"
                f"Apakah Anda ingin memuat data ini ke antrean cetak & QC sekarang?"
            )
            if messagebox.askyesno("Work Order Baru Diterima (API Push)", msg, parent=self.root):
                self._apply_work_order_to_production(payload)
        self.root.after(0, _handle_push)

    def _apply_work_order_to_production(self, wo):
        """Menerapkan payload Work Order dari API ke DataFrame dan antrean produksi"""
        try:
            res = self.api_manager.parse_work_order_to_dataframe(wo)
            if isinstance(res, tuple):
                df, parse_msg = res
            else:
                df = res

            if df is None or len(df) == 0:
                messagebox.showwarning("Data Kosong", "Work Order tidak memiliki data item untuk diproduksi.", parent=self.root)
                return False

            wo_id = str(wo.get("work_order_id", "WO_BATCH"))
            sku_code = str(wo.get("sku_code", "SKU"))

            self.df = df
            self.current_filename = f"API_{wo_id}_{sku_code}"
            self.current_work_order_id = wo_id
            self.total_load_data = len(self.df)
            self.stat_total.set(str(self.total_load_data))

            if hasattr(self, 'lbl_file_chip'):
                self.lbl_file_chip.config(text=f"API: {wo_id} ({sku_code})")
            if hasattr(self, 'draw_progress_gauge'):
                self.draw_progress_gauge(0, self.total_load_data, 0)

            self.resumed_checkpoint = None
            self.checkpoint_judged_map = {}
            self.reset_stats()

            cols = self.df.columns.tolist()
            self.cb_sku['values'] = cols
            self.cb_qr['values'] = cols
            self.cb_matl['values'] = cols

            # Deteksi cerdas kolom (cocok dengan format Excel: ProductSKU, CouponCode_R1, MaterialCode)
            sku_cand = next((c for c in cols if any(k in c.lower() for k in ["productsku", "sku"])), cols[0] if cols else "")
            qr_cand = next((c for c in cols if any(k in c.lower() for k in ["couponcode_r1", "coupon", "qr", "kupon"])), cols[1] if len(cols) > 1 else "")
            mat_cand = next((c for c in cols if any(k in c.lower() for k in ["materialcode", "matl", "material", "mat"])), cols[2] if len(cols) > 2 else "")

            if sku_cand: self.sel_sku.set(sku_cand)
            if qr_cand: self.sel_qr.set(qr_cand)
            if mat_cand: self.sel_matl.set(mat_cand)

            self.update_table()
            self.log_msg(f"[API] Berhasil memuat data Work Order: {wo_id} ({self.total_load_data} item)")

            threading.Thread(target=self.auto_start_printer, daemon=True).start()

            if not (getattr(self, 'is_listening1', False) or getattr(self, 'is_listening2', False)):
                ans = messagebox.askyesno(
                    "Load API Sukses",
                    f"Work Order {wo_id} ({self.total_load_data} item) siap diproduksi.\n"
                    f"Hubungkan Scanner Keyence (Dual Scanner) sekarang?",
                    parent=self.root
                )
                if ans:
                    self.connect_all_scanners()
            return True
        except Exception as e:
            messagebox.showerror("Gagal Memuat Work Order", f"Error memproses data API:\n{e}", parent=self.root)
            self.log_msg(f"[API ERROR] Gagal memuat data Work Order: {e}")
            return False

    def open_fetch_api_dialog(self):
        """Membuka dialog modal untuk menarik daftar Work Order aktif dari API Sistem Utama"""
        win = tk.Toplevel(self.root)
        win.title("Tarik Work Order dari Sistem Utama (ERP / MES)")
        win.geometry("860x520")
        win.minsize(780, 440)
        win.transient(self.root)
        win.grab_set()

        # Center window
        win.update_idletasks()
        w = win.winfo_width(); h = win.winfo_height()
        x = max(0, (win.winfo_screenwidth() // 2) - (w // 2))
        y = max(0, (win.winfo_screenheight() // 2) - (h // 2))
        win.geometry(f"{w}x{h}+{x}+{y}")

        # Top Bar
        top_f = tk.Frame(win, bg="#0f172a", padx=16, pady=12)
        top_f.pack(fill=tk.X)

        tk.Label(
            top_f,
            text="Integrasi API Sistem Utama - Pemilihan Work Order (SPK)",
            font=("Segoe UI", 11, "bold"),
            fg="#f8fafc",
            bg="#0f172a"
        ).pack(anchor="w")

        base_url_display = self.api_base_url.get().strip() or "http://192.168.1.50:8000/api/v1"
        tk.Label(
            top_f,
            text=f"Target Server: {base_url_display}{self.api_endpoint_work_orders.get().strip()}",
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg="#0f172a"
        ).pack(anchor="w", pady=(2, 0))

        # Main Content
        body_f = ttk.Frame(win, padding="12")
        body_f.pack(fill=tk.BOTH, expand=True)

        # Toolbar & Filter
        tb_f = ttk.Frame(body_f)
        tb_f.pack(fill=tk.X, pady=(0, 8))

        lbl_status_fetch = ttk.Label(tb_f, text="Menyiapkan koneksi...", font=("Segoe UI", 9, "italic"))
        lbl_status_fetch.pack(side=tk.LEFT)

        btn_refresh = ttk.Button(tb_f, text="⟳ Ambil Ulang Data API")
        btn_refresh.pack(side=tk.RIGHT)

        # Treeview Daftar WO
        columns = ("wo_id", "sku_code", "sku_name", "batch_no", "qty", "status", "priority")
        wo_tree = ttk.Treeview(body_f, columns=columns, show="headings", selectmode="browse")
        wo_tree.heading("wo_id", text="No. Work Order / SPK")
        wo_tree.heading("sku_code", text="Kode SKU")
        wo_tree.heading("sku_name", text="Nama Produk / Deskripsi")
        wo_tree.heading("batch_no", text="No. Batch")
        wo_tree.heading("qty", text="Target (Box)")
        wo_tree.heading("status", text="Status")
        wo_tree.heading("priority", text="Prioritas")

        wo_tree.column("wo_id", width=140, anchor=tk.W)
        wo_tree.column("sku_code", width=110, anchor=tk.W)
        wo_tree.column("sku_name", width=220, anchor=tk.W)
        wo_tree.column("batch_no", width=110, anchor=tk.CENTER)
        wo_tree.column("qty", width=90, anchor=tk.CENTER)
        wo_tree.column("status", width=90, anchor=tk.CENTER)
        wo_tree.column("priority", width=80, anchor=tk.CENTER)

        tree_scroll = ttk.Scrollbar(body_f, orient=tk.VERTICAL, command=wo_tree.yview)
        wo_tree.configure(yscrollcommand=tree_scroll.set)
        wo_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y, before=wo_tree)

        # Detail Info Box
        detail_card = ttk.LabelFrame(body_f, text=" Detail Work Order Terpilih ", padding="8")
        detail_card.pack(fill=tk.X, pady=(8, 0))

        lbl_detail_wo = ttk.Label(
            detail_card,
            text="Pilih salah satu baris Work Order di atas untuk melihat detail item dan memuat ke mesin.",
            font=("Segoe UI", 8),
            foreground="#475569"
        )
        lbl_detail_wo.pack(anchor="w")

        # Bottom Buttons
        bottom_f = ttk.Frame(win, padding="12")
        bottom_f.pack(fill=tk.X)

        btn_cfg = ttk.Button(
            bottom_f,
            text="⚙ Konfigurasi API",
            command=lambda: [win.destroy(), self.switch_nav("conn")]
        )
        btn_cfg.pack(side=tk.LEFT)

        btn_fallback = ttk.Button(
            bottom_f,
            text="📂 Gunakan File Excel (Fallback)",
            command=lambda: [win.destroy(), self.load_file()]
        )
        btn_fallback.pack(side=tk.LEFT, padx=8)

        btn_close = ttk.Button(bottom_f, text="Batal", command=win.destroy)
        btn_close.pack(side=tk.RIGHT, padx=(8, 0))

        btn_load_wo = tk.Button(
            bottom_f,
            text="✔ Muat Work Order ke Antrean Produksi",
            font=("Segoe UI", 9, "bold"),
            bg="#16a34a",
            fg="#ffffff",
            activebackground="#15803d",
            activeforeground="#ffffff",
            relief="solid",
            bd=1,
            padx=12,
            pady=4,
            cursor="hand2",
            state=tk.DISABLED
        )
        btn_load_wo.pack(side=tk.RIGHT)

        fetched_orders_map = {}

        def _on_item_select(event):
            sel = wo_tree.selection()
            if not sel:
                btn_load_wo.config(state=tk.DISABLED)
                return
            item_id = sel[0]
            wo_obj = fetched_orders_map.get(item_id)
            if wo_obj:
                btn_load_wo.config(state=tk.NORMAL)
                wo_no = wo_obj.get("work_order_id", "-")
                sku = wo_obj.get("sku_code", "-")
                name = wo_obj.get("sku_name", "-")
                qty = wo_obj.get("target_qty", len(wo_obj.get("items", [])))
                batch = wo_obj.get("batch_no", "-")
                note = wo_obj.get("notes", "Tidak ada catatan khusus.")
                lbl_detail_wo.config(
                    text=f"WO: {wo_no}  |  SKU: {sku} - {name}  |  Batch: {batch}  |  Target: {qty} Box\nCatatan: {note}"
                )

        wo_tree.bind("<<TreeviewSelect>>", _on_item_select)

        def _do_load_selected():
            sel = wo_tree.selection()
            if not sel:
                return
            wo_obj = fetched_orders_map.get(sel[0])
            if wo_obj:
                win.destroy()
                self._apply_work_order_to_production(wo_obj)

        btn_load_wo.config(command=_do_load_selected)
        wo_tree.bind("<Double-1>", lambda e: _do_load_selected())

        def _fetch_data():
            lbl_status_fetch.config(text="⟳ Menghubungi Sistem Utama via REST API...")
            btn_refresh.config(state=tk.DISABLED)
            btn_load_wo.config(state=tk.DISABLED)
            wo_tree.delete(*wo_tree.get_children())
            fetched_orders_map.clear()

            base_u = self.api_base_url.get().strip()
            key_u = self.api_key.get().strip()
            try:
                tout = float(self.api_timeout.get().strip())
            except Exception:
                tout = 5.0

            def _thread_fn():
                try:
                    res = self.api_manager.fetch_active_work_orders(
                        base_url=base_u,
                        endpoint=self.api_endpoint_work_orders.get().strip(),
                        api_key=key_u,
                        timeout=tout
                    )
                    if isinstance(res, tuple) and len(res) >= 2:
                        success = bool(res[0])
                        data_or_msg = res[1]
                    else:
                        success = False
                        data_or_msg = "Format respons API tidak valid."
                except Exception as ex:
                    success = False
                    data_or_msg = f"Koneksi gagal: {str(ex)}"

                def _ui_update():
                    btn_refresh.config(state=tk.NORMAL)
                    if success and isinstance(data_or_msg, list) and len(data_or_msg) > 0:
                        count = len(data_or_msg)
                        lbl_status_fetch.config(text=f"✔ Ditemukan {count} Work Order aktif dari Sistem Utama.")
                        for idx, wo in enumerate(data_or_msg):
                            node_id = f"wo_{idx}"
                            fetched_orders_map[node_id] = wo
                            wo_tree.insert(
                                "",
                                tk.END,
                                iid=node_id,
                                values=(
                                    wo.get("work_order_id", "-"),
                                    wo.get("sku_code", "-"),
                                    wo.get("sku_name", "-"),
                                    wo.get("batch_no", "-"),
                                    wo.get("target_qty", len(wo.get("items", []))),
                                    wo.get("status", "ACTIVE"),
                                    wo.get("priority", "NORMAL")
                                )
                            )
                        # Auto-select baris pertama
                        first_id = f"wo_0"
                        wo_tree.selection_set(first_id)
                        wo_tree.focus(first_id)
                        _on_item_select(None)
                    else:
                        err_text = str(data_or_msg) if not success else "Sistem Utama tidak memiliki data Work Order aktif saat ini."
                        lbl_status_fetch.config(text=f"✖ {err_text}")
                        lbl_detail_wo.config(
                            text=f"Keterangan: {err_text}\n"
                            f"Pastikan simulator mock_erp_server.py sedang aktif di port 8000, atau gunakan tombol 'Gunakan File Excel' di bawah."
                        )
                win.after(0, _ui_update)

            threading.Thread(target=_thread_fn, daemon=True).start()

        btn_refresh.config(command=_fetch_data)
        # Jalankan penarikan data awal
        _fetch_data()

    def open_api_contract_dialog(self):
        """Membuka dialog referensi dokumentasi spesifikasi payload REST API (v2.0)"""
        win = tk.Toplevel(self.root)
        win.title("Spesifikasi Kontrak REST API Sistem Utama (v2.0)")
        win.geometry("860x580")
        win.minsize(720, 480)
        win.transient(self.root)

        # Header
        top_f = tk.Frame(win, bg="#0f172a", padx=16, pady=12)
        top_f.pack(fill=tk.X)

        tk.Label(
            top_f,
            text="Dokumentasi & Spesifikasi Integrasi API (Bi-directional)",
            font=("Segoe UI", 11, "bold"),
            fg="#f8fafc",
            bg="#0f172a"
        ).pack(anchor="w")

        tk.Label(
            top_f,
            text="Format JSON Inbound & Outbound untuk komunikasi antara Omega MX dan ERP / MES Pabrik",
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg="#0f172a"
        ).pack(anchor="w", pady=(2, 0))

        # Text Area dengan Scrollbar
        txt_frame = ttk.Frame(win, padding="10")
        txt_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(txt_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        txt_docs = tk.Text(
            txt_frame,
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set,
            bg="#1e1e1e",
            fg="#e2e8f0",
            insertbackground="#ffffff",
            font=("Consolas", 9),
            padx=10,
            pady=10
        )
        txt_docs.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=txt_docs.yview)

        # Ambil dokumentasi markdown dari APIManager
        doc_content = self.api_manager.get_api_documentation_markdown()
        txt_docs.insert(tk.END, doc_content)
        txt_docs.config(state=tk.DISABLED)

        # Bottom Bar
        bot_f = ttk.Frame(win, padding="10")
        bot_f.pack(fill=tk.X)

        def _copy_clipboard():
            self.root.clipboard_clear()
            self.root.clipboard_append(doc_content)
            messagebox.showinfo("Tersalin", "Spesifikasi kontrak API berhasil disalin ke clipboard!", parent=win)

        ttk.Button(bot_f, text="📋 Salin Spesifikasi ke Clipboard", command=_copy_clipboard).pack(side=tk.LEFT)
        ttk.Button(bot_f, text="Tutup", command=win.destroy).pack(side=tk.RIGHT)

    def on_closing(self):
        """ Memastikan aplikasi tutup total, socket hardware diputus dengan aman, dan CMD kembali normal """
        if messagebox.askokcancel("Keluar", "Tutup Aplikasi dan Matikan Server?"):
            try:
                self.save_hardware_config(show_msg=False)
            except Exception: pass
            if getattr(self, 'current_judgments', 0) > 0 and not getattr(self, 'batch_completed', False):
                self.save_current_checkpoint()
            self.is_io_running = False
            self.is_listening = False
            self.is_listening1 = False
            self.is_listening2 = False
            try:
                self.printer.disconnect()
            except Exception: pass
            try:
                self.modbus.close_all()
            except Exception: pass
            try:
                if self.scanner1_socket:
                    self.scanner1_socket.close()
            except Exception: pass
            try:
                if self.scanner2_socket:
                    self.scanner2_socket.close()
            except Exception: pass
            self.root.destroy()
            sys.exit()

if __name__ == "__main__":
    root = tk.Tk()
    app = OmegaBatchApp(root)
    root.mainloop()