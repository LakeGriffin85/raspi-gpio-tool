from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gpio_gertboard import GertboardDiagram, REGIONS, BY_KEY, PI_SIGNALS, SOURCES
from test_live_header import RecordingCanvas


class GertboardAtlasTests(unittest.TestCase):
    def test_all_regions_are_reachable_without_overlap_or_clipped_labels(self):
        selected = []
        canvas = RecordingCanvas()
        diagram = GertboardDiagram(canvas, selected.append)
        self.assertEqual(len(BY_KEY), len(REGIONS))
        for region in REGIONS:
            x1, y1, x2, y2 = region.rect
            self.assertTrue(0 <= x1 < x2 < diagram.WIDTH)
            self.assertTrue(0 <= y1 < y2 < diagram.HEIGHT)
            for other in REGIONS:
                if other is region:
                    continue
                a, b, c, d = other.rect
                self.assertFalse(x1 < c and a < x2 and y1 < d and b < y2,
                                 (region.key, other.key))
            canvas.bindings['<Button-1>'](SimpleNamespace(x=(x1+x2)/2, y=(y1+y2)/2))
            self.assertEqual(selected[-1], region.key)
        self.assertIsNone(diagram.region_at(0, 0))
        before = list(selected)
        canvas.bindings['<Button-1>'](SimpleNamespace(x=0, y=0))
        self.assertEqual(before, selected)

    def test_legacy_pi_labels_are_17_unique_signals_and_not_buffer_or_atmega_names(self):
        self.assertEqual(len(PI_SIGNALS), 17)
        by_label = {old: (gpio, physical) for old, gpio, physical in PI_SIGNALS}
        self.assertEqual(by_label['GP0'], (2, 3))
        self.assertEqual(by_label['GP1'], (3, 5))
        self.assertEqual(by_label['GP21'], (27, 13))
        self.assertEqual(by_label['GP17'], (17, 11))
        self.assertEqual(len({gpio for _, gpio, _ in PI_SIGNALS}), 17)
        self.assertEqual(len({pin for _, _, pin in PI_SIGNALS}), 17)
        self.assertTrue(all(pin <= 26 for _, _, pin in PI_SIGNALS))
        self.assertIn('PB5 ist weder Raspi-GPIO5 noch Buffer B5', BY_KEY['atmega'].details())

    def test_explanation_distinguishes_logic_load_analog_and_reference_from_measurement(self):
        for region in REGIONS:
            self.assertTrue(region.signals, region.key)
            self.assertIn('keine Live-Messung', region.details())
            self.assertIn(region.source, SOURCES)
        self.assertIn('Pull-Ups', BY_KEY['leds'].effect)
        self.assertIn('10 Bit', BY_KEY['adc'].effect)
        self.assertIn('6–15 V', BY_KEY['motor_power'].note)
        self.assertIn('absolut', BY_KEY['motor_power'].note)
        self.assertIn('J5 ist Logik; J19 ist Motorleistung', BY_KEY['motor_logic'].note)
        self.assertIn('keine sechs fertigen Relais', BY_KEY['relay_logic'].note)
        self.assertIn('nicht zugeordnet', BY_KEY['clock'].effect)

    def test_selection_highlight_never_changes_the_illustrated_leds(self):
        canvas = RecordingCanvas()
        diagram = GertboardDiagram(canvas, lambda key: None)
        lights = {i: item.copy() for i, item in canvas.items.items() if item['kind'] == 'oval'}
        for key in BY_KEY:
            diagram.select(key)
            self.assertEqual(diagram.selected, key)
            for i, original in lights.items():
                self.assertEqual(canvas.items[i], original)
        with self.assertRaises(ValueError):
            diagram.select('GPIO99')


if __name__ == '__main__':
    unittest.main(verbosity=2)
