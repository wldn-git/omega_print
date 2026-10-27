import os
import json
import hashlib
import hmac
import secrets
import time

class AuthManager:
    """
    Manajer Otentikasi dan Otoritas User untuk Omega MX System.
    Menyimpan data pengguna di file JSON dengan hash PBKDF2-HMAC-SHA256 (100.000 iterasi) + salt.
    Dilengkapi perlindungan brute-force (lockout 5 percobaan gagal) dan perbandingan constant-time.
    """
    def __init__(self, data_dir=None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = data_dir if data_dir else os.path.join(base_dir, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.users_file = os.path.join(self.data_dir, "users.json")
        self.failed_attempts = {} # username -> {'count': int, 'last_failed': float}
        self._initialize_users_file()

    def _hash_password(self, password: str, salt: str) -> str:
        """Menghasilkan hash PBKDF2-HMAC-SHA256 (100.000 iterasi) dari password + salt"""
        return hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100_000
        ).hex()

    def _verify_password(self, password: str, salt: str, expected_hash: str, hash_type: str = 'pbkdf2') -> tuple:
        """
        Verifikasi password secara constant-time.
        Return: (is_valid: bool, needs_upgrade: bool)
        """
        if hash_type == 'pbkdf2':
            calc_hash = self._hash_password(password, salt)
            return hmac.compare_digest(calc_hash, expected_hash), False
        else:
            # Legacy SHA-256 (1 round)
            salted = (salt + password).encode('utf-8')
            calc_hash = hashlib.sha256(salted).hexdigest()
            is_valid = hmac.compare_digest(calc_hash, expected_hash)
            return is_valid, is_valid # Jika valid, upgrade ke PBKDF2

    def is_locked_out(self, username: str) -> tuple:
        """Cek apakah user sedang dikunci karena terlalu banyak percobaan gagal (5x)"""
        info = self.failed_attempts.get(username)
        if not info or info['count'] < 5:
            return False, 0
        elapsed = time.time() - info['last_failed']
        lockout_duration = 300 # 5 menit
        if elapsed < lockout_duration:
            return True, int(lockout_duration - elapsed)
        # Lockout habis
        self.failed_attempts.pop(username, None)
        return False, 0

    def _record_failed_attempt(self, username: str):
        now = time.time()
        info = self.failed_attempts.get(username, {'count': 0, 'last_failed': now})
        if now - info['last_failed'] > 300:
            info['count'] = 1
        else:
            info['count'] += 1
        info['last_failed'] = now
        self.failed_attempts[username] = info

    def _initialize_users_file(self):
        """Buat file default jika belum ada"""
        if not os.path.exists(self.users_file):
            admin_salt = secrets.token_hex(16)
            op_salt = secrets.token_hex(16)
            default_users = {
                "admin": {
                    "role": "admin",
                    "name": "Administrator",
                    "salt": admin_salt,
                    "password_hash": self._hash_password("admin123", admin_salt),
                    "hash_type": "pbkdf2"
                },
                "operator": {
                    "role": "operator",
                    "name": "Operator Produksi",
                    "salt": op_salt,
                    "password_hash": self._hash_password("operator123", op_salt),
                    "hash_type": "pbkdf2"
                }
            }
            self._save_users(default_users)

    def _load_users(self) -> dict:
        try:
            with open(self.users_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading users: {e}")
            return {}

    def _save_users(self, users: dict) -> bool:
        try:
            with open(self.users_file, "w", encoding="utf-8") as f:
                json.dump(users, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving users: {e}")
            return False

    def authenticate(self, username: str, password: str):
        """
        Memverifikasi kredensial user dengan perlindungan lockout & timing attack.
        Mengembalikan: (success: bool, user_data: dict or None, message: str)
        """
        username = username.strip().lower()
        locked, rem_sec = self.is_locked_out(username)
        if locked:
            return False, None, f"Akun terkunci sementara karena 5x salah. Tunggu {rem_sec} detik."

        users = self._load_users()
        if username not in users:
            self._record_failed_attempt(username)
            return False, None, "Username atau password salah."

        user = users[username]
        salt = user.get("salt", "")
        expected_hash = user.get("password_hash", "")
        hash_type = user.get("hash_type", "sha256_legacy")

        is_valid, needs_upgrade = self._verify_password(password, salt, expected_hash, hash_type)
        if is_valid:
            self.failed_attempts.pop(username, None)
            if needs_upgrade:
                # Upgrade otomatis ke PBKDF2 saat login berhasil
                new_salt = secrets.token_hex(16)
                user["salt"] = new_salt
                user["password_hash"] = self._hash_password(password, new_salt)
                user["hash_type"] = "pbkdf2"
                users[username] = user
                self._save_users(users)

            user_info = {
                "username": username,
                "role": user.get("role", "operator"),
                "name": user.get("name", username),
                "permissions": user.get("permissions", self.get_default_permissions(user.get("role", "operator")))
            }
            return True, user_info, "Login berhasil."
        else:
            self._record_failed_attempt(username)
            return False, None, "Username atau password salah."

    def change_password(self, username: str, old_password: str, new_password: str):
        """Mengubah password pengguna sendiri"""
        username = username.strip().lower()
        if len(new_password) < 6:
            return False, "Password baru minimal 6 karakter."

        users = self._load_users()
        if username not in users:
            return False, "User tidak ditemukan."

        user = users[username]
        salt = user.get("salt", "")
        expected_hash = user.get("password_hash", "")
        hash_type = user.get("hash_type", "sha256_legacy")

        is_valid, _ = self._verify_password(old_password, salt, expected_hash, hash_type)
        if not is_valid:
            return False, "Password lama salah."

        new_salt = secrets.token_hex(16)
        user["salt"] = new_salt
        user["password_hash"] = self._hash_password(new_password, new_salt)
        user["hash_type"] = "pbkdf2"
        users[username] = user

        if self._save_users(users):
            return True, "Password berhasil diperbarui."
        return False, "Gagal menyimpan data password."

    def admin_reset_password(self, target_username: str, new_password: str):
        """Admin mereset password user lain"""
        target_username = target_username.strip().lower()
        if len(new_password) < 6:
            return False, "Password baru minimal 6 karakter."

        users = self._load_users()
        if target_username not in users:
            return False, "User target tidak ditemukan."

        new_salt = secrets.token_hex(16)
        users[target_username]["salt"] = new_salt
        users[target_username]["password_hash"] = self._hash_password(new_password, new_salt)
        users[target_username]["hash_type"] = "pbkdf2"

        if self._save_users(users):
            return True, f"Password untuk '{target_username}' berhasil diubah."
        return False, "Gagal mereset password."

    def get_default_permissions(self, role: str) -> dict:
        """Mendapatkan hak akses default berdasarkan peran pengguna"""
        if role == "admin":
            return {
                "pages": ["main", "history", "conn", "logs", "master"],
                "features": ["export_csv", "fetch_api", "manage_users", "manage_retention", "simulation_mode"]
            }
        else:
            return {
                "pages": ["main", "history", "logs"],
                "features": ["export_csv"]
            }

    def get_user_list(self):
        """Mendapatkan daftar username dan role sederhana"""
        users = self._load_users()
        return [{"username": u, "role": d.get("role"), "name": d.get("name")} for u, d in users.items()]

    def get_all_users_details(self):
        """Mendapatkan daftar seluruh user lengkap dengan informasi hak akses"""
        users = self._load_users()
        result = []
        for uname, udata in users.items():
            role = udata.get("role", "operator")
            perms = udata.get("permissions")
            if not perms:
                perms = self.get_default_permissions(role)
            result.append({
                "username": uname,
                "name": udata.get("name", uname),
                "role": role,
                "permissions": perms
            })
        return result

    def get_user_details(self, username: str):
        """Mendapatkan rincian satu user"""
        username = username.strip().lower()
        users = self._load_users()
        if username not in users:
            return None
        u = users[username]
        role = u.get("role", "operator")
        perms = u.get("permissions") or self.get_default_permissions(role)
        return {
            "username": username,
            "name": u.get("name", username),
            "role": role,
            "permissions": perms
        }

    def add_user(self, username: str, name: str, password: str, role: str = "operator", permissions: dict = None):
        """Menambahkan akun pengguna baru ke database users.json"""
        username = username.strip().lower()
        if not username:
            return False, "Username tidak boleh kosong."
        if len(username) < 3:
            return False, "Username minimal 3 karakter."
        if not username.replace("_", "").replace("-", "").isalnum():
            return False, "Username hanya boleh huruf, angka, underscore, atau tanda hubung."
        if len(password) < 6:
            return False, "Password minimal 6 karakter."

        users = self._load_users()
        if username in users:
            return False, f"Username '{username}' sudah terdaftar dalam sistem."

        if not permissions:
            permissions = self.get_default_permissions(role)

        salt = secrets.token_hex(16)
        users[username] = {
            "role": role,
            "name": name.strip() if name else username,
            "salt": salt,
            "password_hash": self._hash_password(password, salt),
            "hash_type": "pbkdf2",
            "permissions": permissions
        }

        if self._save_users(users):
            return True, f"Pengguna '{username}' berhasil ditambahkan."
        return False, "Gagal menyimpan data pengguna ke file sistem."

    def update_user(self, username: str, name: str = None, password: str = None, role: str = None, permissions: dict = None):
        """Memperbarui informasi nama, password, peran, dan hak akses pengguna"""
        username = username.strip().lower()
        users = self._load_users()
        if username not in users:
            return False, f"Pengguna '{username}' tidak ditemukan."

        user = users[username]
        if name is not None and name.strip():
            user["name"] = name.strip()

        if role is not None and role in ("admin", "operator"):
            user["role"] = role

        if permissions is not None and isinstance(permissions, dict):
            user["permissions"] = permissions

        if password is not None and str(password).strip():
            pw_str = str(password).strip()
            if len(pw_str) < 6:
                return False, "Password baru minimal 6 karakter."
            new_salt = secrets.token_hex(16)
            user["salt"] = new_salt
            user["password_hash"] = self._hash_password(pw_str, new_salt)
            user["hash_type"] = "pbkdf2"

        users[username] = user
        if self._save_users(users):
            return True, f"Data pengguna '{username}' berhasil diperbarui."
        return False, "Gagal menyimpan pembaruan pengguna."

    def delete_user(self, username: str, current_username: str = None):
        """Menghapus pengguna dari sistem dengan proteksi admin utama dan akun yang sedang aktif"""
        username = username.strip().lower()
        if username == "admin":
            return False, "Akun Administrator utama ('admin') tidak dapat dihapus."

        if current_username and username == current_username.strip().lower():
            return False, "Tidak dapat menghapus akun yang sedang aktif digunakan saat ini."

        users = self._load_users()
        if username not in users:
            return False, f"Pengguna '{username}' tidak ditemukan."

        del users[username]
        if self._save_users(users):
            return True, f"Pengguna '{username}' berhasil dihapus dari sistem."
        return False, "Gagal menghapus data pengguna."
