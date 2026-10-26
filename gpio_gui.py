#!/usr/bin/python3
"""GPIO-Werkstatt: live header, pin ownership and independent active GPIOs."""

import argparse
from datetime import datetime
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import time

from guizero import App, Box, Drawing, PushButton, Text, TextBox, Window
from gpio_choices import Choice as Combo, close_choices, set_enabled
from gpio_core import MultiGPIOController, PHYSICAL, HEADER_GPIO, PinState, board_snapshot, read_chip_info
from gpio_availability import (LineInfo, header_access, line_snapshot, GERTBOARD_LABELS,
                               RASPI_PROFILE, GERTBOARD_PROFILE)
from gpio_header import HeaderDiagram
from gpio_orientation import OrientationDiagram
from gpio_support import configure_logging, friendly_error
from gpio_i18n import set_language, tr
from gpio_settings import Settings, load_settings, save_settings

GERTBOARD_TESTS = {
    "LED1 testen": """LED1 prüfen: GPIO17 → B1

1. Raspi herunterfahren, alle Speisungen trennen.
2. J7: obere zwei Pins verbinden (Handbuch Abb. 7).
3. Draht von J2 «GP17» zu J3 «B1» legen.
4. Jumper «B1 out» oberhalb U3 setzen; «B1 in» offen lassen.
5. Starten. App: GPIO17, Ausgang (Start LOW), Pin aktivieren.
6. HIGH: LED D1 an. LOW: LED D1 aus. S1 dabei nicht drücken.

Bleibt D1 aus: Pin freigeben, stromlos J7, Draht und OUT-Jumper prüfen.
Ein HIGH in der App bestätigt allein den Raspi-Pegel.""",
    "Taster S1 testen": """Taster S1 prüfen: GPIO17 → B1

1. Pin freigeben, Raspi herunterfahren, alle Speisungen trennen.
2. Draht GP17 → B1 bleibt; beide B1-IN/OUT-Jumper offen lassen.
   J7 wie beim LED-Test.
3. Starten. App: GPIO17, Eingang, Pull-Up, Pin aktivieren.
4. S1 losgelassen: HIGH. S1 2 Sekunden gedrückt halten: LOW.

Ohne OUT-Brücke kann LED D1 unabhängig vom App-Wert weiter leuchten.
Soll D1 folgen: stromlos nur das B1-OUT-Paar oberhalb U3 mit einem
Steckbrücke oder F-F-Kabel verbinden; B1 IN offen lassen.
GPIO17 bleibt Eingang mit Pull-Up. Losgelassen: D1 an; gedrückt: D1 aus.

Hier GPIO17 verwenden; die alten GP0/GP1 haben feste Pull-Ups.
Die App erkennt die Jumper und Drähte nicht automatisch.""",
}


def main():
    settings = load_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help=tr("Nur simulierte Pins benutzen"))
    parser.add_argument("--language", choices=("de", "en"), default=settings.language)
    board = parser.add_mutually_exclusive_group()
    board.add_argument("--gertboard", dest="gertboard", action="store_true")
    board.add_argument("--no-gertboard", dest="gertboard", action="store_false")
    parser.set_defaults(gertboard=settings.gertboard and gertboard_available())
    args = parser.parse_args()
    if args.gertboard and not gertboard_available():
        parser.error("Gertboard module is not installed; use --no-gertboard.")
    logger, log_path = configure_logging()
    while True:
        set_language(args.language)
        next_settings = run_app(args, logger, log_path)
        if next_settings is None:
            return 0
        args.language, args.gertboard = next_settings.language, next_settings.gertboard


def gertboard_available():
    return Path(__file__).with_name("gpio_gertboard.py").is_file()


