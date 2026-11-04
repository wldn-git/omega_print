# printer_omega.py
import socket
import threading
import time

class OmegaPrinter:
    def __init__(self):
        self._lock = threading.Lock()
        self.sock = None
        self.current_ip = None
        self.current_port = None

    def disconnect(self):
        """Menutup koneksi socket aktif dengan aman"""
        with self._lock:
            if self.sock:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None
                self.current_ip = None
                self.current_port = None

    def _ensure_connected(self, ip, port):
        """Memastikan socket terhubung ke printer (Persistent Connection)"""
        port = int(port)
        if self.sock and (self.current_ip != ip or self.current_port != port):
            # Konfigurasi IP/Port berganti, reset socket lama
            if self.sock:
                try: self.sock.close()
                except Exception: pass
            self.sock = None

        if self.sock is None:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            try:
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            s.settimeout(2.5)
            s.connect((ip, port))

            # Bersihkan greeting awal dengan timeout singkat (0.3s) agar tidak blocking lama
            s.settimeout(0.3)
            try:
                s.recv(1024)
            except Exception:
                pass
            s.settimeout(2.5)

            self.sock = s
            self.current_ip = ip
            self.current_port = port

    def test_connection(self, ip, port):
        """Test koneksi aktual ke printer dan validasi respon STATUS"""
        try:
            reply = self.send_and_read(ip, port, "STATUS")
            if reply and not reply.startswith("ERROR_CONN:"):
                return True, f"Printer Online! (Respon: {reply})"
            return False, f"Printer tidak merespon perintah STATUS ({reply})"
        except Exception as e:
            return False, str(e)

    def _flush_input(self):
        """Menguras buffer sisa respons terdahulu agar tidak tertukar dengan perintah baru"""
        if not self.sock:
            return
        try:
            self.sock.setblocking(False)
            while True:
                data = self.sock.recv(4096)
                if not data:
                    break
        except Exception:
            pass
        finally:
            if self.sock:
                self.sock.setblocking(True)
                self.sock.settimeout(2.5)

    def send_and_read(self, ip, port, message):
        """Kirim perintah ke Omega menggunakan persistent socket dengan auto-recovery/reconnect"""
        with self._lock:
            # Upaya pertama menggunakan socket yang sudah ada
            try:
                self._ensure_connected(ip, port)
                self._flush_input()
                self.sock.sendall(message.encode('utf-8'))
                reply = self.sock.recv(1024).decode('utf-8', errors='ignore').strip()
                if reply:
                    return reply
                # Jika recv kosong, socket telah ditutup oleh server
                raise socket.error("Remote printer menutup koneksi (recv kosong).")
            except Exception:
                # Upaya kedua: Reconnect otomatis (Auto-recovery)
                try:
                    if self.sock:
                        try: self.sock.close()
                        except Exception: pass
                    self.sock = None
                    self._ensure_connected(ip, port)
                    self._flush_input()
                    self.sock.sendall(message.encode('utf-8'))
                    reply = self.sock.recv(1024).decode('utf-8', errors='ignore').strip()
                    return reply if reply else "SENT_NO_REPLY"
                except Exception as e2:
                    if self.sock:
                        try: self.sock.close()
                        except Exception: pass
                    self.sock = None
                    return f"ERROR_CONN:{e2}"

    def get_current_print_count(self, ip, port):
        """Ambil angka current printout (CSTATUS)"""
        reply = self.send_and_read(ip, port, "CSTATUS")
        if reply and "CSTATUS|" in reply:
            try:
                data_part = reply.split("|")[1]          
                current_count = int(data_part.split(",")[0]) 
                return current_count
            except Exception:
                pass
        return -1

    def get_ink_levels(self, ip, port):
        """
        Mengambil level persentase tinta seluruh cartridge aktif melalui perintah INKV.
        Mengembalikan list data cartridge atau list kosong jika gagal / offline.
        """
        reply = self.send_and_read(ip, port, "INKV")
        if reply and not reply.startswith("ERROR_CONN:"):
            return parse_ink_response(reply)
        return []


def parse_ink_response(reply):
    """
    Mem-parsing jawaban perintah INKV dari printer Omega.
    Contoh balasan:
    - "INKV|99.0,99.0,99.0,-1\r\n"
    - "INKVINKV|99.72,100.0"
    - "INKV|100.0,-1"
    Nilai -1 menunjukkan tidak ada cartridge terpasang pada slot tersebut.
    Mengembalikan list dict:
    [
        {"cartridge": 1, "level": 99.0, "status": "ok"},
        {"cartridge": 2, "level": 99.0, "status": "ok"},
        {"cartridge": 3, "level": 99.0, "status": "ok"}
    ]
    Status:
    - "ok": > 30%
    - "warning": 15% - 30%
    - "critical": < 15%
    """
    if not reply or not isinstance(reply, str):
        return []
    if "|" not in reply:
        return []

    try:
        data_part = reply.split("|", 1)[1].strip()
        tokens = [t.strip() for t in data_part.split(",") if t.strip()]
        result = []
        for idx, tok in enumerate(tokens, start=1):
            try:
                val = float(tok)
                # Slot bernilai negatif (seperti -1) menandakan tidak ada cartridge terpasang
                if val >= 0:
                    status = "ok"
                    if val < 15.0:
                        status = "critical"
                    elif val <= 30.0:
                        status = "warning"
                    result.append({
                        "cartridge": idx,
                        "level": round(val, 2),
                        "status": status
                    })
            except ValueError:
                continue
        return result
    except Exception:
        return []
