# ng_image_manager.py
"""
NG Image Manager for Keyence SR-X100
Handles fetching, caching, thumbnailing, and displaying images captured by Keyence SR-X100
transferred via the local Keyence FTP service or generated in simulation mode.
"""

import os
import glob
import time
from datetime import datetime
from PIL import Image, ImageTk, ImageDraw, ImageFont

DEFAULT_KEYENCE_FTP_DIR = r"C:\Users\Public\Documents\KEYENCE\SR-H7W\SRManagementTool\ftp"
FALLBACK_CAPTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ng_captures")

class NGImageManager:
    def __init__(self, ftp_dir=None, fallback_dir=None):
        self.ftp_dir = ftp_dir or DEFAULT_KEYENCE_FTP_DIR
        self.fallback_dir = fallback_dir or FALLBACK_CAPTURE_DIR
        self._ensure_directories()
        self.last_ng_image_path = None
        self.last_ng_meta = {}

    def _ensure_directories(self):
        try:
            if not os.path.exists(self.fallback_dir):
                os.makedirs(self.fallback_dir, exist_ok=True)
        except Exception:
            pass

    def get_latest_ftp_image(self, max_age_seconds=60):
        """
        Mencari file gambar terbaru (.jpg, .jpeg, .png, .bmp) di folder FTP Keyence.
        Jika max_age_seconds diberikan, hanya ambil file yang dibuat/dimodifikasi baru-baru ini.
        """
        search_dirs = [self.ftp_dir, self.fallback_dir]
        valid_extensions = ("*.jpg", "*.jpeg", "*.png", "*.bmp")
        
        latest_file = None
        latest_mtime = 0

        for s_dir in search_dirs:
            if not os.path.exists(s_dir):
                continue
            for ext in valid_extensions:
                pattern = os.path.join(s_dir, ext)
                files = glob.glob(pattern)
                for f in files:
                    try:
                        mtime = os.path.getmtime(f)
                        if mtime > latest_mtime:
                            latest_mtime = mtime
                            latest_file = f
                    except Exception:
                        continue

        if latest_file:
            if max_age_seconds is None or (time.time() - latest_mtime) <= max_age_seconds:
                return latest_file
            return latest_file
        return None

    def get_thumbnail_pil(self, image_path, target_width=250, target_height=140):
        """
        Membuat thumbnail PIL Image dari file gambar dengan menjaga aspect ratio.
        Thread-safe karena hanya mengembalikan PIL Image murni (belum dikonversi ke Tkinter PhotoImage).
        """
        if not image_path or not os.path.exists(image_path):
            return None

        try:
            with Image.open(image_path) as img:
                img_copy = img.copy()
                img_copy.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
                
                thumb_w, thumb_h = img_copy.size
                background = Image.new("RGB", (target_width, target_height), (15, 23, 42)) # Slate 900
                offset_x = (target_width - thumb_w) // 2
                offset_y = (target_height - thumb_h) // 2
                background.paste(img_copy, (offset_x, offset_y))
                return background
        except Exception:
            return None

    def get_placeholder_pil(self, target_width=250, target_height=140, text="No NG capture yet"):
        """
        Membuat PIL Image placeholder kosong yang rapi saat belum ada insiden NG.
        """
        img = Image.new("RGB", (target_width, target_height), (241, 245, 249)) # Slate 100
        draw = ImageDraw.Draw(img)

        # Border tipis
        draw.rectangle([(0, 0), (target_width - 1, target_height - 1)], outline=(203, 213, 225), width=1)

        # Teks placeholder di tengah
        try:
            font = ImageFont.truetype("segoeui.ttf", 11)
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        pos_x = (target_width - text_w) // 2
        pos_y = (target_height - text_h) // 2
        draw.text((pos_x, pos_y), text, fill=(148, 163, 184), font=font)

        return img

    def generate_simulated_ng_image(self, box_no, sku, qr, side="Side A", reason="NOREAD"):
        """
        Membuat gambar simulasi tangkapan Keyence SR-X monokrom/industrial
        saat berjalan dalam Mode Simulasi.
        """
        self._ensure_directories()
        w, h = 640, 400
        img = Image.new("RGB", (w, h), (30, 35, 45))
        draw = ImageDraw.Draw(img)

        # Grid garis halus simulasi sensor CMOS
        for y in range(0, h, 40):
            draw.line([(0, y), (w, y)], fill=(38, 44, 56), width=1)
        for x in range(0, w, 40):
            draw.line([(x, 0), (x, h)], fill=(38, 44, 56), width=1)

        # Simulasi kardus karton di tengah frame
        box_left, box_top = 100, 70
        box_right, box_bottom = 540, 330
        draw.rectangle([(box_left, box_top), (box_right, box_bottom)], fill=(55, 60, 72), outline=(80, 88, 105), width=2)

        # Simulasi label stiker putih di kardus
        lbl_l, lbl_t = 180, 110
        lbl_r, lbl_b = 460, 290
        draw.rectangle([(lbl_l, lbl_t), (lbl_r, lbl_b)], fill=(220, 222, 226), outline=(255, 255, 255), width=1)

        # Bounding box deteksi Keyence (Merah untuk NG / NOREAD)
        draw.rectangle([(lbl_l + 20, lbl_t + 20), (lbl_r - 20, lbl_b - 20)], outline=(239, 68, 68), width=3)
        draw.line([(lbl_l + 10, lbl_t + 10), (lbl_l + 30, lbl_t + 10)], fill=(239, 68, 68), width=4)
        draw.line([(lbl_l + 10, lbl_t + 10), (lbl_l + 10, lbl_t + 30)], fill=(239, 68, 68), width=4)

        try:
            font_title = ImageFont.truetype("segoeuib.ttf", 16)
            font_sub = ImageFont.truetype("segoeui.ttf", 12)
        except Exception:
            font_title = font_sub = ImageFont.load_default()

        # Banner status NG
        draw.rectangle([(20, 15), (280, 45)], fill=(220, 38, 38))
        draw.text((28, 20), f"KEYENCE SR-X100 [{reason}]", fill=(255, 255, 255), font=font_title)

        # Info metadata kardus di pojok kanan atas
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        draw.text((360, 16), f"{side} | Box #{box_no}", fill=(203, 213, 225), font=font_title)
        draw.text((360, 38), f"{ts}", fill=(148, 163, 184), font=font_sub)

        # Teks detail di bagian bawah kardus
        draw.text((lbl_l + 30, lbl_b - 50), f"Expected: {qr}", fill=(15, 23, 42), font=font_sub)
        draw.text((lbl_l + 30, lbl_b - 32), f"SKU: {sku}", fill=(71, 85, 105), font=font_sub)

        filename = f"sim_ng_box{box_no}_{int(time.time())}.jpg"
        filepath = os.path.join(self.fallback_dir, filename)
        img.save(filepath, "JPEG", quality=85)
        return filepath

    def open_image_fullscreen(self, image_path):
        """Membuka gambar di default image viewer OS"""
        if image_path and os.path.exists(image_path):
            try:
                os.startfile(os.path.abspath(image_path))
                return True
            except Exception:
                return False
        return False
