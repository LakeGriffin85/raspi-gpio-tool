"""GPIO control with independent pin lifetimes and explicit activation."""

from gpio_i18n import tr

import re
import shutil
import subprocess
import logging
import fcntl
import os
import struct
from pathlib import Path
from dataclasses import dataclass

LOG = logging.getLogger("raspi_gpio")

PHYSICAL = {
    2: 3, 3: 5, 4: 7, 5: 29, 6: 31, 7: 26, 8: 24, 9: 21,
    10: 19, 11: 23, 12: 32, 13: 33, 14: 8, 15: 10, 16: 36,
    17: 11, 18: 12, 19: 35, 20: 38, 21: 40, 22: 15, 23: 16,
    24: 18, 25: 22, 26: 37, 27: 13,
}

HEADER_GPIO = {physical: gpio for gpio, physical in PHYSICAL.items()}
HEADER_GPIO.update({27: 0, 28: 1})
HEADER_POWER = {1: "3V3", 17: "3V3", 2: "5V", 4: "5V",
                6: "GND", 9: "GND", 14: "GND", 20: "GND",
                25: "GND", 30: "GND", 34: "GND", 39: "GND"}


@dataclass(frozen=True)
class PinState:
    gpio: int
    level: object
    mode: str
    pull: str
    function: str
    raw: str


def parse_board_snapshot(text):
    """Parse plain `pinctrl get`, without relying on fixed column widths."""
    states = {}
    for raw in text.splitlines():
        start = re.match(r"^\s*(\d+):\s*(.*)$", raw)
        if not start:
            continue
        gpio = int(start.group(1))
        if not 0 <= gpio <= 27:
            continue
        body = start.group(2)
        registers, _, comment = body.partition("//")
        level = re.search(r"\|\s*(hi|lo)\b", registers)
        mode = re.search(r"\b(ip|op|a\d+|no)\b", registers)
        pull = re.search(r"\b(pu|pd|pn)\b", registers)
        function = comment.rsplit("=", 1)[-1].strip() if "=" in comment else ""
        states[gpio] = PinState(
            gpio, None if not level else level.group(1) == "hi",
            mode.group(1) if mode else "?", pull.group(1) if pull else "?",
            function, raw.strip(),
        )
    return states


def board_snapshot():
    """One read-only command samples the 28 GPIOs on the 40-pin header."""
    command = shutil.which("pinctrl", path="/usr/bin:/usr/sbin:/bin:/sbin")
    if command is None:
        return {}, tr("pinctrl fehlt; Live-Übersicht nicht verfügbar.")
    try:
        result = subprocess.run(
            [command, "get", "0-27"], capture_output=True, text=True,
            timeout=1, check=True,
        )
        states = parse_board_snapshot(result.stdout)
        if not states:
            return {}, tr("pinctrl hat keine lesbaren GPIO-Zustände geliefert.")
        return states, "" if len(states) == 28 else tr('{v0}/28 GPIOs lesbar', v0=len(states))
    except (OSError, subprocess.SubprocessError) as exc:
        return {}, tr("Live-Übersicht nicht verfügbar: ") + str(exc)


def pin_snapshot(pin):
    """Read pinctrl's diagnostics; never change pin configuration."""
    command = shutil.which("pinctrl", path="/usr/bin:/usr/sbin:/bin:/sbin")
    if command is None:
        return None, tr("pinctrl fehlt; die Live-Anzeige ist erst nach Aktivierung verfügbar.")
    try:
        result = subprocess.run(
            [command, "get", str(pin)], capture_output=True, text=True,
            timeout=1, check=True,
        )
        raw = result.stdout.strip()
        match = re.search(r"\b(hi|lo)\b", raw)
        level = (match.group(1) == "hi") if match else None
        return level, raw or tr("Keine Pin-Diagnose verfügbar.")
    except (OSError, subprocess.SubprocessError) as exc:
        return None, tr("Pin-Diagnose nicht verfügbar: ") + str(exc)


