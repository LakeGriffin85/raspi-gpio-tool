"""Opt-in real Tk test. Uses only MockFactory, never real GPIO hardware.

Run with GPIO_NATIVE_GUI_TEST=1 on a desktop with Tk 8.6+ (or Tk 9).
"""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@unittest.skipUnless(os.environ.get('GPIO_NATIVE_GUI_TEST') == '1', 'Native GUI-Test nur explizit starten')
class NativeChoices(unittest.TestCase):
    def test_idle_language_switch_recreates_real_windows_without_claiming_pins(self):
        import gpio_gui
        from gpio_i18n import set_language
        from guizero import App, PushButton, Window
        from gpio_choices import Choice
        from gpio_settings import load_settings, Settings
        errors, phases, choices, controllers = [], [], [], []
        original_controller = gpio_gui.MultiGPIOController

        def choice(*args, **kw):
            item = Choice(*args, **kw)
            choices.append(item)
            return item

        def controller(**kw):
            item = original_controller(**kw)
            controllers.append(item)
            return item

        def descendants(widget):
            for child in getattr(widget, 'children', []):
                if not isinstance(child, Window):
                    yield child
                    yield from descendants(child)

        def display(app):
            def inspect():
                try:
                    app.tk.update_idletasks()
                    self.assertTrue(all(not item.channels for item in controllers))
                    buttons = {w.text: w for w in descendants(app) if isinstance(w, PushButton)}
                    for widget in descendants(app):
                        if widget.tk.winfo_viewable():
                            bottom = widget.tk.winfo_rooty() + widget.tk.winfo_height() - app.tk.winfo_rooty()
                            left = widget.tk.winfo_rootx() - app.tk.winfo_rootx()
                            right = left + widget.tk.winfo_width()
                            self.assertGreaterEqual(left, -2, 'Main-window content must fit on the left')
                            self.assertLessEqual(right, app.tk.winfo_width() + 2,
                                                 'Main-window content must fit on the right')
                            self.assertLessEqual(bottom, app.tk.winfo_height() + 2,
                                                 'Main-window content must fit vertically: '
                                                 + type(widget).__name__ + ' '
                                                 + str(getattr(widget, 'value', ''))[:100])
                    if not phases:
                        phases.append('de')
                        buttons['Sprache & Module / Language & modules'].tk.invoke()
                        chooser = choices[-1]
                        self.assertFalse(str(app.tk.tk.call('grab', 'current')))
                        chooser._listing.value = 'English · GPIO'
                        chooser.accept()
                    else:
                        phases.append('en')
                        self.assertIn('Activate pin…', buttons)
                        self.assertNotIn('Gertboard test', buttons)
                        self.assertEqual(load_settings(), Settings('en', False))
                        app.destroy()
                except BaseException as exc:
                    errors.append(exc)
                    app.destroy()
            app.tk.after(150, inspect)
            app.tk.mainloop()

        with tempfile.TemporaryDirectory() as cache, \
                patch.dict(os.environ, {'XDG_CACHE_HOME': cache, 'XDG_CONFIG_HOME': cache}), \
                patch.object(sys, 'argv', ['gpio_gui.py', '--demo', '--language', 'de', '--gertboard']), \
                patch.object(App, 'display', display), \
                patch.object(gpio_gui, 'Combo', side_effect=choice), \
                patch.object(gpio_gui, 'MultiGPIOController', side_effect=controller):
            try:
                self.assertEqual(gpio_gui.main(), 0)
            finally:
                set_language('de')
        if errors:
            raise errors[0]
        self.assertEqual(phases, ['de', 'en'])

    def test_live_timer_and_all_selection_windows_use_no_grab(self):
        for language in ("de", "en"):
            with self.subTest(language=language):
                self.run_live_test(language)

    def run_live_test(self, language):
        import tkinter
        if sys.platform == 'darwin' and tkinter.TkVersion < 8.6:
            self.skipTest('Veraltetes macOS-System-Tk; Tk 8.6+ verwenden')
        import gpio_gui
        from gpio_i18n import tr, set_language
        from gpio_choices import Choice
        from guizero import App, PushButton, Text
        errors, choices, controllers = [], [], []
        original_controller = gpio_gui.MultiGPIOController

        def choice(*args, **kw):
            widget = Choice(*args, **kw)
            choices.append(widget)
            return widget

        def controller(**kw):
            instance = original_controller(**kw)
            controllers.append(instance)
            return instance

        def descendants(widget):
            for child in getattr(widget, 'children', []):
                yield child
                yield from descendants(child)

        def display(app):
            def button(text):
                return next(w for w in descendants(app) if isinstance(w, PushButton) and w.text == text)

            def assert_no_grab():
                self.assertFalse(str(app.tk.tk.call('grab', 'current')))

            mode = next(w for w in choices if w._title == tr('Eingang oder Ausgang auswählen'))
            mode.open()
            mode._listing.value = tr('Ausgang (Start LOW)')
            initial = next(w.value for w in descendants(app) if isinstance(w, Text)
                           and str(w.value).startswith('DEMO · Raspi'))
            app.yesno = lambda *args: True

            def finish():
                try:
                    current = next(w.value for w in descendants(app) if isinstance(w, Text)
                                   and str(w.value).startswith('DEMO · Raspi'))
                    self.assertNotEqual(initial, current, 'Live-Timer muss bei offener Auswahl weiterlaufen')
                    self.assertTrue(mode._window.visible)
                    self.assertEqual(mode.value, tr('Eingang'))
                    self.assertEqual(mode._listing.value, tr('Ausgang (Start LOW)'))
                    assert_no_grab()
                    mode.accept()
                    button(tr('Pin aktivieren…')).tk.invoke()
                    button('HIGH / 1').tk.invoke()
                    channel = controllers[0].channels[17]
                    self.assertTrue(channel.level)
                    button(tr('Gertboard-Test')).tk.invoke()
                    guide = choices[-1]
                    self.assertEqual(guide._title, tr('Funktionstest auswählen'))
                    for n in range(20):
                        guide.open()
                        app.tk.update_idletasks()
                        assert_no_grab()
                        guide._listing.value = tr('Taster S1 testen') if n % 2 == 0 else tr('LED1 testen')
                        guide.accept()
                    button(tr('Gertboard-Übersicht')).tk.invoke()
                    atlas = choices[-1]
                    for title in atlas.options:
                        atlas.open()
                        atlas._listing.value = title
                        atlas.accept()
                        assert_no_grab()
                    selection = next(w for w in choices if w._title == tr('GPIO auswählen'))
                    for target in (tr('GPIO{v0}  ·  physischer Pin {v1}', v0=27, v1=13), tr('GPIO{v0}  ·  physischer Pin {v1}', v0=17, v1=11)):
                        selection.open()
                        selection._listing.value = target
                        selection.accept()
                        assert_no_grab()
                    self.assertIs(controllers[0].channels[17], channel)
                    self.assertTrue(channel.level, 'Auswahl darf aktiven Ausgang nicht umschalten')
                    button(tr('Alle aktiven Pins freigeben')).tk.invoke()
                    button('Sprache & Module / Language & modules').tk.invoke()
                    preferences = choices[-1]
                    self.assertTrue(preferences._window.visible)
                    assert_no_grab()
                    preferences.close()
                    print(language, 'Native Tk', tkinter.TkVersion, ': Live-Timer, 20 Testwechsel, 24 Boardbereiche, GPIO-Auswahl OK')
                except BaseException as exc:
                    errors.append(exc)
                finally:
                    app.destroy()

            app.tk.after(2200, finish)
            app.tk.mainloop()

        with tempfile.TemporaryDirectory() as cache, \
                patch.dict(os.environ, {'XDG_CACHE_HOME': cache, 'XDG_CONFIG_HOME': cache}), \
                patch.object(sys, 'argv', ['gpio_gui.py', '--demo', '--language', language, '--gertboard']), \
                patch.object(App, 'display', display), \
                patch.object(gpio_gui, 'Combo', side_effect=choice), \
                patch.object(gpio_gui, 'MultiGPIOController', side_effect=controller):
            self.assertEqual(gpio_gui.main(), 0)
        set_language('de')
        if errors:
            raise errors[0]
        self.assertEqual(controllers[0].channels, {})


if __name__ == '__main__':
    unittest.main(verbosity=2)
