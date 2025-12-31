import json
import os

class SettingsManager:
    def __init__(self, filename="settings.json"):
        self.filepath = filename
        self.settings = self._load_settings()
        self._migrate_dosbox_setting()

    def _load_settings(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def _save_settings(self):
        with open(self.filepath, 'w') as f:
            json.dump(self.settings, f, indent=4)

    def _migrate_dosbox_setting(self):
        if "dosbox_exe" in self.settings:
            path = self.settings.get("dosbox_exe")
            if path and isinstance(path, str):
                new_structure = [{"name": "Default", "path": path, "default": True}]
                self.settings["dosbox_installations"] = new_structure
            del self.settings["dosbox_exe"]
            self._save_settings()

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self._save_settings()