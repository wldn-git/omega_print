import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class LoginDialog:
    """
    Jendela dialog login modern untuk Omega MX System.
    Mendukung login awal dan Switch User saat aplikasi sedang berjalan.
    """
    def __init__(self, parent, auth_manager, on_login_success=None, is_switch_user=False):
        self.parent = parent
        self.auth_manager = auth_manager
        self.on_login_success = on_login_success
        self.is_switch_user = is_switch_user
        self.login_result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Omega MX - Login Akses Pengguna")
        self.dialog.geometry("380x370")
        self.dialog.resizable(False, False)
        self.dialog.configure(bg="#f0f0f0")

        # Set Icon jika tersedia
        try:
            icon_path = resource_path("assets/omega_icon.ico")
            if os.path.exists(icon_path):
                self.dialog.iconbitmap(icon_path)
        except Exception:
            pass

        # Modal behavior
        if self.is_switch_user:
            self.dialog.transient(parent)
            self.dialog.grab_set()
        else:
            self.dialog.deiconify()
            self.dialog.lift()
            self.dialog.focus_force()

        # Center dialog pada layar
        self.dialog.update_idletasks()
        screen_w = self.dialog.winfo_screenwidth()
        screen_h = self.dialog.winfo_screenheight()
        dlg_w = 380
        dlg_h = 370
        x = max(0, int((screen_w - dlg_w) / 2))
        y = max(0, int((screen_h - dlg_h) / 2))
        self.dialog.geometry(f"{dlg_w}x{dlg_h}+{x}+{y}")

        self.dialog.protocol("WM_DELETE_WINDOW", self.on_cancel)

        self._build_ui()
        self.ent_password.focus_set()

    def _build_ui(self):
        # Container dialog native Windows 7 (tanpa border biru / kotak terpisah)
        container = tk.Frame(self.dialog, bg="#f0f0f0", padx=25, pady=18)
        container.pack(fill=tk.BOTH, expand=True)

        # Label Judul Dialog (Bahasa Indonesia Baku)
        title_text = "Ganti Akun Pengguna" if self.is_switch_user else "Silakan Masuk ke Sistem"
        lbl_form_title = tk.Label(container, text=title_text, font=("Segoe UI", 12, "bold"), fg="#1c446c", bg="#f0f0f0")
        lbl_form_title.pack(anchor=tk.W, pady=(0, 14))

        # ID PENGGUNA (Dinamis dari basis data seluruh pengguna terdaftar)
        lbl_user = tk.Label(container, text="ID Pengguna:", font=("Segoe UI", 9, "bold"), fg="#222222", bg="#f0f0f0")
        lbl_user.pack(anchor=tk.W, pady=(0, 3))

        registered_users = []
        try:
            users_info = self.auth_manager.get_all_users_details()
            registered_users = [u["username"] for u in users_info if u.get("username")]
        except Exception as e:
            print(f"Gagal memuat daftar pengguna: {e}")

        if not registered_users:
            registered_users = ["admin", "operator"]

        default_user = registered_users[0]
        if "operator" in registered_users:
            default_user = "operator"

        self.var_user = tk.StringVar(value=default_user)
        self.cb_user = ttk.Combobox(container, textvariable=self.var_user, values=registered_users, font=("Segoe UI", 9), state="readonly")
        self.cb_user.pack(fill=tk.X, pady=(0, 10), ipady=2)
        self.cb_user.bind("<<ComboboxSelected>>", lambda e: self.ent_password.focus_set())

        # KATA SANDI
        lbl_pass = tk.Label(container, text="Kata Sandi:", font=("Segoe UI", 9, "bold"), fg="#222222", bg="#f0f0f0")
        lbl_pass.pack(anchor=tk.W, pady=(0, 3))

        self.var_pass = tk.StringVar()
        self.ent_password = ttk.Entry(container, textvariable=self.var_pass, show="*", font=("Segoe UI", 9))
        self.ent_password.pack(fill=tk.X, pady=(0, 4), ipady=2)
        self.ent_password.bind("<Return>", lambda e: self.do_login())

        # TOGGLE SHOW/HIDE PASSWORD
        self.var_show_pass = tk.BooleanVar(value=False)
        chk_show = tk.Checkbutton(container, text="Tampilkan Kata Sandi", variable=self.var_show_pass,
                                  font=("Segoe UI", 8), bg="#f0f0f0", activebackground="#f0f0f0",
                                  command=self._toggle_password_visibility)
        chk_show.pack(anchor=tk.W, pady=(0, 4))

        # LABEL ERROR
        self.lbl_error = tk.Label(container, text="", font=("Segoe UI", 8, "bold"), fg="#c0392b", bg="#f0f0f0")
        self.lbl_error.pack(fill=tk.X, pady=(0, 4))

        # TOMBOL LOGIN (Windows 7 Aero Primary Button dengan Bevel 3D & Efek Glow)
        btn_login = tk.Button(container, text="MASUK", font=("Segoe UI", 9, "bold"),
                              bg="#246c9e", fg="#ffffff", activebackground="#318ac8", activeforeground="#ffffff",
                              relief="raised", bd=1, highlightthickness=1, highlightbackground="#154970",
                              cursor="hand2", pady=6, command=self.do_login)
        btn_login.pack(fill=tk.X, pady=(0, 6))

        # Efek Hover Aero Glow pada Tombol Login
        btn_login.bind("<Enter>", lambda e: btn_login.config(bg="#318ac8", highlightbackground="#48a6e8"))
        btn_login.bind("<Leave>", lambda e: btn_login.config(bg="#246c9e", highlightbackground="#154970"))

        # TOMBOL BATAL / KELUAR (Windows 7 Classic Pushbutton)
        cancel_text = "Batal" if self.is_switch_user else "Keluar dari Aplikasi"
        btn_cancel = tk.Button(container, text=cancel_text, font=("Segoe UI", 9),
                               bg="#e6e6e6", fg="#1a1a1a", activebackground="#dcdcdc", activeforeground="#000000",
                               relief="raised", bd=1, highlightthickness=1, highlightbackground="#8c8c8c",
                               cursor="hand2", pady=4, command=self.on_cancel)
        btn_cancel.pack(fill=tk.X, pady=(0, 10))

        # Efek Hover khas Windows 7 pada Tombol Standar
        btn_cancel.bind("<Enter>", lambda e: btn_cancel.config(bg="#edf4fc", highlightbackground="#3c7fb1"))
        btn_cancel.bind("<Leave>", lambda e: btn_cancel.config(bg="#e6e6e6", highlightbackground="#8c8c8c"))

        # SYSTEM SECURITY NOTICE (Ditempatkan rapi di dalam container, tidak terpotong)
        lbl_hint = tk.Label(container, text="Sistem Terproteksi | Hubungi Supervisor untuk Hak Akses",
                            font=("Segoe UI", 8), fg="#777777", bg="#f0f0f0")
        lbl_hint.pack(anchor=tk.CENTER)

    def _toggle_password_visibility(self):
        if self.var_show_pass.get():
            self.ent_password.config(show="")
        else:
            self.ent_password.config(show="*")

    def do_login(self):
        username = self.var_user.get().strip()
        password = self.var_pass.get().strip()

        if not username:
            self.lbl_error.config(text="ID Pengguna tidak boleh kosong.")
            return

        if not password:
            self.lbl_error.config(text="Kata sandi tidak boleh kosong.")
            self.ent_password.focus_set()
            return

        success, user_info, msg = self.auth_manager.authenticate(username, password)
        if success:
            self.login_result = user_info
            self.dialog.destroy()
            if self.on_login_success:
                self.on_login_success(user_info)
        else:
            self.lbl_error.config(text=msg)
            self.ent_password.focus_set()
            self.ent_password.selection_range(0, tk.END)

    def on_cancel(self):
        self.login_result = None
        self.dialog.destroy()
        if not self.is_switch_user:
            # Jika login awal dibatalkan, keluar total dari aplikasi
            self.parent.destroy()
            sys.exit()


