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
            if hasattr(socket, 'SIO_KEEPALIVE_VALS'):
                try:
                    # Windows TCP KeepAlive: aktif (1), waktu tunggu 2000ms, interval probe 1000ms
                    s.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 2000, 1000))
                except Exception:
                    pass
            try:
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            s.settimeout(2.5)
            s.connect((ip, port))

            # Bersihkan greeting awal dengan timeout singkat (0.6s) agar buffer bersih
            s.settimeout(0.6)
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
            reply = self.send_and_read(ip, port, "STATUS|0,0")
            if reply and not reply.startswith("ERROR_CONN:") and "EER" not in reply.upper():
                return True, f"Printer Online! (Respon: {reply})"
            return False, f"Printer tidak merespon perintah STATUS ({reply})"
        except Exception as e:
            return False, str(e)

    def check_status(self, ip, port):
        """
        Pengecekan status online printer menggunakan perintah STATUS (Watchdog).
        Format sukses: STATUS|0,0, STATUS|0,1, STATUS|1,0, atau COMD|... (printer merespons, socket TCP aktif).
        Format gagal: STATUS |EER atau timeout / connection error (ERROR_CONN:...).
        Mengembalikan tuple: (is_online: bool, reply: str)
        """
        try:
            reply = self.send_and_read(ip, port, "STATUS|0,0")
            if not reply:
                return False, "NO_REPLY"
            if reply.startswith("ERROR_CONN:"):
                return False, reply
            if "EER" in reply.upper():
                return False, reply
            # Jika printer merespons string apa pun (STATUS|..., COMD|ERR, COMD|OK),
            # ini membuktikan bahwa perangkat keras dan kabel fisik TCP 100% terhubung & aktif!
            return True, reply
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
        # Standardisasi terminasi & parameter protokol ASCII Omega MX
        clean_cmd = message.strip()
        if clean_cmd == "STATUS":
            message = "STATUS|0,0\r\n"
        elif clean_cmd == "CSTATUS":
            message = "CSTATUS|0,0\r\n"
        elif not message.endswith("\r\n"):
            if message.endswith("\n"):
                message = message[:-1] + "\r\n"
            elif message.endswith("\r"):
                message = message + "\n"
            else:
                message = message + "\r\n"

        # Perintah kontrol searah (one-way commands): printer memproses aksi internal tanpa mengirim teks balasan.
        # Tidak perlu menunggu recv() agar tidak terjadi timeout palsu yang memicu popup disconnect.
        is_oneway = clean_cmd.upper() in ("START", "STOP", "CLR", "CLEAR")

        with self._lock:
            # Upaya pertama menggunakan socket yang sudah ada
            try:
                self._ensure_connected(ip, port)
                self._flush_input()
                self.sock.sendall(message.encode('utf-8'))
                if is_oneway:
                    return "OK"
                reply = self.sock.recv(1024).decode('utf-8', errors='ignore').strip()
                if reply and "SERVER CONNECTED" in reply.upper():
                    try:
                        reply = self.sock.recv(1024).decode('utf-8', errors='ignore').strip()
                    except Exception:
                        pass
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
                    if is_oneway:
                        return "OK"
                    reply = self.sock.recv(1024).decode('utf-8', errors='ignore').strip()
                    if reply and "SERVER CONNECTED" in reply.upper():
                        try:
                            reply = self.sock.recv(1024).decode('utf-8', errors='ignore').strip()
                        except Exception:
                            pass
                    return reply if reply else "SENT_NO_REPLY"
                except Exception as e2:
                    if self.sock:
                        try: self.sock.close()
                        except Exception: pass
                    self.sock = None
                    return f"ERROR_CONN:{e2}"

    def get_current_print_count(self, ip, port):
        """Ambil angka current printout (CSTATUS)"""
        reply = self.send_and_read(ip, port, "CSTATUS|0,0")
        if reply and "CSTATUS|" in reply:
            try:
                data_part = reply.split("|")[1]          
                parts = data_part.split(",")
                # Format: CSTATUS|0,239 (di mana 239 adalah total cetak fisik)
                if len(parts) >= 2 and parts[1].strip().isdigit():
                    return int(parts[1].strip())
                return int(parts[0].strip())
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
