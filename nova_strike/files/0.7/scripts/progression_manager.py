import json
import time as pytime
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from scripts.skill_tree import SKILL_NODE_MAPS, SKILL_TREES


PROFILE_IDS = ("slot_1", "slot_2", "slot_3")
ABILITY_IDS = ("striker", "vanguard", "phantom")
CHARACTER_IDS = tuple(SKILL_TREES.keys())

UPGRADE_MAX_LEVEL = 5
UPGRADE_COST_BASE = {
    "damage": 110,
    "reload": 95,
    "health": 125,
}
ABILITY_UPGRADE_COST_BASE = {
    "striker": 135,
    "vanguard": 145,
    "phantom": 140,
}


def _deep_copy_json(value):
    return json.loads(json.dumps(value))


def _new_profile_data() -> Dict:
    return {
        "coins": 0,
        "locked_skin_id": None,
        "upgrades": {
            "damage": 0,
            "reload": 0,
            "health": 0,
        },
        "ability_upgrades": {
            "striker": 0,
            "vanguard": 0,
            "phantom": 0,
        },
        "story_index": 0,
        "checkpoints": {
            "mission": None,
            "free_roam": None,
        },
        "stats": {
            "mission_best_wave": 0,
            "boss_kills": 0,
        },
        "unlocked_attachments": [],
        "skill_unlocks": {
            "striker": [],
            "vanguard": [],
            "phantom": [],
        },
    }


DEFAULT_SAVE = {
    "active_profile": "slot_1",
    "profiles": {
        "slot_1": _new_profile_data(),
        "slot_2": _new_profile_data(),
        "slot_3": _new_profile_data(),
    },
    "challenges": {},
}


