"""应用配置（bb_config.json）的读写。文件在每个用户自己的数据目录里，见 utils/paths.py。"""
import json
import os

from utils.paths import data_path

CONFIG_FILE = "bb_config.json"


class Settings:
    def __init__(self, path=None):
        self.path = path or data_path(CONFIG_FILE)
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def remove(self, key):
        self.data.pop(key, None)

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
