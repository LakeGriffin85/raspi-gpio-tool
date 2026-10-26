"""Static top-view orientation matching the user's photo; no GPIO access."""

from gpio_i18n import tr

YELLOW = "#facc15"
DARK = "#172b3a"
TEXT = "#243348"


class OrientationDiagram:
    WIDTH, HEIGHT = 900, 560
    PIN_X = (674, 724)  # odd = board inside (left), even = outside edge (right)
    FIRST_Y, STEP = 106, 18

    def __init__(self, canvas):
        self.canvas = canvas
        self.pin_items = {}
        self._draw()

    @classmethod
    def position(cls, physical):
        if not 1 <= physical <= 40:
            raise ValueError(tr("Stecker-Pin muss zwischen 1 und 40 liegen."))
        return (cls.PIN_X[(physical - 1) % 2],
                cls.FIRST_Y + (physical - 1) // 2 * cls.STEP)

    def _text(self, x, y, text, size=11, color=TEXT, bold=False, anchor="center"):
        return self.canvas.create_text(x, y, text=text, fill=color, anchor=anchor,
                                       font=("DejaVu Sans", size, "bold" if bold else "normal"))

    def _draw(self):
        c = self.canvas
        c.configure(background="#f3f6fa", highlightthickness=0)
        self._text(450, 19, tr("Wie auf deinem Foto: Bauteile oben · USB und LAN unten"), 14, bold=True)
        self._text(190, 57, tr("Dein Raspi 5 · schematisch"), 12, bold=True)
        # Board outline and landmarks follow the supplied portrait photograph.
        c.create_rectangle(56, 81, 344, 455, fill="#16845d", outline="#116448", width=2)
        for x, y in ((76, 99), (323, 99), (76, 435), (323, 435)):
            c.create_oval(x - 9, y - 9, x + 9, y + 9, fill="#d5bb6d", outline="#bca455")
            c.create_oval(x - 4, y - 4, x + 4, y + 4, fill=DARK, outline=DARK)
        c.create_rectangle(101, 82, 177, 96, fill="#dfc79d", outline="#baa079")
        self._text(139, 109, "PCIe", 8, "white")
        c.create_rectangle(186, 119, 280, 185, fill="#8d99a5", outline="#d5dce3", width=2)
        self._text(232, 160, tr("Funk"), 10, "white")
        c.create_rectangle(105, 224, 196, 308, fill="#9da8b2", outline="#d5dce3", width=2)
        self._text(150, 266, "CPU", 13, DARK, bold=True)
        c.create_rectangle(216, 362, 273, 410, fill=DARK, outline="#cbd5e1")
        self._text(244, 386, "RP1", 11, "white")
        for y, label in ((133, "USB-C"), (247, "HDMI"), (294, "HDMI")):
            c.create_rectangle(41, y - 14, 82, y + 14, fill="#cbd5e1", outline="#64748b")
            self._text(62, y, label, 7)
        for x1, x2, name, fill in ((62, 144, "LAN", "#cbd5e1"),
                                    (158, 235, "USB", "#91b8da"),
                                    (247, 324, "USB", "#cbd5e1")):
            c.create_rectangle(x1, 430, x2, 479, fill=fill, outline="#64748b", width=2)
            self._text((x1 + x2) / 2, 456, name, 12, bold=True)

        # Small header: exactly the same orientation as the enlarged header.
        c.create_rectangle(287, 115, 334, 401, fill=DARK, outline=DARK)
        for physical in range(1, 41):
            x = 300 if physical % 2 else 322
            y = 126 + (physical - 1) // 2 * 14
            color = YELLOW if physical == 1 else "#cbd5e1"
            c.create_oval(x - 3, y - 3, x + 3, y + 3, fill=color, outline=color)
        for x, y, number in ((300, 115, "1"), (322, 115, "2"),
                              (300, 414, "39"), (322, 414, "40")):
            self._text(x, y, number, 9, YELLOW if number == "1" else "white", bold=True)
        c.create_oval(264, 116, 282, 134, fill=YELLOW, outline="#a16207", width=1)
        self._text(178, 202, tr("Dein gelber Punkt"), 11, "white", bold=True)
        c.create_line(253, 196, 272, 138, fill=YELLOW, width=2, arrow="last")
        self._text(266, 145, "Pin 1", 9, "white", anchor="e")

        self._text(476, 164, tr("Blick von oben"), 13, bold=True)
        self._text(476, 190, tr("auf die Bauteile"), 11)
        self._text(476, 257, tr("1 / 39: zur Platine"), 11, bold=True)
        self._text(476, 283, tr("2 / 40: zur Außenkante"), 11)
        self._text(476, 350, "USB / LAN", 12, bold=True)
        c.create_line(476, 370, 476, 419, fill="#64748b", width=3, arrow="last")
        self._text(476, 439, tr("unten"), 11)

        self._text(699, 59, tr("40-Pin-Header vergrößert"), 12, bold=True)
        c.create_rectangle(652, 86, 746, 468, fill=DARK, outline=DARK)
        c.create_oval(624, 96, 644, 116, fill=YELLOW, outline="#a16207")
        c.create_line(644, 106, 663, 106, fill=YELLOW, width=2, arrow="last")
        for physical in range(1, 41):
            x, y = self.position(physical)
            color = YELLOW if physical == 1 else "#cbd5e1"
            if physical == 1:
                dot = c.create_rectangle(x - 6, y - 6, x + 6, y + 6, fill=color, outline=color)
            else:
                dot = c.create_oval(x - 5, y - 5, x + 5, y + 5, fill=color, outline=color)
            edge = physical in (1, 2, 39, 40)
            number = self._text(x - 35 if physical % 2 else x + 35, y,
                                str(physical), 13 if edge else 9,
                                "#a16207" if physical == 1 else TEXT,
                                bold=edge, anchor="e" if physical % 2 else "w")
            self.pin_items[physical] = (dot, number)
        self._text(699, 489, tr("39 / 40 = USB-/LAN-Seite"), 11, bold=True)
        self._text(450, 524, tr("PIN 1–40 = Position am Stecker · nicht die GPIO-Nummer"), 12, bold=True)
        self._text(450, 548, tr("Von oben ansehen; die Unterseite eines abgezogenen Steckers ist spiegelverkehrt."), 10)
