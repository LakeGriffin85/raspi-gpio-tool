# Contributing

Changes and ideas are welcome. The repository is public: everyone can download
it and create a fork. A fork is your own copy, where you can create branches and
commits. A pull request proposes those changes to this project; it does not
immediately change the upstream code. Direct pushes require granted write access.

1. Fork the project and create a branch for one focused change.
2. Run the existing tests using simulated GPIOs.
3. Explain what changed and how it was checked.
4. Open a pull request for review.

```bash
python -m pip install -r tests/requirements-dev.txt
python -m unittest discover -s tests -p 'test_*.py'
```

Use MockFactory for tests; automated tests must not drive real hardware. Keep
physical pin numbers and BCM GPIO numbers distinct. Diagram changes should use
the canonical pin/board models. SVG documentation assets can be regenerated with:

```bash
python tools/render_docs_assets.py
```

English and German UI strings should remain consistent. Do not include credentials,
local logs, identifying image metadata or private machine/network details in a
contribution. Use your preferred public Git identity; a GitHub noreply email can
keep a personal email address out of commit metadata. See [PRIVACY.md](PRIVACY.md).

## Deutsch

Du kannst das Projekt forken und in deinem Fork eigene Commits erstellen. Mit
einem Pull Request schlägst du die Änderung hier vor; die Maintainer prüfen und
übernehmen sie. Direktes Schreiben ins Hauptprojekt braucht ein vergebenes
Schreibrecht. Tests verwenden simulierte Pins. Persönliche Angaben, Zugangsdaten
und Standort-Metadaten gehören nicht in Beiträge.
