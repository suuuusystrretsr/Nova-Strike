from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple


@dataclass(frozen=True)
class GameModeSpec:
    mode_id: str
    display_name: str
    runtime_kind: str
    legacy_world_mode: str
    supports_teams: bool
    team_size_options: Tuple[int, ...]
    min_players: int
    max_players: int
    map_policy: str
    default_map_id: str
    map_pool: Tuple[str, ...]
    description: str = ""

    @property
    def is_multiplayer(self) -> bool:
        return self.runtime_kind == "multiplayer"


@dataclass(frozen=True)
class MatchSettings:
    mode_id: str
    display_name: str
    runtime_kind: str
    legacy_world_mode: str
    map_id: str
    min_players: int
    max_players: int
    supports_teams: bool
    team_size: int
    description: str = ""

    @property
    def is_multiplayer(self) -> bool:
        return self.runtime_kind == "multiplayer"

    def to_dict(self) -> Dict:
        return {
            "mode_id": self.mode_id,
            "display_name": self.display_name,
            "runtime_kind": self.runtime_kind,
            "legacy_world_mode": self.legacy_world_mode,
            "map_id": self.map_id,
            "min_players": int(self.min_players),
            "max_players": int(self.max_players),
            "supports_teams": bool(self.supports_teams),
            "team_size": int(self.team_size),
            "description": self.description,
        }


class GameModeRegistry:
    def __init__(self) -> None:
        self._modes: Dict[str, GameModeSpec] = {
            "mission_pve": GameModeSpec(
                mode_id="mission_pve",
                display_name="Mission Mode",
                runtime_kind="singleplayer",
                legacy_world_mode="mission",
                supports_teams=False,
                team_size_options=(1,),
                min_players=1,
                max_players=1,
                map_policy="fixed",
                default_map_id="mission_outpost_alpha",
                map_pool=("mission_outpost_alpha",),
                description="Objective-driven PvE wave mission.",
            ),
            "free_roam_pve": GameModeSpec(
                mode_id="free_roam_pve",
                display_name="Free Roam",
                runtime_kind="singleplayer",
                legacy_world_mode="free_roam",
                supports_teams=False,
                team_size_options=(1,),
                min_players=1,
                max_players=1,
                map_policy="fixed",
                default_map_id="free_roam_frontier_alpha",
                map_pool=("free_roam_frontier_alpha",),
                description="Open-world PvE exploration and quests.",
            ),
            "ctf": GameModeSpec(
                mode_id="ctf",
                display_name="Capture The Flag",
                runtime_kind="multiplayer",
                legacy_world_mode="mission",
                supports_teams=True,
                team_size_options=(1, 2, 3, 4),
                min_players=2,
                max_players=8,
                map_policy="fixed",
                default_map_id="ctf_bastion_alpha",
                map_pool=("ctf_bastion_alpha",),
                description="Team objective mode for 1v1 through 4v4.",
            ),
            "battle_royale": GameModeSpec(
                mode_id="battle_royale",
                display_name="Battle Royale",
                runtime_kind="multiplayer",
                legacy_world_mode="free_roam",
                supports_teams=False,
                team_size_options=(1,),
                min_players=2,
                max_players=100,
                map_policy="fixed",
                default_map_id="br_frontier_alpha",
                map_pool=("br_frontier_alpha",),
                description="Last-player-standing mode designed for high player counts.",
            ),
            "duel_1v1": GameModeSpec(
                mode_id="duel_1v1",
                display_name="1v1 Duel",
                runtime_kind="multiplayer",
                legacy_world_mode="mission",
                supports_teams=True,
                team_size_options=(1,),
                min_players=2,
                max_players=2,
                map_policy="random",
                default_map_id="duel_arena_alpha",
                map_pool=("duel_arena_alpha", "duel_arena_beta", "duel_arena_gamma"),
                description="Head-to-head duels with random map selection.",
            ),
        }
        self._aliases = {
            "mission": "mission_pve",
            "free_roam": "free_roam_pve",
            "freeroam": "free_roam_pve",
            "battle_royale_mode": "battle_royale",
            "br": "battle_royale",
            "duel": "duel_1v1",
            "1v1": "duel_1v1",
        }

    def resolve_mode(self, mode_id: str) -> GameModeSpec:
        key = str(mode_id or "").strip().lower()
        canonical = self._aliases.get(key, key)
        if canonical in self._modes:
            return self._modes[canonical]
        return self._modes["mission_pve"]

    def choose_team_size(self, mode: GameModeSpec, requested_team_size: Optional[int] = None) -> int:
        if not mode.supports_teams:
            return 1
        if requested_team_size is None:
            return int(mode.team_size_options[0]) if mode.team_size_options else 1
        requested = max(1, int(requested_team_size))
        if requested in mode.team_size_options:
            return requested
        if not mode.team_size_options:
            return 1
        return int(mode.team_size_options[0])

    def build_match_settings(
        self,
        mode_id: str,
        map_id: str,
        requested_team_size: Optional[int] = None,
        requested_max_players: Optional[int] = None,
    ) -> MatchSettings:
        mode = self.resolve_mode(mode_id)
        team_size = self.choose_team_size(mode, requested_team_size)
        if mode.supports_teams:
            max_players = int(max(mode.min_players, min(mode.max_players, team_size * 2)))
        else:
            max_players = int(mode.max_players)
        if requested_max_players is not None:
            max_players = max(mode.min_players, min(mode.max_players, int(requested_max_players)))
        if mode.supports_teams:
            max_players = max(mode.min_players, min(max_players, team_size * 2))
        return MatchSettings(
            mode_id=mode.mode_id,
            display_name=mode.display_name,
            runtime_kind=mode.runtime_kind,
            legacy_world_mode=mode.legacy_world_mode,
            map_id=str(map_id),
            min_players=int(mode.min_players),
            max_players=max_players,
            supports_teams=bool(mode.supports_teams),
            team_size=team_size,
            description=mode.description,
        )

    def get_default_singleplayer_mode_id(self) -> str:
        return "mission_pve"

    def to_legacy_game_mode(self, mode_id: str) -> str:
        mode = self.resolve_mode(mode_id)
        return "free_roam" if mode.legacy_world_mode == "free_roam" else "mission"