class ProgressionManager:
    def __init__(self) -> None:
        self.save_path = Path(__file__).resolve().parent.parent / "save_data.json"
        self.data = _deep_copy_json(DEFAULT_SAVE)
        self._pending_save = False
        self._last_save_ts = 0.0
        self._save_min_interval = 0.35
        self.last_error = ""
        self.load()

    def load(self) -> None:
        if not self.save_path.exists():
            self.save(force=True)
            return
        try:
            loaded = json.loads(self.save_path.read_text(encoding="utf-8"))
            self._merge_loaded_data(loaded if isinstance(loaded, dict) else {})
        except (json.JSONDecodeError, OSError):
            self.data = _deep_copy_json(DEFAULT_SAVE)
            self.save(force=True)

    def save(self, force: bool = False) -> None:
        now = pytime.perf_counter()
        if not force and (now - self._last_save_ts) < self._save_min_interval:
            self._pending_save = True
            return
        try:
            self.save_path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        except OSError as exc:
            self.last_error = f"save_failed: {exc}"
            self._pending_save = True
            return
        self.last_error = ""
        self._last_save_ts = now
        self._pending_save = False

    def update(self) -> None:
        if not self._pending_save:
            return
        now = pytime.perf_counter()
        if (now - self._last_save_ts) >= self._save_min_interval:
            self.save(force=True)

    def flush_pending(self) -> None:
        if self._pending_save:
            self.save(force=True)

    def _merge_loaded_data(self, loaded: Dict) -> None:
        # New schema path.
        if isinstance(loaded.get("profiles"), dict):
            self.data["active_profile"] = str(loaded.get("active_profile", "slot_1"))
            self.data["profiles"] = _deep_copy_json(DEFAULT_SAVE["profiles"])
            for profile_id in PROFILE_IDS:
                incoming_profile = loaded["profiles"].get(profile_id, {})
                self._merge_profile_data(self.data["profiles"][profile_id], incoming_profile if isinstance(incoming_profile, dict) else {})
            incoming_challenges = loaded.get("challenges", {})
            self.data["challenges"] = incoming_challenges if isinstance(incoming_challenges, dict) else {}
            self._sanitize()
            self.save()
            return

        # Backward-compatible migration from old single-profile schema.
        migrated = _deep_copy_json(DEFAULT_SAVE)
        slot_1 = migrated["profiles"]["slot_1"]
        slot_1["coins"] = int(loaded.get("coins", 0))
        old_upgrades = loaded.get("upgrades", {})
        if isinstance(old_upgrades, dict):
            for key in slot_1["upgrades"]:
                slot_1["upgrades"][key] = int(old_upgrades.get(key, 0))
        slot_1["story_index"] = int(loaded.get("story_index", 0))
        self.data = migrated
        self._sanitize()
        self.save()

    def _merge_profile_data(self, base: Dict, incoming: Dict) -> None:
        base["coins"] = int(incoming.get("coins", base["coins"]))
        base["story_index"] = int(incoming.get("story_index", base["story_index"]))
        locked = incoming.get("locked_skin_id", base.get("locked_skin_id"))
        base["locked_skin_id"] = str(locked) if isinstance(locked, str) else None

        incoming_upgrades = incoming.get("upgrades", {})
        if isinstance(incoming_upgrades, dict):
            for key in base["upgrades"]:
                base["upgrades"][key] = int(incoming_upgrades.get(key, base["upgrades"][key]))

        incoming_ability = incoming.get("ability_upgrades", {})
        if isinstance(incoming_ability, dict):
            for key in base["ability_upgrades"]:
                base["ability_upgrades"][key] = int(incoming_ability.get(key, base["ability_upgrades"][key]))

        incoming_checkpoints = incoming.get("checkpoints", {})
        if isinstance(incoming_checkpoints, dict):
            for key in ("mission", "free_roam"):
                checkpoint = incoming_checkpoints.get(key)
                base["checkpoints"][key] = checkpoint if isinstance(checkpoint, dict) else None

        incoming_stats = incoming.get("stats", {})
        if isinstance(incoming_stats, dict):
            for key in base["stats"]:
                base["stats"][key] = int(incoming_stats.get(key, base["stats"][key]))

        unlocked = incoming.get("unlocked_attachments", [])
        if isinstance(unlocked, list):
            base["unlocked_attachments"] = [str(x) for x in unlocked if isinstance(x, str)]

        incoming_skill_unlocks = incoming.get("skill_unlocks", {})
        if not isinstance(incoming_skill_unlocks, dict):
            incoming_skill_unlocks = {}
        for skin_id in CHARACTER_IDS:
            source = incoming_skill_unlocks.get(skin_id, base["skill_unlocks"].get(skin_id, []))
            if not isinstance(source, list):
                source = []
            valid_node_ids = set(SKILL_NODE_MAPS.get(skin_id, {}).keys())
            deduped = []
            for node_id in source:
                if not isinstance(node_id, str):
                    continue
                if node_id not in valid_node_ids:
                    continue
                if node_id in deduped:
                    continue
                deduped.append(node_id)
            base["skill_unlocks"][skin_id] = deduped

    def _sanitize(self) -> None:
        if self.data.get("active_profile") not in PROFILE_IDS:
            self.data["active_profile"] = "slot_1"
        if not isinstance(self.data.get("profiles"), dict):
            self.data["profiles"] = _deep_copy_json(DEFAULT_SAVE["profiles"])
        for profile_id in PROFILE_IDS:
            if profile_id not in self.data["profiles"] or not isinstance(self.data["profiles"][profile_id], dict):
                self.data["profiles"][profile_id] = _new_profile_data()
            self._merge_profile_data(self.data["profiles"][profile_id], self.data["profiles"][profile_id])
            self.data["profiles"][profile_id]["coins"] = max(0, int(self.data["profiles"][profile_id]["coins"]))
            self.data["profiles"][profile_id]["story_index"] = max(0, int(self.data["profiles"][profile_id]["story_index"]))
            if self.data["profiles"][profile_id].get("locked_skin_id") not in CHARACTER_IDS:
                self.data["profiles"][profile_id]["locked_skin_id"] = None
            for key in self.data["profiles"][profile_id]["upgrades"]:
                self.data["profiles"][profile_id]["upgrades"][key] = max(0, min(UPGRADE_MAX_LEVEL, int(self.data["profiles"][profile_id]["upgrades"][key])))
            for key in self.data["profiles"][profile_id]["ability_upgrades"]:
                self.data["profiles"][profile_id]["ability_upgrades"][key] = max(0, min(UPGRADE_MAX_LEVEL, int(self.data["profiles"][profile_id]["ability_upgrades"][key])))
            if not isinstance(self.data["profiles"][profile_id].get("skill_unlocks"), dict):
                self.data["profiles"][profile_id]["skill_unlocks"] = _new_profile_data()["skill_unlocks"]
            for skin_id in CHARACTER_IDS:
                if skin_id not in self.data["profiles"][profile_id]["skill_unlocks"] or not isinstance(self.data["profiles"][profile_id]["skill_unlocks"][skin_id], list):
                    self.data["profiles"][profile_id]["skill_unlocks"][skin_id] = []
        if not isinstance(self.data.get("challenges"), dict):
            self.data["challenges"] = {}

    def _profile(self) -> Dict:
        profile_id = self.get_active_profile_id()
        return self.data["profiles"][profile_id]

    # ------------------
    # Profile Management
    # ------------------
    def list_profiles(self):
        return list(PROFILE_IDS)

    def get_active_profile_id(self) -> str:
        profile_id = str(self.data.get("active_profile", "slot_1"))
        if profile_id not in PROFILE_IDS:
            profile_id = "slot_1"
        return profile_id

    def set_active_profile(self, profile_id: str) -> bool:
        if profile_id not in PROFILE_IDS:
            return False
        self.data["active_profile"] = profile_id
        self.save()
        return True

    def get_locked_skin_id(self) -> Optional[str]:
        locked = self._profile().get("locked_skin_id")
        if locked in CHARACTER_IDS:
            return str(locked)
        return None

    def lock_skin_if_unset(self, skin_id: str) -> bool:
        if skin_id not in CHARACTER_IDS:
            return False
        profile = self._profile()
        current = profile.get("locked_skin_id")
        if current in CHARACTER_IDS:
            return current == skin_id
        profile["locked_skin_id"] = skin_id
        self.save()
        return True

    def clear_character_lock(self) -> None:
        self._profile()["locked_skin_id"] = None
        self.save()

    # ----------
    # Currencies
    # ----------
    def get_coins(self) -> int:
        return int(self._profile().get("coins", 0))

    def add_coins(self, amount: int) -> None:
        if amount <= 0:
            return
        profile = self._profile()
        profile["coins"] = self.get_coins() + int(amount)
        self.save()

    def spend_coins(self, amount: int) -> bool:
        coins = self.get_coins()
        if amount <= 0 or coins < amount:
            return False
        self._profile()["coins"] = coins - int(amount)
        self.save()
        return True

    # -----
    # Story
    # -----
    def get_story_index(self) -> int:
        return int(self._profile().get("story_index", 0))

    def set_story_index(self, value: int) -> None:
        self._profile()["story_index"] = max(0, int(value))
        self.save()

    # --------
    # Upgrades
    # --------
    def get_upgrade_level(self, upgrade_id: str) -> int:
        upgrades = self._profile().get("upgrades", {})
        return int(upgrades.get(upgrade_id, 0))

    def get_upgrade_cost(self, upgrade_id: str) -> int:
        level = self.get_upgrade_level(upgrade_id)
        base = UPGRADE_COST_BASE.get(upgrade_id, 100)
        return int(base + (level * base * 0.65))

    def can_buy_upgrade(self, upgrade_id: str) -> bool:
        level = self.get_upgrade_level(upgrade_id)
        if level >= UPGRADE_MAX_LEVEL:
            return False
        return self.get_coins() >= self.get_upgrade_cost(upgrade_id)

    def buy_upgrade(self, upgrade_id: str) -> bool:
        level = self.get_upgrade_level(upgrade_id)
        if level >= UPGRADE_MAX_LEVEL:
            return False
        cost = self.get_upgrade_cost(upgrade_id)
        if not self.spend_coins(cost):
            return False
        self._profile()["upgrades"][upgrade_id] = level + 1
        self.save()
        return True

    # ----------------
    # Ability Upgrades
    # ----------------
    def get_ability_upgrade_level(self, ability_id: str) -> int:
        ability = self._profile().get("ability_upgrades", {})
        return int(ability.get(ability_id, 0))

    def get_ability_upgrade_cost(self, ability_id: str) -> int:
        level = self.get_ability_upgrade_level(ability_id)
        base = ABILITY_UPGRADE_COST_BASE.get(ability_id, 130)
        return int(base + (level * base * 0.72))

    def buy_ability_upgrade(self, ability_id: str) -> bool:
        if ability_id not in ABILITY_IDS:
            return False
        level = self.get_ability_upgrade_level(ability_id)
        if level >= UPGRADE_MAX_LEVEL:
            return False
        cost = self.get_ability_upgrade_cost(ability_id)
        if not self.spend_coins(cost):
            return False
        self._profile()["ability_upgrades"][ability_id] = level + 1
        self.save()
        return True

    def get_ability_cooldown_multiplier(self, ability_id: str) -> float:
        # Core progression now comes from character skill trees.
        # Keep legacy upgrade levels stored for backward compatibility,
        # but do not scale gameplay from this old upgrade path.
        return 1.0

    def get_ability_duration_bonus(self, ability_id: str) -> float:
        return 0.0

    def get_damage_multiplier(self) -> float:
        return 1.0 + float(self.get_skill_effect_totals().get("damage_mult", 0.0))

    def get_reload_multiplier(self) -> float:
        skill_reload = float(self.get_skill_effect_totals().get("reload_mult", 1.0))
        return max(0.4, skill_reload)

    def get_health_bonus(self) -> int:
        return int(round(float(self.get_skill_effect_totals().get("health_bonus", 0.0))))

    def snapshot_upgrades(self) -> Dict[str, int]:
        profile = self._profile()
        return {
            "damage": self.get_upgrade_level("damage"),
            "reload": self.get_upgrade_level("reload"),
            "health": self.get_upgrade_level("health"),
            "ability_striker": int(profile["ability_upgrades"].get("striker", 0)),
            "ability_vanguard": int(profile["ability_upgrades"].get("vanguard", 0)),
            "ability_phantom": int(profile["ability_upgrades"].get("phantom", 0)),
        }

    # ----------
    # Skill Tree
    # ----------
    def get_unlocked_skill_ids(self, skin_id: str) -> list:
        profile = self._profile()
        unlocks = profile.get("skill_unlocks", {}).get(skin_id, [])
        if not isinstance(unlocks, list):
            return []
        return [node_id for node_id in unlocks if isinstance(node_id, str)]

    def is_skill_unlocked(self, skin_id: str, node_id: str) -> bool:
        return node_id in self.get_unlocked_skill_ids(skin_id)

    def get_skill_effect_totals(self, skin_id: Optional[str] = None) -> Dict[str, float]:
        active_skin = skin_id if skin_id in CHARACTER_IDS else self.get_locked_skin_id()
        if active_skin not in CHARACTER_IDS:
            return {}
        totals: Dict[str, float] = {}
        node_map = SKILL_NODE_MAPS.get(active_skin, {})
        for node_id in self.get_unlocked_skill_ids(active_skin):
            node = node_map.get(node_id)
            if not node:
                continue
            for effect_key, effect_value in node.effects.items():
                totals[effect_key] = float(totals.get(effect_key, 0.0)) + float(effect_value)
        return totals

    def get_skill_tree_nodes(self, skin_id: str):
        return list(SKILL_TREES.get(skin_id, []))

    def can_unlock_skill(self, skin_id: str, node_id: str):
        if skin_id not in CHARACTER_IDS:
            return False, "Invalid character", 0
        if self.get_locked_skin_id() != skin_id:
            return False, "Character not locked to this profile", 0
        node = SKILL_NODE_MAPS.get(skin_id, {}).get(node_id)
        if not node:
            return False, "Skill not found", 0
        if self.is_skill_unlocked(skin_id, node_id):
            return False, "Already unlocked", node.cost
        unlocked = set(self.get_unlocked_skill_ids(skin_id))
        missing = [req for req in node.prereqs if req not in unlocked]
        if missing:
            return False, "Missing prerequisite skill", node.cost
        if self.get_coins() < node.cost:
            return False, "Not enough coins", node.cost
        return True, "OK", node.cost

    def unlock_skill(self, skin_id: str, node_id: str):
        can_unlock, message, _cost = self.can_unlock_skill(skin_id, node_id)
        if not can_unlock:
            return False, message
        node = SKILL_NODE_MAPS[skin_id][node_id]
        if not self.spend_coins(node.cost):
            return False, "Not enough coins"
        unlocks = self._profile()["skill_unlocks"][skin_id]
        unlocks.append(node_id)
        self.save()
        return True, f"Unlocked: {node.name}"

    # -----------
    # Checkpoints
    # -----------
    def save_checkpoint(self, mode: str, payload: Dict) -> None:
        mode_key = "free_roam" if mode == "free_roam" else "mission"
        entry = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "payload": payload if isinstance(payload, dict) else {},
        }
        self._profile()["checkpoints"][mode_key] = entry
        self.save()

    def load_checkpoint(self, mode: str) -> Optional[Dict]:
        mode_key = "free_roam" if mode == "free_roam" else "mission"
        entry = self._profile().get("checkpoints", {}).get(mode_key)
        if not isinstance(entry, dict):
            return None
        payload = entry.get("payload")
        return payload if isinstance(payload, dict) else None

    def clear_checkpoint(self, mode: Optional[str] = None) -> None:
        checkpoints = self._profile().get("checkpoints", {})
        if mode is None:
            checkpoints["mission"] = None
            checkpoints["free_roam"] = None
        else:
            mode_key = "free_roam" if mode == "free_roam" else "mission"
            checkpoints[mode_key] = None
        self.save()

    # ------------
    # Attachments
    # ------------
    def unlock_attachment(self, attachment_id: str) -> None:
        if not attachment_id:
            return
        profile = self._profile()
        unlocked = profile.get("unlocked_attachments", [])
        if attachment_id in unlocked:
            return
        unlocked.append(attachment_id)
        profile["unlocked_attachments"] = unlocked
        self.save()

    def get_unlocked_attachments(self):
        return list(self._profile().get("unlocked_attachments", []))

    # -----
    # Stats
    # -----
    def set_mission_best_wave(self, wave: int) -> None:
        stats = self._profile().get("stats", {})
        stats["mission_best_wave"] = max(int(stats.get("mission_best_wave", 0)), int(wave))
        self._profile()["stats"] = stats
        self.save()

    def get_mission_best_wave(self) -> int:
        return int(self._profile().get("stats", {}).get("mission_best_wave", 0))

    def add_boss_kill(self, amount: int = 1) -> None:
        if amount <= 0:
            return
        stats = self._profile().get("stats", {})
        stats["boss_kills"] = int(stats.get("boss_kills", 0)) + int(amount)
        self._profile()["stats"] = stats
        self.save()

    def get_boss_kills(self) -> int:
        return int(self._profile().get("stats", {}).get("boss_kills", 0))

    # ----------
    # Challenges
    # ----------
    def get_challenge_state(self) -> Dict:
        state = self.data.get("challenges", {})
        return state if isinstance(state, dict) else {}

    def set_challenge_state(self, state: Dict) -> None:
        self.data["challenges"] = state if isinstance(state, dict) else {}
        self.save()

    # ------
    # Resets
    # ------
    def reset_mission_progress(self) -> None:
        profile = self._profile()
        profile["coins"] = 0
        profile["upgrades"] = _new_profile_data()["upgrades"]
        profile["ability_upgrades"] = _new_profile_data()["ability_upgrades"]
        profile["skill_unlocks"] = _new_profile_data()["skill_unlocks"]
        profile["locked_skin_id"] = None
        profile["stats"]["mission_best_wave"] = 0
        profile["checkpoints"]["mission"] = None
        self.save()

    def reset_free_roam_progress(self) -> None:
        profile = self._profile()
        profile["story_index"] = 0
        profile["skill_unlocks"] = _new_profile_data()["skill_unlocks"]
        profile["locked_skin_id"] = None
        profile["checkpoints"]["free_roam"] = None
        self.save()
