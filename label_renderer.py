# label_renderer.py
import os
import sys
import qrcode
from PIL import ImageTk, Image, ImageDraw, ImageFont

def get_asset_path(relative_path):
    """Mendapatkan path absolut ke file aset, bekerja baik di development maupun PyInstaller frozen bundle"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    candidate = os.path.join(base_path, relative_path)
    if os.path.exists(candidate):
        return candidate
    return os.path.abspath(relative_path)

class LabelRenderer:
    def __init__(self):
        pass

    def _get_val(self, coords, key):
        """Fungsi internal untuk membaca nilai kordinat dari StringVar Tkinter"""
        try: 
            return {k: int(v.get()) for k, v in coords[key].items()}
        except Exception: 
            return {"x": 0, "y": 0, "w": 20, "h": 20}

    def generate_preview(self, txt_sku, txt_qr, txt_matl, coords, w_canvas=710, h_canvas=280, preview_w=320):
        """Menghasilkan gambar Preview untuk UI Tkinter"""
        canvas = Image.new('RGB', (w_canvas, h_canvas), "white")
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([0, 0, w_canvas-1, h_canvas-1], outline="black", width=3)

        # Render QR
        q = self._get_val(coords, "qr")
        canvas.paste(qrcode.make(txt_qr).resize((q['w'], q['h'])), (q['x'], q['y']))

        # Render Logos dengan absolute asset resolver
        try:
            for k, f in [("syn", "syngenta.png"), ("ben", "benderang.png"), ("nk", "nk.png")]:
                c = self._get_val(coords, k)
                logo_file = get_asset_path(os.path.join("assets", f))
                if os.path.exists(logo_file):
                    img = Image.open(logo_file).convert("RGBA").resize((c['w'], c['h']), Image.Resampling.LANCZOS)
                    canvas.paste(img, (c['x'], c['y']), img)
        except Exception: 
            pass

        # Render Texts
        sku_c = self._get_val(coords, "sku")
        mat_c = self._get_val(coords, "matl")
        kup_c = self._get_val(coords, "txt_kupon")
        
        try:
            f_sku = ImageFont.truetype("arialbd.ttf", sku_c['w'])
            f_matl = ImageFont.truetype("arial.ttf", mat_c['w'])
            f_kup = ImageFont.truetype("arialbd.ttf", kup_c['w'])
            f_l = ImageFont.truetype("arial.ttf", 18)
        except Exception: 
            f_sku = f_matl = f_kup = f_l = ImageFont.load_default()
        
        draw.text((sku_c['x'], sku_c['y']), txt_sku, fill="black", font=f_sku)
        draw.text((mat_c['x'], mat_c['y']-20), "HOTLINE: 0 800 1 798 798", fill="black", font=f_l)
        draw.text((mat_c['x'], mat_c['y']), f"Material Code: {txt_matl}", fill="black", font=f_matl)
        draw.text((kup_c['x'], kup_c['y']), txt_qr, fill="black", font=f_kup)
        
        # Resize untuk preview UI
        p_h = int((preview_w / w_canvas) * h_canvas)
        preview_img = ImageTk.PhotoImage(canvas.resize((preview_w, p_h), Image.Resampling.LANCZOS))
        
        return preview_img, preview_w, p_h

    def export_pdf(self, txt_sku, txt_qr, txt_matl, coords, w_canvas=710, h_canvas=280):
        """Menghasilkan file PDF untuk Testing"""
        canvas = Image.new('RGB', (w_canvas, h_canvas), "white")
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([0, 0, w_canvas-1, h_canvas-1], outline="black", width=3)

        # Render QR
        q = self._get_val(coords, "qr")
        qr_img = qrcode.make(txt_qr).resize((q['w'], q['h']))
        canvas.paste(qr_img, (q['x'], q['y']))

        # Render Logos dengan absolute asset resolver
        try:
            for k, f in [("syn", "syngenta.png"), ("ben", "benderang.png"), ("nk", "nk.png")]:
                c = self._get_val(coords, k)
                logo_file = get_asset_path(os.path.join("assets", f))
                if os.path.exists(logo_file):
                    img = Image.open(logo_file).convert("RGBA").resize((c['w'], c['h']), Image.Resampling.LANCZOS)
                    canvas.paste(img, (c['x'], c['y']), img)
        except Exception: 
            pass

        # Render Texts
        sku_cfg = self._get_val(coords, "sku")
        mat_cfg = self._get_val(coords, "matl")
        kupon_cfg = self._get_val(coords, "txt_kupon")
        
        try:
            f_sku = ImageFont.truetype("arialbd.ttf", sku_cfg['w'])
            f_matl = ImageFont.truetype("arial.ttf", mat_cfg['w'])
            f_kupon = ImageFont.truetype("arialbd.ttf", kupon_cfg['w'])
            f_label = ImageFont.truetype("arial.ttf", 14)
        except Exception: 
            f_sku = f_matl = f_kupon = f_label = ImageFont.load_default()

        draw.text((sku_cfg['x'], sku_cfg['y']), txt_sku, fill="black", font=f_sku)
        draw.text((mat_cfg['x'], mat_cfg['y']-20), "HOTLINE: 0 800 1 798 798", fill="black", font=f_label)
        draw.text((mat_cfg['x'], mat_cfg['y']), "Material Code:", fill="black", font=f_matl)
        draw.text((mat_cfg['x']+155, mat_cfg['y']), txt_matl, fill="black", font=f_matl)
        draw.text((kupon_cfg['x'], kupon_cfg['y']), txt_qr, fill="black", font=f_kupon)

        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = os.path.join(output_dir, f"Test_Print_{txt_sku}.pdf")
        canvas.save(pdf_path, "PDF", resolution=200.0)
        
        return pdf_path