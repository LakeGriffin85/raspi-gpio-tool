"""Live 40-pin header drawn on a standard Tk canvas. No hardware access here."""

from gpio_i18n import tr

from gpio_core import HEADER_GPIO, HEADER_POWER
from gpio_availability import GERTBOARD_LABELS
from gpio_orientation import YELLOW

HIGH = "#169b62"
LOW = "#7c8b9e"
UNKNOWN = "#cbd5e1"
SELECTED = "#0284c7"
MODE_COLOR = "#2563eb"
RESERVED = "#8b5cf6"
BUSY = "#c24136"
BUS = "#b86c00"
OWNED = "#0f8a8a"
ACCESS_COLOR = {"fixed": "#64748b", "reserved": RESERVED, "busy": BUSY,
                "bus": BUS, "owned": OWNED, "unknown": "#94a3b8", "unconnected": "#cbd5e1"}


class HeaderDiagram:
    WIDTH, HEIGHT = 650, 555
    FIRST_Y, STEP = 44, 23

    def __init__(self, canvas, on_select, on_inspect=None):
        self.canvas = canvas
        self.on_select = on_select
        self.on_inspect = on_inspect
        self.items = {}
        self.styles = {}
        self.gertboard = False
        self.visible_pins = 40
        self._draw()
        canvas.bind("<Button-1>", self._click)

    def _draw(self):
        c = self.canvas
        self.visible_pins = 26 if self.gertboard else 40
        rows = self.visible_pins // 2
        bottom = self.FIRST_Y + (rows - 1) * self.STEP + 18
        self.height = bottom + (78 if self.gertboard else 56)
        c.configure(background="#f3f6fa", highlightthickness=0, width=self.WIDTH, height=self.height)
        title = (tr("Gertboard · J1 mit 26 Pins · gelber Punkt = Pin 1") if self.gertboard else
                 tr("40-Pin-Header · gelber Punkt = Pin 1"))
        self.title = c.create_text(325, 13, text=title, font=("DejaVu Sans", 11, "bold"), fill="#243348")
        c.create_rectangle(252, 27, 398, bottom, fill="#172b3a", outline="#172b3a", width=1)
        for physical in range(1, self.visible_pins + 1):
            row, side = (physical - 1) // 2, (physical - 1) % 2
            y = self.FIRST_Y + row * self.STEP
            left = side == 0
            x1, x2 = (8, 240) if left else (410, 642)
            pin_x, number_x = (296, 268) if left else (354, 382)
            name_x, mode_x, level_x = ((18, 96, 231) if left else (420, 498, 633))
            card = c.create_rectangle(x1, y - 10, x2, y + 10, fill="white", outline="#e2e8f0", width=1)
            c.create_line(x2 if left else x1, y, 252 if left else 398, y,
                          fill="#b9c6d2", width=1)
            if physical == 1:
                dot = c.create_rectangle(pin_x - 7, y - 7, pin_x + 7, y + 7,
                                         fill=UNKNOWN, outline=UNKNOWN, width=1)
            else:
                dot = c.create_oval(pin_x - 7, y - 7, pin_x + 7, y + 7,
                                    fill=UNKNOWN, outline=UNKNOWN, width=1)
            c.create_text(number_x, y, text=str(physical), fill=YELLOW if physical == 1 else "#e2e8f0",
                          font=("DejaVu Sans Mono", 11, "bold") if physical in (1, 2, self.visible_pins - 1, self.visible_pins) else ("DejaVu Sans Mono", 9))
            if physical == 1:
                c.create_oval(pin_x - 13, y - 13, pin_x + 13, y + 13,
                              outline=YELLOW, width=3)
            gpio = HEADER_GPIO.get(physical)
            name = f"GPIO{gpio}" if gpio is not None else HEADER_POWER[physical]
            if physical == 27:
                name = "GPIO0/ID"
            elif physical == 28:
                name = "GPIO1/ID"
            name_id = c.create_text(name_x, y, text=name, anchor="w", fill="#243348",
                                    font=("DejaVu Sans", 10, "bold"))
            mode_id = c.create_text(mode_x, y, text="", anchor="w", fill="#52647b", font=("DejaVu Sans", 8))
            level_id = c.create_text(level_x, y, text="", anchor="e", fill="#52647b", font=("DejaVu Sans Mono", 9, "bold"))
            mark = c.create_text(pin_x, y, text="", fill="white", font=("DejaVu Sans", 11, "bold"))
            self.items[physical] = (card, dot, mode_id, level_id, name_id, mark)

        for x, color, label in [(10, HIGH, "HIGH"), (82, LOW, "LOW"),
                               (150, UNKNOWN, tr("Pegel ?")), (244, BUSY, tr("belegt")),
                               (333, BUS, "Bus"), (401, RESERVED, tr("reserviert")),
                               (526, OWNED, tr("diese App"))]:
            c.create_oval(x, bottom + 18, x + 10, bottom + 28, fill=color, outline=color)
            c.create_text(x + 17, bottom + 23, text=label, anchor="w", fill="#52647b", font=("DejaVu Sans", 9))
        c.create_text(325, bottom + 46, text=tr("× = hier nicht schaltbar · Anklicken zeigt den Grund · ↑/↓ = Pull"),
                      fill="#52647b", font=("DejaVu Sans", 9))
        if self.gertboard:
            c.create_text(325, bottom + 68, text=tr("17 GPIOs · Pegel am Raspi · Buffer und Versorgung separat prüfen"),
                          fill="#52647b", font=("DejaVu Sans", 9))

    def update(self, states, selected, access=None, gertboard=False):
        if self.gertboard != gertboard:
            self.canvas.delete("all")
            self.items.clear()
            self.styles.clear()
            self.gertboard = gertboard
            self._draw()
        for physical, items in self.items.items():
            gpio = HEADER_GPIO.get(physical)
            state = states.get(gpio)
            if gpio is None:
                kind = HEADER_POWER[physical]
                color = {"3V3": "#d9910c", "5V": "#dc3d59", "GND": "#334155"}[kind]
                mode, level = (tr("Masse"), "GND") if kind == "GND" else (tr("Versorgung"), kind)
            else:
                color = UNKNOWN if state is None or state.level is None else HIGH if state.level else LOW
                level = "?" if state is None or state.level is None else "HIGH" if state.level else "LOW"
                if state is None:
                    mode = tr("unbekannt")
                elif state.mode in ("ip", "op"):
                    mode = {"ip": "IN", "op": "OUT"}[state.mode]
                    mode += {"pu": " ↑", "pd": " ↓", "pn": "", "?": ""}.get(state.pull, "")
                else:
                    mode = (state.function or state.mode)[:13]
                if gpio in (0, 1):
                    mode = tr("reserviert")
            selected_pin = gpio is not None and gpio == selected
            alt = state is not None and state.mode not in ("ip", "op", "?", "no")
            availability = access.get(physical) if access is not None else None
            kind = availability.kind if availability else "reserved" if gpio in (0, 1) else "available"
            name = GERTBOARD_LABELS.get(gpio, f"GPIO{gpio}") if gertboard and gpio is not None else f"GPIO{gpio}" if gpio is not None else HEADER_POWER[physical]
            if not gertboard and gpio in (0, 1):
                name += "/ID"
            if kind == "unconnected":
                mode, level, color = tr("nicht am GB"), "—", UNKNOWN
            elif gertboard and gpio in (2, 3, 27):
                mode = f"GPIO{gpio} · " + mode
                mode = mode[:17]
            status_color = ACCESS_COLOR.get(kind, "#e2e8f0")
            outline = SELECTED if selected_pin else status_color
            mode_color = status_color if kind in ("busy", "bus", "reserved", "owned") else MODE_COLOR if alt else "#52647b"
            if kind == "busy":
                mode = tr("belegt")
            elif kind == "owned" and not (gertboard and gpio in (2, 3, 27)):
                mode += " · App"
            blocked = kind in ("fixed", "reserved", "busy", "bus", "unconnected")
            mark_text = "×" if blocked else "?" if kind == "unknown" else ""
            style = (color, mode, level, outline, selected_pin, mode_color, mark_text, kind, name)
            if self.styles.get(physical) == style:
                continue
            card, dot, mode_id, level_id, name_id, mark = items
            fill = "#e0f2fe" if selected_pin else "#edfafa" if kind == "owned" else "#fef2f2" if kind == "busy" else "#fff8eb" if kind == "bus" else "#f1f5f9" if kind == "unconnected" else "white"
            self.canvas.itemconfigure(card, fill=fill, outline=outline,
                                      width=2 if selected_pin or blocked or kind == "owned" else 1)
            self.canvas.itemconfigure(dot, fill=color, outline=status_color if kind != "available" else color,
                                      width=2)
            self.canvas.itemconfigure(mode_id, text=mode, fill=mode_color)
            self.canvas.itemconfigure(level_id, text=level, fill=color)
            self.canvas.itemconfigure(name_id, text=name, fill="#94a3b8" if kind == "unconnected" else "#243348")
            self.canvas.itemconfigure(mark, text=mark_text, fill="#243348" if color == UNKNOWN else "white")
            self.styles[physical] = style

    def _click(self, event):
        physical = self.physical_at(event.x, event.y)
        if physical is not None and self.on_inspect is not None:
            self.on_inspect(physical)
            return
        gpio = HEADER_GPIO.get(physical)
        if gpio is not None and gpio not in (0, 1):
            self.on_select(gpio)

    def physical_at(self, x, y):
        if not 8 <= x <= 642:
            return None
        row = round((y - self.FIRST_Y) / self.STEP)
        if not 0 <= row < self.visible_pins // 2 or abs(y - (self.FIRST_Y + row * self.STEP)) > 10:
            return None
        return row * 2 + (1 if x < self.WIDTH / 2 else 2)