def read_chip_info(path):
    """Read Linux GPIO chip metadata without requesting or changing any line."""
    # GPIO_GET_CHIPINFO_IOCTL from Linux's public <linux/gpio.h> ABI:
    # struct gpiochip_info { char name[32]; char label[32]; __u32 lines; }.
    data = bytearray(struct.calcsize("=32s32sI"))
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0))
    try:
        fcntl.ioctl(descriptor, 0x8044B401, data, True)
    finally:
        os.close(descriptor)
    name, label, lines = struct.unpack("=32s32sI", data)
    return (name.split(b"\0", 1)[0].decode(errors="replace"),
            label.split(b"\0", 1)[0].decode(errors="replace"), lines)


def find_header_chip(sys_root=Path("/sys/bus/gpio/devices"), dev_root=Path("/dev")):
    """Identify the RP1 by its /dev metadata; sysfs is only a fallback."""
    found = []
    errors = []
    for device in sorted(dev_root.glob("gpiochip*")):
        match = re.fullmatch(r"gpiochip(\d+)", device.name)
        if not match:
            continue
        try:
            name, label, lines = read_chip_info(device)
        except OSError as exc:
            errors.append(f"{device.name}: {exc}")
            continue
        found.append((device.name, label, lines))
        if label == "pinctrl-rp1" and lines >= 28:
            LOG.info("Header-Controller: %s [%s], %s GPIOs", device.name, label, lines)
            return int(match.group(1))
    roots = [sys_root]
    if sys_root == Path("/sys/bus/gpio/devices"):
        roots.insert(0, Path("/sys/class/gpio"))
    for root in roots:
        for directory in sorted(root.glob("gpiochip*")):
            match = re.fullmatch(r"gpiochip(\d+)", directory.name)
            if not match or not (dev_root / directory.name).exists():
                continue
            try:
                label = (directory / "label").read_text().strip()
            except OSError:
                continue
            found.append((directory.name, label))
            if label == "pinctrl-rp1":
                LOG.info("Header-Controller (sysfs): %s [%s]", directory.name, label)
                return int(match.group(1))
    raise RuntimeError(tr("RP1-GPIO-Controller nicht gefunden. Erkannte Controller: ") + repr(found) +
                       (tr(". Gerätefehler: ") + "; ".join(errors) if errors else ""))


def create_lgpio_factory():
    from gpiozero.pins.lgpio import LGPIOFactory
    return LGPIOFactory(chip=find_header_chip())


