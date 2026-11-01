"""记住上次的目录与修改内容。首次使用时沿用 tkinter 版的设置。"""
import json
import os

_BASE = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SteelSectionProbe")
DEFAULT_PATH = os.path.join(_BASE, "SchemaPatcherFluent", "settings.json")
LEGACY_PATH = os.path.join(_BASE, "SchemaPatcher", "settings.json")


class SettingsStore(object):
    def __init__(self, path=DEFAULT_PATH, legacy_path=LEGACY_PATH):
        self.path = path
        self.legacy_path = legacy_path

    def load(self):
        for candidate in (self.path, self.legacy_path):
            try:
                with open(candidate, "r", encoding="utf-8-sig") as stream:
                    data = json.load(stream)
                if isinstance(data, dict):
                    return {"schema_dir": str(data.get("schema_dir", "")),
                            "backup_dir": str(data.get("backup_dir", "")),
                            "feature": str(data.get("feature", ""))}
            except (OSError, ValueError):
                continue
        return {"schema_dir": "", "backup_dir": "", "feature": ""}

    def save(self, values):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as stream:
                json.dump(values, stream, ensure_ascii=False, indent=2)
        except OSError:
            pass