class ChangePasswordDialog:
    """
    Dialog untuk mengubah password pengguna yang sedang login,
    atau Admin mereset password akun lain.
    """
    def __init__(self, parent, auth_manager, current_user_info):
        self.parent = parent
        self.auth_manager = auth_manager
        self.current_user = current_user_info

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Ubah Password - Omega MX")
        self.dialog.geometry("380x360")
        self.dialog.resizable(False, False)
        self.dialog.configure(bg="#f0f0f0")

        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center
        self.dialog.update_idletasks()
        sw = self.dialog.winfo_screenwidth()
        sh = self.dialog.winfo_screenheight()
        x = max(0, int((sw - 380) / 2))
        y = max(0, int((sh - 360) / 2))
        self.dialog.geometry(f"380x360+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        lbl_t = tk.Label(self.dialog, text="Ganti Password Akun", font=("Segoe UI", 12, "bold"), fg="#1c446c", bg="#f0f0f0")
        lbl_t.pack(pady=(15, 10))

        frame = tk.Frame(self.dialog, bg="#ffffff", padx=20, pady=15, highlightthickness=1, highlightbackground="#aec3db")
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        is_admin = self.current_user.get("role") == "admin"

        # Target user selection jika admin
        row = 0
        if is_admin:
            tk.Label(frame, text="Pilih Akun:", font=("Segoe UI", 9, "bold"), fg="#24476b", bg="#ffffff").grid(row=row, column=0, sticky="w", pady=4)
            self.var_target_user = tk.StringVar(value=self.current_user.get("username"))
            user_list = [u["username"] for u in self.auth_manager.get_user_list()]
            cb = ttk.Combobox(frame, textvariable=self.var_target_user, values=user_list, state="readonly", width=18, font=("Segoe UI", 9))
            cb.grid(row=row, column=1, sticky="w", pady=4)
            row += 1
        else:
            self.var_target_user = tk.StringVar(value=self.current_user.get("username"))

        # Password Lama (hanya wajib jika mengubah akun sendiri dan bukan bypass admin)
        tk.Label(frame, text="Password Lama:", font=("Segoe UI", 9), fg="#24476b", bg="#ffffff").grid(row=row, column=0, sticky="w", pady=4)
        self.var_old_pass = tk.StringVar()
        self.ent_old = ttk.Entry(frame, textvariable=self.var_old_pass, show="*", width=20, font=("Segoe UI", 9))
        self.ent_old.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        # Password Baru
        tk.Label(frame, text="Password Baru:", font=("Segoe UI", 9), fg="#24476b", bg="#ffffff").grid(row=row, column=0, sticky="w", pady=4)
        self.var_new_pass = tk.StringVar()
        self.ent_new = ttk.Entry(frame, textvariable=self.var_new_pass, show="*", width=20, font=("Segoe UI", 9))
        self.ent_new.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        # Konfirmasi Password Baru
        tk.Label(frame, text="Ulangi Password:", font=("Segoe UI", 9), fg="#24476b", bg="#ffffff").grid(row=row, column=0, sticky="w", pady=4)
        self.var_conf_pass = tk.StringVar()
        self.ent_conf = ttk.Entry(frame, textvariable=self.var_conf_pass, show="*", width=20, font=("Segoe UI", 9))
        self.ent_conf.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        self.lbl_msg = tk.Label(frame, text="", font=("Segoe UI", 8, "bold"), fg="#c0392b", bg="#ffffff")
        self.lbl_msg.grid(row=row, column=0, columnspan=2, pady=6)
        row += 1

        btn_save = tk.Button(frame, text="Simpan Password Baru", font=("Segoe UI", 9, "bold"),
                             bg="#246c9e", fg="#ffffff", activebackground="#318ac8", activeforeground="#ffffff",
                             relief="raised", bd=1, highlightthickness=1, highlightbackground="#154970",
                             cursor="hand2", pady=6, command=self.do_save)
        btn_save.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        btn_save.bind("<Enter>", lambda e: btn_save.config(bg="#318ac8", highlightbackground="#48a6e8"))
        btn_save.bind("<Leave>", lambda e: btn_save.config(bg="#246c9e", highlightbackground="#154970"))

    def do_save(self):
        target = self.var_target_user.get().strip()
        old_pass = self.var_old_pass.get().strip()
        new_pass = self.var_new_pass.get().strip()
        conf_pass = self.var_conf_pass.get().strip()

        if new_pass != conf_pass:
            self.lbl_msg.config(text="Konfirmasi password baru tidak cocok.")
            return

        if len(new_pass) < 4:
            self.lbl_msg.config(text="Password baru minimal 4 karakter.")
            return

        is_admin = self.current_user.get("role") == "admin"
        if is_admin and target != self.current_user.get("username"):
            # Admin mereset password user lain tanpa perlu password lama
            success, msg = self.auth_manager.admin_reset_password(target, new_pass)
        else:
            # Ganti password sendiri perlu password lama
            success, msg = self.auth_manager.change_password(target, old_pass, new_pass)

        if success:
            messagebox.showinfo("Berhasil", msg, parent=self.dialog)
            self.dialog.destroy()
        else:
            self.lbl_msg.config(text=msg)
