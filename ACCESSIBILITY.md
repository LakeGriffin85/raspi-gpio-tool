# Accessibility

The project aims to make GPIO state and ownership understandable to beginners.
The following describes the current interface, rather than a claim of compliance
with an accessibility standard.

- Pin levels use **HIGH / LOW** text as well as colour. Ownership and unavailable
  pins also have text explanations; the live diagram includes symbols and a legend.
- A GPIO can be chosen from a selection list instead of clicking its diagram.
  Selection windows have **Apply** and **Cancel** buttons, with **Enter** to accept
  and **Escape** to cancel. Opening a selection does not activate a pin.
- English and German interface text is included. Physical pin numbers and BCM
  GPIO numbers are labelled separately.

## Known limits

The Tk/guizero interface has not been systematically tested with screen readers,
full keyboard-only workflows or all operating-system scaling settings. The drawn
header and board atlas may not expose all their information to assistive software.
Some windows use fixed dimensions and may be difficult on small displays or with
large text. Remote desktops can also affect focus and keyboard behaviour.

Please [report an accessibility barrier](https://github.com/LakeGriffin85/raspi-gpio-tool/issues/new?template=bug_report.yml).
Mention the app version, operating system, display scaling and assistive software
if relevant, plus what you expected and what happened. You do not need to disclose
a disability or other personal information. Text descriptions are welcome when
screenshots are not useful.

## Deutsch

Pegel und Pin-Zustände werden mit Text und Farbe angezeigt. Auswahllisten bieten
eine Alternative zum Anklicken der Grafik. Die Bedienung mit Screenreader,
ausschliesslich per Tastatur und bei starker Vergrösserung ist noch nicht umfassend
geprüft. Barrieren können über die Fehlermelde-Vorlage gemeldet werden; persönliche
oder medizinische Angaben sind dafür nicht nötig.
