"""Exercise the actual picker lifecycle without a display or GPIO access."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gpio_choices
from gpio_choices import Choice, close_choices, set_enabled


class FakeTk:
    def __init__(self):
        self.bindings = {}
        self.grab_set = Mock(side_effect=AssertionError('No menu grabs'))
        self.wait_window = Mock(side_effect=AssertionError('No nested event loops'))
        self.focus_force = Mock(side_effect=AssertionError('No forced focus'))
        self.lift = Mock()

    def bind(self, event, callback, add=None):
        self.bindings[event] = callback


class FakeWidget:
    def __init__(self, master=None, **kw):
        self.master = master
        self.tk = FakeTk()
        self.title = kw.get('title')
        self.text = kw.get('text', '')
        self.command = kw.get('command')
        self._enabled = kw.get('enabled', True)
        self.enabled_writes = 0

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        self._enabled = value
        self.enabled_writes += 1


class FakeWindow(FakeWidget):
    all = []

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.visible = kw.get('visible', True)
        self.show_calls = []
        self.all.append(self)

    def show(self, wait=False):
        if wait:
            raise AssertionError('Picker must remain nonmodal')
        self.show_calls.append(wait)
        self.visible = True

    def hide(self):
        self.visible = False


class FakeList(FakeWidget):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.items = list(kw.get('items', []))
        self.value = None

    def clear(self):
        self.items = []
        self.value = None

    def append(self, option):
        self.items.append(option)


class ChoiceTests(unittest.TestCase):
    def setUp(self):
        FakeWindow.all = []
        Choice._active = None
        self.patches = patch.multiple(gpio_choices, Box=FakeWidget, Text=FakeWidget,
                                      PushButton=FakeWidget, ListBox=FakeList, Window=FakeWindow)
        self.patches.start()
        self.app = FakeWidget(title='App')

    def tearDown(self):
        close_choices()
        self.patches.stop()

    def test_marking_cancel_and_escape_do_not_commit_or_call_the_handler(self):
        changed = Mock()
        choice = Choice(self.app, ['Eingang', 'Ausgang'], command=changed)
        choice.open()
        choice._listing.value = 'Ausgang'
        self.assertEqual(choice.value, 'Eingang')
        choice._window.tk.bindings['<Escape>'](None)
        changed.assert_not_called()
        self.assertIsNone(Choice._active)
        self.assertFalse(choice._window.visible)
        choice.open()
        self.assertEqual(choice._listing.value, 'Eingang')
        choice._listing.value = 'Ausgang'
        choice._window.tk.bindings['<Return>'](None)
        self.assertEqual(choice.value, 'Ausgang')
        changed.assert_called_once_with()
        self.assertIsNone(Choice._active)

    def test_repeated_live_ticks_leave_open_picker_unchanged(self):
        choice = Choice(self.app, ['A', 'B'])
        choice.open()
        choice._listing.value = 'B'
        for _ in range(1000):
            set_enabled(choice, True)
        self.assertEqual(choice._button.enabled_writes, 0)
        self.assertTrue(choice._window.visible)
        self.assertEqual(choice._listing.value, 'B')
        choice.accept()
        self.assertEqual(choice.value, 'B')
        self.assertEqual(choice._window.show_calls, [False])

    def test_window_reuse_and_only_one_picker_open_for_the_whole_app(self):
        one = Choice(self.app, ['A', 'B'])
        help_window = FakeWindow(self.app, title='Test')
        two = Choice(FakeWidget(help_window), ['LED', 'Taster'])
        one.open()
        two.open()
        self.assertFalse(one._window.visible)
        self.assertTrue(two._window.visible)
        self.assertIs(two._window.master, help_window)
        two._window.when_closed()
        for _ in range(100):
            one.open()
            one.close()
        self.assertEqual(len(FakeWindow.all), 3)  # two pickers and the help window
        self.assertIsNone(Choice._active)
        two.open()
        help_window.tk.bindings['<Unmap>'](SimpleNamespace(widget=help_window.tk))
        self.assertFalse(two._window.visible)

    def test_disabling_or_changing_options_invalidates_an_old_pending_selection(self):
        changed = Mock()
        choice = Choice(self.app, ['GPIO17', 'GPIO21'], command=changed)
        choice.open()
        choice._listing.value = 'GPIO21'
        set_enabled(choice, False)
        choice.accept()
        self.assertEqual(choice.value, 'GPIO17')
        changed.assert_not_called()
        set_enabled(choice, True)
        choice.open()
        choice.clear()
        choice.append('GPIO27')
        choice.accept()
        self.assertEqual(choice.value, 'GPIO27')
        changed.assert_not_called()
        choice.open()
        self.assertEqual(choice._listing.items, ['GPIO27'])

    def test_programmatic_changes_are_silent_and_callback_errors_cannot_strand_a_picker(self):
        changed = Mock(side_effect=RuntimeError('handler failed'))
        choice = Choice(self.app, ['A', 'B'], command=changed)
        choice.open()
        choice.value = 'B'
        changed.assert_not_called()
        self.assertFalse(choice._window.visible)
        choice.open()
        choice._listing.value = 'A'
        with self.assertRaisesRegex(RuntimeError, 'handler failed'):
            choice.accept()
        self.assertFalse(choice._window.visible)
        self.assertIsNone(Choice._active)

    def test_invalid_or_empty_choices_do_not_create_or_commit_a_window(self):
        choice = Choice(self.app, [])
        choice.open()
        self.assertIsNone(choice._window)
        with self.assertRaises(ValueError):
            choice.value = 'missing'
        with self.assertRaises(ValueError):
            Choice(self.app, ['A'], selected='missing')
        choice.append('A')
        self.assertEqual(choice.value, 'A')
        choice.open()
        choice._listing.value = None
        choice.accept()
        self.assertEqual(choice.value, 'A')
        self.assertTrue(choice._window.visible)

    def test_shutdown_drops_active_reference_even_if_tk_destroyed_the_window(self):
        choice = Choice(self.app, ['A', 'B'])
        choice.open()
        choice._window.hide = Mock(side_effect=gpio_choices.TclError('application destroyed'))
        close_choices()
        self.assertIsNone(Choice._active)


if __name__ == '__main__':
    unittest.main(verbosity=2)
