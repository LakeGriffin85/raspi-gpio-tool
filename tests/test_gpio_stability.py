from pathlib import Path
import sys
import tempfile
import struct
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gpio_core import GPIOController, PinState, find_header_chip, read_chip_info
from gpio_support import friendly_error
from gpiozero.pins.mock import MockFactory


class StabilityTests(unittest.TestCase):
    def test_500_activation_release_cycles_close_all_owned_factories(self):
        factories = []

        def build():
            factory = MockFactory()
            original = factory.close
            factory.closed_by_controller = False

            def close():
                original()
                factory.closed_by_controller = True

            factory.close = close
            factories.append(factory)
            return factory

        controller = GPIOController(factory_builder=build)
        for index in range(500):
            pin = (17, 18, 22, 23)[index % 4]
            mode = 'output' if index % 2 else 'input'
            controller.activate(pin, mode, 'up')
            if mode == 'output':
                controller.write(True)
            else:
                self.assertIsNone(controller.device.pin.when_changed)
            controller.release()
            self.assertIsNone(controller.factory)
            self.assertIsNone(controller.device)
            self.assertTrue(factories[-1].closed_by_controller)
        self.assertEqual(len(factories), 500)
        controller.close()

    def test_failed_activation_closes_factory_and_allows_clean_retry(self):
        factory = MockFactory()
        with patch.object(factory, 'close', wraps=factory.close) as close:
            controller = GPIOController(factory_builder=lambda: factory)
            with patch('gpiozero.DigitalOutputDevice', side_effect=RuntimeError('GPIO busy')):
                with self.assertLogs('raspi_gpio', level='ERROR'):
                    with self.assertRaises(RuntimeError):
                        controller.activate(17, 'output')
            close.assert_called_once()
            self.assertIsNone(controller.factory)
            self.assertIsNone(controller.device)
        controller._factory_builder = MockFactory
        controller.activate(17, 'output')
        self.assertFalse(controller.level)
        controller.close()

    def test_hardware_preflight_does_not_overwrite_i2c_spi_or_uart(self):
        for pin, function in [(2, 'SDA1'), (10, 'SPI0_MOSI'), (14, 'TXD0')]:
            controller = GPIOController()
            states = {pin: PinState(pin, True, 'a3', 'pu', function, '')}
            with patch('gpio_core.board_snapshot', return_value=(states, '')), \
                    patch('gpio_core.create_lgpio_factory') as factory:
                with self.assertRaisesRegex(RuntimeError, function):
                    controller.activate(pin, 'output')
                factory.assert_not_called()

    def test_unreadable_preflight_fails_before_claiming_pin(self):
        controller = GPIOController()
        with patch('gpio_core.board_snapshot', return_value=({}, 'pinctrl fehlt')):
            with self.assertRaisesRegex(RuntimeError, 'nicht geprüft'):
                controller.activate(17, 'output')
        self.assertIsNone(controller.factory)

    def test_fixed_pull_up_pins_reject_pull_down_before_factory_creation(self):
        controller = GPIOController(factory_builder=MockFactory)
        with self.assertRaisesRegex(ValueError, 'festen Pull-Up'):
            controller.activate(2, 'input', 'down')
        self.assertIsNone(controller.factory)

    def test_chip_index_is_detected_from_rp1_driver_label(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'sys').mkdir()
            (root / 'dev').mkdir()
            for index, label in [(0, 'pinctrl-rp1'), (4, 'other-controller')]:
                path = root / 'sys' / f'gpiochip{index}'
                path.mkdir()
                (path / 'label').write_text(label)
                (root / 'dev' / path.name).touch()
            self.assertEqual(find_header_chip(root / 'sys', root / 'dev'), 0)

    def test_unknown_chip_is_not_guessed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(RuntimeError, 'nicht gefunden'):
                find_header_chip(root, root)

    def test_device_metadata_finds_rp1_without_any_sysfs_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'gpiochip0').touch()
            (root / 'gpiochip10').touch()
            with patch('gpio_core.read_chip_info', return_value=('gpiochip0', 'pinctrl-rp1', 54)):
                self.assertEqual(find_header_chip(root / 'nonexistent-sysfs', root), 0)

    def test_device_scan_skips_internal_controller_and_unreadable_devices(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('gpiochip0', 'gpiochip10', 'gpiochip15'):
                (root / name).touch()

            def metadata(path):
                if path.name == 'gpiochip0':
                    raise PermissionError('no access')
                if path.name == 'gpiochip10':
                    return path.name, 'gpio-brcmstb', 32
                return path.name, 'pinctrl-rp1', 54

            with patch('gpio_core.read_chip_info', side_effect=metadata):
                self.assertEqual(find_header_chip(root / 'nonexistent', root), 15)

    def test_metadata_uses_readonly_chip_info_ioctl_and_closes_fd(self):
        def ioctl(fd, request, data, mutate):
            self.assertEqual(fd, 123)
            self.assertEqual(request, 0x8044B401)
            self.assertTrue(mutate)
            data[:] = struct.pack('=32s32sI', b'gpiochip0', b'pinctrl-rp1', 54)

        with patch('gpio_core.os.open', return_value=123) as opened, \
                patch('gpio_core.os.close') as closed, \
                patch('gpio_core.fcntl.ioctl', side_effect=ioctl):
            self.assertEqual(read_chip_info(Path('/dev/gpiochip0')), ('gpiochip0', 'pinctrl-rp1', 54))
        import os
        self.assertEqual(opened.call_args.args[1] & os.O_ACCMODE, os.O_RDONLY)
        closed.assert_called_once_with(123)

    def test_metadata_closes_fd_when_ioctl_fails(self):
        with patch('gpio_core.os.open', return_value=123), \
                patch('gpio_core.os.close') as closed, \
                patch('gpio_core.fcntl.ioctl', side_effect=OSError('ioctl failure')):
            with self.assertRaises(OSError):
                read_chip_info(Path('/dev/gpiochip0'))
        closed.assert_called_once_with(123)

    def test_busy_and_native_error_have_actionable_messages(self):
        self.assertIn('belegt', friendly_error(RuntimeError('GPIO busy'), 4))
        self.assertIn('GPIO4', friendly_error(RuntimeError('GPIO busy'), 4))
        self.assertIn('Fehlerprotokoll', friendly_error(RuntimeError('unexpected error'), 17))

    def test_failed_lgpio_reset_still_closes_chip_handle(self):
        cls = type('LGPIOFactory', (), {'__module__': 'gpiozero.pins.lgpio'})
        factory = cls()
        factory._handle = 42
        factory.close = Mock(side_effect=RuntimeError('unexpected error'))
        close_chip = Mock()
        controller = GPIOController(factory_builder=lambda: factory)
        controller.factory = factory
        with patch.dict(sys.modules, {'lgpio': SimpleNamespace(gpiochip_close=close_chip)}):
            with self.assertRaises(RuntimeError):
                controller.release()
        close_chip.assert_called_once_with(42)
        self.assertIsNone(factory._handle)
        self.assertIsNone(controller.factory)


if __name__ == '__main__':
    unittest.main(verbosity=2)
