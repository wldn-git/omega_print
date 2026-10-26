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
                "name": user.get("name", username)
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

    def get_user_list(self):
        """Mendapatkan daftar username dan role"""
        users = self._load_users()
        return [{"username": u, "role": d.get("role"), "name": d.get("name")} for u, d in users.items()]
