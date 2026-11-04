# test_ng_watermark.py
import os
import time
import unittest
import tkinter as tk
from PIL import Image
from ng_image_manager import NGImageManager
from main import OmegaBatchApp

class TestNGWatermark(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.app = OmegaBatchApp(cls.root)
        cls.root.update()

        cls.test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_temp_ng")
        cls.test_archive = os.path.join(cls.test_dir, "archive")
        cls.test_incoming = os.path.join(cls.test_dir, "incoming")
        os.makedirs(cls.test_archive, exist_ok=True)
        os.makedirs(cls.test_incoming, exist_ok=True)

        cls.mgr = NGImageManager(ftp_dir=cls.test_incoming, fallback_dir=cls.test_archive)

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

        # Cleanup test files
        import shutil
        if os.path.exists(cls.test_dir):
            try:
                shutil.rmtree(cls.test_dir, ignore_errors=True)
            except Exception:
                pass

    def test_01_apply_ng_watermark_mismatch(self):
        """Verifikasi watermark diterapkan pada insiden MISMATCH dengan 6 atribut lengkap"""
        raw_path = os.path.join(self.test_incoming, "test_raw_mismatch.jpg")
        img = Image.new("RGB", (640, 480), (60, 60, 60))
        img.save(raw_path, "JPEG")

        watermarked = self.mgr.apply_ng_watermark(
            input_image_path=raw_path,
            box_no=5,
            sku="NK 6172 BTGT",
            coupon_qr="ECQPEJ9Z",
            material_code="3XNUAMFA",
            timestamp_str="2026-11-04 16:15:30",
            incident_type="MISMATCH",
            side="Side A"
        )

        self.assertTrue(os.path.exists(watermarked))
        self.assertIn("MISMATCH", watermarked)
        # Verifikasi gambar valid dan dapat dibuka oleh Pillow
        with Image.open(watermarked) as im:
            self.assertEqual(im.size, (640, 480))

    def test_02_apply_ng_watermark_noread(self):
        """Verifikasi watermark diterapkan pada insiden NOREAD"""
        raw_path = os.path.join(self.test_incoming, "test_raw_noread.jpg")
        img = Image.new("RGB", (640, 480), (40, 40, 40))
        img.save(raw_path, "JPEG")

        watermarked = self.mgr.apply_ng_watermark(
            input_image_path=raw_path,
            box_no=3,
            sku="NK 6172 BTGT",
            coupon_qr="ECAL9AAA",
            material_code="3XJUH6AZ",
            timestamp_str="2026-11-04 16:18:00",
            incident_type="NOREAD",
            side="Side B"
        )

        self.assertTrue(os.path.exists(watermarked))
        self.assertIn("NOREAD", watermarked)

    def test_03_process_ng_capture_archives_and_cleans_incoming(self):
        """Verifikasi process_ng_capture mengarsipkan hasil watermark dan menghapus raw incoming"""
        raw_path = os.path.join(self.test_incoming, "incoming_box7.jpg")
        img = Image.new("RGB", (800, 600), (70, 70, 70))
        img.save(raw_path, "JPEG")

        final_path = self.mgr.process_ng_capture(
            box_no=7,
            sku="SKU-PROD-99",
            coupon_qr="QR999",
            material_code="MAT999",
            timestamp_str="2026-11-04 16:20:00",
            incident_type="MISMATCH",
            side="Side A",
            is_sim=False
        )

        self.assertTrue(os.path.exists(final_path))
        # Raw file di incoming harus sudah dibersihkan
        self.assertFalse(os.path.exists(raw_path))

    def test_04_cleanup_incoming_ftp_images(self):
        """Verifikasi cleanup_incoming_ftp_images menghapus foto raw OK dari incoming tanpa menyentuh archive"""
        ok_raw = os.path.join(self.test_incoming, "ok_box10.jpg")
        img = Image.new("RGB", (400, 300), (80, 80, 80))
        img.save(ok_raw, "JPEG")
        self.assertTrue(os.path.exists(ok_raw))

        # Panggil cleanup dengan max_age_seconds besar agar terhapus
        self.mgr.cleanup_incoming_ftp_images(max_age_seconds=100)
        self.assertFalse(os.path.exists(ok_raw))

    def test_05_main_app_trigger_ng_capture_update(self):
        """Verifikasi trigger_ng_capture_update di main app memperbarui label badge dan info"""
        self.app.trigger_ng_capture_update(
            box_no=12,
            box_sku="TEST-SKU",
            box_qr="TEST-QR",
            box_mat="TEST-MAT",
            s1_str="MISMATCHED-VAL",
            s2_str="TEST-QR"
        )

        for _ in range(15):
            self.root.update()
            if self.app.lbl_ng_badge.cget("text") == "SIDE A : MISMATCH":
                break
            time.sleep(0.05)

        self.assertEqual(self.app.lbl_ng_badge.cget("text"), "SIDE A : MISMATCH")
        self.assertIn("Box #12", self.app.lbl_ng_info.cget("text"))
        self.assertIsNotNone(self.app.current_ng_image_path)
        self.assertTrue(os.path.exists(self.app.current_ng_image_path))

if __name__ == "__main__":
    unittest.main()
