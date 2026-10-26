"""Photo-matched, read-only Gertboard connector atlas (21 Oct. 2012).

Connector names/positions come from the owner's board photograph. Functional
relationships: original Fen Logic manual rev. 2; chip functions: Microchip,
TI/ST and ROHM. This module never opens hardware or infers wiring/LED state.
"""

from dataclasses import dataclass
from gpio_i18n import tr

MANUAL = "https://www.farnell.com/datasheets/1683444.pdf"
SOURCES = {
    "manual": ("Gertboard-Handbuch Rev. 2", MANUAL),
    "adc": ("Microchip MCP3002", "https://www.microchip.com/en-us/product/mcp3002"),
    "dac": ("Microchip MCP4822 / MCP48x2", "https://www.microchip.com/en-us/product/mcp4822"),
    "avr": ("Microchip ATmega328P", "https://www.microchip.com/en-us/product/atmega328p"),
    "buffer": ("TI SN74AHC244", "https://www.ti.com/product/SN74AHC244"),
    "relay": ("ST ULN2803A", "https://www.st.com/en/interfaces-and-transceivers/uln2803a.html"),
    "motor": ("ROHM BD6222HFP", "https://www.rohm.com/products/motor-actuator-drivers/dc-brush-motor/bd6222hfp-product"),
}

# Left to right in the supplied top-view photo, NOT connector pin numbers.
PI_SIGNALS = (
    ("GP25", 25, 22), ("GP24", 24, 18), ("GP23", 23, 16),
    ("GP22", 22, 15), ("GP21", 27, 13), ("GP18", 18, 12),
    ("GP17", 17, 11), ("GP15", 15, 10), ("GP14", 14, 8),
    ("GP11", 11, 23), ("GP10", 10, 19), ("GP9", 9, 21),
    ("GP8", 8, 24), ("GP7", 7, 26), ("GP4", 4, 7),
    ("GP1", 3, 5), ("GP0", 2, 3),
)
COLORS = {
    "Raspi": "#78c9ff", "Buffer": "#ffcf7a", "Analog": "#9de4c8",
    "ATmega": "#d9b7ff", "Leistung": "#ffa49d", "Versorgung": "#e4d9ac",
    "Übersicht": "#c6e5da",
}


@dataclass(frozen=True)
class Region:
    key: str
    title: str
    label: str
    domain: str
    rect: tuple
    intro: str
    signals: tuple
    effect: str
    note: str = ""
    source: str = "manual"

    def details(self):
        rows = [tr(self.intro), "", tr("ANSCHLÜSSE / SIGNALE")]
        rows.extend(f"{tr(name)}\n  {tr(meaning)}" for name, meaning in self.signals)
        rows += ["", tr("WIRKUNG"), tr(self.effect)]
        if self.note:
            rows += ["", tr("BEACHTEN"), tr(self.note)]
        source_name, _ = SOURCES[self.source]
        rows += ["", tr("Grundlage: Boardfoto · {source}", source=tr(source_name)),
                 tr("Anschlüsse zum Nachschlagen; keine Live-Messung.")]
        return "\n".join(rows)


