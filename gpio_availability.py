"""Read-only line ownership and the reasons a header pin cannot be selected."""

from gpio_i18n import tr

from dataclasses import dataclass
import fcntl
import os
from pathlib import Path
import struct

from gpio_core import HEADER_GPIO, HEADER_POWER, find_header_chip

RASPI_PROFILE = "Raspi 5 · 40-Pin-Header"
GERTBOARD_PROFILE = "Gertboard · 21.10.2012 · 26-polig"
# Original Gertboard User Manual rev. 2.0, GPIO table, printed page 11.
# The old GP0/GP1/GP21 silkscreen refers to the first Raspberry Pi revision.
GERTBOARD_LABELS = {gpio: f"GP{gpio}" for physical, gpio in HEADER_GPIO.items() if physical <= 26}
GERTBOARD_LABELS.update({2: "GP0", 3: "GP1", 27: "GP21"})


@dataclass(frozen=True)
class LineInfo:
    gpio: int
    name: str
    consumer: str
    used: bool


@dataclass(frozen=True)
class PinAccess:
    kind: str
    label: str
    reason: str

    @property
    def can_activate(self):
        return self.kind == "available"


def read_line_info(descriptor, gpio):
    """GPIO_V2_GET_LINEINFO_IOCTL reads metadata; it never requests a line.

    Linux's public 256-byte gpio_v2_line_info ABI: name[32], consumer[32],
    offset, num_attrs, flags, ten 16-byte attributes and four padding words.
    This provides ownership, not the electrical level.
    """
    data = bytearray(256)
    struct.pack_into("=I", data, 64, gpio)
    fcntl.ioctl(descriptor, 0xc100b405, data, True)
    name, consumer, offset, _, flags = struct.unpack_from("=32s32sIIQ", data)
    if offset != gpio:
        raise OSError(tr("GPIO-Metadaten enthalten einen unerwarteten Pin-Index."))
    return LineInfo(gpio, name.split(b"\0", 1)[0].decode(errors="replace"),
                    consumer.split(b"\0", 1)[0].decode(errors="replace"), bool(flags & 1))


def line_snapshot(chip=None, dev_root=Path("/dev")):
    """Read all header consumers through a temporary read-only chip handle."""
    lines, errors = {}, []
    try:
        if chip is None:
            chip = find_header_chip(dev_root=dev_root)
        descriptor = os.open(dev_root / f"gpiochip{chip}",
                             os.O_RDONLY | getattr(os, "O_CLOEXEC", 0))
        try:
            for gpio in range(28):
                try:
                    lines[gpio] = read_line_info(descriptor, gpio)
                except OSError as exc:
                    errors.append(f"GPIO{gpio}: {exc}")
        finally:
            os.close(descriptor)
    except (OSError, RuntimeError) as exc:
        errors.append(str(exc))
    return lines, (tr("Belegung nicht vollständig lesbar: ") + "; ".join(errors) if errors else "")


def pin_access(physical, states, lines, owned=(), gertboard=False):
    if gertboard and physical > 26:
        return PinAccess("unconnected", tr("nicht am Gertboard"),
                         tr('Stecker-Pin {v0} liegt außerhalb des 26-poligen Gertboard-Anschlusses. Er gehört weiterhin zum Raspi, ist über dieses Board aber nicht herausgeführt.', v0=physical))
    gpio = HEADER_GPIO.get(physical)
    if gpio is None:
        kind = HEADER_POWER[physical]
        explanation = (tr("Masseanschluss (GND)") if kind == "GND" else
                       tr("fest verdrahtete ") + (tr("3,3-V-Versorgung") if kind == "3V3" else tr("5-V-Versorgung")))
        return PinAccess("fixed", tr("fest"), explanation + tr(". Kein schaltbarer GPIO."))
    if gpio in (0, 1):
        return PinAccess("reserved", tr("reserviert"),
                         tr('GPIO{v0}: für die HAT-Erkennung (ID-EEPROM) reserviert. Die Werkstatt steuert diese beiden Pins nicht.', v0=gpio))
    if gpio in owned:
        return PinAccess("owned", tr("in dieser App"), tr('GPIO{v0}: durch diese Werkstatt aktiviert.', v0=gpio))
    state, line = states.get(gpio), lines.get(gpio)
    if state is not None and state.mode not in ("ip", "op", "no", "?"):
        owner = tr(" Benutzer: ") + line.consumer + "." if line and line.used and line.consumer else ""
        return PinAccess("bus", tr("Sonderfunktion"),
                         tr('GPIO{v0}: Sonderfunktion {v1} ist aktiv.', v0=gpio, v1=state.function or state.mode)
                         + owner + tr(" Die Werkstatt überschreibt sie nicht."))
    if line is not None and line.used:
        consumer = line.consumer or tr("Kernel/anderes Programm (ohne Benutzername)")
        return PinAccess("busy", tr("belegt"), tr('GPIO{v0}: belegt durch {v1}. Der Pin wird erst verfügbar, wenn dieser Benutzer ihn freigibt.', v0=gpio, v1=consumer))
    if line is None or state is None or state.mode == "?":
        return PinAccess("unknown", tr("ungeprüft"), tr('GPIO{v0}: aktuelle Belegung oder Pin-Funktion nicht lesbar. Es wird kein freier Pin angenommen.', v0=gpio))
    note = tr(" Fester Pull-Up: als Eingang nur mit Pull-Up verwenden.") if gpio in (2, 3) else ""
    return PinAccess("available", tr("verfügbar"), tr('GPIO{v0}: aktuell nicht belegt; beim Aktivieren wird erneut geprüft.', v0=gpio) + note)


def header_access(states, lines, owned=(), gertboard=False):
    return {physical: pin_access(physical, states, lines, owned, gertboard) for physical in range(1, 41)}
