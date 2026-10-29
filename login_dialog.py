import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from i18n import i18n, tr

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class LoginDialog:
    """
    Jendela dialog login modern untuk Omega MX System.
    Mendukung login awal, Switch User, dan pemilihan bahasa (ID / EN) langsung di dialog.
    """
    def __init__(self, parent, auth_manager, on_login_success=None, is_switch_user=False):
        self.parent = parent
        self.auth_manager = auth_manager
        self.on_login_success = on_login_success
        self.is_switch_user = is_switch_user
        self.login_result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.withdraw()
        self.dialog.title(tr("login_win_title"))
        self.dialog.resizable(False, False)
        self.dialog.configure(bg="#f1f5f9")

        # Set Icon jika tersedia
        try:
            icon_path = resource_path("assets/omega_icon.ico")
            if os.path.exists(icon_path):
                self.dialog.iconbitmap(icon_path)
        except Exception:
            pass

        self.dialog.protocol("WM_DELETE_WINDOW", self.on_cancel)

        self._build_ui()

        # Center dialog pada layar sebelum ditampilkan agar tidak berkedip pindah posisi
        self.dialog.update_idletasks()
        screen_w = self.dialog.winfo_screenwidth()
        screen_h = self.dialog.winfo_screenheight()
        dlg_w = 390
        dlg_h = max(355, self.dialog.winfo_reqheight() + 10)
        x = max(0, int((screen_w - dlg_w) / 2))
        y = max(0, int((screen_h - dlg_h) / 2))
        self.dialog.geometry(f"{dlg_w}x{dlg_h}+{x}+{y}")

        # Tampilkan dialog setelah posisi & UI siap
        self.dialog.deiconify()
        self.dialog.lift()
        self.dialog.focus_force()

        if self.is_switch_user:
            self.dialog.transient(parent)
            self.dialog.grab_set()

        self.ent_password.focus_set()

    def _build_ui(self):
        # Card Container Putih Bersih tanpa Header Hitam & tanpa Pilihan Bahasa
        outer = tk.Frame(self.dialog, bg="#f1f5f9", padx=18, pady=18)
        outer.pack(fill=tk.BOTH, expand=True)

        container = tk.Frame(
            outer, bg="#ffffff", padx=22, pady=20,
            relief="flat", bd=0, highlightthickness=1, highlightbackground="#cbd5e1", highlightcolor="#cbd5e1"
        )
        container.pack(fill=tk.BOTH, expand=True)

        title_text = tr("login_hdr_switch") if self.is_switch_user else tr("login_hdr_initial")
        self.lbl_form_title = tk.Label(container, text=title_text, font=("Segoe UI", 12, "bold"), fg="#0f172a", bg="#ffffff")
        self.lbl_form_title.pack(anchor=tk.W, pady=(0, 14))

        # ID PENGGUNA (Dinamis dari basis data seluruh pengguna terdaftar)
        self.lbl_user = tk.Label(container, text=tr("login_lbl_user"), font=("Segoe UI", 9, "bold"), fg="#334155", bg="#ffffff")
        self.lbl_user.pack(anchor=tk.W, pady=(0, 4))

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
        self.lbl_pass = tk.Label(container, text=tr("login_lbl_pass"), font=("Segoe UI", 9, "bold"), fg="#334155", bg="#ffffff")
        self.lbl_pass.pack(anchor=tk.W, pady=(0, 4))

        self.var_pass = tk.StringVar()
        self.ent_password = ttk.Entry(container, textvariable=self.var_pass, show="*", font=("Segoe UI", 9))
        self.ent_password.pack(fill=tk.X, pady=(0, 4), ipady=2)
        self.ent_password.bind("<Return>", lambda e: self.do_login())

        # TOGGLE SHOW/HIDE PASSWORD
        self.var_show_pass = tk.BooleanVar(value=False)
        self.chk_show = ttk.Checkbutton(
            container, text=tr("login_chk_show"), variable=self.var_show_pass,
            command=self._toggle_password_visibility
        )
        self.chk_show.pack(anchor=tk.W, pady=(2, 4))

        # LABEL ERROR
        self.lbl_error = tk.Label(container, text="", font=("Segoe UI", 8, "bold"), fg="#dc2626", bg="#ffffff")
        self.lbl_error.pack(fill=tk.X, pady=(0, 4))

        # TOMBOL LOGIN (Flat Modern Primary Button)
        self.btn_login = tk.Button(
            container, text=tr("login_btn_submit"), font=("Segoe UI", 9, "bold"),
            bg="#2563eb", fg="#ffffff", activebackground="#1d4ed8", activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", pady=7, command=self.do_login
        )
        self.btn_login.pack(fill=tk.X, pady=(2, 6))
        self.btn_login.bind("<Enter>", lambda e: self.btn_login.config(bg="#1d4ed8"))
        self.btn_login.bind("<Leave>", lambda e: self.btn_login.config(bg="#2563eb"))

        # TOMBOL BATAL / KELUAR
        cancel_text = tr("login_btn_cancel") if self.is_switch_user else tr("login_btn_exit")
        self.btn_cancel = tk.Button(
            container, text=cancel_text, font=("Segoe UI", 9, "bold"),
            bg="#e2e8f0", fg="#334155", activebackground="#cbd5e1", activeforeground="#0f172a",
            relief="flat", bd=0, cursor="hand2", pady=6, command=self.on_cancel
        )
        self.btn_cancel.pack(fill=tk.X, pady=(0, 10))
        self.btn_cancel.bind("<Enter>", lambda e: self.btn_cancel.config(bg="#cbd5e1"))
        self.btn_cancel.bind("<Leave>", lambda e: self.btn_cancel.config(bg="#e2e8f0"))

        # SYSTEM SECURITY NOTICE
        self.lbl_hint = tk.Label(
            container, text=tr("login_security_hint"),
            font=("Segoe UI", 8), fg="#94a3b8", bg="#ffffff"
        )
        self.lbl_hint.pack(anchor=tk.CENTER)

    def _toggle_password_visibility(self):
        if self.var_show_pass.get():
            self.ent_password.config(show="")
        else:
            self.ent_password.config(show="*")

    def do_login(self):
        username = self.var_user.get().strip()
        password = self.var_pass.get().strip()

        if not username:
            self.lbl_error.config(text=tr("login_err_empty_user"))
            return

        if not password:
            self.lbl_error.config(text=tr("login_err_empty_pass"))
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
            self.parent.destroy()
            sys.exit()