REGIONS = (
    Region("overview", "Warum so viele Anschlüsse?", "17 Raspi-GPIOs\n+ Funktionsblöcke", "Übersicht", (30, 520, 246, 568),
           "Viele Stifte sind Ein- und Ausgänge derselben Schaltung oder gehören zum eigenen Mikrocontroller.",
           (("J2: GP…", "17 Signale vom Raspi"),
            ("J3: B1–B12 ↔ oben: BUF1–BUF12", "Zwei Seiten von 12 Buffer-Kanälen"),
            ("J25: PB…, PC…, PD…", "Pins des separaten ATmega")),
           "Erst deine Drähte verbinden die Funktionsblöcke. J1 führt Versorgung und Raspi-Signale aufs Board.",
           "B1 bedeutet Buffer 1, nicht GPIO1. Mehr Stifte erzeugen keine zusätzlichen Raspi-GPIOs."),
    Region("leds", "Oben · BUF1–BUF12 und LEDs", "BUF1–BUF12 · D1–D12", "Buffer", (124, 56, 490, 130),
           "Die obere Leiste ist die Außen-Seite der Buffer. Die LEDs zeigen den dortigen Logikpegel.",
           tuple((f"BUF{n} / D{n}", f"Außenanschluss Kanal {n}; zugehörige LED") for n in range(1, 13)),
           "HIGH: LED an. LOW: LED aus. Unbeschaltete Eingänge werden durch Pull-Ups HIGH: alle LEDs an kann normal sein.",
           "Mit OUT-Jumper und ungetriebenem B-Eingang kann der Pegel undefiniert werden. Eine leuchtende LED belegt keinen HIGH-Pegel am Raspi."),
    Region("power_top", "Oben links · 3V3", "3V3", "Versorgung", (28, 74, 108, 116),
           "Links neben BUF1 ist auf deinem Foto die 3V3-Leiste beschriftet.",
           (("3V3", "Feste 3,3-V-Boardversorgung"),),
           "Ein Versorgungspunkt für kleine Logikschaltungen, kein weiterer GPIO und kein LED-Kanal.",
           "Die Versorgung hängt von der korrekten Boardeinspeisung ab. Die App misst diese Spannung nicht."),
    Region("buttons", "S1–S3 · Taster", "S1       S2       S3", "Buffer", (174, 146, 324, 192),
           "Die drei Taster wirken auf die Raspi-Seite der ersten drei Kanäle.",
           (("S1 → B1", "Gedrückt: über Widerstand nach GND"),
            ("S2 → B2", "Gleiche Funktion für Kanal 2"),
            ("S3 → B3", "Gleiche Funktion für Kanal 3")),
           "Als Eingang mit Pull-Up: losgelassen HIGH, gedrückt LOW. GP17 → B1 ist ein einfacher erster Test.",
           "IN-Jumper für den Tastertest offen lassen. Die Anleitung im Hauptfenster zeigt den vollständigen Aufbau."),
    Region("buffer1", "U3 · Buffer 1–4 / IN und OUT", "U3 · B1–B4\nOUT oben · IN unten", "Buffer", (174, 218, 324, 336),
           "Jeder Kanal verbindet Bn mit BUFn über einen Buffer, je nach Richtungsjumper.",
           (("B1 ↔ BUF1", "Kanal 1, außerdem Taster S1"), ("B2 ↔ BUF2", "Kanal 2, außerdem S2"),
            ("B3 ↔ BUF3", "Kanal 3, außerdem S3"), ("B4 ↔ BUF4", "Kanal 4"),
            ("IN / OUT", "IN: BUF → B → Pi; OUT: Pi → B → BUF")),
           "Die Richtung gilt aus Sicht des Raspi. GPIO17 wird erst durch einen Draht GP17 → B1 zu Kanal 1.",
           "Nur die passende Richtung setzen; vor dem Umstecken alle Speisungen trennen.", "buffer"),
    Region("buffer2", "U4 · Buffer 5–8 / IN und OUT", "U4 · B5–B8\nOUT oben · IN unten", "Buffer", (338, 146, 490, 246),
           "Vier weitere Kanäle desselben Buffer-Prinzips.",
           tuple((f"B{n} ↔ BUF{n}", f"Kanal {n}, Anzeige D{n}") for n in range(5, 9)) +
           (("IN / OUT", "IN: zur Pi-Seite; OUT: zur BUF-Leiste"),),
           "Ein Draht von J2 zu J3 wählt den Raspi-GPIO. Der Jumper wählt die Richtung.",
           "B7 ist Buffer-Kanal 7, nicht automatisch Raspi-GPIO7.", "buffer"),
    Region("buffer3", "U5 · Buffer 9–12 / IN und OUT", "U5 · B9–B12\nOUT oben · IN unten", "Buffer", (338, 268, 490, 368),
           "Die letzten vier der insgesamt zwölf Buffer-Kanäle.",
           tuple((f"B{n} ↔ BUF{n}", f"Kanal {n}, Anzeige D{n}") for n in range(9, 13)) +
           (("IN / OUT", "IN: zur Pi-Seite; OUT: zur BUF-Leiste"),),
           "Wie U3/U4: Zuordnung per Draht, Richtung per Jumper. Die App kennt diese Verdrahtung nicht.",
           "Die zwölf Kanäle sind unabhängig verdrahtbar, ohne feste GPIO-Nummer.", "buffer"),
    Region("buffer_pi", "J3 · B1–B12 auf der Pi-Seite", "J3 · B1–B12", "Buffer", (174, 394, 490, 432),
           "Hier werden die Buffer-Kanäle mit den gewünschten Raspi-Signalen verbunden.",
           tuple((f"B{n}", f"Pi-Seite von Buffer {n}") for n in range(1, 13)),
           "Beispiel: J2 GP17 → J3 B1, B1 OUT gesetzt: GPIO17 steuert BUF1 und LED D1.",
           "J3 und die obere BUF-Leiste sind verschiedene Seiten der Buffer."),
    Region("gpio", "J2 · 17 Raspi-Signale", "J2 · GP25 … GP0", "Raspi", (260, 482, 570, 516),
           "Reihenfolge wie auf deinem Foto: von links nach rechts. GPIO = BCM-Nummer; Pin = physischer J1-Steckerpin.",
           tuple((old, f"GPIO{gpio} · J1-Pin {physical}") for old, gpio, physical in PI_SIGNALS),
           "Diese Signale sind mit J1 verbunden; von hier führst du Drähte zu B1–B12, SPI oder Treibereingängen.",
           "Historisch: GP0 = GPIO2, GP1 = GPIO3, GP21 = GPIO27 am Pi 5. Andere App-Namen PB/PC/PD gehören zum ATmega."),
    Region("pi", "J1 · Verbindung zum Raspi", "J1 · 26-polig", "Raspi", (260, 530, 570, 568),
           "J1 bezeichnet den ganzen 26-poligen Anschluss auf der Unterseite.",
           (("1–26", "Physische Steckernummern, keine GPIO-Nummern"),
            ("Pin 1", "Quadratische Markierung / Punkt am Board"),
            ("Signale / Versorgung", "17 Raspi-Signale sowie Versorgung und Masse")),
           "J1 führt zum Raspi; die 17 Signale erscheinen an J2. Pi-Pins 27–40 liegen außerhalb dieses Anschlusses.",
           "Die Grafik zeigt die Bauteilseite wie dein Foto. Für die Raspi-Lage gibt es »Steckrichtung · gelber Punkt«."),
    Region("spi", "J11 · SPI zu ADC und DAC", "J11 · SPI", "Raspi", (420, 442, 524, 474),
           "Diese Anschlussgruppe führt zum Analogteil. Für den SPI-Bus werden Drähte zu J2 benötigt.",
           (("SCLK ↔ GP11", "GPIO11: Takt"), ("MOSI ↔ GP10", "GPIO10: Daten vom Pi"),
            ("MISO ↔ GP9", "GPIO9: Daten zum Pi"), ("CSA ↔ GP8", "GPIO8 / CE0: ADC auswählen"),
            ("CSB ↔ GP7", "GPIO7 / CE1: DAC auswählen")),
           "Mehrere SPI-Chips teilen Takt und Datenleitungen. Der jeweilige Chip-Select wählt das Ziel.",
           "Die Werkstatt zeigt die Anschlüsse; ADC/DAC werden hier noch nicht ausgelesen oder angesteuert."),
    Region("uart", "J64 · serielle Verbindung zum ATmega", "J64 · UART", "ATmega", (338, 442, 412, 474),
           "Zwei Leitungen für die Kommunikation zwischen Raspi und ATmega.",
           (("MCTX → GP15", "ATmega TX / PD1 → Pi RX / GPIO15"),
            ("MCRX ← GP14", "ATmega RX / PD0 ← Pi TX / GPIO14")),
           "Eine passende ATmega-Firmware kann hier Messwerte senden und Befehle empfangen.",
           "3,3-V-Logik-UART, kein RS-232-Anschluss. Beide Seiten brauchen passende Software und gemeinsame Masse.", "avr"),
    Region("adc", "J28 / U6 · analog messen", "J28 · ADC\nAD0 · AD1", "Analog", (28, 146, 108, 212),
           "Der MCP3002 wandelt zwei analoge Eingangsspannungen in digitale Messwerte um.",
           (("AD0", "Analogeingang 0"), ("AD1", "Analogeingang 1"),
            ("GND", "Bezug der Eingangsspannung"), ("J11 / CSA", "SPI-Verbindung zum Raspi")),
           "10 Bit ergeben Werte von 0 bis 1023. Mit der Boardversorgung liegt der Messbereich bei 0 bis 3,3 V gegen GND.",
           "Die Raspi-GPIOs selbst messen nur Logikpegel. Der ADC ergänzt die Analogmessung; keine 5 V an AD0/AD1.", "adc"),
    Region("dac", "J29 / U10 · analoge Spannung ausgeben", "J29 · DAC\nDA0 · DA1", "Analog", (28, 222, 108, 280),
           "Ein MCP48x2 setzt digitale Vorgaben in zwei analoge Ausgangsspannungen um.",
           (("DA0", "Analogausgang 0"), ("DA1", "Analogausgang 1"),
            ("GND", "Spannungsbezug"), ("J11 / CSB", "SPI-Steuerung vom Raspi")),
           "Für Sollwerte und Testspannungen. MCP4802/4812/4822 bieten je nach bestücktem Chip 8/10/12 Bit.",
           "Ausgangsbereich hängt von Chip, Verstärkung und Versorgung ab. Kein Leistungsausgang für einen Motor.", "dac"),
    Region("atmega", "J25 / U8 · eigener ATmega-Mikrocontroller", "J25 / U8\nATmega\nPB…\nPD…\nPC…", "ATmega", (28, 312, 164, 508),
           "Diese vielen Pins gehören zum ATmega328P auf dem Gertboard. Er kann ein eigenes Programm ausführen.",
           (("PB0–PB5", "Digitale Ports; PB3=MOSI, PB4=MISO, PB5=SCK"),
            ("PD0–PD7", "Digitale Ports; PD0=RX, PD1=TX"),
            ("PC0–PC5", "Digitale Ports oder ADC-Eingänge des ATmega"),
            ("GND", "Gemeinsame Masse")),
           "Eigene Firmware bestimmt Eingang, Ausgang, PWM oder Analogmessung. Damit entstehen zusätzliche I/Os des ATmega.",
           "PB5 ist weder Raspi-GPIO5 noch Buffer B5. Ein Klick in der GPIO-Werkstatt programmiert den ATmega nicht.", "avr"),
    Region("isp", "J23 · ATmega programmieren", "J23 · ISP", "ATmega", (112, 270, 164, 302),
           "Der sechspolige ISP-Anschluss dient zum Programmieren des ATmega.",
           (("MOSI / MISO / SCK", "Programmierdaten und Takt"),
            ("RESET", "ATmega für Programmierung zurücksetzen"),
            ("3V3 / GND", "Boardversorgung und Masse")),
           "Mit geeignetem 3,3-V-Programmieradapter und Firmware lässt sich der ATmega beschreiben.",
           "Signalnamen, keine Lage-Zeichnung der sechs Kontakte. Pin-1-Markierung und Adapterbelegung vor dem Anschließen prüfen.", "avr"),
    Region("clock", "J71 / X1 · Punkt neben dem Taktbauteil", "J71 · X1", "ATmega", (174, 350, 260, 382),
           "Auf deinem Foto liegt der einzelne Lötpunkt J71 neben X1.",
           (("J71", "Einzelner Prüf-/Lötpunkt"), ("X1", "Taktbauteil beim ATmega")),
           "Die genaue Verbindung von J71 ist ohne passenden Revisionsschaltplan hier nicht zugeordnet.",
           "Kein zusätzlicher Raspi-GPIO. Für normale Buffer-Experimente wird dieser Punkt nicht benötigt."),
    Region("motor_power", "J19 / U7 · Motor und Motorspeisung", "J19 · MOTOR\nGND · MOTA · MOTB · MOT+", "Leistung", (506, 56, 692, 130),
           "Die Schraubklemme gehört zur H-Brücke BD6222HFP, die auf deinem Foto bestückt ist.",
           (("GND", "Minus / gemeinsame Masse der Motorspeisung"),
            ("MOTA / MOTB", "Die beiden Motoranschlüsse, Leistungsausgänge"),
            ("MOT+", "Plus der separaten Motorspeisung")),
           "Der Treiber kann die Polarität am Gleichstrommotor wechseln. Die kleinen Steuersignale kommen über J5.",
           "ROHM nennt 6–15 V Betriebsspannung; 18 V ist der absolute Grenzwert, keine normale Betriebseinstellung. Motorstrom und Kühlung gesondert prüfen.", "motor"),
    Region("motor_logic", "J5 · Motor-Steuereingänge", "J5 · MOTA/B", "Leistung", (506, 394, 576, 432),
           "Die beiden kleinen Pins sind die Logikeingänge der Motorsteuerung.",
           (("MOTA", "Steuersignal A"), ("MOTB", "Steuersignal B")),
           "Die Kombination bestimmt Drehen, Bremsen oder Leerlauf; geeignete PWM kann die Geschwindigkeit steuern.",
           "Gleiche Signalnamen wie an J19, aber andere Aufgabe: J5 ist Logik; J19 ist Motorleistung. Kein Motor direkt an J5.", "motor"),
    Region("relay_logic", "J4 · sechs Lasttreiber-Eingänge", "J4 · RLY1–6", "Leistung", (584, 394, 692, 432),
           "J4 steuert sechs Kanäle des ULN2803A an.",
           tuple((f"RLY{n}", f"Logikeingang für Lasttreiber {n}") for n in range(1, 7)),
           "Ein HIGH am gewählten Eingang schaltet den zugehörigen Open-Collector-Ausgang nach Masse.",
           "Auf dem Board sind Transistortreiber, keine sechs fertigen Relais. J4 trägt keine Lastversorgung.", "relay"),
    Region("relay_power", "J12–J17 / U12 · Lastanschlüsse", "J12–J17\nRLY1–6\n+ RPWR", "Leistung", (600, 164, 692, 378),
           "Die Paare am rechten Rand sind die Lastseite des ULN2803A.",
           tuple((f"J{11+n}: RLY{n} + RPWR", f"Lastanschluss Kanal {n} und gemeinsames Versorgungsnetz") for n in range(1, 7)),
           "Der RLY-Ausgang zieht bei Aktivierung nach GND; er liefert selbst keine positive Spannung. RPWR ist die gemeinsame Lastversorgung / Rückführung der Schutzdioden.",
           "Externe Lastversorgung, Masse und zulässige Ströme müssen zum Aufbau passen. RPWR nicht mit einem Raspi-GPIO verbinden.", "relay"),
    Region("power", "Versorgung · J7, J8, J24 und 3V3/GND", "J7 · J8 · J24\n3V3 / 5V / GND", "Versorgung", (584, 446, 692, 514),
           "Versorgungspins sind feste Spannungen, keine schaltbaren GPIOs.",
           (("J7: obere zwei Kontakte", "Jumper zur Versorgung der Boardlogik"),
            ("J24: unterer Pin mit 5V", "5-V-Versorgung vom Raspi"),
            ("3V3 / GND", "Versorgung / Masse an entsprechend beschrifteten Punkten"),
            ("J8 / weitere Kontakte", "Hier keine ungeprüfte Brückenbelegung angegeben")),
           "Die Boardlogik arbeitet mit 3,3 V. Das Anschließen der GPIOs ersetzt den J7-Versorgungsjumper nicht.",
           "Nur eindeutig beschriftete Versorgungspunkte nutzen; nicht beliebige Nachbarpins kurzschließen. Motor und Lasten haben eigene Versorgungsanschlüsse."),
    Region("patch", "Lochraster · eigene kleine Schaltung", "LOCHRASTER\n3V3 / GND", "Versorgung", (506, 164, 584, 378),
           "Die freien Lötaugen sind Platz für zusätzliche Bauteile.",
           (("Lötaugen", "Eigene Verdrahtung und Bauteile"),
            ("3V3 / GND daneben", "Beschriftete Versorgungspunkte")),
           "Zum Beispiel für Widerstände oder eine kleine Sensorschaltung. Ein Lötauge ist nicht automatisch ein GPIO.",
           "Welche Pads zusammenhängen, vor dem Löten am stromlosen Board mit Durchgangsprüfung feststellen."),
    Region("optional", "Unbestückte Flächen · J9 / U2 / L1", "J9 / U2 / L1\nunbestückt", "Versorgung", (584, 530, 692, 568),
           "Auf deinem Foto sind in dieser Ecke große freie Pads und unbestückte Bauteilflächen.",
           (("J9 / U2 / L1", "Revisionsabhängige bzw. unbestückte Positionen"),),
           "Diese Ansicht ordnet den freien Flächen keine einsatzbereite Funktion zu.",
           "Kein zusätzlicher GPIO und keine Anleitung zur Nachbestückung. Dafür ist der genaue Schaltplan deiner Revision nötig."),
)
BY_KEY = {region.key: region for region in REGIONS}


