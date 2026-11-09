import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk
import time
from main import OmegaBatchApp
from modbus_io import ModbusController

class TestModbusInterlock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        with patch.object(OmegaBatchApp, 'auto_connect_hardware_on_startup', return_value=None):
            self.app = OmegaBatchApp(self.root)
        self.app.modbus = MagicMock(spec=ModbusController)

    def tearDown(self):
        self.app.is_io_running = False

    def test_evaluate_conveyor_permissive_idle(self):
        """Saat idle (belum batch print), konveyor tidak diizinkan jalan (DO 4 = False)"""
        self.app.is_printing = False
        self.assertFalse(self.app.evaluate_conveyor_permissive())

    def test_evaluate_conveyor_permissive_running(self):
        """Saat batch RUNNING dan semua hardware aman, konveyor diizinkan jalan (DO 4 = True)"""
        self.app.is_printing = True
        self.app.pause_requested = False
        self.app.stop_requested = False
        self.app.interlock_alarm_active = False
        self.app.modbus_alarm_active = False
        self.app.cascade_warning_active = False
        self.app._active_alarm_dialogs = {}
        self.app.printer_connected = True
        self.app.is_listening1 = True
        self.app.is_listening2 = True
        self.app.is_simulation.set(False)

        self.assertTrue(self.app.evaluate_conveyor_permissive())

    def test_evaluate_conveyor_permissive_safety_pause(self):
        """Saat di-PAUSE atau ada alarm interlock, konveyor harus dilarang jalan (DO 4 = False)"""
        self.app.is_printing = True
        self.app.printer_connected = True
        self.app.is_listening1 = True
        self.app.is_listening2 = True
        self.app.is_simulation.set(False)

        # 1. Operator Pause
        self.app.pause_requested = True
        self.assertFalse(self.app.evaluate_conveyor_permissive())

        # 2. Interlock / E-Stop Alarm
        self.app.pause_requested = False
        self.app.interlock_alarm_active = True
        self.assertFalse(self.app.evaluate_conveyor_permissive())

        # 3. Disconnect Dialog Active
        self.app.interlock_alarm_active = False
        self.app._active_alarm_dialogs = {"printer": MagicMock()}
        self.assertFalse(self.app.evaluate_conveyor_permissive())

    def test_e_stop_di3_tripped_auto_pauses(self):
        """Jika DI 3 (E-Stop/Angin) drop ke False (0) saat cetak, sistem otomatis PAUSE & matikan izin konveyor"""
        self.app.is_printing = True
        self.app.pause_requested = False
        self.app.is_simulation.set(False)

        # DI: [DI0=1, DI1=0, DI2=0, DI3=0 (E-Stop Off), DI4=1]
        di_bits = [True, False, False, False, True]
        self.app._process_di_signals(di_bits)

        self.assertTrue(self.app.interlock_alarm_active)
        self.assertTrue(self.app.pause_requested)
        self.assertFalse(self.app.evaluate_conveyor_permissive())

    def test_conveyor_feedback_trip_auto_pauses(self):
        """Jika konveyor diberi izin jalan tapi motor mati/trip (DI 4 = False) setelah 2.5s, sistem otomatis PAUSE"""
        self.app.is_printing = True
        self.app.pause_requested = False
        self.app.is_simulation.set(False)
        self.app._last_conveyor_permissive = True
        self.app._conveyor_permissive_start_time = time.time() - 3.0 # Sudah lewat 3 detik

        # DI: [DI0=0, DI1=0, DI2=0, DI3=1, DI4=0 (Motor tidak berputar)]
        di_bits = [False, False, False, True, False]
        self.app._process_di_signals(di_bits)

        self.assertTrue(self.app._conveyor_feedback_alarm_active)
        self.assertTrue(self.app.pause_requested)

    def test_modbus_controller_padding_fallback(self):
        """Memastikan driver modbus_io mengisi bit default saat slave hanya mengembalikan 4 bit"""
        modbus = ModbusController()
        mock_client = MagicMock()
        mock_res_di = MagicMock()
        mock_res_di.isError.return_value = False
        mock_res_di.bits = [True, False, True, False] # 4 bit
        mock_client.read_discrete_inputs.return_value = mock_res_di

        mock_res_do = MagicMock()
        mock_res_do.isError.return_value = False
        mock_res_do.bits = [False, True, False, True] # 4 bit
        mock_client.read_coils.return_value = mock_res_do

        modbus._get_tcp_client = MagicMock(return_value=mock_client)

        ok, di_bits, do_bits, err = modbus.read_io_tcp("127.0.0.1", 502, slave_id=1, di_count=5, do_count=6)
        self.assertTrue(ok)
        self.assertEqual(len(di_bits), 5)
        self.assertEqual(len(do_bits), 6)
        self.assertEqual(di_bits[0:4], [True, False, True, False])
        self.assertEqual(di_bits[4], False) # Padded bit
        self.assertEqual(do_bits[4], False) # Padded bit
        self.assertEqual(do_bits[5], False) # Padded bit

    def test_modbus_server_option_b_operations(self):
        """Memastikan fungsionalitas Modbus TCP Server (Opsi B) berjalan sempurna: DO coils, DI coils, pulse, dan lifecycle"""
        modbus = ModbusController()
        test_port = 15505
        ok, msg = modbus.start_tcp_server(host='127.0.0.1', port=test_port)
        self.assertTrue(ok)
        self.assertTrue(modbus.is_tcp_server_running())

        try:
            # 1. PC set DO 0..5
            test_do = [True, False, True, False, True, False]
            modbus.server_set_do_coils(test_do)
            self.assertTrue(modbus.server_get_coil(0))
            self.assertFalse(modbus.server_get_coil(1))
            self.assertTrue(modbus.server_get_coil(4))

            # 2. PLC menulis ke coils 10..14 (DI) via TCP client
            from pyModbusTCP.client import ModbusClient
            c = ModbusClient('127.0.0.1', test_port, auto_open=True, auto_close=True)
            w_ok = c.write_multiple_coils(10, [True, True, False, True, False])
            self.assertTrue(w_ok)

            # 3. PC membaca DI 0..4 dari server
            ok_di, di_bits, err = modbus.server_get_di_coils(start_address=10, count=5)
            self.assertTrue(ok_di)
            self.assertEqual(di_bits, [True, True, False, True, False])

            # 4. PC membaca DO yang dibaca PLC
            plc_read_do = c.read_coils(0, 6)
            self.assertEqual(plc_read_do, test_do)

            # 5. Test pulse DO 0
            t = modbus.server_pulse_do(address=0, duration=0.1)
            time.sleep(0.05)
            self.assertTrue(modbus.server_get_coil(0))
            t.join()
            self.assertFalse(modbus.server_get_coil(0))
        finally:
            modbus.stop_tcp_server()
            self.assertFalse(modbus.is_tcp_server_running())

    def test_sync_conveyor_permissive_server_mode(self):
        """Saat dalam mode Server (Opsi B), sinkronisasi izin konveyor harus memanggil server_set_coil(4, val)"""
        self.app.modbus_role.set("Server (Opsi B: PLC TCPMDR/W)")
        self.app.modbus_mode.set("TCP")
        self.app.is_printing = True
        self.app.pause_requested = False
        self.app.stop_requested = False
        self.app.interlock_alarm_active = False
        self.app.modbus_alarm_active = False
        self.app.cascade_warning_active = False
        self.app._active_alarm_dialogs = {}
        self.app.printer_connected = True
        self.app.is_listening1 = True
        self.app.is_listening2 = True
        self.app.is_simulation.set(False)

        self.app.modbus.server_set_coil = MagicMock()
        self.app._sync_conveyor_permissive()
        time.sleep(0.1) # Beri waktu worker thread

        self.app.modbus.server_set_coil.assert_called_with(4, True)

if __name__ == '__main__':
    unittest.main()

