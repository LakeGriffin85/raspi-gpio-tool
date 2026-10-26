"""Small, local UI preferences. No hardware or network configuration."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile


@dataclass(frozen=True)
class Settings:
    language: str = "en"
    gertboard: bool = False

    def __post_init__(self):
        if self.language not in ("de", "en") or type(self.gertboard) is not bool:
            raise ValueError("Invalid UI settings")


def settings_path():
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "raspi-gpio-tool" / "settings.json"


def load_settings():
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return Settings()
        return Settings(data.get("language", "en"), data.get("gertboard", False))
    except (OSError, ValueError, TypeError):
        return Settings()


def save_settings(settings):
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".settings-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"language": settings.language, "gertboard": settings.gertboard}, stream)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
