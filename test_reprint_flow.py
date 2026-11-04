# test_reprint_flow.py
import os
import unittest
import tkinter as tk
from unittest.mock import patch, MagicMock
from main import OmegaBatchApp

class TestReprintFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.app = OmegaBatchApp(cls.root)
        cls.test_cache_file = os.path.join(cls.app.data_manager.data_dir, "test_ink_cache_reprint_temp.json")
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

    def setUp(self):
        # Bersihkan tabel treeview
        for item in self.app.tree.get_children():
            self.app.tree.delete(item)
        self.app.waiting_queue.clear()
        self.app.ng_list.clear()

    def test_01_reprint_prompt_when_only_ng_remains(self):
        """Verifikasi jika hanya tersisa item NG, START BATCH PRINT menawarkan Reprint NG"""
        # Masukkan 1 item OK dan 2 item NG
        it_ok = self.app.tree.insert("", "end", values=("1", "SKU1", "QR1", "MAT1", "QC OK"), tags=('ok',))
        it_ng1 = self.app.tree.insert("", "end", values=("2", "SKU2", "QR2", "MAT2", "QC NG"), tags=('ng',))
        it_ng2 = self.app.tree.insert("", "end", values=("3", "SKU3", "QR3", "MAT3", "QC NG"), tags=('ng',))
        self.app.is_simulation.set(True)

        with patch('main.messagebox.askyesno', return_value=True) as mock_yesno, \
             patch.object(self.app, 'do_printing_loop') as mock_loop:
            self.app.run_batch_print()
            mock_yesno.assert_called()
            mock_loop.assert_called_with([it_ng1, it_ng2])
            self.assertEqual(self.app.print_cycle, 2)

    def test_02_already_judged_items_counted_in_progres(self):
        """Verifikasi data yang sudah OK dihitung di progres agar tidak desync 2/3 (Left: 1)"""
        it_ok = self.app.tree.insert("", "end", values=("1", "SKU1", "QR1", "MAT1", "QC OK"), tags=('ok',))
        it_new1 = self.app.tree.insert("", "end", values=("2", "SKU2", "QR2", "MAT2", "Siap Cetak"), tags=())
        it_new2 = self.app.tree.insert("", "end", values=("3", "SKU3", "QR3", "MAT3", "Siap Cetak"), tags=())
        self.app.total_valid_print_data = 3
        self.app.is_simulation.set(True)

        with patch('main.messagebox.askyesno', return_value=True), \
             patch('threading.Thread'):
            self.app.run_batch_print()
            self.assertEqual(self.app.count_ok, 1) # Item 1 dihitung
            self.assertEqual(self.app.current_judgments, 1) # Start dari 1
            self.assertEqual(self.app.expected_total_judgments, 3)

if __name__ == "__main__":
    unittest.main()
