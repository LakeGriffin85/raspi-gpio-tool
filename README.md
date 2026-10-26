# Raspberry Pi GPIO Tool

A desktop GPIO workshop for **Raspberry Pi 5**: inspect the live 40-pin header,
understand why a pin is unavailable, and explicitly activate inputs or outputs.
The interface is available in **English and German**. An optional **Gertboard**
module adds a 26-pin view, a connector atlas and LED/button instructions.

[Deutsche Anleitung](README.de.md) · [Gertboard guide](docs/GERTBOARD.md)

## Features

- Live header with BCM GPIO numbers, physical pin numbers, HIGH/LOW and ownership.
- Multiple independent active pins; changing the selected pin preserves other pins.
- Busy kernel lines, alternate bus functions and HAT ID pins are not taken over.
- Normal selection windows instead of native Tk popup menus, suitable for remote desktops.
- Remembered language/module preferences; changing them requires releasing active pins.
- Hardware-free demo mode, pin-orientation diagrams and local diagnostics.

## Requirements

Raspberry Pi 5 with a graphical Raspberry Pi OS based on Debian Trixie, Python 3
and an active desktop session. The GPIO backend uses gpiozero/lgpio and identifies
the RP1 controller from device metadata rather than assuming its chip number.
Other boards and operating systems have not been validated.

The installer uses the Raspberry Pi OS packages `python3-guizero`, `python3-gpiozero`,
`python3-lgpio`, `lxterminal` and `xdg-user-dirs`. It does not configure a network
service, VNC, file sharing or Homebrew. Run it as your normal desktop user.

## Install from source

```bash
git clone https://github.com/LakeGriffin85/raspi-gpio-tool.git
cd raspi-gpio-tool
bash install.sh
```

For the edition that includes the optional Gertboard atlas:

```bash
bash install.sh --gertboard
```

The installer asks for sudo to install OS packages. It reads controller/ownership
metadata before installing the app and does not activate a GPIO. Existing app
files and launchers are backed up. Close a running GPIO Workshop before updating.

Open **Raspberry Pi GPIO Tool** from the desktop or application menu. The public
app is stored under `$XDG_DATA_HOME/raspi-gpio-tool` (normally
`~/.local/share/raspi-gpio-tool`). The public launchers are separate from earlier
personal workshop editions. The hardware lock remains compatible with those editions.

Alternatively, download either release ZIP, extract it and run its `install.sh`
on the Pi. English and German are included in both editions. The Gertboard edition
includes the module; enable it through **Language & modules** when needed. The base
edition does not include the Gertboard atlas. Installing the base edition over an
existing add-on does not remove that add-on or overwrite your preferences.

## Use

The overview reads pins once per second. Selecting a pin or opening a help window
does not configure it. **Activate pin** requests the selected line after confirmation.
Outputs start LOW; owned outputs are set LOW before release or application exit.
Use **Release pin** or **Release all active pins** when finished.

Use **Sprache & Module / Language & modules** to select English/German and
GPIO-only/Gertboard mode. All active pins must be released first. Preferences are
stored in `$XDG_CONFIG_HOME/raspi-gpio-tool/settings.json` (normally under `~/.config`).

From the installed application directory:

```bash
/usr/bin/python3 gpio_gui.py --language en --no-gertboard
/usr/bin/python3 gpio_gui.py --language de --gertboard
/usr/bin/python3 gpio_gui.py --demo --language en
```

Demo mode uses simulated pins only. The optional atlas file is not required for
the base view. GPIO diagnostics are local to `$XDG_CACHE_HOME/raspi-gpio`
(normally `~/.cache/raspi-gpio`); review logs before sharing them.

## Electrical scope

GPIO signalling is **3.3 V**. GPIO inputs read digital HIGH/LOW, not analogue
voltage. The one-second overview is not a logic analyser or frequency counter.
3V3/5V/GND labels identify fixed pin types; they are not voltage measurements.
Physical header positions and BCM GPIO numbers are different numbering schemes.
Disconnect all power sources before changing wires or jumpers.

## Development and validation

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r tests/requirements-dev.txt
python -m unittest discover -s tests -p 'test_*.py'
python tools/build_release.py
```

Tests use simulated GPIOs and widgets. Optional native Tk tests require a desktop
and Tk 8.6 or later:

```bash
GPIO_NATIVE_GUI_TEST=1 python -m unittest discover -s tests -p 'test_gpio_choices_native.py'
```

The selection-window fix and bilingual candidate were approved for finalisation
by a Raspberry Pi user. Automated tests cover both languages, ownership decisions,
multiple active pins, optional-module loading and an idle settings restart.
This is not a claim of validation on every desktop, circuit or operating system.

`tools/build_release.py` creates deterministic base and Gertboard ZIPs in `dist/`.
Only explicit runtime files, instructions and the licence enter those packages.
It validates the embedded Python/JSON and shell syntax without running the installer.

## Licence

[MIT](LICENSE). External libraries and linked manufacturer manuals retain their
own licences. No library sources, manufacturer PDF manuals or personal photographs
are bundled. See [THIRD_PARTY.md](THIRD_PARTY.md) for reference links.
