# Security policy

## Supported versions

Security fixes are intended for the latest stable release. Older releases do not
have a separate maintenance branch. This is a volunteer project; there is no
guaranteed response time or commercial support commitment.

## Report a vulnerability privately

Use [GitHub's private vulnerability reporting form](https://github.com/LakeGriffin85/raspi-gpio-tool/security/advisories/new),
also available under **Security and quality → Advisories → Report a vulnerability**.
Include the affected version, a minimal reproduction and the expected impact.
Please give maintainers an opportunity to investigate before public disclosure.

Do not open a public issue containing exploit details, passwords, access tokens,
private logs or identifying photographs. Remove unrelated personal information
even from private reports. Ordinary bugs and feature requests belong in
[Issues](https://github.com/LakeGriffin85/raspi-gpio-tool/issues).

The application controls physical GPIOs. Report incorrect ownership checks or
unexpected output changes, including the BCM GPIO number and physical pin number.
Use simulated GPIOs for reproduction where possible; do not recreate a potentially
damaging circuit just to submit a report. A software fix cannot validate a circuit's
electrical safety.

## Deutsch

Sicherheitslücken bitte über das oben verlinkte private GitHub-Formular melden.
Keine Zugangsdaten, privaten Protokolle oder Exploit-Details in öffentliche Issues
stellen. Unterstützt wird die aktuelle stabile Version, ohne garantierte
Reaktionszeit. Normale Fehler und Ideen gehören in die öffentlichen Issues.
