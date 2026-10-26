"""Selection lists without Tk popup menus or mouse/keyboard grabs.

OptionMenu can retain an invisible menu grab in the user's remote desktop.
This control uses an ordinary, nonmodal window instead. Opening, highlighting
or cancelling a choice never runs its change callback. Only explicit acceptance
does, and programmatic changes remain silent like guizero.Combo.value.
"""

from gpio_i18n import tr

import logging
from tkinter import TclError
from guizero import Box, ListBox, PushButton, Text, Window

LOG = logging.getLogger("raspi_gpio")


class Choice:
    _active = None

    def __init__(self, master, options, selected=None, command=None, grid=None,
                 align=None, width=None, title=None):
        self.master = master
        self._options = [str(item) for item in options]
        if selected is not None and str(selected) not in self._options:
            raise ValueError(tr("Auswahl nicht in den Optionen: ") + str(selected))
        self._selected = str(selected) if selected is not None else next(iter(self._options), "")
        self._on_change = command
        self._title = title or tr("Auswählen")
        self._window = self._listing = None
        self._button = PushButton(master, text=self._caption(), command=self.open,
                                  grid=grid, align=align, width=width, pady=5, padx=6)
        self.tk = self._button.tk

    def _caption(self):
        return (self._selected or tr("Auswählen")) + "  ▸"

    @property
    def options(self):
        return list(self._options)

    @property
    def value(self):
        return self._selected

    @value.setter
    def value(self, value):
        value = str(value)
        if value not in self._options:
            raise ValueError(tr("Auswahl nicht in den Optionen: ") + value)
        self.close()
        self._selected = value
        self._button.text = self._caption()

    @property
    def enabled(self):
        return self._button.enabled

    @enabled.setter
    def enabled(self, value):
        value = bool(value)
        if not value:
            self.close()
        if self._button.enabled != value:
            self._button.enabled = value

    def update_command(self, command):
        self._on_change = command

    def clear(self):
        self.close()
        self._options = []
        self._selected = ""
        self._button.text = self._caption()

    def append(self, option):
        self.close()
        self._options.append(str(option))
        if not self._selected:
            self._selected = self._options[0]
        self._button.text = self._caption()

    def open(self):
        if not self.enabled or not self._options:
            return
        if Choice._active is not None and Choice._active is not self:
            Choice._active.close()
        if self._window is None:
            owner = self.master
            while getattr(owner, "master", None) is not None and getattr(owner, "title", None) is None:
                owner = owner.master
            list_height = max(76, min(12, len(self._options))*26)
            self._window = Window(owner, title=self._title, width=560,
                                  height=list_height+150, bg="#f3f6fa", visible=False)
            Text(self._window, text=self._title, size=15, bold=True, color="#136b69")
            Text(self._window, text=tr("Eintrag markieren und übernehmen · Esc: abbrechen"), size=10)
            self._listing = ListBox(self._window, items=[], scrollbar=True,
                                    width=520, height=list_height)
            self._listing.when_double_clicked = lambda event: self.accept()
            actions = Box(self._window)
            PushButton(actions, text=tr("Übernehmen"), command=self.accept, align="left")
            PushButton(actions, text=tr("Abbrechen"), command=self.close, align="left")
            self._window.when_closed = self.close
            self._window.tk.bind("<Escape>", lambda event: self.close(), add="+")
            self._window.tk.bind("<Return>", lambda event: self.accept(), add="+")
            owner.tk.bind("<Unmap>", lambda event: self.close() if event.widget is owner.tk else None,
                          add="+")
        self._listing.clear()
        for option in self._options:
            self._listing.append(option)
        self._listing.value = self._selected
        Choice._active = self
        # Never call show(wait=True), wait_window, grab_set or focus_force.
        self._window.show(wait=False)
        self._window.tk.lift()
        LOG.info("Auswahl geöffnet: %s", self._title)

    def accept(self):
        if Choice._active is not self or not self.enabled or self._listing is None:
            return
        chosen = self._listing.value
        if chosen not in self._options:
            return
        changed = chosen != self._selected
        self.value = chosen  # Close before callback: exceptions cannot strand a menu.
        LOG.info("Auswahl übernommen: %s = %s", self._title, chosen)
        if changed and self._on_change is not None:
            self._on_change()

    def close(self):
        if Choice._active is self:
            Choice._active = None
        if self._window is not None and self._window.visible:
            try:
                self._window.hide()
            except TclError:
                # The root may already have destroyed this child during shutdown.
                LOG.debug("Auswahlfenster bereits zerstört: %s", self._title)
            LOG.info("Auswahl geschlossen: %s", self._title)


def set_enabled(widget, enabled):
    """Avoid resetting widget state every second while the user interacts."""
    enabled = bool(enabled)
    if widget.enabled != enabled:
        widget.enabled = enabled


def close_choices():
    if Choice._active is not None:
        Choice._active.close()
