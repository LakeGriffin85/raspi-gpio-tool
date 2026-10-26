"""German source messages and an explicit English catalogue.

Only UI text is translated. Pin numbers, command arguments and protocol fields
keep their original values. Switching language requires a new, idle UI.
"""

import json
from pathlib import Path

_language = "de"
_english = None


def set_language(language):
    global _language, _english
    if language not in ("de", "en"):
        raise ValueError("Unsupported language: " + str(language))
    if language == "en" and _english is None:
        _english = json.loads(Path(__file__).with_name("gpio_locale_en.json").read_text(encoding="utf-8"))
    _language = language


def tr(message, **values):
    translated = _english.get(message, message) if _language == "en" else message
    return translated.format(**values) if values else translated
