from pathlib import Path
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gpio_core import HEADER_GPIO, HEADER_POWER, PinState, board_snapshot, parse_board_snapshot
from gpio_header import HeaderDiagram, HIGH, LOW, UNKNOWN


class RecordingCanvas:
    def __init__(self):
        self.items = {}
        self.bindings = {}
        self.changes = 0
        self.configuration = {}

    def configure(self, **kw):
        self.configuration.update(kw)

    def delete(self, target):
        if target != "all":
            raise ValueError(target)
        self.items.clear()

    def create(self, kind, *coordinates, **options):
        ident = len(self.items) + 1
        self.items[ident] = {"kind": kind, "coordinates": coordinates, **options}
        return ident

    def create_rectangle(self, *args, **kw):
        return self.create("rectangle", *args, **kw)

    def create_oval(self, *args, **kw):
        return self.create("oval", *args, **kw)

    def create_line(self, *args, **kw):
        return self.create("line", *args, **kw)

    def create_text(self, *args, **kw):
        return self.create("text", *args, **kw)

    def itemconfigure(self, ident, **kw):
        self.items[ident].update(kw)
        self.changes += 1

    def bind(self, event, callback):
        self.bindings[event] = callback


class LiveHeaderTests(unittest.TestCase):
    def test_real_pinctrl_input_output_and_alt_formats(self):
        result = parse_board_snapshot(
            " 2: a3    pu | hi // GPIO2 = SDA1\n"
            "17: ip    pd | lo // GPIO17 = input\n"
            "18: op    pn | hi // GPIO18 = output\n"
            "27: no    pn | lo // GPIO27 = none\n"
            "28: ip    pn | hi // GPIO28 = input\n"
            "garbage\n")
        self.assertEqual(set(result), {2, 17, 18, 27})
        self.assertEqual(result[2].function, "SDA1")
        self.assertEqual(result[2].mode, "a3")
        self.assertTrue(result[2].level)
        self.assertFalse(result[17].level)
        self.assertEqual(result[18].pull, "pn")

    def test_unknown_state_does_not_become_low(self):
        result = parse_board_snapshot("17: ?? | ?? // GPIO17\n")
        self.assertIsNone(result[17].level)
        self.assertEqual(result[17].mode, "?")

    def test_one_read_only_command_for_all_header_gpio(self):
        with patch("gpio_core.shutil.which", return_value="/usr/bin/pinctrl"), \
                patch("gpio_core.subprocess.run") as run:
            run.return_value.stdout = "\n".join(f"{n}: ip pn | lo // GPIO{n} = input" for n in range(28))
            states, warning = board_snapshot()
        self.assertEqual(len(states), 28)
        self.assertEqual(warning, "")
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], ["/usr/bin/pinctrl", "get", "0-27"])

    def test_error_never_returns_stale_or_fabricated_values(self):
        with patch("gpio_core.shutil.which", return_value="/usr/bin/pinctrl"), \
                patch("gpio_core.subprocess.run", side_effect=subprocess.TimeoutExpired("pinctrl", 1)):
            states, warning = board_snapshot()
        self.assertEqual(states, {})
        self.assertIn("nicht verfügbar", warning)

    def test_all_40_physical_pins_have_exactly_one_kind(self):
        self.assertEqual(set(HEADER_GPIO) | set(HEADER_POWER), set(range(1, 41)))
        self.assertFalse(set(HEADER_GPIO) & set(HEADER_POWER))
        self.assertEqual(HEADER_GPIO[11], 17)
        self.assertEqual(HEADER_GPIO[27], 0)
        self.assertEqual(HEADER_GPIO[28], 1)
        self.assertEqual(HEADER_POWER[1], "3V3")
        self.assertEqual(HEADER_POWER[2], "5V")
        self.assertEqual(HEADER_POWER[39], "GND")

    def test_visual_live_levels_modes_and_unknown(self):
        canvas = RecordingCanvas()
        diagram = HeaderDiagram(canvas, lambda pin: None)
        self.assertEqual(len(diagram.items), 40)
        states = {17: PinState(17, True, "op", "pn", "output", ""),
                  2: PinState(2, False, "a3", "pu", "SDA1", "")}
        diagram.update(states, 17)
        _, dot, mode, level, _, _ = diagram.items[11]
        self.assertEqual(canvas.items[dot]["fill"], HIGH)
        self.assertEqual(canvas.items[level]["text"], "HIGH")
        self.assertEqual(canvas.items[mode]["text"], "OUT")
        _, dot2, mode2, _, _, _ = diagram.items[3]
        self.assertEqual(canvas.items[dot2]["fill"], LOW)
        self.assertEqual(canvas.items[mode2]["text"], "SDA1")
        diagram.update({}, 17)
        self.assertEqual(canvas.items[dot]["fill"], UNKNOWN)
        self.assertEqual(canvas.items[level]["text"], "?")

    def test_unchanged_board_does_not_redraw(self):
        canvas = RecordingCanvas()
        diagram = HeaderDiagram(canvas, lambda pin: None)
        diagram.update({}, 17)
        changes = canvas.changes
        diagram.update({}, 17)
        self.assertEqual(canvas.changes, changes)

    def test_click_positions_select_every_usable_gpio(self):
        canvas = RecordingCanvas()
        selected = []
        diagram = HeaderDiagram(canvas, selected.append)
        for physical, gpio in HEADER_GPIO.items():
            x = 100 if physical % 2 else 500
            y = diagram.FIRST_Y + (physical - 1) // 2 * diagram.STEP
            diagram._click(SimpleNamespace(x=x, y=y))
            if gpio not in (0, 1):
                self.assertEqual(selected[-1], gpio)
        self.assertEqual(set(selected), set(range(2, 28)))

    def test_power_reserved_and_empty_clicks_do_not_select(self):
        canvas = RecordingCanvas()
        selected = []
        diagram = HeaderDiagram(canvas, selected.append)
        for physical in list(HEADER_POWER) + [27, 28]:
            diagram._click(SimpleNamespace(x=100 if physical % 2 else 500,
                                           y=diagram.FIRST_Y + (physical - 1) // 2 * diagram.STEP))
        for x, y in [(0, 44), (100, 5), (100, 540), (700, 44)]:
            diagram._click(SimpleNamespace(x=x, y=y))
        self.assertEqual(selected, [])

    def test_gertboard_view_contains_only_26_pins_and_has_no_hidden_click_targets(self):
        canvas = RecordingCanvas()
        inspected = []
        diagram = HeaderDiagram(canvas, lambda pin: None, inspected.append)
        diagram.update({}, 17, gertboard=True)
        self.assertEqual(set(diagram.items), set(range(1, 27)))
        self.assertLess(canvas.configuration['height'], HeaderDiagram.HEIGHT)
        for physical in range(27, 41):
            diagram._click(SimpleNamespace(x=100 if physical % 2 else 500,
                                           y=diagram.FIRST_Y + (physical - 1) // 2 * diagram.STEP))
        self.assertEqual(inspected, [])
        diagram._click(SimpleNamespace(x=500, y=diagram.FIRST_Y + 12 * diagram.STEP))
        self.assertEqual(inspected, [26])
        diagram.update({}, 17, gertboard=False)
        self.assertEqual(set(diagram.items), set(range(1, 41)))
        self.assertEqual(canvas.configuration['height'], HeaderDiagram.HEIGHT)
        diagram._click(SimpleNamespace(x=500, y=diagram.FIRST_Y + 19 * diagram.STEP))
        self.assertEqual(inspected, [26, 40])


if __name__ == "__main__":
    unittest.main(verbosity=2)