def run_app(args, logger, log_path):
    # The normal GPIO app works even when the optional atlas module is absent.
    if args.gertboard:
        from gpio_gertboard import GertboardDiagram, REGIONS, BY_KEY, SOURCES
    gertboard_tests = {tr(name): tr(body) for name, body in GERTBOARD_TESTS.items()}

    app = App(title=tr("GPIO-Werkstatt · Live 2.7.0") + (" · DEMO" if args.demo else ""),
              width=1180, height=900, bg="#f3f6fa")
    app.text_color, app.font, app.text_size = "#243348", "DejaVu Sans", 11

    cache = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "raspi-gpio"
    cache.mkdir(parents=True, exist_ok=True)
    lock = (cache / ("demo.lock" if args.demo else "hardware.lock")).open("a+")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        app.info(tr("Bereits geöffnet"), tr("Die GPIO-Werkstatt ist schon geöffnet."))
        app.destroy()
        lock.close()
        return None

    factory = None
    if args.demo:
        from gpiozero.pins.mock import MockFactory
        factory = MockFactory()
    controller = MultiGPIOController(factory=factory)
    ui = {"changing": False, "refreshing": False, "closing": False, "access": {}}

    Text(app, text=tr("GPIO-Werkstatt"), size=23, bold=True, color="#136b69")
    Text(app, text=tr("Live-Header · mehrere Pins gleichzeitig · Aktualisierung jede Sekunde"), size=11)
    if args.demo:
        Text(app, text=tr("DEMO: simulierte Zustände, kein Zugriff auf echte GPIOs."),
             color="#8a4800", bold=True, size=10)
    else:
        Text(app, text=tr("Die Übersicht liest nur. Konfiguriert wird erst mit »Pin aktivieren«."),
             color="#52647b", size=10)

    settings_row = Box(app)
    profile_row = Box(app)
    raspi_profile, gertboard_profile = tr(RASPI_PROFILE), tr(GERTBOARD_PROFILE)
    profile = Combo(profile_row, options=[raspi_profile, gertboard_profile] if args.gertboard else [raspi_profile], align="left", width=34,
                    title=tr("Ansicht auswählen"))

    def show_settings():
        if controller.channels or ui["changing"] or ui["closing"]:
            return
        if "settings_choice" not in ui:
            choices = {
                "Deutsch · GPIO": Settings("de", False),
                "Deutsch · GPIO + Gertboard": Settings("de", True),
                "English · GPIO": Settings("en", False),
                "English · GPIO + Gertboard": Settings("en", True),
            }
            if not gertboard_available():
                choices = {label: value for label, value in choices.items() if not value.gertboard}
            current = Settings(args.language, args.gertboard)
            choice = Combo(app, options=list(choices),
                           selected=next(label for label, value in choices.items() if value == current),
                           title="Sprache & Module / Language & modules")
            # Choice owns a normal button; this one is only a reusable dialog.
            choice._button.visible = False

            def apply_settings():
                if controller.channels or ui["changing"] or ui["closing"]:
                    return
                selected = choices[choice.value]
                try:
                    save_settings(selected)
                except OSError as exc:
                    show_error(exc)
                    return
                ui["next_settings"] = selected
                close_choices()
                app.destroy()

            choice.update_command(apply_settings)
            ui["settings_choice"] = choice
            ui["settings_options"] = choices
        current = Settings(args.language, args.gertboard)
        ui["settings_choice"].value = next(label for label, value in ui["settings_options"].items()
                                           if value == current)
        ui["settings_choice"].open()

    settings_button = PushButton(settings_row, text="Sprache & Module / Language & modules",
                                 align="left", command=show_settings, pady=5)

    def show_orientation():
        if ui["changing"] or ui["closing"]:
            return
        if "orientation" not in ui:
            window = Window(app, title=tr("Steckrichtung · dein gelber Punkt bei Pin 1"),
                            width=920, height=610, bg="#f3f6fa", visible=False)
            orientation = Drawing(window, width=OrientationDiagram.WIDTH,
                                  height=OrientationDiagram.HEIGHT)
            OrientationDiagram(orientation.tk)
            PushButton(window, text=tr("Schließen"), command=window.hide, pady=5)
            ui["orientation"] = window
        ui["orientation"].show()

    PushButton(profile_row, text=tr("Steckrichtung · gelber Punkt"), align="left", command=show_orientation, pady=5)

    def show_gertboard_overview():
        if ui["changing"] or ui["closing"]:
            return
        if "gertboard_overview" not in ui:
            window = Window(app, title=tr("Gertboard · Anschlüsse entdecken · 21.10.2012"),
                            width=1190, height=760, bg="#f3f6fa", visible=False)
            Text(window, text=tr("Dein Gertboard · Anschlüsse entdecken"), size=19, bold=True, color="#136b69")
            Text(window, text=tr("Region anklicken oder rechts auswählen · Beschriftung und Wirkung nachschlagen"), size=10)
            content = Box(window, layout="grid")
            board = Drawing(content, width=GertboardDiagram.WIDTH, height=GertboardDiagram.HEIGHT,
                            grid=[0, 0], align="top")
            details = Box(content, grid=[1, 0], align="top")
            options = {tr(region.title): region.key for region in REGIONS}
            choice = Combo(details, options=list(options), width=42, title=tr("Gertboard-Bereich auswählen"))
            domain = Text(details, text="", size=10, color="#136b69", bold=True, width=47, height=2)
            description = TextBox(details, text="", width=47, height=27,
                                  multiline=True, scrollbar=True, enabled=False)
            description.text_size = 10
            description.tk.configure(background="#ffffff", foreground="#243348",
                                     padx=10, pady=10, spacing3=4, relief="flat", borderwidth=1)
            diagram = GertboardDiagram(board.tk, lambda key: select_region(key))

            def select_region(key):
                region = BY_KEY[key]
                # Programmatic selection does not execute the change callback.
                choice.value = tr(region.title)
                domain.value = tr(region.domain) + " · " + tr(region.title)
                description.value = region.details()
                description.tk.yview_moveto(0)
                diagram.select(key)

            choice.update_command(lambda: select_region(options[choice.value]))
            select_region("overview")

            def show_sources():
                key = options[choice.value]
                source = SOURCES[BY_KEY[key].source]
                app.info(tr("Quelle · ") + tr(source[0]), source[1] + "\n\n" + tr(
                         "Weitere Grundlage: Boardfoto, Aufdruck 21 Oct. 2012.\n"
                         "Die Grafik ist eine schematische Orientierungshilfe. "
                         "Jumper, Drähte, Pegel und Bauteilvarianten werden nicht automatisch erkannt."))

            PushButton(details, text=tr("Quelle zum Bereich"), command=show_sources, pady=5)
            PushButton(window, text=tr("Schließen"), command=window.hide, pady=5)
            ui["gertboard_overview"] = window
        ui["gertboard_overview"].show()

    if args.gertboard:
        PushButton(profile_row, text=tr("Gertboard-Übersicht"), align="left", command=show_gertboard_overview, pady=5)

    def show_gertboard_test():
        if ui["changing"] or ui["closing"]:
            return
        if "gertboard_test" not in ui:
            window = Window(app, title=tr("Gertboard · erster Funktionstest"),
                            width=800, height=590, bg="#f3f6fa", visible=False)
            Text(window, text=tr("Gertboard: LED und Taster prüfen"), size=17, bold=True)
            Text(window, text=tr("Anleitung · führt keine Pin-Aktion aus"), size=10, color="#52647b")
            choice = Combo(window, options=list(gertboard_tests), width=25, title=tr("Funktionstest auswählen"))
            instructions = TextBox(window, text=gertboard_tests[choice.value], width=82, height=20,
                                   multiline=True, scrollbar=True, enabled=False)
            instructions.text_size = 10
            instructions.tk.configure(padx=10, pady=8, background="#ffffff", relief="flat")
            choice.update_command(lambda: setattr(instructions, "value", gertboard_tests[choice.value]))
            Text(window, text=tr("Handbuch: Abb. 7 und Kapitel ‚Buffered I/O, LEDs, and Pushbuttons‘"), size=9)
            PushButton(window, text=tr("Schließen"), command=window.hide, pady=5)
            ui["gertboard_test"] = window
        ui["gertboard_test"].show()

    if args.gertboard:
        PushButton(profile_row, text=tr("Gertboard-Test"), align="left", command=show_gertboard_test, pady=5)
        PushButton(profile_row, text=tr("Gertboard-Hinweise"), align="left", command=lambda: app.info(
        tr("Gertboard · 21.10.2012"),
        tr("26-poliger Anschluss J1, 17 GPIO-Signale an J2.\n"
        "Alte Board-Beschriftung am Pi 5: GP0 = GPIO2, GP1 = GPIO3, GP21 = GPIO27.\n\n"
        "B1–B12 sind Buffer-Kanäle, keine festen GPIO-Nummern. Ihre Zuordnung hängt von deinen Drähten ab. "
        "Auch die IN/OUT-Jumper müssen zur gewählten Richtung passen; die App erkennt diese nicht.\n\n"
        "ADC, DAC, Motorsteuerung und ATmega werden von dieser Version noch nicht bedient. "
        "Die alten C-Beispiele greifen direkt auf den BCM2835 zu und sind kein Pi-5-Treiber.\n\n"
        "Die Profilwahl ändert keine elektrische Verbindung oder System-Schnittstelle. "
        "Anschluss und Ausrichtung müssen vorher zum 26-poligen J1 passen.\n"
        "Handbuch: https://www.farnell.com/datasheets/1683444.pdf")), pady=5)

    body = Box(app, layout="grid")
    drawing = Drawing(body, width=HeaderDiagram.WIDTH, height=HeaderDiagram.HEIGHT, grid=[0, 0], align="top")
    panel = Box(body, grid=[1, 0], align="top")
    Text(panel, text=tr("Pin bedienen"), size=17, bold=True)
    Text(panel, text=tr("GPIO in der Grafik anklicken oder hier auswählen."), size=10)
    labels = {tr('GPIO{v0}  ·  physischer Pin {v1}', v0=pin, v1=physical): pin
              for pin, physical in sorted(PHYSICAL.items())}
    picker = Box(panel, layout="grid", border=1)
    Text(picker, text="GPIO", grid=[0, 0], align="left", size=10)
    selection = Combo(picker, options=list(labels),
                      selected=tr("GPIO17  ·  physischer Pin 11"), grid=[1, 0], width=31,
                      title=tr("GPIO auswählen"))
    Text(picker, text=tr("Modus"), grid=[0, 1], align="left", size=10)
    mode = Combo(picker, options=[tr("Eingang"), tr("Ausgang (Start LOW)")], grid=[1, 1], width=31,
                 title=tr("Eingang oder Ausgang auswählen"))
    Text(picker, text="Pull", grid=[0, 2], align="left", size=10)
    pull = Combo(picker, options=[tr("Ohne Pull"), "Pull-Up", "Pull-Down"],
                 selected="Pull-Up", grid=[1, 2], width=31, title=tr("Pull-Widerstand auswählen"))

    physical_text = Text(panel, text="", size=11, width=49)
    level_text = Text(panel, text="—", size=28, bold=True, color="#64748b")
    live_status = Text(panel, text=tr("Lese GPIOs…"), size=9, color="#52647b", width=50, height=2)
    detail_text = Text(panel, text="", size=9, font="DejaVu Sans Mono", width=49, height=2)
    access_text = Text(panel, text="", size=10, width=49, height=3)
    state_text = Text(panel, text=tr("Nur Anzeige · kein Pin durch diese App belegt"), size=10, width=49, height=2)
    error_text = Text(panel, text="", color="#a33131", width=49, height=3, size=10)
    buttons = Box(panel, layout="grid")

    def show_error(exc):
        if isinstance(exc, BaseException):
            logger.error("GPIO-/GUI-Aktion fehlgeschlagen", exc_info=(type(exc), exc, exc.__traceback__))
            message = friendly_error(exc, labels.get(selection.value))
        else:
            message = str(exc)
        error_text.value = textwrap.fill(message, 48)

    def callback_error(kind, exc, trace):
        logger.error("Tk-Callback fehlgeschlagen", exc_info=(kind, exc, trace))
        if not ui["closing"]:
            error_text.value = tr("GUI-Fehler abgefangen. Details im Fehlerprotokoll.")

    app.tk.report_callback_exception = callback_error

    def select_from_diagram(pin):
        if ui["changing"] or ui["closing"]:
            return
        selection.value = next(label for label, gpio in labels.items() if gpio == pin)
        selection_changed()

    def selection_changed():
        if ui["changing"] or ui["closing"]:
            return
        channel = controller.channels.get(labels[selection.value])
        if channel is not None:
            mode.value = tr("Ausgang (Start LOW)") if channel.mode == "output" else tr("Eingang")
            pull.value = {"none": tr("Ohne Pull"), "up": "Pull-Up", "down": "Pull-Down"}[channel.pull]
        error_text.value = ""
        refresh()

    def profile_changed():
        # Never hide an active pin by changing the board view.
        if controller.channels:
            profile.value = ui.get("profile", raspi_profile)
            show_error(tr("Vor dem Ansichtswechsel zuerst alle aktiven Pins freigeben."))
            return
        ui["profile"] = profile.value
        previous = selection.value
        allowed = [label for label, gpio in labels.items()
                   if profile.value != gertboard_profile or gpio in GERTBOARD_LABELS]
        selection.clear()
        for label in allowed:
            selection.append(label)
        selection.value = previous if previous in allowed else tr("GPIO17  ·  physischer Pin 11")
        error_text.value = ""
        refresh()

    def inspect_pin(physical):
        if ui["changing"] or ui["closing"]:
            return
        pin = HEADER_GPIO.get(physical)
        if pin in PHYSICAL:
            select_from_diagram(pin)
            return
        availability = ui["access"].get(physical)
        if availability is not None:
            ui["changing"] = True
            sync_controls()
            try:
                app.info(tr('Stecker-Pin {v0}', v0=physical), availability.reason)
            finally:
                ui["changing"] = False
                sync_controls()

    diagram = HeaderDiagram(drawing.tk, select_from_diagram, inspect_pin)

    def demo_snapshot():
        tick = int(time.monotonic())
        states = {pin: PinState(pin, bool((tick + pin) % 4 < 2),
                              "ip" if pin % 2 else "op", "pu" if pin % 2 else "pn",
                              "input" if pin % 2 else "output", tr("Simulierter Pin"))
                for pin in range(28)}
        states[2] = PinState(2, True, "a3", "pu", "SDA1", tr("DEMO: I²C-Sonderfunktion"))
        states[3] = PinState(3, True, "a3", "pu", "SCL1", tr("DEMO: I²C-Sonderfunktion"))
        return states

    def refresh_data():
        pin = labels[selection.value]
        gertboard = profile.value == gertboard_profile
        board_name = (GERTBOARD_LABELS.get(pin, tr("nicht an J2")) + " → ") if gertboard else ""
        physical_text.value = board_name + tr('GPIO{v0} → Stecker-Pin {v1}', v0=pin, v1=PHYSICAL[pin])
        states, warning = (demo_snapshot(), "") if args.demo else board_snapshot()
        if args.demo:
            lines = {gpio: LineInfo(gpio, f"GPIO{gpio}", "w1-demo" if gpio == 4 else "", gpio == 4)
                     for gpio in range(28)}
            line_warning = ""
        else:
            lines, line_warning = line_snapshot()
        for active_pin, channel in list(controller.channels.items()):
            try:
                if args.demo and channel.mode == "input":
                    if int(time.monotonic()) % 2:
                        channel.device.pin.drive_high()
                    else:
                        channel.device.pin.drive_low()
                states[active_pin] = PinState(active_pin, channel.level,
                                             "op" if channel.mode == "output" else "ip",
                                             {"none": "pn", "up": "pu", "down": "pd"}[channel.pull],
                                             channel.mode,
                                             tr('GPIO{v0}: in dieser App als {v1} aktiviert', v0=active_pin, v1=channel.mode))
            except Exception as exc:
                show_error(exc)
        ui["access"] = header_access(states, lines, controller.channels, gertboard)
        availability = ui["access"][PHYSICAL[pin]]
        access_text.value = textwrap.fill(availability.reason, 48)
        access_text.text_color = {"busy": "#a33131", "bus": "#996000", "reserved": "#8b5cf6",
                                  "owned": "#0f8a8a", "available": "#136b69"}.get(availability.kind, "#52647b")
        state = states.get(pin)
        value = None if state is None else state.level
        level_text.value = "HIGH · 1" if value is True else "LOW · 0" if value is False else "—"
        level_text.text_color = "#169b62" if value is True else "#475569"
        detail_text.value = textwrap.fill(state.raw if state else tr("Für diesen Pin ist kein Live-Wert verfügbar."), 48)
        if warning or line_warning:
            live_status.value = textwrap.fill((warning or line_warning)[:94], 49)
            live_status.text_color = "#a33131"
        else:
            prefix = "DEMO" if args.demo else "LIVE"
            count = sum(gpio in states for gpio in GERTBOARD_LABELS) if gertboard else len(states)
            target = "Gertboard" if gertboard else "Raspi"
            total = 17 if gertboard else 28
            live_status.value = f"{prefix} · {target} {count}/{total} GPIOs · {datetime.now():%H:%M:%S} · 1 s"
            live_status.text_color = "#136b69"
        diagram.update(states, pin, ui["access"], gertboard)
        sync_controls()

    def refresh():
        if ui["changing"] or ui["refreshing"] or ui["closing"]:
            return
        ui["refreshing"] = True
        try:
            refresh_data()
        except Exception as exc:
            show_error(exc)
        finally:
            ui["refreshing"] = False

    def sync_controls():
        pin = labels[selection.value]
        channel = controller.channels.get(pin)
        active = channel is not None
        availability = ui["access"].get(PHYSICAL[pin])
        set_enabled(selection, not ui["changing"])
        set_enabled(profile, not controller.channels and not ui["changing"])
        set_enabled(settings_button, not controller.channels and not ui["changing"])
        if "settings_choice" in ui:
            set_enabled(ui["settings_choice"], not controller.channels and not ui["changing"])
        for widget in (mode, pull):
            set_enabled(widget, not active and not ui["changing"])
        set_enabled(activate_button, not active and not ui["changing"] and availability is not None
                    and availability.can_activate)
        set_enabled(release_button, active and not ui["changing"])
        for widget in (low_button, high_button):
            set_enabled(widget, active and channel.mode == "output" and not ui["changing"])
        set_enabled(release_all_button, bool(controller.channels) and not ui["changing"])
        active_labels = [f"{gpio} ({'OUT' if entry.mode == 'output' else 'IN'})"
                         for gpio, entry in sorted(controller.channels.items())]
        shown = ", ".join(active_labels[:6]) + (tr(' + {v0} weitere', v0=len(active_labels) - 6) if len(active_labels) > 6 else "")
        state_text.value = textwrap.fill(tr('{v0} aktiv · GPIO ', v0=len(active_labels)) + shown, 48) if active_labels else tr("Nur Anzeige · kein Pin durch diese App belegt")

    def activate():
        if ui["changing"] or ui["closing"]:
            return
        pin = labels[selection.value]
        refresh()
        availability = ui["access"].get(PHYSICAL[pin])
        if availability is None or not availability.can_activate:
            show_error(availability.reason if availability else tr("Pin-Belegung noch nicht geprüft."))
            return
        output = mode.value == tr("Ausgang (Start LOW)")
        text = (tr('GPIO{v0} (physischer Pin {v1}) wird als Ausgang konfiguriert.\nEr startet sofort mit LOW (0). Nur für eine dafür geeignete Schaltung.\n\nIst dieser Pin frei und entsprechend beschaltet?', v0=pin, v1=PHYSICAL[pin]) if output else
                tr('GPIO{v0} (physischer Pin {v1}) wird als Eingang konfiguriert.\nPull-Einstellung: {v2}.\n\nIst dieser Pin frei und als Eingang beschaltet?', v0=pin, v1=PHYSICAL[pin], v2=pull.value))
        ui["changing"] = True
        sync_controls()
        try:
            if not app.yesno(tr("Pin konfigurieren"), text):
                return
            error_text.value = ""
            controller.activate(pin, "output" if output else "input",
                                {tr("Ohne Pull"): "none", "Pull-Up": "up", "Pull-Down": "down"}[pull.value])
        except Exception as exc:
            show_error(exc)
        finally:
            ui["changing"] = False
            sync_controls()
            refresh()

    def release():
        if ui["changing"] or ui["closing"]:
            return
        ui["changing"] = True
        sync_controls()
        try:
            error_text.value = ""
            controller.release(labels[selection.value])
        except Exception as exc:
            show_error(exc)
        finally:
            ui["changing"] = False
            sync_controls()
            refresh()

    def write(high):
        if ui["changing"] or ui["closing"]:
            return
        ui["changing"] = True
        sync_controls()
        try:
            controller.write(labels[selection.value], high)
            error_text.value = ""
        except Exception as exc:
            show_error(exc)
        finally:
            ui["changing"] = False
            sync_controls()
            refresh()

    def release_all():
        if ui["changing"] or ui["closing"]:
            return
        ui["changing"] = True
        sync_controls()
        try:
            error_text.value = ""
            controller.release_all()
        except Exception as exc:
            show_error(exc)
        finally:
            ui["changing"] = False
            sync_controls()
            refresh()

    def show_pinout():
        try:
            subprocess.Popen(["lxterminal", "-e", str(Path(__file__).with_name("gpio-terminal.sh"))])
        except OSError as exc:
            app.error(tr("Terminal konnte nicht starten"), str(exc))

    def show_diagnostics():
        try:
            states, warning = board_snapshot() if not args.demo else ({}, "DEMO")
            logger.info("Diagnose: %s", warning or "Pin-Anzeige lesbar")
            for state in states.values():
                logger.info("Pin-Diagnose: %s", state.raw)
            lines, line_warning = line_snapshot() if not args.demo else ({}, "DEMO")
            logger.info("Belegungsdiagnose: %s", line_warning or "lesbar")
            for line in lines.values():
                logger.info("GPIO%s: used=%s consumer=%r", line.gpio, line.used, line.consumer)
            for device in Path("/dev").glob("gpiochip*"):
                try:
                    name, label, count = read_chip_info(device)
                    logger.info("Controller: %s [%s], %s GPIOs", name, label, count)
                except OSError as exc:
                    logger.info("Controller nicht lesbar: %s: %s", device, exc)
            app.info(tr("Fehlerprotokoll"), tr('Diagnose wurde gespeichert in:\n{v0}\n\nAuch unerwartete Fehler werden dort mit vollständigem Fehlertext protokolliert.', v0=log_path))
        except Exception as exc:
            show_error(exc)

    activate_button = PushButton(buttons, text=tr("Pin aktivieren…"), command=activate,
                                 grid=[0, 0], width=17, pady=5)
    release_button = PushButton(buttons, text=tr("Pin freigeben"), command=release,
                                grid=[1, 0], width=17, enabled=False, pady=5)
    low_button = PushButton(buttons, text="LOW / 0", command=write, args=[False],
                            grid=[0, 1], width=17, enabled=False, pady=5)
    high_button = PushButton(buttons, text="HIGH / 1", command=write, args=[True],
                             grid=[1, 1], width=17, enabled=False, pady=5)
    release_all_button = PushButton(panel, text=tr("Alle aktiven Pins freigeben"), command=release_all,
                                    enabled=False, pady=5)
    Text(panel, text=tr("Freigeben/Schließen: eigener Ausgang zuerst LOW."), size=9)
    PushButton(panel, text=tr("GPIO-Terminal öffnen"), command=show_pinout, pady=5)
    PushButton(panel, text=tr("Diagnose speichern"), command=show_diagnostics, pady=5)

    Text(app, text=tr("GPIO-Signalpins: 3,3 V · I²C/SPI/UART-Pins können bereits belegt sein."), size=10)
    Text(app, text=tr("Live-Abtastung: 1 s, kein Logikanalysator · 3V3/5V/GND: Belegung, keine Spannungsmessung"),
         size=9, color="#52647b")
    selection.update_command(selection_changed)
    profile.update_command(profile_changed)
    ui["profile"] = raspi_profile
    refresh()
    app.repeat(1000, refresh)
    try:
        app.display()
    finally:
        ui["closing"] = True
        close_choices()
        try:
            controller.close()
        except Exception:
            logger.exception("Fehler beim Freigeben während des Schließens")
        finally:
            lock.close()
    return ui.get("next_settings")


if __name__ == "__main__":
    sys.exit(main())
