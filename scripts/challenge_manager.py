from datetime import datetime
from hashlib import sha256
from typing import Callable, Dict, List, Optional


class ChallengeManager:
    def __init__(self, progression_manager, notify: Optional[Callable[[str], None]] = None) -> None:
        self.progression_manager = progression_manager
        self.notify = notify or (lambda _msg: None)
        self._load_or_create_challenges()

    def _load_or_create_challenges(self) -> bool:
        now = datetime.now()
        daily_key = now.strftime("%Y-%m-%d")
        iso_year, iso_week, _ = now.isocalendar()
        weekly_key = f"{iso_year}-W{iso_week:02d}"

        state = self.progression_manager.get_challenge_state()
        profiles = state.get("profiles", {})
        if not isinstance(profiles, dict):
            profiles = {}
        profile_id = self.progression_manager.get_active_profile_id()
        profile_state = profiles.get(profile_id, {})
        if not isinstance(profile_state, dict):
            profile_state = {}
        changed = False

        daily = profile_state.get("daily")
        if not isinstance(daily, dict) or daily.get("cycle_key") != daily_key:
            daily = self._create_daily_challenge(daily_key)
            changed = True

        weekly = profile_state.get("weekly")
        if not isinstance(weekly, dict) or weekly.get("cycle_key") != weekly_key:
            weekly = self._create_weekly_challenge(weekly_key)
            changed = True

        next_profile_state = {"daily": daily, "weekly": weekly}
        if profiles.get(profile_id) != next_profile_state:
            profiles[profile_id] = next_profile_state
            state["profiles"] = profiles
            changed = True

        if changed:
            self.progression_manager.set_challenge_state(state)
        return changed

    def _create_daily_challenge(self, cycle_key: str) -> Dict:
        variants = [
            {"title": "Daily Hunt", "event": "enemy_kills", "target": 22, "reward": 85},
            {"title": "Daily Payday", "event": "coins_collected", "target": 120, "reward": 90},
            {"title": "Daily Operative", "event": "ability_casts", "target": 10, "reward": 88},
            {"title": "Daily Arms", "event": "weapon_pickups", "target": 6, "reward": 92},
        ]
        variant = variants[self._stable_bucket(cycle_key, len(variants))]
        return {
            "cycle_key": cycle_key,
            "title": variant["title"],
            "event": variant["event"],
            "target": int(variant["target"]),
            "reward": int(variant["reward"]),
            "progress": 0,
            "completed": False,
            "claimed": False,
        }

    def _create_weekly_challenge(self, cycle_key: str) -> Dict:
        variants = [
            {"title": "Weekly Breaker", "event": "boss_kills", "target": 4, "reward": 320},
            {"title": "Weekly Frontline", "event": "mission_completions", "target": 3, "reward": 290},
            {"title": "Weekly Purge", "event": "enemy_kills", "target": 140, "reward": 300},
        ]
        variant = variants[self._stable_bucket("weekly:" + cycle_key, len(variants))]
        return {
            "cycle_key": cycle_key,
            "title": variant["title"],
            "event": variant["event"],
            "target": int(variant["target"]),
            "reward": int(variant["reward"]),
            "progress": 0,
            "completed": False,
            "claimed": False,
        }

    def _stable_bucket(self, seed: str, modulo: int) -> int:
        if modulo <= 1:
            return 0
        digest = sha256(seed.encode("utf-8")).hexdigest()
        return int(digest[:12], 16) % modulo

    def _get_active_state(self):
        state = self.progression_manager.get_challenge_state()
        profiles = state.get("profiles", {})
        if not isinstance(profiles, dict):
            profiles = {}
        profile_id = self.progression_manager.get_active_profile_id()
        profile_state = profiles.get(profile_id, {})
        if not isinstance(profile_state, dict):
            now = datetime.now()
            daily_key = now.strftime("%Y-%m-%d")
            iso_year, iso_week, _ = now.isocalendar()
            weekly_key = f"{iso_year}-W{iso_week:02d}"
            profile_state = {"daily": self._create_daily_challenge(daily_key), "weekly": self._create_weekly_challenge(weekly_key)}
            profiles[profile_id] = profile_state
            state["profiles"] = profiles
            self.progression_manager.set_challenge_state(state)
        return state, profiles, profile_id, profile_state

    def _award_if_completed(self, entry: Dict, kind: str) -> None:
        if entry.get("completed") and not entry.get("claimed"):
            reward = int(entry.get("reward", 0))
            if reward > 0:
                self.progression_manager.add_coins(reward)
            entry["claimed"] = True
            title = entry.get("title", kind.title())
            self.notify(f"{title} complete: +{reward} coins")

    def _increment_event(self, event_name: str, amount: int = 1) -> None:
        if amount <= 0:
            return
        self._load_or_create_challenges()
        state, profiles, profile_id, profile_state = self._get_active_state()
        changed = False
        for kind in ("daily", "weekly"):
            entry = profile_state.get(kind, {})
            if not isinstance(entry, dict):
                continue
            if entry.get("event") != event_name:
                continue
            if entry.get("completed", False):
                continue
            target = max(1, int(entry.get("target", 1)))
            progress = int(entry.get("progress", 0)) + int(amount)
            entry["progress"] = min(target, progress)
            if entry["progress"] >= target:
                entry["completed"] = True
            self._award_if_completed(entry, kind)
            changed = True
        if changed:
            profiles[profile_id] = profile_state
            state["profiles"] = profiles
            self.progression_manager.set_challenge_state(state)

    def on_enemy_killed(self, amount: int = 1) -> None:
        self._increment_event("enemy_kills", amount)

    def on_coin_collected(self, amount: int = 1) -> None:
        self._increment_event("coins_collected", amount)

    def on_boss_killed(self, amount: int = 1) -> None:
        self._increment_event("boss_kills", amount)

    def on_mission_completed(self, amount: int = 1) -> None:
        self._increment_event("mission_completions", amount)

    def on_ability_cast(self, amount: int = 1) -> None:
        self._increment_event("ability_casts", amount)

    def on_weapon_pickup(self, amount: int = 1) -> None:
        self._increment_event("weapon_pickups", amount)

    def get_tracker_lines(self) -> List[str]:
        self._load_or_create_challenges()
        _state, _profiles, _profile_id, profile_state = self._get_active_state()
        lines: List[str] = []
        for kind, prefix in (("daily", "Daily"), ("weekly", "Weekly")):
            entry = profile_state.get(kind, {})
            if not isinstance(entry, dict):
                continue
            title = entry.get("title", prefix)
            progress = int(entry.get("progress", 0))
            target = int(entry.get("target", 1))
            status = "Done" if entry.get("completed", False) else f"{progress}/{target}"
            lines.append(f"{prefix}: {title} ({status})")
        return lines[:2]
