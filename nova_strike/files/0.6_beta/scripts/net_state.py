from dataclasses import dataclass, field
from typing import Dict, List


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("1", "true", "yes", "y", "on"):
            return True
        if v in ("0", "false", "no", "n", "off"):
            return False
    return bool(value)


@dataclass
class Vec3State:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def to_dict(self) -> Dict:
        return {"x": float(self.x), "y": float(self.y), "z": float(self.z)}

    @classmethod
    def from_dict(cls, payload: Dict) -> "Vec3State":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            x=_safe_float(payload.get("x", 0.0)),
            y=_safe_float(payload.get("y", 0.0)),
            z=_safe_float(payload.get("z", 0.0)),
        )


@dataclass
class PlayerActionState:
    move_x: float = 0.0
    move_z: float = 0.0
    sprint: bool = False
    jump: bool = False
    fire: bool = False
    reload: bool = False
    ability: bool = False
    aim: bool = False

    def to_dict(self) -> Dict:
        return {
            "move_x": float(self.move_x),
            "move_z": float(self.move_z),
            "sprint": bool(self.sprint),
            "jump": bool(self.jump),
            "fire": bool(self.fire),
            "reload": bool(self.reload),
            "ability": bool(self.ability),
            "aim": bool(self.aim),
        }

    @classmethod
    def from_dict(cls, payload: Dict) -> "PlayerActionState":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            move_x=_safe_float(payload.get("move_x", 0.0)),
            move_z=_safe_float(payload.get("move_z", 0.0)),
            sprint=_safe_bool(payload.get("sprint", False)),
            jump=_safe_bool(payload.get("jump", False)),
            fire=_safe_bool(payload.get("fire", False)),
            reload=_safe_bool(payload.get("reload", False)),
            ability=_safe_bool(payload.get("ability", False)),
            aim=_safe_bool(payload.get("aim", False)),
        )


@dataclass
class WeaponSyncState:
    weapon_id: str = "rifle"
    rarity: str = "common"
    ammo_in_mag: int = 0
    reserve_ammo: int = 0
    reloading: bool = False

    def to_dict(self) -> Dict:
        return {
            "weapon_id": str(self.weapon_id),
            "rarity": str(self.rarity),
            "ammo_in_mag": int(self.ammo_in_mag),
            "reserve_ammo": int(self.reserve_ammo),
            "reloading": bool(self.reloading),
        }

    @classmethod
    def from_dict(cls, payload: Dict) -> "WeaponSyncState":
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            weapon_id=str(payload.get("weapon_id", "rifle")),
            rarity=str(payload.get("rarity", "common")),
            ammo_in_mag=max(0, _safe_int(payload.get("ammo_in_mag", 0))),
            reserve_ammo=max(0, _safe_int(payload.get("reserve_ammo", 0))),
            reloading=_safe_bool(payload.get("reloading", False)),
        )


@dataclass
class PlayerSyncState:
    player_id: str
    sequence: int
    timestamp: float
    position: Vec3State
    velocity: Vec3State
    rotation_y: float
    pitch: float
    health: float
    health_max: float
    alive: bool
    active_weapon_index: int
    skin_id: str = "striker"
    team_id: str = ""
    weapons: List[WeaponSyncState] = field(default_factory=list)
    actions: PlayerActionState = field(default_factory=PlayerActionState)
    state_flags: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "player_id": str(self.player_id),
            "sequence": int(self.sequence),
            "timestamp": float(self.timestamp),
            "position": self.position.to_dict(),
            "velocity": self.velocity.to_dict(),
            "rotation_y": float(self.rotation_y),
            "pitch": float(self.pitch),
            "health": float(self.health),
            "health_max": float(self.health_max),
            "alive": bool(self.alive),
            "active_weapon_index": int(self.active_weapon_index),
            "skin_id": str(self.skin_id),
            "team_id": str(self.team_id),
            "weapons": [weapon.to_dict() for weapon in self.weapons],
            "actions": self.actions.to_dict(),
            "state_flags": {str(k): bool(v) for k, v in self.state_flags.items()},
        }

    @classmethod
    def from_dict(cls, payload: Dict) -> "PlayerSyncState":
        payload = payload if isinstance(payload, dict) else {}
        weapons_payload = payload.get("weapons", [])
        if not isinstance(weapons_payload, list):
            weapons_payload = []
        flags = payload.get("state_flags", {})
        flags = flags if isinstance(flags, dict) else {}
        return cls(
            player_id=str(payload.get("player_id", "unknown")),
            sequence=max(0, _safe_int(payload.get("sequence", 0))),
            timestamp=_safe_float(payload.get("timestamp", 0.0)),
            position=Vec3State.from_dict(payload.get("position", {})),
            velocity=Vec3State.from_dict(payload.get("velocity", {})),
            rotation_y=_safe_float(payload.get("rotation_y", 0.0)),
            pitch=_safe_float(payload.get("pitch", 0.0)),
            health=max(0.0, _safe_float(payload.get("health", 0.0))),
            health_max=max(1.0, _safe_float(payload.get("health_max", 100.0))),
            alive=_safe_bool(payload.get("alive", True)),
            active_weapon_index=max(0, _safe_int(payload.get("active_weapon_index", 0))),
            skin_id=str(payload.get("skin_id", "striker")),
            team_id=str(payload.get("team_id", "")),
            weapons=[WeaponSyncState.from_dict(entry) for entry in weapons_payload if isinstance(entry, dict)],
            actions=PlayerActionState.from_dict(payload.get("actions", {})),
            state_flags={str(k): _safe_bool(v, False) for k, v in flags.items()},
        )
