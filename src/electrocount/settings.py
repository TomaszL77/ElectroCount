"""Local user preferences; tests can point to an isolated INI file."""
import os
from pathlib import Path
from PySide6.QtCore import QSettings
from .diagnostics import data_dir


class Settings:
    def __init__(self):
        path = Path(os.environ.get("ELECTROCOUNT_SETTINGS_PATH",
                    str(data_dir()/"settings.ini")))
        path.parent.mkdir(parents=True, exist_ok=True)
        self.store = QSettings(str(path), QSettings.Format.IniFormat)

    def get(self, key, default=False):
        return self.store.value(key, default, type=bool)

    def text(self, key, default=""):
        return self.store.value(key, default, type=str)

    def has(self, key):
        return self.store.contains(key)

    def set(self, key, value):
        self.store.setValue(key, value)
        self.store.sync()