class GertboardDiagram:
    """Clickable static board, oriented like the owner's landscape photograph."""
    WIDTH, HEIGHT = 720, 618

    def __init__(self, canvas, on_select):
        self.canvas, self.on_select = canvas, on_select
        self.selected, self.items = "", {}
        self._draw()
        canvas.bind("<Button-1>", self._click)
        self.select("overview")

    def text(self, x, y, value, size=9, fill="#effcf5", bold=False, anchor="center"):
        return self.canvas.create_text(x, y, text=tr(value), fill=fill, anchor=anchor,
                                       font=("DejaVu Sans", size, "bold" if bold else "normal"))

    def _draw(self):
        c = self.canvas
        c.configure(background="#f3f6fa", highlightthickness=0)
        self.text(360, 18, "Wie auf deinem Foto · Bauteilseite · J1 unten", 12, "#243348", True)
        c.create_rectangle(12, 38, 708, 584, fill="#1a6b53", outline="#0c4838", width=2)
        for x, y in ((26, 51), (695, 51), (26, 570), (695, 570)):
            c.create_oval(x-6, y-6, x+6, y+6, fill="#c9b775", outline="#e7dcae")
        self.text(214, 454, "Gertboard", 9, bold=True)
        self.text(214, 472, "21 Oct. 2012", 8)
        for region in REGIONS:
            x1, y1, x2, y2 = region.rect
            color = COLORS[region.domain]
            rect = c.create_rectangle(x1, y1, x2, y2, fill="#164a3c", outline=color, width=1)
            # Sparse contact marks convey headers; they are neutral, not live LEDs.
            if region.key == "leds":
                for n in range(12):
                    x = x1 + 19 + n*29.5
                    c.create_rectangle(x-3, y1+9, x+3, y1+15, fill="#cbbd83", outline="")
                    c.create_oval(x-3, y1+24, x+3, y1+30, fill="#b4c7be", outline="")
                    self.text(x, y1+41, str(n+1), 7)
                label = self.text((x1+x2)/2, y2-12, region.label, 9, color, True)
            elif region.key == "buttons":
                for x in (x1+26, (x1+x2)/2, x2-26):
                    c.create_oval(x-8, y1+7, x+8, y1+23, fill="#c2d2c9", outline="#789789")
                label = self.text((x1+x2)/2, y2-11, region.label, 8, color, True)
            elif region.key.startswith("buffer") and region.key[-1:] in ("1", "2", "3"):
                for n in range(4):
                    x = x1+24+n*(x2-x1-48)/3
                    for y in (y1+12, y2-12):
                        c.create_rectangle(x-5, y-2, x+5, y+2, fill="#cbbd83", outline="")
                c.create_rectangle(x1+9, y1+23, x2-9, y2-23, fill="#253b35", outline="#809c8e")
                label = self.text((x1+x2)/2, (y1+y2)/2, region.label, 8, color, True)
            elif region.key in ("gpio", "buffer_pi"):
                count = 17 if region.key == "gpio" else 12
                for n in range(count):
                    x = x1+12+n*(x2-x1-24)/(count-1)
                    c.create_rectangle(x-2, y1+6, x+2, y1+11, fill="#cbbd83", outline="")
                label = self.text((x1+x2)/2, y2-11, region.label, 9, color, True)
            elif region.key == "pi":
                for n in range(13):
                    x = x1+16+n*(x2-x1-32)/12
                    for y in (y1+20, y1+29):
                        c.create_rectangle(x-2, y-2, x+2, y+2, fill="#cbbd83", outline="")
                c.create_oval(x1+11, y1+24, x1+21, y1+34, outline="#facc15", width=2)
                label = self.text((x1+x2)/2, y1+7, region.label, 8, color, True)
            elif region.key == "motor_power":
                for n in range(4):
                    x=x1+26+n*(x2-x1-52)/3
                    c.create_oval(x-7,y1+10,x+7,y1+24,fill="#86a899",outline="#b4c7be")
                    c.create_line(x-4,y1+14,x+4,y1+20,fill="#253b35",width=2)
                label = self.text((x1+x2)/2, y2-22, region.label, 8, color, True)
            elif region.key == "patch":
                for row in range(10):
                    for col in range(3):
                        x,y=x1+14+col*24,y1+14+row*20
                        c.create_oval(x-3,y-3,x+3,y+3,fill="#205945",outline="#b3b88f")
                # An opaque small plate keeps the name legible over the pads.
                c.create_rectangle(x1+2,(y1+y2)/2-23,x2-2,(y1+y2)/2+23,fill="#164a3c",outline="")
                label = self.text((x1+x2)/2, (y1+y2)/2, region.label, 8, color, True)
            else:
                size = 7 if x2-x1 < 60 else 8 if x2-x1 < 110 else 9
                label = self.text((x1+x2)/2, (y1+y2)/2, region.label, size, color, True)
            self.items[region.key] = (rect, label)
        self.text(360, 601, "Bereich anklicken → Details rechts · schematisch, keine Live-Anzeige", 10, "#52647b")

    @staticmethod
    def region_at(x, y):
        for region in REGIONS:
            x1, y1, x2, y2 = region.rect
            if x1 <= x <= x2 and y1 <= y <= y2:
                return region.key
        return None

    def _click(self, event):
        key = self.region_at(event.x, event.y)
        if key:
            self.on_select(key)

    def select(self, key):
        if key not in BY_KEY:
            raise ValueError("Unbekannter Gertboard-Bereich: " + str(key))
        for region in REGIONS:
            rect, _ = self.items[region.key]
            chosen = region.key == key
            self.canvas.itemconfigure(rect, fill="#2a6050" if chosen else "#164a3c",
                                      outline="#fff0a3" if chosen else COLORS[region.domain],
                                      width=3 if chosen else 1)
        self.selected = key