class ChangePasswordDialog:
    """
    Dialog untuk mengubah password pengguna yang sedang login,
    atau Admin mereset password akun lain (Mendukung Bahasa ID / EN).
    """
    def __init__(self, parent, auth_manager, current_user_info):
        self.parent = parent
        self.auth_manager = auth_manager
        self.current_user = current_user_info

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(tr("chg_win_title"))
        self.dialog.geometry("390x360")
        self.dialog.resizable(False, False)
        self.dialog.configure(bg="#f1f5f9")

        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center
        self.dialog.update_idletasks()
        sw = self.dialog.winfo_screenwidth()
        sh = self.dialog.winfo_screenheight()
        x = max(0, int((sw - 390) / 2))
        y = max(0, int((sh - 360) / 2))
        self.dialog.geometry(f"390x360+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        lbl_t = tk.Label(self.dialog, text=tr("chg_hdr"), font=("Segoe UI", 12, "bold"), fg="#0f172a", bg="#f1f5f9")
        lbl_t.pack(pady=(14, 10))

        frame = tk.Frame(self.dialog, bg="#ffffff", padx=20, pady=16, relief="flat", bd=0, highlightthickness=1, highlightbackground="#cbd5e1")
        frame.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 16))

        is_admin = self.current_user.get("role") == "admin"

        row = 0
        if is_admin:
            tk.Label(frame, text=tr("chg_lbl_account"), font=("Segoe UI", 9, "bold"), fg="#334155", bg="#ffffff").grid(row=row, column=0, sticky="w", pady=5)
            self.var_target_user = tk.StringVar(value=self.current_user.get("username"))
            user_list = [u["username"] for u in self.auth_manager.get_user_list()]
            cb = ttk.Combobox(frame, textvariable=self.var_target_user, values=user_list, state="readonly", width=18, font=("Segoe UI", 9))
            cb.grid(row=row, column=1, sticky="w", pady=5)
            row += 1
        else:
            self.var_target_user = tk.StringVar(value=self.current_user.get("username"))

        # Password Lama
        tk.Label(frame, text=tr("chg_lbl_old"), font=("Segoe UI", 9), fg="#334155", bg="#ffffff").grid(row=row, column=0, sticky="w", pady=5)
        self.var_old_pass = tk.StringVar()
        self.ent_old = ttk.Entry(frame, textvariable=self.var_old_pass, show="*", width=20, font=("Segoe UI", 9))
        self.ent_old.grid(row=row, column=1, sticky="w", pady=5)
        row += 1

        # Password Baru
        tk.Label(frame, text=tr("chg_lbl_new"), font=("Segoe UI", 9), fg="#334155", bg="#ffffff").grid(row=row, column=0, sticky="w", pady=5)
        self.var_new_pass = tk.StringVar()
        self.ent_new = ttk.Entry(frame, textvariable=self.var_new_pass, show="*", width=20, font=("Segoe UI", 9))
        self.ent_new.grid(row=row, column=1, sticky="w", pady=5)
        row += 1

        # Konfirmasi Password Baru
        tk.Label(frame, text=tr("chg_lbl_conf"), font=("Segoe UI", 9), fg="#334155", bg="#ffffff").grid(row=row, column=0, sticky="w", pady=5)
        self.var_conf_pass = tk.StringVar()
        self.ent_conf = ttk.Entry(frame, textvariable=self.var_conf_pass, show="*", width=20, font=("Segoe UI", 9))
        self.ent_conf.grid(row=row, column=1, sticky="w", pady=5)
        row += 1

        self.lbl_msg = tk.Label(frame, text="", font=("Segoe UI", 8, "bold"), fg="#dc2626", bg="#ffffff")
        self.lbl_msg.grid(row=row, column=0, columnspan=2, pady=6)
        row += 1

        btn_save = tk.Button(
            frame, text=tr("chg_btn_save"), font=("Segoe UI", 9, "bold"),
            bg="#2563eb", fg="#ffffff", activebackground="#1d4ed8", activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", pady=7, command=self.do_save
        )
        btn_save.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        btn_save.bind("<Enter>", lambda e: btn_save.config(bg="#1d4ed8"))
        btn_save.bind("<Leave>", lambda e: btn_save.config(bg="#2563eb"))

    def do_save(self):
        target = self.var_target_user.get().strip()
        old_pass = self.var_old_pass.get().strip()
        new_pass = self.var_new_pass.get().strip()
        conf_pass = self.var_conf_pass.get().strip()

        if new_pass != conf_pass:
            self.lbl_msg.config(text=tr("chg_err_mismatch"))
            return

        if len(new_pass) < 6:
            self.lbl_msg.config(text=tr("chg_err_min_len"))
            return

        is_admin = self.current_user.get("role") == "admin"
        if is_admin and target != self.current_user.get("username"):
            success, msg = self.auth_manager.admin_reset_password(target, new_pass)
        else:
            success, msg = self.auth_manager.change_password(target, old_pass, new_pass)

        if success:
            messagebox.showinfo("OK", msg, parent=self.dialog)
            self.dialog.destroy()
        else:
            self.lbl_msg.config(text=msg)
