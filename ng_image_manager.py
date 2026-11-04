# ng_image_manager.py
"""
NG Image Manager for Keyence SR-X100
Handles fetching, caching, thumbnailing, watermarking, and displaying images captured by Keyence SR-X100.
Features:
- Embedded standalone background FTP server (pyftpdlib) for zero-dependency standalone installation.
- Smart auto-detection: If port 21 is already used (e.g., Keyence SRManagementTool), falls back to monitoring the Keyence FTP folder.
- If port 21 is free (fresh PC install), embedded FTP server starts automatically and receives images to data/ng_captures/incoming/.
- Full Industrial Watermarking for NG Incidents:
  Watermarks Box #, SKU, Coupon QR, Material Code, Timestamp, and Incident Type (MISMATCH / NOREAD).
- Automatic archiving into data/ng_captures/ and disk retention cleanup for OK images.
- Real-time event callback on image reception.
- Realistic simulated capture generation with watermark in simulation mode.
"""

import os
import glob
import time
import socket
import threading
from datetime import datetime
from PIL import Image, ImageTk, ImageDraw, ImageFont

DEFAULT_KEYENCE_FTP_DIR = r"C:\Users\Public\Documents\KEYENCE\SR-H7W\SRManagementTool\ftp"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FALLBACK_CAPTURE_DIR = os.path.join(BASE_DIR, "data", "ng_captures")


