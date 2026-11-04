# test_hardware_watchdog.py
import unittest
from unittest.mock import patch, MagicMock
from printer_omega import OmegaPrinter

class TestHardwareWatchdog(unittest.TestCase):
    def setUp(self):
        self.printer = OmegaPrinter()

    @patch.object(OmegaPrinter, 'send_and_read')
    def test_printer_status_success(self, mock_send):
        # Sesuai gambar spesifikasi: STATUS|0,0\r\n
        mock_send.return_value = "STATUS|0,0\r\n"
        is_online, reply = self.printer.check_status("192.168.100.10", 6008)
        self.assertTrue(is_online)
        self.assertIn("STATUS|0,0", reply)

    @patch.object(OmegaPrinter, 'send_and_read')
    def test_printer_status_play(self, mock_send):
        mock_send.return_value = "STATUS|1,0\r\n"
        is_online, reply = self.printer.check_status("192.168.100.10", 6008)
        self.assertTrue(is_online)

    @patch.object(OmegaPrinter, 'send_and_read')
    def test_printer_status_failure_eer(self, mock_send):
        # Sesuai gambar spesifikasi: STATUS |EER \r\n (failed to obtain)
        mock_send.return_value = "STATUS |EER \r\n"
        is_online, reply = self.printer.check_status("192.168.100.10", 6008)
        self.assertFalse(is_online)

    @patch.object(OmegaPrinter, 'send_and_read')
    def test_printer_status_conn_error(self, mock_send):
        mock_send.return_value = "ERROR_CONN:[WinError 10061] target machine actively refused it"
        is_online, reply = self.printer.check_status("192.168.100.10", 6008)
        self.assertFalse(is_online)

if __name__ == "__main__":
    unittest.main()
