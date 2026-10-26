# modbus_io.py
import threading
import time
from pymodbus.client import ModbusTcpClient, ModbusSerialClient

class ModbusController:
    def __init__(self):
        self._lock = threading.Lock()
        self._tcp_client = None
        self._tcp_cfg = None
        self._rtu_client = None
        self._rtu_cfg = None
        self._coil_locks = {}
        self._coil_lock_mutex = threading.Lock()

    def _get_coil_lock(self, address):
        with self._coil_lock_mutex:
            if address not in self._coil_locks:
                self._coil_locks[address] = threading.Lock()
            return self._coil_locks[address]

    def close_all(self):
        """Menutup seluruh koneksi Modbus yang aktif"""
        with self._lock:
            if self._tcp_client is not None:
                try:
                    self._tcp_client.close()
                except Exception:
                    pass
                self._tcp_client = None
                self._tcp_cfg = None
            if self._rtu_client is not None:
                try:
                    self._rtu_client.close()
                except Exception:
                    pass
                self._rtu_client = None
                self._rtu_cfg = None

    def _get_tcp_client(self, ip, port):
        """Mendapatkan atau menginisiasi koneksi persistent Modbus TCP"""
        cfg = (str(ip), int(port))
        if self._tcp_client is not None and self._tcp_cfg != cfg:
            try: self._tcp_client.close()
            except Exception: pass
            self._tcp_client = None
            self._tcp_cfg = None

        if self._tcp_client is None:
            self._tcp_client = ModbusTcpClient(ip, port=int(port))
            self._tcp_cfg = cfg

        if not self._tcp_client.connected:
            self._tcp_client.connect()
        return self._tcp_client

    def _get_rtu_client(self, com, baud, parity, stopbits, databits):
        """Mendapatkan atau menginisiasi koneksi persistent Modbus RTU / Serial"""
        p_str = parity[0] if parity != "None" else 'N'
        cfg = (str(com), int(baud), p_str, int(float(stopbits)), int(databits))
        if self._rtu_client is not None and self._rtu_cfg != cfg:
            try: self._rtu_client.close()
            except Exception: pass
            self._rtu_client = None
            self._rtu_cfg = None

        if self._rtu_client is None:
            self._rtu_client = ModbusSerialClient(
                port=com, baudrate=int(baud), parity=p_str,
                stopbits=int(float(stopbits)), bytesize=int(databits), timeout=1
            )
            self._rtu_cfg = cfg

        if not self._rtu_client.connected:
            self._rtu_client.connect()
        return self._rtu_client

    def test_tcp(self, ip, port, slave_id=1):
        """Test koneksi TCP Modbus: Coba baca Coil (DO), Discrete Input (DI), dan Holding Register (HR)"""
        with self._lock:
            try:
                client = self._get_tcp_client(ip, port)
                if client.connected:
                    # 1. Coba baca Coils / DO (F01) - Prioritas utama
                    res_coils = client.read_coils(address=0, count=4, device_id=int(slave_id))
                    if not res_coils.isError():
                        return True, f"Koneksi Sukses! Modbus I/O Online.\nStatus Coil/DO: {res_coils.bits[:4]}"

                    # 2. Coba baca Discrete Inputs / DI (F02)
                    res_di = client.read_discrete_inputs(address=0, count=4, device_id=int(slave_id))
                    if not res_di.isError():
                        return True, f"Koneksi Sukses! Modbus I/O Online.\nStatus Input/DI: {res_di.bits[:4]}"

                    # 3. Fallback: Coba baca Holding Register (F03)
                    res_hr = client.read_holding_registers(address=0, count=1, device_id=int(slave_id))
                    if not res_hr.isError():
                        val = res_hr.registers[0]
                        return True, f"Koneksi Sukses!\nData Register[0]: {val}"

                    return False, "Modbus Terhubung, tapi Slave menolak bacaan.\n(Pastikan Slave ID sesuai di simulator)."
                else:
                    return False, f"Gagal koneksi ke Modbus Slave ({ip}:{port}).\nPastikan Simulator/PLC sedang aktif."
            except Exception as e:
                self.close_all()
                return False, f"Modbus Exception: {str(e)}"

    def test_rtu(self, com, baud, parity, stopbits, databits, slave_id=1):
        """Test koneksi RTU/Serial Modbus: Coba baca Coil (DO), Discrete Input (DI), dan Holding Register (HR)"""
        with self._lock:
            try:
                client = self._get_rtu_client(com, baud, parity, stopbits, databits)
                if client.connected:
                    # 1. Coba baca Coils / DO (F01)
                    res_coils = client.read_coils(address=0, count=4, device_id=int(slave_id))
                    if not res_coils.isError():
                        return True, f"Koneksi Berhasil! Modbus RTU Online.\nStatus Coil/DO: {res_coils.bits[:4]}"

                    # 2. Coba baca Discrete Inputs / DI (F02)
                    res_di = client.read_discrete_inputs(address=0, count=4, device_id=int(slave_id))
                    if not res_di.isError():
                        return True, f"Koneksi Berhasil! Modbus RTU Online.\nStatus Input/DI: {res_di.bits[:4]}"

                    # 3. Fallback: Coba baca Holding Register (F03)
                    res_hr = client.read_holding_registers(address=0, count=1, device_id=int(slave_id))
                    if not res_hr.isError():
                        val = res_hr.registers[0]
                        return True, f"Koneksi Berhasil!\nData Register[0]: {val}"

                    return False, "RTU Terhubung, tapi Slave tidak merespon bacaan (Cek Slave ID)."
                else:
                    return False, f"Gagal buka port {com}"
            except Exception as e:
                self.close_all()
                return False, f"RTU Error: {str(e)}"

    def read_io_tcp(self, ip, port, slave_id=1):
        """Membaca 4 bit DI & 4 bit DO via TCP menggunakan persistent connection"""
        with self._lock:
            try:
                client = self._get_tcp_client(ip, port)
                if client.connected:
                    di_res = client.read_discrete_inputs(address=0, count=4, device_id=int(slave_id))
                    do_res = client.read_coils(address=0, count=4, device_id=int(slave_id))
                    if not di_res.isError() and not do_res.isError():
                        return True, di_res.bits[:4], do_res.bits[:4], ""
                    else:
                        # Auto-recovery: Reconnect jika respon error
                        self._tcp_client = None
                        return False, [], [], "Gagal baca data bit I/O."
                return False, [], [], "Port Tertutup / Simulator Offline"
            except Exception as e:
                self._tcp_client = None
                return False, [], [], str(e)

    def read_io_rtu(self, com, baud, parity, stopbits, databits, slave_id=1):
        """Membaca 4 bit DI & 4 bit DO via RTU/Serial menggunakan persistent connection"""
        with self._lock:
            try:
                client = self._get_rtu_client(com, baud, parity, stopbits, databits)
                if client.connected:
                    di_res = client.read_discrete_inputs(address=0, count=4, device_id=int(slave_id))
                    do_res = client.read_coils(address=0, count=4, device_id=int(slave_id))
                    if not di_res.isError() and not do_res.isError():
                        return True, di_res.bits[:4], do_res.bits[:4], ""
                    else:
                        self._rtu_client = None
                        return False, [], [], "Gagal baca data bit I/O RTU."
                return False, [], [], f"Gagal buka {com}"
            except Exception as e:
                self._rtu_client = None
                return False, [], [], str(e)

    def write_coil_tcp(self, ip, port, address, value, slave_id=1):
        """Menulis 1 bit Coil / DO via TCP menggunakan persistent connection"""
        with self._lock:
            try:
                client = self._get_tcp_client(ip, port)
                if client.connected:
                    res = client.write_coil(address=int(address), value=bool(value), device_id=int(slave_id))
                    if not res.isError():
                        return True, f"Coil {address} diset ke {value}"
                    self._tcp_client = None
                    return False, f"Modbus Error tulis coil {address}: {res}"
                return False, f"Gagal koneksi ke Modbus TCP {ip}:{port}"
            except Exception as e:
                self._tcp_client = None
                return False, f"Exception write_coil_tcp: {str(e)}"

    def write_coil_rtu(self, com, baud, parity, stopbits, databits, address, value, slave_id=1):
        """Menulis 1 bit Coil / DO via RTU/Serial menggunakan persistent connection"""
        with self._lock:
            try:
                client = self._get_rtu_client(com, baud, parity, stopbits, databits)
                if client.connected:
                    res = client.write_coil(address=int(address), value=bool(value), device_id=int(slave_id))
                    if not res.isError():
                        return True, f"Coil {address} diset ke {value}"
                    self._rtu_client = None
                    return False, f"Modbus Error tulis coil {address}: {res}"
                return False, f"Gagal buka port {com}"
            except Exception as e:
                self._rtu_client = None
                return False, f"Exception write_coil_rtu: {str(e)}"

    def pulse_coil_tcp(self, ip, port, address, duration=0.5, slave_id=1, on_complete=None):
        """Memberi pulsa aktif (ON -> durasi -> OFF) ke Solenoid/Rejector via TCP di background thread (antrean aman per-coil)"""
        coil_lock = self._get_coil_lock(address)
        def _pulse():
            with coil_lock:
                ok_on, msg_on = self.write_coil_tcp(ip, port, address, True, slave_id)
                time.sleep(duration)
                ok_off, msg_off = self.write_coil_tcp(ip, port, address, False, slave_id)
                if on_complete:
                    on_complete(ok_on and ok_off, f"Pulse DO {address} selesai.")

        t = threading.Thread(target=_pulse, daemon=True)
        t.start()
        return t

    def pulse_coil_rtu(self, com, baud, parity, stopbits, databits, address, duration=0.5, slave_id=1, on_complete=None):
        """Memberi pulsa aktif (ON -> durasi -> OFF) ke Solenoid/Rejector via RTU di background thread (antrean aman per-coil)"""
        coil_lock = self._get_coil_lock(address)
        def _pulse():
            with coil_lock:
                ok_on, msg_on = self.write_coil_rtu(com, baud, parity, stopbits, databits, address, True, slave_id)
                time.sleep(duration)
                ok_off, msg_off = self.write_coil_rtu(com, baud, parity, stopbits, databits, address, False, slave_id)
                if on_complete:
                    on_complete(ok_on and ok_off, f"Pulse DO {address} selesai.")

        t = threading.Thread(target=_pulse, daemon=True)
        t.start()
        return t