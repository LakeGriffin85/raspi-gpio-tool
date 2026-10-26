"""Translation completeness and local settings must not change pin ownership."""
import json
import os
from pathlib import Path
from string import Formatter
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gpio_i18n import tr, set_language
from gpio_settings import Settings, load_settings, save_settings, settings_path
from gpio_gertboard import REGIONS
from gpio_availability import pin_access, LineInfo
from gpio_core import PinState


class LocalisationTests(unittest.TestCase):
    def tearDown(self):
        set_language('de')

    def test_catalogue_preserves_all_format_fields_and_specifiers(self):
        catalogue = json.loads(Path(__file__).resolve().parents[1].joinpath('gpio_locale_en.json').read_text())
        fields = lambda text: sorted((name, fmt, conversion) for _, name, fmt, conversion
                                     in Formatter().parse(text) if name is not None)
        for source, target in catalogue.items():
            with self.subTest(source=source):
                self.assertTrue(target)
                self.assertEqual(fields(source), fields(target))

    def test_every_board_region_has_english_details_and_signal_meanings(self):
        set_language('en')
        for region in REGIONS:
            with self.subTest(region=region.key):
                self.assertNotEqual(tr(region.title), region.title)
                self.assertNotEqual(tr(region.intro), region.intro)
                self.assertNotEqual(tr(region.effect), region.effect)
                self.assertIn('CONNECTORS / SIGNALS', region.details())
                self.assertIn('not a live measurement', region.details())
                for name, meaning in region.signals:
                    # Technical identities such as UART TX/RX are intentionally unchanged.
                    self.assertTrue(tr(meaning))
                    self.assertIn(tr(name), region.details())
                self.assertNotIn('keine Live-Messung', region.details())

    def test_translating_ownership_reasons_keeps_decisions_and_ids(self):
        states = {17: PinState(17, False, 'ip', 'pu', 'input', '')}
        lines = {17: LineInfo(17, 'GPIO17', 'driver-name', True)}
        for owned in ((), (17,)):
            set_language('de'); german = pin_access(11, states, lines, owned)
            set_language('en'); english = pin_access(11, states, lines, owned)
            self.assertEqual((german.kind, german.can_activate), (english.kind, english.can_activate))
            self.assertNotEqual(german.reason, english.reason)
            self.assertIn('GPIO17', english.reason)
        self.assertIn('driver-name', pin_access(11, states, lines).reason)

    def test_preferences_roundtrip_atomic_write_and_corruption_fallback(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'XDG_CONFIG_HOME': temp}):
            self.assertEqual(load_settings(), Settings())
            save_settings(Settings('en', False))
            self.assertEqual(load_settings(), Settings('en', False))
            self.assertEqual(settings_path().stat().st_mode & 0o777, 0o600)
            for bad in ('[]', '{', '{"language":"xx"}', '{"gertboard":"false"}'):
                settings_path().write_text(bad)
                self.assertEqual(load_settings(), Settings())
            self.assertEqual(list(settings_path().parent.glob('.settings-*')), [])

    def test_language_roundtrip_and_unknown_protocol_text_are_lossless(self):
        set_language('en'); self.assertEqual(tr('Pin freigeben'), 'Release pin')
        self.assertEqual(tr('GPIO17 = SDA1 [driver]'), 'GPIO17 = SDA1 [driver]')
        set_language('de'); self.assertEqual(tr('Pin freigeben'), 'Pin freigeben')
        with self.assertRaises(ValueError):
            set_language('xx')
