import json
import time as pytime
from pathlib import Path
from typing import Any, Dict


DEFAULT_SETTINGS: Dict[str, Any] = {
    "graphics_preset": "MEDIUM",
    "mouse_sensitivity": 1.0,
    "fov": 86.0,
    "master_volume": 0.8,
    "display_mode": "borderless_fullscreen",
    "selected_skin": "striker",
    "graphics_user_selected": False,
}


class SettingsManager:
    def __init__(self) -> None:
        self.settings_path = Path(__file__).resolve().parent.parent / "settings.json"
        self.data = json.loads(json.dumps(DEFAULT_SETTINGS))
        self.last_error = ""
        self._pending_save = False
        self._last_save_ts = 0.0
        self._save_min_interval = 0.2
        self.load()

    def load(self) -> None:
        if not self.settings_path.exists():
            self.save(force=True)
            return
        try:
            loaded = json.loads(self.settings_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data.update(loaded)
                # Migrate old configs that defaulted to HIGH without explicit user choice.
                if not self.data.get("graphics_user_selected", False) and self.data.get("graphics_preset") == "HIGH":
                    self.data["graphics_preset"] = "MEDIUM"
                    self.save(force=True)
        except (json.JSONDecodeError, OSError):
            self.data = json.loads(json.dumps(DEFAULT_SETTINGS))
            self.save(force=True)

    def save(self, force: bool = False) -> None:
        now = pytime.perf_counter()
        if not force and (now - self._last_save_ts) < self._save_min_interval:
            self._pending_save = True
            return
        try:
            self.settings_path.write_text(
                json.dumps(self.data, indent=2),
                encoding="utf-8",
            )
            self.last_error = ""
            self._last_save_ts = now
            self._pending_save = False
        except OSError as exc:
            self.last_error = f"save_failed: {exc}"
            self._pending_save = True

    def update(self) -> None:
        if not self._pending_save:
            return
        now = pytime.perf_counter()
        if (now - self._last_save_ts) >= self._save_min_interval:
            self.save(force=True)

    def flush_pending(self) -> None:
        if self._pending_save:
            self.save(force=True)

    def get_graphics_preset(self) -> str:
        preset = str(self.data.get("graphics_preset", "MEDIUM")).upper()
        return preset if preset in {"LOW", "MEDIUM", "HIGH", "ULTRA"} else "MEDIUM"

    def set_graphics_preset(self, preset: str) -> None:
        self.data["graphics_preset"] = preset.upper()
        self.data["graphics_user_selected"] = True
        self.save()

    def get_mouse_sensitivity(self) -> float:
        return float(self.data.get("mouse_sensitivity", 1.0))

    def set_mouse_sensitivity(self, value: float) -> None:
        self.data["mouse_sensitivity"] = max(0.2, min(3.0, float(value)))
        self.save()

    def get_fov(self) -> float:
        return float(self.data.get("fov", 86.0))

    def set_fov(self, value: float) -> None:
        self.data["fov"] = max(65.0, min(110.0, float(value)))
        self.save()

    def get_master_volume(self) -> float:
        return float(self.data.get("master_volume", 0.8))

    def set_master_volume(self, value: float) -> None:
        self.data["master_volume"] = max(0.0, min(1.0, float(value)))
        self.save()

    def get_display_mode(self) -> str:
        mode = str(self.data.get("display_mode", "borderless_fullscreen")).strip().lower()
        if mode in {"fullscreen", "borderless_fullscreen", "windowed"}:
            return mode
        return "borderless_fullscreen"

    def set_display_mode(self, mode: str) -> None:
        normalized = str(mode or "").strip().lower()
        if normalized not in {"fullscreen", "borderless_fullscreen", "windowed"}:
            normalized = "borderless_fullscreen"
        self.data["display_mode"] = normalized
        self.save()

    def get_selected_skin(self) -> str:
        return str(self.data.get("selected_skin", "striker"))

    def set_selected_skin(self, skin_id: str) -> None:
        self.data["selected_skin"] = skin_id
        self.save()
