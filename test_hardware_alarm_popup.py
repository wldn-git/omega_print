# test_hardware_alarm_popup.py
import os
import time
import unittest
import tkinter as tk
from unittest.mock import MagicMock, patch
from main import OmegaBatchApp

class TestHardwareAlarmPopup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.app = OmegaBatchApp(cls.root)
        cls.test_cache_file = os.path.join(cls.app.data_manager.data_dir, "test_ink_cache_alarm_temp.json")
        cls.app.data_manager.ink_cache_file = cls.test_cache_file
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        try:
            if hasattr(cls.app, '_refresh_timer_id') and cls.app._refresh_timer_id:
                cls.root.after_cancel(cls.app._refresh_timer_id)
        except Exception:
            pass
        try:
            if hasattr(cls, 'test_cache_file') and os.path.exists(cls.test_cache_file):
                os.remove(cls.test_cache_file)
        except Exception:
            pass
        try:
            cls.root.destroy()
        except Exception:
            pass

    def tearDown(self):
        # Bersihkan dialog yang tersisa setelah tiap test
        if hasattr(self.app, '_active_alarm_dialogs'):
            for dev, win in list(self.app._active_alarm_dialogs.items()):
                try:
                    win.destroy()
                except Exception:
                    pass
            self.app._active_alarm_dialogs.clear()

    def test_01_popup_creation_and_ui_elements(self):
        """Verifikasi dialog alarm printer tercipta dengan elemen UI lengkap"""
        self.app.show_hardware_alarm_popup("printer")
        self.root.update()

        self.assertIn("printer", self.app._active_alarm_dialogs)
        win = self.app._active_alarm_dialogs["printer"]
        self.assertIsInstance(win, tk.Toplevel)

        # Cari tombol di dalam window
        buttons = []
        def _find_buttons(w):
            for child in w.winfo_children():
                if isinstance(child, tk.Button):
                    buttons.append(child)
                _find_buttons(child)
        _find_buttons(win)

        self.assertGreaterEqual(len(buttons), 2)
        btn_texts = [b.cget("text") for b in buttons]
        # Pastikan ada tombol retry dan dismiss
        self.assertTrue(any("Hubungkan" in t or "Retry" in t for t in btn_texts))
        self.assertTrue(any("Tutup" in t or "Dismiss" in t for t in btn_texts))

        # Tutup window
        win.destroy()
        self.app._active_alarm_dialogs.pop("printer", None)

    def test_02_prevent_duplicate_dialogs(self):
        """Verifikasi anti-spam: tidak membuka dialog ganda untuk perangkat yang sama"""
        self.app.show_hardware_alarm_popup("printer")
        self.root.update()
        win1 = self.app._active_alarm_dialogs["printer"]

        # Panggil lagi
        self.app.show_hardware_alarm_popup("printer")
        self.root.update()
        win2 = self.app._active_alarm_dialogs["printer"]

        self.assertIs(win1, win2)
        win1.destroy()
        self.app._active_alarm_dialogs.pop("printer", None)

    def test_03_scanner_alarm_and_retry_callback(self):
        """Verifikasi tombol Coba Hubungkan Ulang memicu reconnect scanner"""
        original_connect = self.app.connect_scanner
        mock_connect = MagicMock()
        self.app.connect_scanner = mock_connect

        try:
            self.app.show_hardware_alarm_popup("scanner1")
            self.root.update()
            win = self.app._active_alarm_dialogs["scanner1"]

            # Cari tombol Retry
            retry_btn = None
            def _find_retry(w):
                nonlocal retry_btn
                for child in w.winfo_children():
                    if isinstance(child, tk.Button) and ("Hubungkan" in child.cget("text") or "Retry" in child.cget("text")):
                        retry_btn = child
                        return
                    _find_retry(child)
            _find_retry(win)

            self.assertIsNotNone(retry_btn)
            # Klik tombol Retry
            retry_btn.invoke()
            time.sleep(0.1) # Beri waktu thread lambda berjalan

            mock_connect.assert_called_with(1)
            self.assertNotIn("scanner1", self.app._active_alarm_dialogs)
        finally:
            self.app.connect_scanner = original_connect

    def test_04_manual_disconnect_does_not_trigger_popup(self):
        """Verifikasi pemutusan manual oleh operator tidak memicu alarm darurat"""
        self.app.disconnect_scanner(1)
        self.root.update()
        self.assertTrue(self.app._manual_disconnect_s1)
        self.assertNotIn("scanner1", self.app._active_alarm_dialogs)

    def test_05_dismiss_button(self):
        """Verifikasi tombol Tutup / Abaikan menutup window dan membersihkan status dialog"""
        self.app.show_hardware_alarm_popup("scanner2")
        self.root.update()
        win = self.app._active_alarm_dialogs["scanner2"]

        # Cari tombol dismiss
        dismiss_btn = None
        def _find_dismiss(w):
            nonlocal dismiss_btn
            for child in w.winfo_children():
                if isinstance(child, tk.Button) and ("Tutup" in child.cget("text") or "Dismiss" in child.cget("text")):
                    dismiss_btn = child
                    return
                _find_dismiss(child)
        _find_dismiss(win)

        self.assertIsNotNone(dismiss_btn)
        dismiss_btn.invoke()
        self.root.update()

        self.assertNotIn("scanner2", self.app._active_alarm_dialogs)

    def test_06_auto_dismiss_alarm_popup(self):
        """Verifikasi _dismiss_alarm_popup menutup dialog secara otomatis saat hardware pulih"""
        self.app.show_hardware_alarm_popup("printer")
        self.root.update()
        self.assertIn("printer", self.app._active_alarm_dialogs)

        self.app._dismiss_alarm_popup("printer")
        self.root.update()
        self.assertNotIn("printer", self.app._active_alarm_dialogs)

    def test_07_stop_batch_clears_waiting_queue(self):
        """Verifikasi stop_batch_print membersihkan item waiting di GUI dan buffer"""
        # Masukkan item dummy ke waiting_queue
        item_id = self.app.tree.insert("", "end", values=("1", "SKU1", "QR1", "MAT1", "Antrean Cetak"), tags=('waiting',))
        self.app.waiting_queue.append(item_id)
        self.app.is_printing = True

        with patch.object(self.app, 'send_and_read', return_value="OK"), \
             patch('main.messagebox.askyesno', return_value=True):
            self.app.stop_batch_print()
            for _ in range(20):
                self.root.update()
                if len(self.app.waiting_queue) == 0:
                    break
                time.sleep(0.1)
            self.assertEqual(len(self.app.waiting_queue), 0)
        self.assertIn(self.app.tree.item(item_id, 'tags'), [(), '', []])

if __name__ == "__main__":
    unittest.main()
