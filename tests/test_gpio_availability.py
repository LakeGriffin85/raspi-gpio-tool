from pathlib import Path
import os
import struct
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gpio_availability import (LineInfo, GERTBOARD_LABELS, header_access, line_snapshot,
                               pin_access, read_line_info)
from gpio_core import GPIOController, MultiGPIOController, PHYSICAL, PinState
from gpio_header import HeaderDiagram, BUSY, BUS, OWNED
from gpiozero.pins.mock import MockFactory
from test_live_header import RecordingCanvas


class AvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.states = {gpio: PinState(gpio, False, 'ip', 'pn', 'input', '') for gpio in range(28)}
        self.lines = {gpio: LineInfo(gpio, f'GPIO{gpio}', '', False) for gpio in range(28)}

    def test_readonly_v2_metadata_uses_exact_abi_and_preserves_unnamed_claims(self):
        def ioctl(fd, request, data, mutate):
            self.assertEqual((fd, request, len(data), mutate), (123, 0xc100b405, 256, True))
            self.assertEqual(struct.unpack_from('=I', data, 64)[0], 4)
            self.assertEqual(data[:64] + data[68:], bytes(252))
            struct.pack_into('=32s32sIIQ', data, 0, b'GPIO4', b'w1', 4, 0, 1 | 4)
        with patch('gpio_availability.fcntl.ioctl', side_effect=ioctl):
            self.assertEqual(read_line_info(123, 4), LineInfo(4, 'GPIO4', 'w1', True))

    def test_all_metadata_uses_one_readonly_handle_and_closes_it(self):
        with patch('gpio_availability.os.open', return_value=123) as opened, \
                patch('gpio_availability.os.close') as closed, \
                patch('gpio_availability.read_line_info', side_effect=lambda fd, gpio: self.lines[gpio]) as read:
            lines, warning = line_snapshot(chip=0)
        self.assertEqual(opened.call_args.args[1] & os.O_ACCMODE, os.O_RDONLY)
        self.assertEqual(read.call_count, 28)
        self.assertEqual(len(lines), 28)
        self.assertEqual(warning, '')
        closed.assert_called_once_with(123)

    def test_metadata_failure_is_unknown_not_available_and_fd_is_closed(self):
        with patch('gpio_availability.os.open', return_value=123), \
                patch('gpio_availability.os.close') as closed, \
                patch('gpio_availability.read_line_info', side_effect=OSError('denied')):
            lines, warning = line_snapshot(chip=0)
        self.assertEqual(lines, {})
        self.assertIn('denied', warning)
        self.assertEqual(pin_access(11, self.states, lines).kind, 'unknown')
        closed.assert_called_once_with(123)

    def test_hardware_fixed_and_reserved_are_distinct_from_temporary_ownership(self):
        access = header_access(self.states, self.lines)
        self.assertEqual(len(access), 40)
        self.assertEqual(access[1].kind, 'fixed')
        self.assertEqual(access[6].kind, 'fixed')
        self.assertEqual(access[27].kind, 'reserved')
        self.lines[4] = LineInfo(4, 'GPIO4', 'w1', True)
        self.assertIn('w1', pin_access(7, self.states, self.lines).reason)
        self.lines[4] = LineInfo(4, 'GPIO4', '', False)
        self.assertTrue(pin_access(7, self.states, self.lines).can_activate)

    def test_alt_function_protected_even_when_linux_does_not_claim_line(self):
        self.states[2] = PinState(2, True, 'a3', 'pu', 'SDA1', '')
        access = pin_access(3, self.states, self.lines)
        self.assertEqual(access.kind, 'bus')
        self.assertIn('SDA1', access.reason)
        self.assertFalse(access.can_activate)

    def test_unnamed_claim_blocks_and_owned_claim_is_not_mislabelled(self):
        self.lines[17] = LineInfo(17, 'GPIO17', '', True)
        self.assertEqual(pin_access(11, self.states, self.lines).kind, 'busy')
        self.assertEqual(pin_access(11, self.states, self.lines, {17}).kind, 'owned')

    def test_activation_rechecks_claim_after_a_previously_free_snapshot(self):
        self.assertTrue(pin_access(11, self.states, self.lines).can_activate)
        self.lines[17] = LineInfo(17, 'GPIO17', 'another-program', True)
        controller = GPIOController()
        with patch('gpio_core.board_snapshot', return_value=(self.states, '')), \
                patch('gpio_availability.line_snapshot', return_value=(self.lines, '')), \
                patch('gpio_core.create_lgpio_factory') as factory:
            with self.assertRaisesRegex(RuntimeError, 'another-program'):
                controller.activate(17, 'output')
            factory.assert_not_called()

    def test_graphic_marks_busy_bus_and_owned_without_hiding_logic_level(self):
        self.lines[4] = LineInfo(4, 'GPIO4', 'w1', True)
        self.states[2] = PinState(2, True, 'a3', 'pu', 'SDA1', '')
        access = header_access(self.states, self.lines, {17})
        canvas = RecordingCanvas()
        inspected = []
        diagram = HeaderDiagram(canvas, lambda pin: None, inspected.append)
        diagram.update(self.states, 27, access)
        for physical, color, mark_text in [(7, BUSY, '×'), (3, BUS, '×'), (11, OWNED, '')]:
            card, dot, _, _, _, mark = diagram.items[physical]
            self.assertEqual(canvas.items[card]['outline'], color)
            self.assertEqual(canvas.items[mark]['text'], mark_text)
        for physical in (1, 6, 27, 28):
            diagram._click(SimpleNamespace(x=100 if physical % 2 else 500,
                                           y=diagram.FIRST_Y + (physical - 1) // 2 * diagram.STEP))
        self.assertEqual(inspected, [1, 6, 27, 28])

    def test_gertboard_has_17_gpio_and_old_labels_do_not_target_reserved_gpio0_1(self):
        self.assertEqual(len(GERTBOARD_LABELS), 17)
        self.assertEqual((GERTBOARD_LABELS[2], GERTBOARD_LABELS[3], GERTBOARD_LABELS[27]),
                         ('GP0', 'GP1', 'GP21'))
        access = header_access(self.states, self.lines, gertboard=True)
        available = {gpio for gpio, physical in PHYSICAL.items() if access[physical].can_activate}
        self.assertEqual(available, set(GERTBOARD_LABELS))
        self.assertNotIn(0, available)
        self.assertNotIn(1, available)
        for physical in range(27, 41):
            self.assertEqual(access[physical].kind, 'unconnected')
        self.assertTrue(access[13].can_activate)
        canvas = RecordingCanvas()
        diagram = HeaderDiagram(canvas, lambda pin: None)
        diagram.update(self.states, 27, access, gertboard=True)
        self.assertEqual(canvas.items[diagram.items[13][4]]['text'], 'GP21')
        self.assertEqual(canvas.items[diagram.items[3][4]]['text'], 'GP0')
        self.assertNotIn(40, diagram.items)
        diagram.update(self.states, 27, header_access(self.states, self.lines))
        self.assertEqual(canvas.items[diagram.items[13][4]]['text'], 'GPIO27')


class MultiPinTests(unittest.TestCase):
    def test_outputs_stay_independent_while_input_is_read_and_one_pin_is_released(self):
        multi = MultiGPIOController(factory_builder=MockFactory)
        try:
            multi.activate(17, 'output')
            multi.activate(27, 'input', 'up')
            multi.activate(22, 'output')
            multi.write(17, True)
            self.assertTrue(multi.channels[17].level)
            self.assertFalse(multi.channels[22].level)
            self.assertTrue(multi.channels[27].level)
            other_factory = multi.channels[17].factory
            multi.release(22)
            self.assertTrue(multi.channels[17].level)
            self.assertIs(multi.channels[17].factory, other_factory)
            multi.release(27)
            self.assertTrue(multi.channels[17].level)
        finally:
            multi.close()

    def test_failed_second_activation_does_not_close_or_change_first_output(self):
        multi = MultiGPIOController(factory_builder=MockFactory)
        try:
            multi.activate(17, 'output')
            multi.write(17, True)
            with patch('gpiozero.InputDevice', side_effect=RuntimeError('GPIO busy')):
                with self.assertLogs('raspi_gpio', level='ERROR'):
                    with self.assertRaises(RuntimeError):
                        multi.activate(27, 'input', 'up')
            self.assertEqual(set(multi.channels), {17})
            self.assertTrue(multi.channels[17].level)
            with self.assertRaises(RuntimeError):
                multi.activate(17, 'input', 'up')
            self.assertTrue(multi.channels[17].level)
        finally:
            multi.close()

    def test_all_pins_close_even_if_one_output_off_fails(self):
        multi = MultiGPIOController(factory_builder=MockFactory)
        for gpio in (17, 22, 27):
            multi.activate(gpio, 'output')
            multi.write(gpio, True)
        last_pin = multi.channels[27].device.pin
        with patch.object(multi.channels[17].device, 'off', side_effect=RuntimeError('failed')):
            with self.assertLogs('raspi_gpio', level='ERROR'):
                with self.assertRaises(RuntimeError):
                    multi.release_all()
        self.assertEqual(multi.channels, {})
        self.assertFalse(last_pin.states[-1].state)


if __name__ == '__main__':
    unittest.main(verbosity=2)
