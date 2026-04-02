import re
from pathlib import Path

from .json_store import load_json, write_json_atomic
from .models import GameConfig
from .paths import AppPaths


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-z0-9_\\-]", "_", value.strip().lower())


class GameRegistry:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    def _game_file(self, game_id: str) -> Path:
        safe = _safe_id(game_id)
        return self.paths.installed_games_dir / f"{safe}.json"

    def list_games(self) -> list[GameConfig]:
        games: list[GameConfig] = []
        for path in sorted(self.paths.installed_games_dir.glob("*.json")):
            raw = load_json(path, default={})
            if not isinstance(raw, dict):
                continue
            game = GameConfig.from_dict(raw)
            if not game.game_id or not game.display_name:
                continue
            games.append(game)
        games.sort(key=lambda item: item.display_name.lower())
        return games

    def get_game(self, game_id: str) -> GameConfig | None:
        raw = load_json(self._game_file(game_id), default={})
        if not isinstance(raw, dict):
            return None
        game = GameConfig.from_dict(raw)
        return game if game.game_id else None

    def save_game(self, game: GameConfig) -> None:
        if not game.game_id:
            raise ValueError("game_id is required")
        write_json_atomic(self._game_file(game.game_id), game.to_dict())

    def remove_game(self, game_id: str) -> None:
        path = self._game_file(game_id)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
