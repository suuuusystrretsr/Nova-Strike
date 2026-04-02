from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class MapSpec:
    map_id: str
    display_name: str
    world_layout: str
    supported_modes: Tuple[str, ...]
    description: str = ""

    def supports_mode(self, mode_id: str) -> bool:
        return str(mode_id) in self.supported_modes


class MapRegistry:
    def __init__(self) -> None:
        self._maps: Dict[str, MapSpec] = {
            "mission_outpost_alpha": MapSpec(
                map_id="mission_outpost_alpha",
                display_name="Outpost Alpha",
                world_layout="mission",
                supported_modes=("mission_pve",),
                description="Core mission map.",
            ),
            "free_roam_frontier_alpha": MapSpec(
                map_id="free_roam_frontier_alpha",
                display_name="Frontier Sector",
                world_layout="free_roam",
                supported_modes=("free_roam_pve",),
                description="Core free roam map.",
            ),
            "ctf_bastion_alpha": MapSpec(
                map_id="ctf_bastion_alpha",
                display_name="Bastion Arena",
                world_layout="mission",
                supported_modes=("ctf",),
                description="Initial fixed CTF map.",
            ),
            "br_frontier_alpha": MapSpec(
                map_id="br_frontier_alpha",
                display_name="Frontier Expanse",
                world_layout="free_roam",
                supported_modes=("battle_royale",),
                description="Initial fixed battle royale map.",
            ),
            "duel_arena_alpha": MapSpec(
                map_id="duel_arena_alpha",
                display_name="Duel Arena Alpha",
                world_layout="mission",
                supported_modes=("duel_1v1",),
                description="1v1 map rotation entry.",
            ),
            "duel_arena_beta": MapSpec(
                map_id="duel_arena_beta",
                display_name="Duel Arena Beta",
                world_layout="mission",
                supported_modes=("duel_1v1",),
                description="1v1 map rotation entry.",
            ),
            "duel_arena_gamma": MapSpec(
                map_id="duel_arena_gamma",
                display_name="Duel Arena Gamma",
                world_layout="mission",
                supported_modes=("duel_1v1",),
                description="1v1 map rotation entry.",
            ),
        }

    def get(self, map_id: str) -> Optional[MapSpec]:
        return self._maps.get(str(map_id or ""))

    def find_first_for_mode(self, mode_id: str) -> Optional[MapSpec]:
        for map_spec in self._maps.values():
            if map_spec.supports_mode(mode_id):
                return map_spec
        return None

    def _pick_valid_fixed_map(self, mode, preferred_map_id: Optional[str]) -> str:
        if preferred_map_id:
            preferred = self.get(preferred_map_id)
            if preferred and preferred.supports_mode(mode.mode_id):
                return preferred.map_id
        default_map = self.get(mode.default_map_id)
        if default_map and default_map.supports_mode(mode.mode_id):
            return default_map.map_id
        for map_spec in self._maps.values():
            if map_spec.supports_mode(mode.mode_id):
                return map_spec.map_id
        return "mission_outpost_alpha"

    def select_map_for_mode(self, mode, rng, preferred_map_id: Optional[str] = None) -> str:
        if mode.map_policy == "random":
            pool = []
            for candidate_id in mode.map_pool:
                map_spec = self.get(candidate_id)
                if map_spec and map_spec.supports_mode(mode.mode_id):
                    pool.append(map_spec.map_id)
            if not pool:
                return self._pick_valid_fixed_map(mode, preferred_map_id)
            if preferred_map_id and preferred_map_id in pool:
                return preferred_map_id
            return rng.choice(pool)
        return self._pick_valid_fixed_map(mode, preferred_map_id)

    def resolve_world_layout(self, mode, map_id: str) -> str:
        map_spec = self.get(map_id)
        if map_spec:
            return map_spec.world_layout
        return mode.legacy_world_mode
