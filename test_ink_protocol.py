# test_ink_protocol.py
import unittest
from printer_omega import parse_ink_response, OmegaPrinter

class TestInkProtocol(unittest.TestCase):
    def test_parse_standard_4_heads_with_empty_slot(self):
        # Dokumentasi: INKV|99.0,99.0,99.0,-1\r\n
        raw = "INKV|99.0,99.0,99.0,-1\r\n"
        parsed = parse_ink_response(raw)
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0]["cartridge"], 1)
        self.assertEqual(parsed[0]["level"], 99.0)
        self.assertEqual(parsed[0]["status"], "ok")
        self.assertEqual(parsed[1]["cartridge"], 2)
        self.assertEqual(parsed[1]["level"], 99.0)
        self.assertEqual(parsed[2]["cartridge"], 3)
        self.assertEqual(parsed[2]["level"], 99.0)

    def test_parse_echo_two_cartridges(self):
        # Aktual user: INKVINKV|99.72,100.0
        raw = "INKVINKV|99.72,100.0"
        parsed = parse_ink_response(raw)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["cartridge"], 1)
        self.assertEqual(parsed[0]["level"], 99.72)
        self.assertEqual(parsed[0]["status"], "ok")
        self.assertEqual(parsed[1]["cartridge"], 2)
        self.assertEqual(parsed[1]["level"], 100.0)

    def test_status_thresholds(self):
        raw = "INKV|12.5,25.0,80.0"
        parsed = parse_ink_response(raw)
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0]["status"], "critical")
        self.assertEqual(parsed[1]["status"], "warning")
        self.assertEqual(parsed[2]["status"], "ok")

    def test_empty_or_invalid_responses(self):
        self.assertEqual(parse_ink_response(""), [])
        self.assertEqual(parse_ink_response(None), [])
        self.assertEqual(parse_ink_response("ERROR_CONN:timeout"), [])
        self.assertEqual(parse_ink_response("INKV|-1,-1"), [])
        self.assertEqual(parse_ink_response("RANDOM_TEXT"), [])

if __name__ == "__main__":
    unittest.main()

