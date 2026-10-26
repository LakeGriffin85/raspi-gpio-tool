import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gpio_core import GPIOController, PHYSICAL, pin_snapshot
from gpiozero.pins.mock import MockFactory


class GPIOTests(unittest.TestCase):
    def setUp(self):
        self.factory = MockFactory()
        self.controller = GPIOController(self.factory)

    def tearDown(self):
        self.controller.close()

    def test_startup_never_claims_a_pin(self):
        self.assertIsNone(self.controller.device)
        self.assertEqual(self.factory.pins, {})

    def test_output_starts_low_and_can_switch_both_ways(self):
        self.controller.activate(17, "output")
        self.assertFalse(self.controller.level)
        self.controller.write(True)
        self.assertTrue(self.controller.level)
        self.controller.write(False)
        self.assertFalse(self.controller.level)

    def test_input_tracks_external_signal(self):
        self.controller.activate(17, "input", "none")
        self.controller.device.pin.drive_high()
        self.assertTrue(self.controller.level)
        self.controller.device.pin.drive_low()
        self.assertFalse(self.controller.level)

    def test_pull_up_and_pull_down(self):
        self.controller.activate(17, "input", "up")
        self.assertTrue(self.controller.level)
        self.controller.release()
        self.controller.activate(17, "input", "down")
        self.assertFalse(self.controller.level)

    def test_input_cannot_be_written(self):
        self.controller.activate(17, "input", "up")
        with self.assertRaises(RuntimeError):
            self.controller.write(False)
        self.assertEqual(self.controller.device.pin.function, "input")

    def test_release_drives_output_low_before_closing(self):
        self.controller.activate(17, "output")
        pin = self.controller.device.pin
        self.controller.write(True)
        self.controller.release()
        self.assertFalse(pin.states[-1].state)
        self.assertEqual(pin.function, "input")
        self.assertIsNone(self.controller.device)
        self.assertIsNone(self.controller.pin)
        self.controller.release()

    def test_cannot_change_pin_while_active(self):
        self.controller.activate(17, "output")
        with self.assertRaises(RuntimeError):
            self.controller.activate(18, "output")
        self.assertEqual(self.controller.pin, 17)

    def test_reserved_invalid_pin_and_mode_rejected_before_claim(self):
        for pin, mode, pull in [(0, "output", "none"), (1, "input", "up"),
                                (99, "output", "none"), (17, "invalid", "none"),
                                (17, "input", "invalid")]:
            with self.assertRaises(ValueError):
                self.controller.activate(pin, mode, pull)
        self.assertEqual(self.factory.pins, {})

    def test_same_hardware_pin_cannot_be_claimed_by_two_controllers(self):
        other = GPIOController(self.factory)
        self.controller.activate(17, "output")
        with self.assertRaises(Exception):
            other.activate(17, "output")
        self.assertIsNone(other.device)

    def test_cleanup_even_if_output_off_fails(self):
        self.controller.activate(17, "output")
        device = self.controller.device
        with patch.object(device, "off", side_effect=RuntimeError("disconnected")):
            with self.assertRaises(RuntimeError):
                self.controller.release()
        self.assertTrue(device.closed)
        self.assertIsNone(self.controller.device)

    def test_read_only_snapshot_invokes_only_get(self):
        with patch("gpio_core.shutil.which", return_value="/usr/bin/pinctrl"), \
                patch("gpio_core.subprocess.run") as run:
            run.return_value.stdout = "17: ip pu | hi // GPIO17 = input"
            value, detail = pin_snapshot(17)
        self.assertTrue(value)
        self.assertIn("GPIO17", detail)
        self.assertEqual(run.call_args.args[0], ["/usr/bin/pinctrl", "get", "17"])

    def test_header_mapping_excludes_power_ground_and_reserved(self):
        self.assertEqual(PHYSICAL[17], 11)
        self.assertEqual(len(set(PHYSICAL.values())), 26)
        self.assertTrue(set(PHYSICAL.values()).isdisjoint({1, 2, 4, 6, 9, 14, 17,
                                                         20, 25, 27, 28, 30, 34, 39}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