def is_port_in_use(port, host="127.0.0.1"):
    """Mengecek apakah port tertentu sedang digunakan oleh proses lain"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.bind((host, port))
            return False
        except (socket.error, OSError):
            return True


class EmbeddedFTPServer:
    """Server FTP internal ringan berbasis pyftpdlib untuk instalasi standalone tanpa software Keyence eksternal"""
    def __init__(self, target_dir, port=21, user="admin", password="admin", on_file_received_cb=None):
        self.target_dir = os.path.abspath(target_dir)
        self.port = port
        self.user = user
        self.password = password
        self.on_file_received_cb = on_file_received_cb
        self.server = None
        self.thread = None
        self.is_running = False

    def start(self):
        try:
            from pyftpdlib.authorizers import DummyAuthorizer
            from pyftpdlib.handlers import FTPHandler
            from pyftpdlib.servers import FTPServer

            if not os.path.exists(self.target_dir):
                os.makedirs(self.target_dir, exist_ok=True)

            authorizer = DummyAuthorizer()
            authorizer.add_user(self.user, self.password, self.target_dir, perm="elradfmw")

            cb = self.on_file_received_cb

            class CustomFTPHandler(FTPHandler):
                def on_file_received(self, file):
                    super().on_file_received(file)
                    if cb:
                        try:
                            cb(file)
                        except Exception:
                            pass

            handler = CustomFTPHandler
            handler.authorizer = authorizer
            handler.banner = "Omega MX Embedded FTP Ready."

            self.server = FTPServer(("0.0.0.0", self.port), handler)
            self.server.max_cons = 10
            self.server.max_cons_per_ip = 5

            def _serve():
                self.is_running = True
                try:
                    self.server.serve_forever(timeout=1.0)
                except Exception:
                    pass
                finally:
                    self.is_running = False

            self.thread = threading.Thread(target=_serve, daemon=True)
            self.thread.start()
            return True, f"Embedded FTP Server aktif di 0.0.0.0:{self.port} (Dir: {self.target_dir})"
        except Exception as e:
            self.is_running = False
            return False, f"Gagal memulai Embedded FTP: {e}"

    def stop(self):
        if self.server:
            try:
                self.server.close_all()
            except Exception:
                pass
            self.server = None
        self.is_running = False


class NGImageManager:
    def __init__(self, ftp_dir=None, fallback_dir=None, on_image_received=None):
        self.ftp_dir = ftp_dir or DEFAULT_KEYENCE_FTP_DIR
        self.archive_dir = fallback_dir or FALLBACK_CAPTURE_DIR
        self.incoming_dir = os.path.join(self.archive_dir, "incoming")
        self.fallback_dir = self.archive_dir  # Kompatibilitas mundur
        self._ensure_directories()
        self.last_ng_image_path = None
        self.last_ng_meta = {}
        self.on_image_received = on_image_received
        self.embedded_server = None
        self.server_status = "idle"

    def _ensure_directories(self):
        try:
            if not os.path.exists(self.archive_dir):
                os.makedirs(self.archive_dir, exist_ok=True)
            if not os.path.exists(self.incoming_dir):
                os.makedirs(self.incoming_dir, exist_ok=True)
        except Exception:
            pass

    def start_ftp_service(self, port=21, user="admin", password="admin"):
        """
        Smart FTP Initialization:
        1. Jika Port 21 sedang dipakai (misal Keyence SRManagementTool running):
           Mode fallback: Gunakan monitoring folder Keyence eksternal.
        2. Jika Port 21 BEBAS (di PC baru / fresh install):
           Nyalakan Embedded FTP Server internal otomatis!
        """
        self._ensure_directories()
        if is_port_in_use(port):
            self.server_status = "external_used"
            return False, f"Port {port} sudah digunakan oleh service lain (Keyence). Menggunakan mode monitoring folder eksternal."

        try:
            self.embedded_server = EmbeddedFTPServer(
                target_dir=self.incoming_dir,
                port=port,
                user=user,
                password=password,
                on_file_received_cb=self._on_embedded_file_received
            )
            ok, msg = self.embedded_server.start()
            if ok:
                self.server_status = "embedded_running"
            return ok, msg
        except Exception as e:
            self.server_status = "failed"
            return False, f"Gagal inisialisasi embedded FTP: {e}"

    def _on_embedded_file_received(self, file_path):
        """Callback saat file gambar baru selesai diupload oleh scanner ke embedded FTP"""
        self.last_ng_image_path = file_path
        if self.on_image_received:
            try:
                self.on_image_received(file_path)
            except Exception:
                pass

    def get_latest_ftp_image(self, max_age_seconds=60):
        """
        Mencari file gambar terbaru (.jpg, .jpeg, .png, .bmp) di folder FTP (embedded atau Keyence).
        """
        search_dirs = [self.incoming_dir, self.ftp_dir]
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

    def apply_ng_watermark(self, input_image_path, box_no, sku, coupon_qr, material_code, timestamp_str, incident_type, side="Side A", output_path=None):
        """
        Menerapkan watermark industri permanen ke gambar insiden NG:
        - Box #
        - SKU
        - Coupon QR
        - Material Code
        - Waktu
        - Jenis Insiden (MISMATCH atau NOREAD)
        Menyimpan gambar hasil watermark ke folder arsip NG secara thread-safe.
        """
        if not input_image_path or not os.path.exists(input_image_path):
            return None

        self._ensure_directories()
        try:
            with Image.open(input_image_path) as raw_img:
                img = raw_img.convert("RGB")

            w, h = img.size
            # Banner proporsional terhadap resolusi (minimal 90px, maks 160px)
            banner_h = max(90, min(160, int(h * 0.18)))

            # Semi-transparent dark overlay (Slate 900)
            overlay = Image.new("RGBA", (w, banner_h), (15, 23, 42, 240))
            img.paste(overlay, (0, h - banner_h), overlay)

            draw = ImageDraw.Draw(img)
            # Garis aksen merah pembatas banner
            accent_width = max(2, int(w * 0.003))
            draw.line([(0, h - banner_h), (w, h - banner_h)], fill=(220, 38, 38), width=accent_width)

            # Dynamic font sizing berdasarkan resolusi gambar (lebih besar, tebal & kontras)
            base_size = max(13, min(24, int(w / 40)))
            small_size = max(11, min(18, int(w / 50)))
            try:
                font_bold = ImageFont.truetype("segoeuib.ttf", base_size)
                font_regular = ImageFont.truetype("segoeui.ttf", small_size)
                font_badge = ImageFont.truetype("segoeuib.ttf", max(10, min(16, int(base_size * 0.95))))
            except Exception:
                font_bold = font_regular = font_badge = ImageFont.load_default()

            pad_x = max(12, int(w * 0.02))
            y_base = h - banner_h + int(banner_h * 0.13)

            # 1. Badge Jenis Insiden (Merah: MISMATCH / NOREAD)
            inc_upper = str(incident_type).upper()
            if "NOREAD" in inc_upper or "NO-READ" in inc_upper:
                badge_text = "NOREAD"
            elif "MISMATCH" in inc_upper:
                badge_text = "MISMATCH"
            else:
                badge_text = inc_upper

            badge_bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
            bw = (badge_bbox[2] - badge_bbox[0]) + 14
            bh = (badge_bbox[3] - badge_bbox[1]) + 6

            draw.rectangle([(pad_x, y_base), (pad_x + bw, y_base + bh)], fill=(220, 38, 38))
            draw.text((pad_x + 7, y_base + 3), badge_text, fill=(255, 255, 255), font=font_badge)

            # 2. Baris Atas: Box # | SKU | Side
            top_txt = f"Box #{box_no}   |   SKU: {sku}   |   {side}"
            draw.text((pad_x + bw + 12, y_base + 3), top_txt, fill=(255, 255, 255), font=font_bold)

            # 3. Baris Bawah: Coupon QR | Material Code | Waktu
            y_line2 = y_base + bh + int(banner_h * 0.12)
            bot_txt = f"Coupon QR: {coupon_qr}   |   Material Code: {material_code}   |   Waktu: {timestamp_str}"
            draw.text((pad_x, y_line2), bot_txt, fill=(226, 232, 240), font=font_regular)

            if not output_path:
                ts_clean = timestamp_str.replace(":", "").replace("-", "").replace(" ", "_")
                filename = f"ng_box{box_no}_{badge_text}_{ts_clean}.jpg"
                output_path = os.path.join(self.archive_dir, filename)

            img.save(output_path, "JPEG", quality=90)
            return output_path
        except Exception as e:
            print(f"[NG WATERMARK ERROR] {e}")
            return input_image_path

    def process_ng_capture(self, box_no, sku, coupon_qr, material_code, timestamp_str, incident_type, side="Side A", is_sim=False):
        """
        Memproses tangkapan insiden NG:
        1. Jika aktual (bukan simulasi), cari file gambar terbaru dari incoming FTP.
        2. Jika ditemukan, beri watermark lengkap dan simpan ke archive_dir.
        3. Jika tidak ditemukan atau mode simulasi, buat gambar simulasi berwatermark lengkap.
        4. Mengembalikan path file gambar berwatermark yang siap ditampilkan dan dibuka full-res.
        """
        self._ensure_directories()
        raw_img_path = None

        if not is_sim:
            raw_img_path = self.get_latest_ftp_image(max_age_seconds=60)

        if raw_img_path and os.path.exists(raw_img_path):
            watermarked_path = self.apply_ng_watermark(
                input_image_path=raw_img_path,
                box_no=box_no,
                sku=sku,
                coupon_qr=coupon_qr,
                material_code=material_code,
                timestamp_str=timestamp_str,
                incident_type=incident_type,
                side=side
            )
            # Hapus file raw dari incoming agar tidak dipakai ulang boks berikutnya
            try:
                if os.path.abspath(raw_img_path) != os.path.abspath(watermarked_path):
                    os.remove(raw_img_path)
            except Exception:
                pass
            return watermarked_path
        else:
            return self.generate_simulated_ng_image(
                box_no=box_no,
                sku=sku,
                coupon_qr=coupon_qr,
                material_code=material_code,
                timestamp_str=timestamp_str,
                incident_type=incident_type,
                side=side
            )

    def cleanup_incoming_ftp_images(self, max_age_seconds=10):
        """
        Membersihkan file gambar raw sementara dari folder FTP saat boks dinilai OK
        agar kapasitas disk tidak membengkak ketika Keyence diset ke mode 'All images'.
        """
        search_dirs = [self.incoming_dir, self.ftp_dir]
        valid_extensions = ("*.jpg", "*.jpeg", "*.png", "*.bmp")
        now = time.time()
        for s_dir in search_dirs:
            if not os.path.exists(s_dir):
                continue
            for ext in valid_extensions:
                pattern = os.path.join(s_dir, ext)
                for f in glob.glob(pattern):
                    try:
                        mtime = os.path.getmtime(f)
                        if (now - mtime) <= max_age_seconds or (now - mtime) > 3600:
                            os.remove(f)
                    except Exception:
                        pass

    def get_thumbnail_pil(self, image_path, target_width=250, target_height=140):
        """
        Membuat thumbnail PIL Image dari file gambar dengan menjaga aspect ratio.
        Thread-safe karena mengembalikan PIL Image murni.
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

        draw.rectangle([(0, 0), (target_width - 1, target_height - 1)], outline=(203, 213, 225), width=1)

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

    def generate_simulated_ng_image(self, box_no, sku, coupon_qr=None, material_code=None, timestamp_str=None, incident_type="NOREAD", side="Side A", **kwargs):
        """
        Membuat gambar simulasi tangkapan Keyence SR-X monokrom/industrial
        dengan watermark lengkap saat berjalan dalam Mode Simulasi.
        """
        self._ensure_directories()
        w, h = 640, 400
        img = Image.new("RGB", (w, h), (30, 35, 45))
        draw = ImageDraw.Draw(img)

        # Kompatibilitas argumen lama
        if coupon_qr is None and "qr" in kwargs:
            coupon_qr = kwargs["qr"]
        if incident_type == "NOREAD" and "reason" in kwargs:
            incident_type = kwargs["reason"]
        if material_code is None:
            material_code = "-"
        if timestamp_str is None:
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Grid garis halus simulasi sensor CMOS
        for y in range(0, h, 40):
            draw.line([(0, y), (w, y)], fill=(38, 44, 56), width=1)
        for x in range(0, w, 40):
            draw.line([(x, 0), (x, h)], fill=(38, 44, 56), width=1)

        # Simulasi kardus karton di tengah frame
        box_left, box_top = 100, 50
        box_right, box_bottom = 540, 290
        draw.rectangle([(box_left, box_top), (box_right, box_bottom)], fill=(55, 60, 72), outline=(80, 88, 105), width=2)

        # Simulasi label stiker putih di kardus
        lbl_l, lbl_t = 180, 80
        lbl_r, lbl_b = 460, 260
        draw.rectangle([(lbl_l, lbl_t), (lbl_r, lbl_b)], fill=(220, 222, 226), outline=(255, 255, 255), width=1)

        # Bounding box deteksi Keyence (Merah untuk NG / NOREAD / MISMATCH)
        draw.rectangle([(lbl_l + 20, lbl_t + 20), (lbl_r - 20, lbl_b - 20)], outline=(239, 68, 68), width=3)
        draw.line([(lbl_l + 10, lbl_t + 10), (lbl_l + 30, lbl_t + 10)], fill=(239, 68, 68), width=4)
        draw.line([(lbl_l + 10, lbl_t + 10), (lbl_l + 10, lbl_t + 30)], fill=(239, 68, 68), width=4)

        try:
            font_title = ImageFont.truetype("segoeuib.ttf", 15)
            font_sub = ImageFont.truetype("segoeui.ttf", 11)
        except Exception:
            font_title = font_sub = ImageFont.load_default()

        # Banner status internal Keyence
        draw.rectangle([(20, 15), (280, 42)], fill=(220, 38, 38))
        draw.text((28, 20), f"KEYENCE SR-X100 [{incident_type}]", fill=(255, 255, 255), font=font_title)

        draw.text((lbl_l + 30, lbl_b - 50), f"Coupon: {coupon_qr}", fill=(15, 23, 42), font=font_sub)
        draw.text((lbl_l + 30, lbl_b - 32), f"SKU: {sku}", fill=(71, 85, 105), font=font_sub)

        # Simpan file sementara untuk diproses watermark
        ts_clean = timestamp_str.replace(":", "").replace("-", "").replace(" ", "_")
        temp_filename = f"temp_sim_{box_no}_{ts_clean}.jpg"
        temp_path = os.path.join(self.archive_dir, temp_filename)
        img.save(temp_path, "JPEG", quality=85)

        # Terapkan watermark resmi
        final_path = self.apply_ng_watermark(
            input_image_path=temp_path,
            box_no=box_no,
            sku=sku,
            coupon_qr=coupon_qr,
            material_code=material_code,
            timestamp_str=timestamp_str,
            incident_type=incident_type,
            side=side
        )

        try:
            if os.path.exists(temp_path) and os.path.abspath(temp_path) != os.path.abspath(final_path):
                os.remove(temp_path)
        except Exception:
            pass

        return final_path

    def open_image_fullscreen(self, image_path):
        """Membuka gambar di default image viewer OS"""
        if image_path and os.path.exists(image_path):
            try:
                os.startfile(os.path.abspath(image_path))
                return True
            except Exception:
                return False
        return False
