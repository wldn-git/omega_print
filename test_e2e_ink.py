# test_e2e_ink.py
import unittest
import tkinter as tk
from unittest.mock import MagicMock
from printer_omega import parse_ink_response
from main import OmegaBatchApp

class TestE2EInkMonitoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.app = OmegaBatchApp(cls.root)
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def test_01_gui_card_existence_and_clean_title(self):
        """Verifikasi card Ink Cartridge Level ada dan judul teks polos tanpa emoji/ikon"""
        self.assertTrue(hasattr(self.app, 'card_ink_level'))
        self.assertTrue(hasattr(self.app, 'lbl_ink_title'))
        self.assertTrue(hasattr(self.app, 'f_ink_bars'))
        # Pastikan judul murni teks "Ink Cartridge Level"
        self.assertEqual(self.app.lbl_ink_title.cget("text"), "Ink Cartridge Level")

    def test_02_dynamic_two_cartridges_render(self):
        """Verifikasi perenderan dinamis 2 cartridge (kasus aktual: 99.72% dan 100.0%)"""
        two_cartridges = [
            {"cartridge": 1, "level": 99.72, "status": "ok"},
            {"cartridge": 2, "level": 100.0, "status": "ok"}
        ]
        self.app.update_ink_level_ui(two_cartridges)
        self.root.update()

        # Harus ada 2 widget baris di dalam f_ink_bars
        rows = self.app.f_ink_bars.winfo_children()
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(self.app.current_ink_levels), 2)
        self.assertEqual(self.app.current_ink_levels[0]["level"], 99.72)
        self.assertEqual(self.app.current_ink_levels[1]["level"], 100.0)

    def test_03_dynamic_three_cartridges_render(self):
        """Verifikasi perenderan dinamis jika printer mengirim 3 cartridge (slot ke-4 adalah -1)"""
        raw_reply = "INKV|99.0,85.5,12.0,-1\r\n"
        parsed = parse_ink_response(raw_reply)
        self.assertEqual(len(parsed), 3) # slot -1 diabaikan
        self.app.update_ink_level_ui(parsed)
        self.root.update()

        rows = self.app.f_ink_bars.winfo_children()
        self.assertEqual(len(rows), 3)
        self.assertEqual(self.app.current_ink_levels[2]["status"], "critical") # 12.0% < 15.0%

    def test_04_telemetry_payload_contains_ink(self):
        """Verifikasi telemetri /api/v1/status menyertakan data level tinta"""
        status_dict = self.app.get_system_status_dict()
        self.assertIn("ink_levels", status_dict)
        self.assertIn("ink_last_updated", status_dict)
        self.assertEqual(len(status_dict["ink_levels"]), 3)

if __name__ == "__main__":
    unittest.main()