class GPIOController:
    def __init__(self, factory=None, factory_builder=None):
        self.factory = factory
        self._owns_factory = factory is None
        self._factory_builder = factory_builder or create_lgpio_factory
        self._hardware_checks = factory is None and factory_builder is None
        self.device = None
        self.pin = None
        self.mode = None
        self.pull = None

    def activate(self, pin, mode, pull="none"):
        if self.device is not None:
            raise RuntimeError(tr("Zuerst den aktiven Pin freigeben."))
        if pin not in PHYSICAL:
            raise ValueError(tr("GPIO0/1 sowie Strom- und Massepins sind nicht auswählbar."))
        if mode not in ("input", "output"):
            raise ValueError(tr("Unbekannter Betriebsmodus."))
        if pull not in ("none", "up", "down"):
            raise ValueError(tr("Unbekannte Pull-Konfiguration."))

        if self._hardware_checks:
            states, warning = board_snapshot()
            state = states.get(pin)
            if state is None:
                raise RuntimeError(tr("Pin-Konfiguration konnte nicht geprüft werden: ") + warning)
            if state.mode not in ("ip", "op", "no"):
                raise RuntimeError(tr('GPIO{v0} ist als {v1} konfiguriert. Die aktive Sonderfunktion wird nicht überschrieben.', v0=pin, v1=state.function or state.mode))
            from gpio_availability import line_snapshot, pin_access
            lines, warning = line_snapshot()
            access = pin_access(PHYSICAL[pin], states, lines)
            if not access.can_activate:
                raise RuntimeError(access.reason + (" " + warning if warning else ""))
        if pin in (2, 3) and mode == "input" and pull != "up":
            raise ValueError(tr('GPIO{v0} hat einen festen Pull-Up; dafür Pull-Up wählen.', v0=pin))

        from gpiozero import InputDevice, DigitalOutputDevice

        if self.factory is None:
            self.factory = self._factory_builder()

        LOG.info("Aktivieren: GPIO%s mode=%s pull=%s", pin, mode, pull)
        try:
            if mode == "output":
                device = DigitalOutputDevice(
                    pin, active_high=True, initial_value=False, pin_factory=self.factory,
                )
            else:
                # Level polling needs no edge notifications or native alert threads.
                device = InputDevice(
                    pin, pull_up={"none": None, "up": True, "down": False}[pull],
                    active_state=True if pull == "none" else None,
                    pin_factory=self.factory,
                )
        except Exception:
            LOG.exception("Aktivieren fehlgeschlagen: GPIO%s", pin)
            try:
                self._close_owned_factory()
            except Exception:
                LOG.exception("Controller-Bereinigung nach Aktivierungsfehler fehlgeschlagen")
            raise
        self.device, self.pin, self.mode = device, pin, mode
        self.pull = pull

    @property
    def level(self):
        if self.device is None:
            return None
        return bool(self.device.pin.state)

    def write(self, high):
        if self.device is None or self.mode != "output":
            raise RuntimeError(tr("Zuerst einen Ausgang aktivieren."))
        self.device.value = bool(high)

    def release(self):
        device, mode = self.device, self.mode
        try:
            if device is not None:
                try:
                    if mode == "output":
                        device.off()
                finally:
                    device.close()
        finally:
            self.device = self.pin = self.mode = self.pull = None
            # LGPIOPin.close only resets to input. Closing our factory releases
            # the actual kernel line requests as well.
            self._close_owned_factory()

    def _close_owned_factory(self):
        if self._owns_factory and self.factory is not None:
            factory, self.factory = self.factory, None
            try:
                factory.close()
            except Exception:
                # Some lgpio errors occur while resetting a pin in close(),
                # before LGPIOFactory reaches gpiochip_close. Still close the
                # chip handle so failed cleanup does not retain kernel claims.
                if type(factory).__module__ == "gpiozero.pins.lgpio":
                    handle = getattr(factory, "_handle", None)
                    if handle is not None:
                        try:
                            import lgpio
                            lgpio.gpiochip_close(handle)
                            factory._handle = None
                        except Exception:
                            LOG.exception("Auch direkte Controller-Freigabe fehlgeschlagen")
                raise

    def close(self):
        try:
            self.release()
        finally:
            if self.factory is not None:
                self.factory.close()
                self.factory = None


class MultiGPIOController:
    """One controller/factory per pin, so releasing one never resets another.

    A shared injected factory is used only for tests/demo. Hardware factories
    are separate and their kernel claims end when the individual pin closes.
    """
    def __init__(self, factory=None, factory_builder=None):
        self.channels = {}
        self._factory = factory
        self._factory_builder = factory_builder

    def activate(self, pin, mode, pull="none"):
        if pin in self.channels:
            raise RuntimeError(tr('GPIO{v0} ist in dieser Werkstatt bereits aktiv.', v0=pin))
        channel = GPIOController(self._factory, self._factory_builder)
        channel.activate(pin, mode, pull)
        self.channels[pin] = channel

    def write(self, pin, high):
        if pin not in self.channels:
            raise RuntimeError(tr('GPIO{v0} ist nicht aktiviert.', v0=pin))
        self.channels[pin].write(high)

    def release(self, pin):
        channel = self.channels.pop(pin, None)
        if channel is not None:
            channel.release()

    def release_all(self):
        errors = []
        for pin in list(self.channels):
            try:
                self.release(pin)
            except Exception as exc:
                LOG.exception("GPIO%s konnte nicht vollständig freigegeben werden", pin)
                errors.append(f"GPIO{pin}: {exc}")
        if errors:
            raise RuntimeError("; ".join(errors))

    def close(self):
        try:
            self.release_all()
        finally:
            if self._factory is not None:
                self._factory.close()
                self._factory = None
