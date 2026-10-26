"""Run the actual GUI callbacks with display-free widgets and real mock GPIOs."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gpio_gui
import gpio_choices
from gpio_core import MultiGPIOController
from test_live_header import RecordingCanvas


class Widget:
    all = []

    def __init__(self, master=None, **kw):
        self.text = kw.get('text', '')
        self.master = master
        self.title = kw.get('title')
        self.value = self.text
        self.enabled = kw.get('enabled', True)
        self.command = kw.get('command')
        self.args = kw.get('args', [])
        self.options = kw.get('options', [])
        if self.options:
            self.value = kw.get('selected', self.options[0])
        bindings = {}
        self.tk = SimpleNamespace(configure=Mock(), yview_moveto=Mock(), lift=Mock(),
                                  bindings=bindings,
                                  bind=lambda event, callback, add=None: bindings.update({event: callback}))
        self.all.append(self)

    def update_command(self, command):
        self.command = command

    def click(self):
        if self.enabled:
            return self.command(*self.args)

    def choose(self, value):
        if value not in self.options:
            raise ValueError(value)
        self.value = value
        if self.command:
            self.command()

    def clear(self):
        self.options = []
        self.value = ''

    def append(self, option):
        self.options.append(option)
        if len(self.options) == 1:
            self.value = option


class Drawing(Widget):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.tk = RecordingCanvas()


class Window(Widget):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.visible = kw.get('visible', True)

    def hide(self):
        self.visible = False

    def show(self, wait=False):
        if wait:
            raise AssertionError('Auswahl darf keine modale Eingabesperre verwenden')
        self.visible = True


class App(Widget):
    scenario = None
    instance = None

    def __init__(self, **kw):
        super().__init__(**kw)
        App.instance = self
        self.notices = []
        self.yesno = Mock(return_value=True)

    def info(self, title, message):
        self.notices.append((title, message))

    def repeat(self, delay, callback):
        self.tick = callback

    def display(self):
        App.scenario(self)

    def destroy(self):
        self.destroyed = True


class GUIFlows(unittest.TestCase):
    def run_app(self, scenario, real_choices=False, language='de', gertboard=True):
        Widget.all = []
        App.scenario = scenario
        self.multi = None
        self.choices = []
        self.controllers = []

        def choice(*args, **kw):
            widget = gpio_choices.Choice(*args, **kw)
            self.choices.append(widget)
            return widget

        def controller(**kw):
            self.multi = MultiGPIOController(**kw)
            self.controllers.append(self.multi)
            return self.multi

        with tempfile.TemporaryDirectory() as temp, \
                patch.dict(os.environ, {'XDG_CACHE_HOME': temp, 'XDG_CONFIG_HOME': temp}), \
                patch.object(sys, 'argv', ['gpio_gui.py', '--demo', '--language', language]
                             + ([] if gertboard is None else ['--gertboard' if gertboard else '--no-gertboard'])), \
                patch.multiple(gpio_gui, App=App, Box=Widget, Text=Widget,
                               Combo=choice if real_choices else Widget,
                               Drawing=Drawing, PushButton=Widget, TextBox=Widget, Window=Window), \
                patch.multiple(gpio_choices, Box=Widget, Text=Widget, PushButton=Widget,
                               ListBox=Widget, Window=Window), \
                patch.object(gpio_gui, 'MultiGPIOController', side_effect=controller), \
                patch.object(gpio_gui, 'configure_logging', return_value=(Mock(), Path(temp) / 'log')):
            try:
                self.assertEqual(gpio_gui.main(), 0)
            finally:
                gpio_gui.set_language('de')

    def controls(self):
        combos = [widget for widget in Widget.all if widget.options and not widget.options[0].startswith('Raspi')]
        buttons = {widget.text: widget for widget in Widget.all if widget.command and not widget.options}
        return combos, buttons

    def test_english_gpio_controls_preserve_two_active_pin_assignments(self):
        def scenario(app):
            choices = {choice._title: choice for choice in self.choices}
            selection = choices['Select GPIO']
            mode = choices['Select input or output']
            buttons = {w.text: w for w in Widget.all if w.command and not w.options}
            self.assertNotIn('Gertboard test', buttons)
            mode.value = 'Output (starts LOW)'
            buttons['Activate pin…'].click()
            buttons['HIGH / 1'].click()
            original = self.multi.channels[17]
            selection.value = 'GPIO27  ·  physical pin 13'
            selection._on_change()
            mode.value = 'Input'
            buttons['Activate pin…'].click()
            self.assertEqual(set(self.multi.channels), {17, 27})
            selection.value = 'GPIO17  ·  physical pin 11'
            selection._on_change()
            self.assertEqual(mode.value, 'Output (starts LOW)')
            self.assertIs(self.multi.channels[17], original)
            self.assertTrue(original.level)
            self.assertIn('physical pin 11', app.yesno.call_args_list[0].args[1])
            self.assertFalse(buttons['Sprache & Module / Language & modules'].enabled)
            buttons['Release all active pins'].click()
            self.assertEqual(self.multi.channels, {})
        self.run_app(scenario, real_choices=True, language='en', gertboard=False)

    def test_language_and_module_switch_rebuilds_only_an_idle_app(self):
        phase = []
        def scenario(app):
            def in_app(widget):
                while getattr(widget, 'master', None) is not None:
                    widget = widget.master
                return widget is app
            buttons = {w.text: w for w in Widget.all if in_app(w) and w.command and not w.options}
            if not phase:
                self.assertEqual(self.multi.channels, {})
                settings = buttons['Sprache & Module / Language & modules']
                settings.click()
                chooser = self.choices[-1]
                chooser._listing.value = 'English · GPIO'
                mode = next(c for c in self.choices if c._title == 'Eingang oder Ausgang auswählen')
                mode.value = 'Ausgang (Start LOW)'
                buttons['Pin aktivieren…'].click()
                buttons['HIGH / 1'].click()
                self.assertFalse(chooser._window.visible)
                self.assertFalse(settings.enabled)
                self.assertTrue(self.multi.channels[17].level)
                buttons['Alle aktiven Pins freigeben'].click()
                settings.click()
                self.assertEqual(chooser.value, 'Deutsch · GPIO + Gertboard')
                chooser._listing.value = 'English · GPIO'
                chooser.accept()
                self.assertTrue(app.destroyed)
                from gpio_settings import load_settings, Settings
                self.assertEqual(load_settings(), Settings('en', False))
                phase.append('changed')
            else:
                self.assertIn('Activate pin…', buttons)
                self.assertNotIn('Gertboard test', buttons)
                self.assertTrue(all(not c.channels for c in self.controllers))
                phase.append('restarted')
        self.run_app(scenario, real_choices=True)
        self.assertEqual(phase, ['changed', 'restarted'])

    def test_base_app_starts_when_optional_module_is_absent(self):
        import builtins
        original_import = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name == 'gpio_gertboard':
                raise AssertionError('Base app must not import the optional Gertboard module')
            return original_import(name, *args, **kwargs)
        def scenario(app):
            self.assertEqual(self.multi.channels, {})
            self.assertIn('GPIO Workshop', app.title)
            self.assertFalse(any(w.text.startswith('Gertboard') for w in Widget.all))
        with patch.object(gpio_gui, 'gertboard_available', return_value=False), \
                patch('builtins.__import__', side_effect=guarded):
            self.run_app(scenario, real_choices=True, language='en', gertboard=None)

    def test_switch_and_release_two_pins_and_inspect_blocked_pins(self):
        def scenario(app):
            (selection, mode, pull), buttons = self.controls()
            self.assertTrue(buttons['Pin aktivieren…'].enabled)
            mode.value = 'Ausgang (Start LOW)'
            buttons['Pin aktivieren…'].click()
            buttons['HIGH / 1'].click()
            self.assertTrue(self.multi.channels[17].level)
            self.assertTrue(selection.enabled)
            selection.choose('GPIO27  ·  physischer Pin 13')
            mode.value = 'Eingang'
            buttons['Pin aktivieren…'].click()
            self.assertEqual(set(self.multi.channels), {17, 27})
            selection.choose('GPIO17  ·  physischer Pin 11')
            self.assertEqual(mode.value, 'Ausgang (Start LOW)')
            self.assertTrue(buttons['HIGH / 1'].enabled)
            self.assertTrue(self.multi.channels[17].level)
            selection.choose('GPIO4  ·  physischer Pin 7')
            self.assertFalse(buttons['Pin aktivieren…'].enabled)
            self.assertTrue(any('w1-demo' in str(widget.value) for widget in Widget.all))
            selection.choose('GPIO2  ·  physischer Pin 3')
            self.assertFalse(buttons['Pin aktivieren…'].enabled)
            self.assertTrue(any('SDA1' in str(widget.value) for widget in Widget.all))
            drawing = next(widget for widget in Widget.all if isinstance(widget, Drawing))
            drawing.tk.bindings['<Button-1>'](SimpleNamespace(x=100, y=44))
            self.assertIn('Kein schaltbarer GPIO', app.notices[-1][1])
            self.assertEqual(set(self.multi.channels), {17, 27})
            selection.choose('GPIO17  ·  physischer Pin 11')
            buttons['Pin freigeben'].click()
            self.assertEqual(set(self.multi.channels), {27})
            self.assertTrue(buttons['Alle aktiven Pins freigeben'].enabled)
            buttons['Alle aktiven Pins freigeben'].click()
            self.assertEqual(self.multi.channels, {})
            self.assertFalse(buttons['Alle aktiven Pins freigeben'].enabled)
            self.assertFalse(buttons['Pin freigeben'].enabled)
            self.assertTrue(buttons['Pin aktivieren…'].enabled)
        self.run_app(scenario)

    def test_real_selection_windows_survive_live_updates_without_touching_other_pins(self):
        def scenario(app):
            choices = {choice._title: choice for choice in self.choices}
            mode = choices['Eingang oder Ausgang auswählen']
            mode.open()
            mode._listing.value = 'Ausgang (Start LOW)'
            for _ in range(30):
                app.tick()
            self.assertTrue(mode._window.visible)
            self.assertEqual(mode.value, 'Eingang')
            self.assertEqual(mode._listing.value, 'Ausgang (Start LOW)')
            self.assertEqual(self.multi.channels, {})
            mode.accept()
            buttons = {w.text: w for w in Widget.all if w.command and not w.options}
            buttons['Pin aktivieren…'].click()
            buttons['HIGH / 1'].click()
            channel = self.multi.channels[17]
            self.assertTrue(channel.level)
            mode.open()  # disabled while this pin is active
            self.assertFalse(mode._window.visible)
            buttons['Gertboard-Test'].click()
            guide = self.choices[-1]
            self.assertEqual(guide._title, 'Funktionstest auswählen')
            guide.open()
            guide._listing.value = 'Taster S1 testen'
            for _ in range(30):
                app.tick()
            self.assertTrue(guide._window.visible)
            guide.accept()
            self.assertTrue(any('Ohne OUT-Brücke' in str(w.value) for w in Widget.all))
            self.assertIs(self.multi.channels[17], channel)
            self.assertTrue(channel.level)
            selection = choices['GPIO auswählen']
            selection.open()
            selection._listing.value = 'GPIO27  ·  physischer Pin 13'
            selection.accept()
            self.assertEqual(selection.value, 'GPIO27  ·  physischer Pin 13')
            self.assertIs(self.multi.channels[17], channel)
            self.assertTrue(channel.level)
            self.assertIsNone(gpio_choices.Choice._active)
        self.run_app(scenario, real_choices=True)
        self.assertEqual(self.multi.channels, {})

    def test_orientation_window_reopens_without_reconfiguring_active_pins(self):
        def scenario(app):
            (selection, mode, pull), buttons = self.controls()
            mode.value = 'Ausgang (Start LOW)'
            buttons['Pin aktivieren…'].click()
            buttons['HIGH / 1'].click()
            channel = self.multi.channels[17]
            buttons['Steckrichtung · gelber Punkt'].click()
            windows = [widget for widget in Widget.all if isinstance(widget, Window)]
            self.assertEqual(len(windows), 1)
            self.assertTrue(windows[0].visible)
            self.assertTrue(channel.level)
            windows[0].hide()
            buttons['Steckrichtung · gelber Punkt'].click()
            self.assertTrue(windows[0].visible)
            self.assertEqual(len([widget for widget in Widget.all if isinstance(widget, Window)]), 1)
            self.assertIs(self.multi.channels[17], channel)
            self.assertTrue(channel.level)
        self.run_app(scenario)

    def test_cancelling_activation_and_failed_second_activation_preserve_existing_pin(self):
        def scenario(app):
            (selection, mode, pull), buttons = self.controls()
            app.yesno.return_value = False
            buttons['Pin aktivieren…'].click()
            self.assertEqual(self.multi.channels, {})
            app.yesno.return_value = True
            mode.value = 'Ausgang (Start LOW)'
            buttons['Pin aktivieren…'].click()
            buttons['HIGH / 1'].click()
            selection.choose('GPIO27  ·  physischer Pin 13')
            mode.value = 'Eingang'
            with patch('gpiozero.InputDevice', side_effect=RuntimeError('GPIO busy')):
                with self.assertLogs('raspi_gpio', level='ERROR'):
                    buttons['Pin aktivieren…'].click()
            self.assertEqual(set(self.multi.channels), {17})
            self.assertTrue(self.multi.channels[17].level)
            self.assertTrue(selection.enabled)
            self.assertTrue(buttons['Pin aktivieren…'].enabled)
        self.run_app(scenario)
        self.assertEqual(self.multi.channels, {})

    def test_gertboard_explorer_selection_scroll_and_reopen_preserve_active_output(self):
        def scenario(app):
            (selection, mode, pull), buttons = self.controls()
            mode.value = 'Ausgang (Start LOW)'
            buttons['Pin aktivieren…'].click()
            buttons['HIGH / 1'].click()
            channel = self.multi.channels[17]
            buttons['Gertboard-Übersicht'].click()
            windows = [w for w in Widget.all if isinstance(w, Window)]
            self.assertEqual(len(windows), 1)
            self.assertTrue(windows[0].visible)
            choice = next(w for w in Widget.all if w.options and
                          w.options[0] == 'Warum so viele Anschlüsse?')
            atlas = [w for w in Widget.all if isinstance(w, Drawing)][-1]
            text = next(w for w in Widget.all if 'B1 bedeutet Buffer 1' in str(w.value))
            from gpio_gertboard import REGIONS, BY_KEY
            for region in REGIONS:
                x1, y1, x2, y2 = region.rect
                atlas.tk.bindings['<Button-1>'](SimpleNamespace(x=(x1+x2)/2, y=(y1+y2)/2))
                self.assertEqual(choice.value, region.title)
                self.assertIn(region.intro, text.value)
                self.assertFalse(text.enabled)
                self.assertTrue(channel.level)
                self.assertIs(self.multi.channels[17], channel)
                self.assertEqual(set(self.multi.channels), {17})
            choice.choose(BY_KEY['gpio'].title)
            self.assertIn('GPIO27 · J1-Pin 13', text.value)
            text.tk.yview_moveto.assert_called_with(0)
            windows[0].hide()
            buttons['Gertboard-Übersicht'].click()
            self.assertTrue(windows[0].visible)
            self.assertEqual(len([w for w in Widget.all if isinstance(w, Window)]), 1)
            source = next(w for w in Widget.all if w.text == 'Quelle zum Bereich')
            source.click()
            self.assertIn('https://www.farnell.com/', app.notices[-1][1])
            self.assertTrue(channel.level)
        self.run_app(scenario)

    def test_gertboard_legacy_gp21_selects_gpio27_and_profile_never_hides_live_pins(self):
        def scenario(app):
            (selection, mode, pull), buttons = self.controls()
            profile = next(widget for widget in Widget.all if widget.options and widget.options[0].startswith('Raspi'))
            profile.choose(gpio_gui.GERTBOARD_PROFILE)
            self.assertEqual(len(selection.options), 17)
            self.assertNotIn('GPIO21  ·  physischer Pin 40', selection.options)
            selection.choose('GPIO27  ·  physischer Pin 13')
            self.assertTrue(buttons['Pin aktivieren…'].enabled)
            self.assertTrue(any('GP21 → GPIO27' in str(widget.value) for widget in Widget.all))
            buttons['Pin aktivieren…'].click()
            self.assertEqual(set(self.multi.channels), {27})
            self.assertFalse(profile.enabled)
            buttons['Alle aktiven Pins freigeben'].click()
            self.assertTrue(profile.enabled)
            profile.choose(gpio_gui.RASPI_PROFILE)
            self.assertEqual(len(selection.options), 26)
            selection.choose('GPIO21  ·  physischer Pin 40')
            self.assertTrue(buttons['Pin aktivieren…'].enabled)
        self.run_app(scenario)

    def test_cropped_profile_resets_an_unconnected_selection_and_test_help_does_not_write_gpio(self):
        def scenario(app):
            (selection, mode, pull), buttons = self.controls()
            profile = next(widget for widget in Widget.all if widget.options and widget.options[0].startswith('Raspi'))
            selection.choose('GPIO21  ·  physischer Pin 40')
            profile.choose(gpio_gui.GERTBOARD_PROFILE)
            self.assertEqual(selection.value, 'GPIO17  ·  physischer Pin 11')
            mode.value = 'Ausgang (Start LOW)'
            buttons['Pin aktivieren…'].click()
            buttons['HIGH / 1'].click()
            channel = self.multi.channels[17]
            buttons['Gertboard-Test'].click()
            guide = next(widget for widget in Widget.all if widget.options and widget.options[0] == 'LED1 testen')
            guide.choose('Taster S1 testen')
            self.assertTrue(any('S1 losgelassen: HIGH' in str(widget.value) for widget in Widget.all))
            self.assertIs(self.multi.channels[17], channel)
            self.assertTrue(channel.level)
            self.assertEqual(channel.mode, 'output')
        self.run_app(scenario)


if __name__ == '__main__':
    unittest.main(verbosity=2)
