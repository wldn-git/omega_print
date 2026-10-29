# user_management_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox
from i18n import tr

class UserManagementDialog(tk.Toplevel):
    """
    Formulir Modal Tambah & Ubah Akun Pengguna dengan Hak Akses Granular (Mendukung Bahasa ID & EN).
    Memungkinkan pengaturan peran (Admin / Operator), hak akses halaman, dan izin fitur.
    """
    def __init__(self, parent, auth_manager, user_to_edit=None, current_username=None, on_success=None):
        super().__init__(parent)
        self.auth_manager = auth_manager
        self.user_to_edit = user_to_edit
        self.current_username = current_username
        self.on_success = on_success
        self.is_edit_mode = bool(user_to_edit)

        title_text = tr("um_title_edit", username=user_to_edit['username']) if self.is_edit_mode else tr("um_title_add")
        self.title(title_text)
        self.configure(bg="#f1f5f9")
        self.geometry("560x660")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Variabel Form
        self.var_uname = tk.StringVar(value=user_to_edit["username"] if self.is_edit_mode else "")
        self.var_name = tk.StringVar(value=user_to_edit.get("name", "") if self.is_edit_mode else "")
        self.var_role = tk.StringVar(value=user_to_edit.get("role", "operator") if self.is_edit_mode else "operator")
        self.var_pwd = tk.StringVar()
        self.var_pwd_confirm = tk.StringVar()

        # Variabel Hak Akses Halaman
        existing_perms = user_to_edit.get("permissions", {}) if self.is_edit_mode else {}
        existing_pages = existing_perms.get("pages", ["main", "history", "logs"])
        existing_feats = existing_perms.get("features", ["export_csv"])

        self.page_vars = {
            "main": tk.BooleanVar(value="main" in existing_pages or not self.is_edit_mode),
            "history": tk.BooleanVar(value="history" in existing_pages or not self.is_edit_mode),
            "conn": tk.BooleanVar(value="conn" in existing_pages if self.is_edit_mode else False),
            "logs": tk.BooleanVar(value="logs" in existing_pages or not self.is_edit_mode),
            "master": tk.BooleanVar(value="master" in existing_pages if self.is_edit_mode else False)
        }

        # Variabel Hak Akses Fitur
        self.feat_vars = {
            "export_csv": tk.BooleanVar(value="export_csv" in existing_feats or not self.is_edit_mode),
            "fetch_api": tk.BooleanVar(value="fetch_api" in existing_feats if self.is_edit_mode else False),
            "simulation_mode": tk.BooleanVar(value="simulation_mode" in existing_feats if self.is_edit_mode else False),
            "manage_users": tk.BooleanVar(value="manage_users" in existing_feats if self.is_edit_mode else False)
        }

        self._build_ui()
        self._center_window()

    def _center_window(self):
        self.update_idletasks()
        w = max(560, self.winfo_reqwidth())
        h = max(655, self.winfo_reqheight() + 12)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        if h > sh - 60:
            h = sh - 60
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _on_role_change(self):
        """Otomatis sesuaikan rekomendasi izin saat radiobutton peran dipilih (hanya pada mode tambah)"""
        if self.is_edit_mode:
            return
        role = self.var_role.get()
        if role == "admin":
            for v in self.page_vars.values(): v.set(True)
            for v in self.feat_vars.values(): v.set(True)
        else:
            self.page_vars["main"].set(True)
            self.page_vars["history"].set(True)
            self.page_vars["conn"].set(False)
            self.page_vars["logs"].set(True)
            self.page_vars["master"].set(False)

            self.feat_vars["export_csv"].set(True)
            self.feat_vars["fetch_api"].set(False)
            self.feat_vars["simulation_mode"].set(False)
            self.feat_vars["manage_users"].set(False)

    def _build_ui(self):
        container = ttk.Frame(self, style="Surface.TFrame", padding="16")
        container.pack(fill=tk.BOTH, expand=True)

        # Reserve Bottom Action Bar terlebih dahulu agar tidak pernah terpotong
        btn_box = ttk.Frame(container, style="Surface.TFrame")
        btn_box.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        btn_cancel = tk.Button(
            btn_box, text=tr("um_btn_cancel"), font=("Segoe UI", 9, "bold"),
            bg="#e2e8f0", fg="#334155", activebackground="#cbd5e1", activeforeground="#0f172a",
            relief="flat", bd=0, padx=16, pady=6, cursor="hand2", command=self.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, padx=(8, 0))

        btn_save = tk.Button(
            btn_box, text=tr("um_btn_save"), font=("Segoe UI", 9, "bold"),
            bg="#2563eb", fg="#ffffff", activebackground="#1d4ed8", activeforeground="#ffffff",
            relief="flat", bd=0, padx=18, pady=6, cursor="hand2", command=self._save_user
        )
        btn_save.pack(side=tk.RIGHT)

        # 1. Header Informasi
        hdr_frame = ttk.Frame(container, style="Surface.TFrame")
        hdr_frame.pack(fill=tk.X, pady=(0, 10))
        title = tr("um_hdr_edit") if self.is_edit_mode else tr("um_hdr_add")
        ttk.Label(hdr_frame, text=title, style="Surface.TLabel", font=("Segoe UI", 12, "bold"), foreground="#0f172a").pack(anchor="w")
        ttk.Label(hdr_frame, text=tr("um_sub"), style="Surface.TLabel", font=("Segoe UI", 8, "italic"), foreground="#64748b").pack(anchor="w")

        # 2. Card Identitas Akun
        grp_acc = ttk.LabelFrame(container, text=tr("um_grp_identity"), padding="10")
        grp_acc.pack(fill=tk.X, pady=(0, 8))

        # Username
        r_u = ttk.Frame(grp_acc)
        r_u.pack(fill=tk.X, pady=3)
        ttk.Label(r_u, text=tr("um_lbl_uname"), width=22).pack(side=tk.LEFT)
        ent_u = ttk.Entry(r_u, textvariable=self.var_uname, width=28)
        ent_u.pack(side=tk.LEFT, padx=5)
        if self.is_edit_mode:
            ent_u.config(state="readonly")
            ttk.Label(r_u, text=tr("um_lbl_perm"), font=("Segoe UI", 8, "italic"), foreground="#94a3b8").pack(side=tk.LEFT)

        # Nama Lengkap
        r_n = ttk.Frame(grp_acc)
        r_n.pack(fill=tk.X, pady=3)
        ttk.Label(r_n, text=tr("um_lbl_fullname"), width=22).pack(side=tk.LEFT)
        ent_n = ttk.Entry(r_n, textvariable=self.var_name, width=28)
        ent_n.pack(side=tk.LEFT, padx=5)

        # Peran (Role)
        r_r = ttk.Frame(grp_acc)
        r_r.pack(fill=tk.X, pady=4)
        ttk.Label(r_r, text=tr("um_lbl_role"), width=22).pack(side=tk.LEFT)
        ttk.Radiobutton(r_r, text=tr("um_role_op"), variable=self.var_role, value="operator", command=self._on_role_change).pack(side=tk.LEFT, padx=(5, 12))
        ttk.Radiobutton(r_r, text=tr("um_role_adm"), variable=self.var_role, value="admin", command=self._on_role_change).pack(side=tk.LEFT)

        # Password
        r_p = ttk.Frame(grp_acc)
        r_p.pack(fill=tk.X, pady=3)
        lbl_p_text = tr("um_lbl_pwd_new") if self.is_edit_mode else tr("um_lbl_pwd")
        ttk.Label(r_p, text=lbl_p_text, width=22).pack(side=tk.LEFT)
        ttk.Entry(r_p, textvariable=self.var_pwd, show="*", width=24).pack(side=tk.LEFT, padx=5)
        if self.is_edit_mode:
            ttk.Label(r_p, text=tr("um_lbl_pwd_hint"), font=("Segoe UI", 8, "italic"), foreground="#64748b").pack(side=tk.LEFT)

        # Konfirmasi Password
        r_pc = ttk.Frame(grp_acc)
        r_pc.pack(fill=tk.X, pady=3)
        ttk.Label(r_pc, text=tr("um_lbl_pwd_conf"), width=22).pack(side=tk.LEFT)
        ttk.Entry(r_pc, textvariable=self.var_pwd_confirm, show="*", width=24).pack(side=tk.LEFT, padx=5)

        # 3. Card Hak Akses Halaman
        grp_pages = ttk.LabelFrame(container, text=tr("um_grp_pages"), padding="10")
        grp_pages.pack(fill=tk.X, pady=(0, 8))

        pages_info = [
            ("main", tr("um_page_main")),
            ("history", tr("um_page_history")),
            ("conn", tr("um_page_conn")),
            ("logs", tr("um_page_logs")),
            ("master", tr("um_page_master"))
        ]

        for p_key, p_desc in pages_info:
            cb = ttk.Checkbutton(grp_pages, text=p_desc, variable=self.page_vars[p_key])
            cb.pack(anchor="w", pady=2)

        # 4. Card Hak Akses Fitur Khusus
        grp_feats = ttk.LabelFrame(container, text=tr("um_grp_feats"), padding="10")
        grp_feats.pack(fill=tk.X, pady=(0, 4))

        feats_info = [
            ("export_csv", tr("um_feat_csv")),
            ("fetch_api", tr("um_feat_api")),
            ("simulation_mode", tr("um_feat_sim")),
            ("manage_users", tr("um_feat_users"))
        ]

        for f_key, f_desc in feats_info:
            cb = ttk.Checkbutton(grp_feats, text=f_desc, variable=self.feat_vars[f_key])
            cb.pack(anchor="w", pady=2)

    def _save_user(self):
        uname = self.var_uname.get().strip().lower()
        name = self.var_name.get().strip()
        role = self.var_role.get().strip()
        pwd = self.var_pwd.get().strip()
        pwd_confirm = self.var_pwd_confirm.get().strip()

        if not uname:
            return messagebox.showerror("Error", "ID Pengguna (Username) wajib diisi / Username is required.", parent=self)

        if not name:
            name = uname

        # Validasi Password
        if not self.is_edit_mode:
            if not pwd:
                return messagebox.showerror("Error", "Kata sandi wajib diisi / Password is required.", parent=self)
            if len(pwd) < 6:
                return messagebox.showerror("Error", tr("chg_err_min_len"), parent=self)
            if pwd != pwd_confirm:
                return messagebox.showerror("Error", tr("chg_err_mismatch"), parent=self)
        else:
            if pwd:
                if len(pwd) < 6:
                    return messagebox.showerror("Error", tr("chg_err_min_len"), parent=self)
                if pwd != pwd_confirm:
                    return messagebox.showerror("Error", tr("chg_err_mismatch"), parent=self)

        # Bangun Struktur Hak Akses
        allowed_pages = [k for k, v in self.page_vars.items() if v.get()]
        allowed_feats = [k for k, v in self.feat_vars.items() if v.get()]

        if not allowed_pages:
            return messagebox.showerror("Error", "Minimal 1 halaman harus dipilih / Select at least 1 page.", parent=self)

        perms = {
            "pages": allowed_pages,
            "features": allowed_feats
        }

        if not self.is_edit_mode:
            ok, msg = self.auth_manager.add_user(
                username=uname,
                name=name,
                password=pwd,
                role=role,
                permissions=perms
            )
        else:
            ok, msg = self.auth_manager.update_user(
                username=uname,
                name=name,
                password=pwd if pwd else None,
                role=role,
                permissions=perms
            )

        if ok:
            messagebox.showinfo("OK", msg, parent=self)
            if self.on_success:
                try:
                    self.on_success(uname)
                except TypeError:
                    self.on_success()
            self.destroy()
        else:
            messagebox.showerror("Error", msg, parent=self)
