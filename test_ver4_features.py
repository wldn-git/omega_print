# test_ver4_features.py
import os
import time
import unittest
import tkinter as tk
from unittest.mock import patch, MagicMock
from i18n import tr
from auth_manager import AuthManager
from data_manager import DataManager
from printer_omega import OmegaPrinter
from main import OmegaBatchApp

class TestVer4Features(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.app = OmegaBatchApp(cls.root)
        cls.app.printer.send_and_read = MagicMock(return_value="OK")
        cls.app.printer.test_connection = MagicMock(return_value=(True, "Online"))
        cls.app.printer.check_status = MagicMock(return_value=(True, "STATUS|1,0"))
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        try:
            if hasattr(cls.app, '_refresh_timer_id') and cls.app._refresh_timer_id:
                cls.root.after_cancel(cls.app._refresh_timer_id)
        except Exception:
            pass
        try:
            cls.root.destroy()
        except Exception:
            pass

    def test_01_developer_account_credentials_and_seeding(self):
        """Verifikasi akun developer dengan password 123456 dan role developer selalu tersedia"""
        auth = AuthManager()
        success, uinfo, msg = auth.authenticate("developer", "123456")
        self.assertTrue(success, f"Autentikasi developer gagal: {msg}")
        self.assertEqual(uinfo["role"], "developer")
        self.assertIn("simulation_mode", uinfo["permissions"]["features"])
        self.assertIn("developer_tools", uinfo["permissions"]["features"])

    def test_02_developer_account_hidden_from_standard_listings(self):
        """Verifikasi akun developer disembunyikan dari dropdown login dan tabel user publik"""
        auth = AuthManager()
        users_public = auth.get_all_users_details(include_advance=False)
        usernames_public = [u["username"] for u in users_public]
        self.assertNotIn("developer", usernames_public)

        user_list_public = auth.get_user_list(include_advance=False)
        self.assertNotIn("developer", [u["username"] for u in user_list_public])

        # Pastikan akun developer tidak bisa dihapus oleh user management
        can_delete, del_msg = auth.delete_user("developer")
        self.assertFalse(can_delete)

    def test_03_admin_and_operator_permissions_lack_simulation(self):
        """Verifikasi role admin dan operator tidak memiliki izin simulation_mode"""
        auth = AuthManager()
        admin_perms = auth.get_default_permissions("admin")
        self.assertNotIn("simulation_mode", admin_perms["features"])

        op_perms = auth.get_default_permissions("operator")
        self.assertNotIn("simulation_mode", op_perms["features"])

    def test_04_default_simulation_is_false_on_startup(self):
        """Verifikasi variabel mode simulasi secara default adalah False saat aplikasi dimulai"""
        self.assertFalse(self.app.is_simulation.get())
        self.assertFalse(self.app.auto_judge_sim.get())

    def test_05_apply_user_permissions_simulation_visibility(self):
        """Verifikasi card_sim dan is_simulation hanya aktif untuk role developer"""
        # 1. Login sebagai Operator
        self.app.current_user = {"username": "operator", "role": "operator", "name": "Op", "permissions": {}}
        self.app.is_simulation.set(True) # Coba paksa True
        self.app.apply_user_permissions()
        self.assertFalse(self.app.is_simulation.get())
        self.assertFalse(self.app.check_is_simulation())
        self.assertFalse(bool(self.app.card_sim.winfo_manager()))

        # 2. Login sebagai Admin
        self.app.current_user = {"username": "admin", "role": "admin", "name": "Administrator", "permissions": {}}
        self.app.is_simulation.set(True) # Coba paksa True
        self.app.apply_user_permissions()
        self.assertFalse(self.app.is_simulation.get())
        self.assertFalse(self.app.check_is_simulation())
        self.assertFalse(bool(self.app.card_sim.winfo_manager()))

        # 3. Login sebagai Developer
        self.app.current_user = {"username": "developer", "role": "developer", "name": "Dev", "permissions": {}}
        self.app.apply_user_permissions()
        self.assertTrue(bool(self.app.card_sim.winfo_manager()))
        self.assertEqual(self.app.lbl_user_badge.cget("text"), "DEVELOPER: Dev")

    def test_06_printer_protocol_crlf_enforcement(self):
        """Verifikasi OmegaPrinter secara otomatis menambahkan CRLF jika belum ada"""
        printer = OmegaPrinter()
        mock_sock = MagicMock()
        printer.sock = mock_sock
        printer.current_ip = "127.0.0.1"
        printer.current_port = 6008
        printer._flush_input = MagicMock() # Mock flush agar tidak loop membaca mock recv

        mock_sock.recv.return_value = b"OK\r\n"
        reply = printer.send_and_read("127.0.0.1", 6008, "STOP")
        mock_sock.sendall.assert_called_with(b"STOP\r\n")

        reply = printer.send_and_read("127.0.0.1", 6008, "CLR\n")
        mock_sock.sendall.assert_called_with(b"CLR\r\n")

        reply = printer.send_and_read("127.0.0.1", 6008, "RESET|2\r\n")
        mock_sock.sendall.assert_called_with(b"RESET|2\r\n")

    def test_07_stop_batch_print_clears_queue_and_resets_unprinted_items(self):
        """Verifikasi STOP batch membersihkan antrean, mereset item belum tercetak ke Siap Cetak, dan purge printer"""
        # Setup tabel simulasi
        for item in self.app.tree.get_children():
            self.app.tree.delete(item)
        self.app.table_items_data.clear()
        self.app.waiting_queue.clear()

        it1 = self.app.tree.insert("", "end", values=("1", "SKU1", "QR1", "MAT1", "QC OK"), tags=('ok',))
        it2 = self.app.tree.insert("", "end", values=("2", "SKU2", "QR2", "MAT2", "In Print Queue"), tags=('waiting',))
        it3 = self.app.tree.insert("", "end", values=("3", "SKU3", "QR3", "MAT3", "In Print Queue"), tags=('waiting',))

        self.app.table_items_data[it1] = {'no': '1', 'sku': 'SKU1', 'qr': 'QR1', 'mat': 'MAT1', 'status': 'QC OK'}
        self.app.table_items_data[it2] = {'no': '2', 'sku': 'SKU2', 'qr': 'QR2', 'mat': 'MAT2', 'status': 'In Print Queue'}
        self.app.table_items_data[it3] = {'no': '3', 'sku': 'SKU3', 'qr': 'QR3', 'mat': 'MAT3', 'status': 'In Print Queue'}

        self.app.waiting_queue.extend([it2, it3])
        self.app.is_printing = True

        with patch('main.messagebox.askyesno', return_value=True), \
             patch.object(self.app.data_manager, 'remove_unprinted_coupons') as mock_remove_cp:
            self.app.stop_batch_print()
            self.root.update()

            # Verifikasi item 2 dan 3 dikembalikan ke Siap Cetak
            ready_str = tr("st_ready_print")
            self.assertEqual(self.app.tree.set(it2, "status"), ready_str)
            self.assertEqual(self.app.tree.set(it3, "status"), ready_str)
            self.assertIn(self.app.tree.item(it2, 'tags'), ('', ()))
            self.assertIn(self.app.tree.item(it3, 'tags'), ('', ()))
            self.assertEqual(self.app.table_items_data[it2]['status'], ready_str)

            # Item 1 (OK) tidak boleh berubah
            self.assertEqual(self.app.tree.set(it1, "status"), "QC OK")
            self.assertEqual(self.app.tree.item(it1, 'tags'), ('ok',))

            # Waiting queue kosong
            self.assertEqual(len(self.app.waiting_queue), 0)

            # Kupon unprinted dihapus dari database index duplikat
            mock_remove_cp.assert_called_once()
            args, _ = mock_remove_cp.call_args
            self.assertIn("QR2", args[0])
            self.assertIn("QR3", args[0])

    def test_08_startup_auto_connect_triggers_silent_hardware_calls(self):
        """Verifikasi auto_connect_hardware_on_startup memanggil test_tcp dan connect_all_scanners secara silent"""
        with patch.object(self.app, 'test_tcp') as mock_test_tcp, \
             patch.object(self.app, 'connect_all_scanners') as mock_conn_scanners:
            self.app.auto_connect_hardware_on_startup()
            mock_test_tcp.assert_called_once_with(silent=True)
            mock_conn_scanners.assert_called_once_with(silent=True)

if __name__ == "__main__":
    unittest.main()
