"""Local diagnostics and exception logging for GPIO-Werkstatt."""

from gpio_i18n import tr

import faulthandler
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import platform
import sys
import threading

_FAULT_STREAM = None


def configure_logging():
    global _FAULT_STREAM
    directory = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "raspi-gpio"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "werkstatt.log"
    logger = logging.getLogger("raspi_gpio")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(path, maxBytes=300_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    if _FAULT_STREAM is None:
        _FAULT_STREAM = (directory / "native-crash.log").open("a", buffering=1)
        faulthandler.enable(file=_FAULT_STREAM, all_threads=True)
    logger.info("GPIO-Werkstatt Stabilitätsupdate gestartet · Python %s · %s",
                platform.python_version(), platform.platform())

    previous_hook = sys.excepthook

    def exception_hook(kind, value, trace):
        logger.critical("Unbehandelte Ausnahme", exc_info=(kind, value, trace))
        previous_hook(kind, value, trace)

    sys.excepthook = exception_hook

    def thread_hook(args):
        logger.error("Thread-Ausnahme: %s", args.thread.name,
                     exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    threading.excepthook = thread_hook
    return logger, path


def friendly_error(exc, gpio=None):
    message = str(exc).strip("'\"")
    prefix = f"GPIO{gpio}: " if gpio is not None else ""
    if "gpio busy" in message.lower() or "already in use" in message.lower():
        return prefix + tr("belegt durch Kernel oder ein anderes Programm. Der Pin wird nicht übernommen.")
    if "unexpected error" in message.lower():
        return prefix + tr("GPIO-Treiberfehler. Details stehen im Fehlerprotokoll.")
    if "permission denied" in message.lower() or "not permitted" in message.lower():
        return prefix + tr("Zugriff verweigert. GPIO-Gruppenrechte und Controller prüfen.")
    return prefix + message
