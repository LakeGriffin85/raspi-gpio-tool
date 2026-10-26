from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gpio_orientation import OrientationDiagram, YELLOW
from gpio_header import HeaderDiagram
from test_live_header import RecordingCanvas


class OrientationTests(unittest.TestCase):
    def test_photo_orientation_has_odd_pins_inside_and_40_at_bottom_outside(self):
        canvas = RecordingCanvas()
        diagram = OrientationDiagram(canvas)
        self.assertEqual(set(diagram.pin_items), set(range(1, 41)))
        self.assertEqual(len({diagram.position(pin) for pin in range(1, 41)}), 40)
        one, two, thirty_nine, forty = map(diagram.position, (1, 2, 39, 40))
        self.assertLess(one[0], two[0])
        self.assertEqual(one[1], two[1])
        self.assertEqual(thirty_nine[1], forty[1])
        self.assertLess(one[1], thirty_nine[1])
        self.assertEqual(one[0], thirty_nine[0])
        self.assertEqual(two[0], forty[0])
        self.assertEqual(canvas.items[diagram.pin_items[1][0]]['fill'], YELLOW)
        for physical, (_, number) in diagram.pin_items.items():
            self.assertEqual(canvas.items[number]['text'], str(physical))

    def test_landmarks_and_top_view_warning_are_explicit(self):
        canvas = RecordingCanvas()
        OrientationDiagram(canvas)
        texts = [item.get('text', '') for item in canvas.items.values()]
        self.assertTrue(any('USB und LAN unten' in text for text in texts))
        self.assertIn('Dein gelber Punkt', texts)
        self.assertTrue(any('nicht die GPIO-Nummer' in text for text in texts))
        self.assertTrue(any('spiegelverkehrt' in text for text in texts))

    def test_live_header_pin1_marker_remains_visible_in_both_profiles(self):
        canvas = RecordingCanvas()
        diagram = HeaderDiagram(canvas, lambda pin: None)
        rings = [ident for ident, item in canvas.items.items()
                 if item['kind'] == 'oval' and item.get('outline') == YELLOW and item.get('width') == 3]
        self.assertEqual(len(rings), 1)
        for profile in (False, True, False):
            diagram.update({}, 17, gertboard=profile)
            self.assertEqual(canvas.items[rings[0]]['outline'], YELLOW)
            self.assertIn('gelber Punkt = Pin 1', canvas.items[diagram.title]['text'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
