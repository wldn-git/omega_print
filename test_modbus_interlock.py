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

if __name__ == '__main__':
    unittest.main()

