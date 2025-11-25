import os
import json
from constants import BASE_DIR

class SettingsManager:
    def __init__(self):
        self.config_file = os.path.join(BASE_DIR, "launcher_settings.json")
        self.defaults = {
            "root_dir": "dosroot",
            "zip_dir": "zipped",
            "dosbox_exe": "", 
            "global_conf": "",
            "capture_dir": "capture",
            "theme": "darkly"
        }
        self.paths = self.defaults.copy()
        self.load()

    def _make_absolute(self, path):
        if not path: return ""
        if os.path.isabs(path): return path
        return os.path.normpath(os.path.join(BASE_DIR, path))

    def _make_relative(self, path):
        if not path: return ""
        abs_path = os.path.abspath(path)
        abs_base = os.path.abspath(BASE_DIR)
        try:
            common = os.path.commonpath([abs_base, abs_path])
            if common == abs_base:
                return os.path.relpath(abs_path, abs_base)
        except: pass
        return path

    def load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.paths.update(data)
            except: pass

    def save(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.paths, f, indent=4)
        except Exception as e:
            print(f"Config save error: {e}")

    def get(self, key):
        val = self.paths.get(key, self.defaults.get(key, ""))
        if key in ["root_dir", "zip_dir", "dosbox_exe", "global_conf", "capture_dir"]:
            if key == "capture_dir" and not os.path.isabs(val) and os.sep not in val:
                return val
            return self._make_absolute(val)
        return val

    def set(self, key, value):
        if key in ["root_dir", "zip_dir", "dosbox_exe", "global_conf", "capture_dir"]:
            if key == "capture_dir" and not os.path.isabs(value) and os.sep not in value:
                self.paths[key] = value
            else:
                self.paths[key] = self._make_relative(value)
        else:
            self.paths[key] = value