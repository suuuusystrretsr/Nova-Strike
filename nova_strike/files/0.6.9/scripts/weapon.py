import math
import random

from ursina import Entity, Vec3, camera, color, destroy, lerp, raycast, scene

from scripts.bullet import Bullet


WEAPON_LIBRARY = {
    "rifle": {
        "display_name": "VX Rifle",
        "damage": 13,
        "fire_rate": 10.0,
        "mag_size": 32,
        "reserve_ammo": 220,
        "reload_time": 1.55,
        "range": 150,
        "automatic": True,
        "spread": 1.4,
        "pellets": 1,
        "recoil_pitch": 2.0,
        "recoil_yaw": 0.95,
        "view_kick": 0.9,
        "muzzle_color": color.rgba(120, 220, 255, 200),
        "tracer_color": color.rgba(170, 220, 255, 120),
        "sound": "rifle_shot",
        "projectile": False,
        "projectile_speed": 0,
    },
    "shotgun": {
        "display_name": "Marauder Shotgun",
        "damage": 11,
        "fire_rate": 1.25,
        "mag_size": 8,
        "reserve_ammo": 54,
        "reload_time": 2.1,
        "range": 65,
        "automatic": False,
        "spread": 7.5,
        "pellets": 7,
        "recoil_pitch": 4.8,
        "recoil_yaw": 1.6,
        "view_kick": 1.9,
        "muzzle_color": color.rgba(255, 194, 128, 220),
        "tracer_color": color.rgba(255, 188, 128, 115),
        "sound": "shotgun_shot",
        "projectile": False,
        "projectile_speed": 0,
    },
    "pistol": {
        "display_name": "Sidearm Pistol",
        "damage": 24,
        "fire_rate": 4.4,
        "mag_size": 14,
        "reserve_ammo": 98,
        "reload_time": 1.25,
        "range": 105,
        "automatic": False,
        "spread": 1.9,
        "pellets": 1,
        "recoil_pitch": 2.9,
        "recoil_yaw": 1.2,
        "view_kick": 1.2,
        "muzzle_color": color.rgba(255, 214, 146, 205),
        "tracer_color": color.rgba(255, 210, 165, 105),
        "sound": "pistol_shot",
        "projectile": True,
        "projectile_speed": 68,
    },
    "smg": {
        "display_name": "Wasp SMG",
        "damage": 8,
        "fire_rate": 15.4,
        "mag_size": 38,
        "reserve_ammo": 280,
        "reload_time": 1.38,
        "range": 95,
        "automatic": True,
        "spread": 2.2,
        "pellets": 1,
        "recoil_pitch": 1.35,
        "recoil_yaw": 0.75,
        "view_kick": 0.62,
        "muzzle_color": color.rgba(145, 235, 255, 215),
        "tracer_color": color.rgba(165, 228, 255, 110),
        "sound": "rifle_shot",
        "projectile": False,
        "projectile_speed": 0,
    },
    "sniper": {
        "display_name": "Longshot Sniper",
        "damage": 58,
        "fire_rate": 0.85,
        "mag_size": 6,
        "reserve_ammo": 42,
        "reload_time": 2.45,
        "range": 220,
        "automatic": False,
        "spread": 0.35,
        "pellets": 1,
        "recoil_pitch": 7.0,
        "recoil_yaw": 1.8,
        "view_kick": 2.2,
        "muzzle_color": color.rgba(210, 236, 255, 230),
        "tracer_color": color.rgba(190, 228, 255, 155),
        "sound": "pistol_shot",
        "projectile": False,
        "projectile_speed": 0,
    },
    "lmg": {
        "display_name": "Bulldog LMG",
        "damage": 14,
        "fire_rate": 8.3,
        "mag_size": 60,
        "reserve_ammo": 320,
        "reload_time": 2.65,
        "range": 145,
        "automatic": True,
        "spread": 2.8,
        "pellets": 1,
        "recoil_pitch": 2.4,
        "recoil_yaw": 1.2,
        "view_kick": 1.15,
        "muzzle_color": color.rgba(255, 212, 152, 220),
        "tracer_color": color.rgba(255, 206, 145, 125),
        "sound": "rifle_shot",
        "projectile": False,
        "projectile_speed": 0,
    },
    # Backward aliases to keep compatibility with older saves/loadouts.
    "pulse_rifle": {"alias": "rifle"},
    "plasma_launcher": {"alias": "shotgun"},
}

RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]
RARITY_LABELS = {
    "common": "Common",
    "uncommon": "Uncommon",
    "rare": "Rare",
    "epic": "Epic",
    "legendary": "Legendary",
}
RARITY_COLORS = {
    "common": color.rgb(198, 206, 216),
    "uncommon": color.rgb(112, 222, 140),
    "rare": color.rgb(88, 176, 255),
    "epic": color.rgb(188, 120, 255),
    "legendary": color.rgb(255, 196, 86),
}
RARITY_DAMAGE_MULT = {"common": 1.0, "uncommon": 1.11, "rare": 1.24, "epic": 1.42, "legendary": 1.63}
RARITY_FIRE_RATE_MULT = {"common": 1.0, "uncommon": 1.02, "rare": 1.04, "epic": 1.07, "legendary": 1.1}
RARITY_RELOAD_MULT = {"common": 1.0, "uncommon": 0.97, "rare": 0.92, "epic": 0.86, "legendary": 0.8}
RARITY_SPREAD_MULT = {"common": 1.0, "uncommon": 0.97, "rare": 0.92, "epic": 0.86, "legendary": 0.8}
RARITY_RECOIL_MULT = {"common": 1.0, "uncommon": 0.95, "rare": 0.89, "epic": 0.82, "legendary": 0.76}
RARITY_MAG_BONUS = {"common": 0, "uncommon": 2, "rare": 4, "epic": 7, "legendary": 11}
RARITY_ATTACHMENT_COUNT = {"common": 0, "uncommon": 1, "rare": 1, "epic": 2, "legendary": 3}

ATTACHMENT_LIBRARY = {
    "scope": {
        "label": "Scope",
        "weapon_types": {"rifle", "sniper", "lmg", "smg", "pistol"},
        "damage_mult": 1.06,
        "spread_mult": 0.78,
        "reload_mult": 1.0,
        "fire_rate_mult": 0.97,
        "recoil_mult": 0.88,
        "mag_bonus": 0,
    },
    "silencer": {
        "label": "Silencer",
        "weapon_types": {"rifle", "smg", "pistol"},
        "damage_mult": 0.95,
        "spread_mult": 0.86,
        "reload_mult": 1.0,
        "fire_rate_mult": 1.04,
        "recoil_mult": 0.9,
        "mag_bonus": 0,
    },
    "extended_mag": {
        "label": "Extended Mag",
        "weapon_types": {"rifle", "smg", "lmg", "shotgun", "pistol"},
        "damage_mult": 1.0,
        "spread_mult": 1.02,
        "reload_mult": 1.08,
        "fire_rate_mult": 1.0,
        "recoil_mult": 1.0,
        "mag_bonus": 7,
    },
    "stabilizer": {
        "label": "Stabilizer",
        "weapon_types": {"rifle", "smg", "lmg", "sniper"},
        "damage_mult": 1.0,
        "spread_mult": 0.82,
        "reload_mult": 1.0,
        "fire_rate_mult": 1.0,
        "recoil_mult": 0.72,
        "mag_bonus": 0,
    },
    "drum": {
        "label": "Drum",
        "weapon_types": {"lmg", "smg", "rifle"},
        "damage_mult": 1.0,
        "spread_mult": 1.05,
        "reload_mult": 1.18,
        "fire_rate_mult": 0.94,
        "recoil_mult": 1.08,
        "mag_bonus": 18,
    },
}


def normalize_weapon_id(weapon_id: str) -> str:
    if weapon_id in WEAPON_LIBRARY and "alias" not in WEAPON_LIBRARY[weapon_id]:
        return weapon_id
    alias = WEAPON_LIBRARY.get(weapon_id, {}).get("alias", "")
    if alias in WEAPON_LIBRARY and "alias" not in WEAPON_LIBRARY[alias]:
        return alias
    return "rifle"


def normalize_rarity(rarity: str) -> str:
    r = str(rarity or "").strip().lower()
    if r not in RARITY_LABELS:
        return "common"
    return r


def rarity_rank(rarity: str) -> int:
    return RARITY_ORDER.index(normalize_rarity(rarity))


def normalize_attachment_ids(weapon_id: str, attachment_ids) -> list:
    if not isinstance(attachment_ids, (list, tuple)):
        return []
    valid = []
    for attachment_id in attachment_ids:
        if attachment_id not in ATTACHMENT_LIBRARY:
            continue
        if weapon_id not in ATTACHMENT_LIBRARY[attachment_id]["weapon_types"]:
            continue
        if attachment_id not in valid:
            valid.append(attachment_id)
    return valid


def roll_attachments(weapon_id: str, rarity: str, rng=None) -> list:
    count = RARITY_ATTACHMENT_COUNT.get(normalize_rarity(rarity), 0)
    if count <= 0:
        return []
    pool = [
        attachment_id
        for attachment_id, cfg in ATTACHMENT_LIBRARY.items()
        if weapon_id in cfg["weapon_types"]
    ]
    if not pool:
        return []
    active_rng = rng if rng else random
    active_rng.shuffle(pool)
    return pool[: min(count, len(pool))]


class Weapon:
    def __init__(
        self,
        owner,
        game_manager,
        asset_loader,
        weapon_id: str,
        rarity: str = "common",
        attachments=None,
    ) -> None:
        self.owner = owner
        self.game_manager = game_manager
        self.asset_loader = asset_loader
        self.rng = getattr(game_manager, "rng", random)

        self.weapon_id = normalize_weapon_id(weapon_id)
        self.rarity = normalize_rarity(rarity)
        self.config = WEAPON_LIBRARY[self.weapon_id]
        self.base_display_name = self.config["display_name"]
        self.rarity_label = RARITY_LABELS[self.rarity]
        self.rarity_color = RARITY_COLORS[self.rarity]
        self.attachments = normalize_attachment_ids(self.weapon_id, attachments)
        if not self.attachments:
            self.attachments = roll_attachments(self.weapon_id, self.rarity, rng=self.rng)
        self.attachment_labels = [ATTACHMENT_LIBRARY[a]["label"] for a in self.attachments]
        attachment_suffix = f" +{len(self.attachments)}A" if self.attachments else ""
        self.display_name = f"{self.rarity_label} {self.base_display_name}{attachment_suffix}"

        damage_mult = RARITY_DAMAGE_MULT[self.rarity]
        fire_rate_mult = RARITY_FIRE_RATE_MULT[self.rarity]
        reload_mult = RARITY_RELOAD_MULT[self.rarity]
        spread_mult = RARITY_SPREAD_MULT[self.rarity]
        recoil_mult = RARITY_RECOIL_MULT[self.rarity]
        mag_bonus = RARITY_MAG_BONUS[self.rarity]
        for attachment_id in self.attachments:
            attachment = ATTACHMENT_LIBRARY.get(attachment_id, {})
            damage_mult *= float(attachment.get("damage_mult", 1.0))
            fire_rate_mult *= float(attachment.get("fire_rate_mult", 1.0))
            reload_mult *= float(attachment.get("reload_mult", 1.0))
            spread_mult *= float(attachment.get("spread_mult", 1.0))
            recoil_mult *= float(attachment.get("recoil_mult", 1.0))
            mag_bonus += int(attachment.get("mag_bonus", 0))

        self.damage = self.config["damage"] * damage_mult
        self.fire_rate = self.config["fire_rate"] * fire_rate_mult
        self.mag_size = int(self.config["mag_size"] + mag_bonus)
        reserve_base = int(self.config["reserve_ammo"])
        self.reserve_cap = int(reserve_base + (mag_bonus * max(1, reserve_base // max(1, self.config["mag_size"]))))
        self.range = self.config["range"] * (1.04 if self.weapon_id == "sniper" else 1.0)
        self.reload_time = max(0.3, self.config["reload_time"] * reload_mult)
        self.automatic = self.config["automatic"]
        self.spread = max(0.08, self.config["spread"] * spread_mult)
        self.pellets = self.config["pellets"]
        self.projectile = self.config["projectile"]
        self.projectile_speed = self.config["projectile_speed"]
        self.recoil_pitch_amount = self.config["recoil_pitch"] * recoil_mult
        self.recoil_yaw_amount = self.config["recoil_yaw"] * recoil_mult

        self.ammo_in_mag = self.mag_size
        self.reserve_ammo = self.reserve_cap
        self.reload_timer = 0.0
        self.fire_cooldown = 0.0
        self.reloading = False
        self.active = False

        self.view_model = self.asset_loader.load_weapon_model(
            self.weapon_id,
            parent=camera,
            rarity=self.rarity,
            attachments=self.attachments,
        )
        self.view_model.enabled = False
        self.view_model.position = (0.33, -0.29, 0.58)
        self.view_model.rotation = (9, 194, 0)
        self.bob_time = 0.0
        self.idle_time = self.rng.uniform(0, 7)
        self.shot_anim = 0.0
        self.recoil_pitch = 0.0
        self.recoil_yaw = 0.0
        self.recoil_roll = 0.0
        self.reload_blend = 0.0

    def equip(self, enabled: bool) -> None:
        self.active = enabled
        self.view_model.enabled = enabled and self.game_manager.state == "playing"

    def is_better_than(self, other: "Weapon") -> bool:
        return rarity_rank(self.rarity) > rarity_rank(other.rarity)

    def add_reserve_ammo(self, amount: int) -> None:
        if amount <= 0:
            return
        self.reserve_ammo = min(self.reserve_cap, self.reserve_ammo + int(amount))

    def get_save_data(self) -> dict:
        return {
            "weapon_id": self.weapon_id,
            "rarity": self.rarity,
            "attachments": list(self.attachments),
            "ammo_in_mag": int(self.ammo_in_mag),
            "reserve_ammo": int(self.reserve_ammo),
        }

    def fixed_update(self, dt: float) -> None:
        dt = max(1e-5, float(dt))
        self.fire_cooldown = max(0.0, self.fire_cooldown - dt)
        if self.reloading:
            self.reload_timer -= dt
            self.reload_blend = min(1.0, self.reload_blend + dt * 3.2)
            if self.reload_timer <= 0:
                self._finish_reload()
        else:
            self.reload_blend = max(0.0, self.reload_blend - dt * 4.0)

    def render_update(self, frame_dt: float, allow_view: bool = True) -> None:
        dt = max(0.0, float(frame_dt))
        is_view_enabled = self.active and allow_view and self.game_manager.state == "playing"
        self.view_model.enabled = is_view_enabled
        if not is_view_enabled:
            return

        self.idle_time += dt
        self.shot_anim = max(0.0, self.shot_anim - dt * 12.5)
        self.recoil_pitch = lerp(self.recoil_pitch, 0.0, min(1.0, dt * 13.0))
        self.recoil_yaw = lerp(self.recoil_yaw, 0.0, min(1.0, dt * 11.2))
        self.recoil_roll = lerp(self.recoil_roll, 0.0, min(1.0, dt * 10.5))
        self._animate_weapon_parts()
        self._update_viewmodel_pose(dt)

    def trigger_pull(self) -> bool:
        if not self.active:
            return False
        if self.reloading or self.fire_cooldown > 0:
            return False
        if self.ammo_in_mag <= 0:
            self.start_reload()
            return False

        self.ammo_in_mag -= 1
        runtime_fire_rate = self.fire_rate
        if hasattr(self.owner, "get_fire_rate_multiplier"):
            runtime_fire_rate *= max(0.1, float(self.owner.get_fire_rate_multiplier()))
        self.fire_cooldown = 1.0 / max(0.01, runtime_fire_rate)
        self.shot_anim = 1.0

        recoil_mult = float(self.owner.get_recoil_multiplier()) if hasattr(self.owner, "get_recoil_multiplier") else 1.0
        spread_mult = float(self.owner.get_spread_multiplier()) if hasattr(self.owner, "get_spread_multiplier") else 1.0
        crit_chance = float(self.owner.get_crit_chance()) if hasattr(self.owner, "get_crit_chance") else 0.0
        crit_multiplier = float(self.owner.get_crit_multiplier()) if hasattr(self.owner, "get_crit_multiplier") else 1.5

        self.recoil_pitch += self.recoil_pitch_amount * recoil_mult
        self.recoil_yaw += self.rng.uniform(-self.recoil_yaw_amount, self.recoil_yaw_amount) * recoil_mult
        self.recoil_roll += self.rng.uniform(-1.0, 1.0) * (0.9 + self.config["view_kick"] * 0.35)

        self._spawn_muzzle_flash()
        self._play_shot_sound()
        self.game_manager.on_weapon_fired(self.config["view_kick"] * 0.22)
        self.owner.apply_view_recoil(self.config["view_kick"])

        origin, forward_dir, right_dir, up_dir = self._resolve_fire_basis()
        hit_registered = False
        base_damage = self.damage * self.owner.get_damage_multiplier()
        if self.projectile:
            bullet_direction = self._apply_spread(
                forward_dir,
                self.spread * spread_mult * 0.8,
                right_vector=right_dir,
                up_vector=up_dir,
            )
            projectile_damage = base_damage
            if self.rng.random() < crit_chance:
                projectile_damage *= crit_multiplier
            Bullet(
                game_manager=self.game_manager,
                owner=self.owner,
                origin=origin,
                direction=bullet_direction,
                speed=self.projectile_speed,
                damage=projectile_damage,
                bullet_color=self.rarity_color,
            )
        else:
            for _ in range(self.pellets):
                pellet_dir = self._apply_spread(
                    forward_dir,
                    self.spread * spread_mult,
                    right_vector=right_dir,
                    up_vector=up_dir,
                )
                if self._hitscan_fire(origin, pellet_dir, base_damage, crit_chance, crit_multiplier):
                    hit_registered = True

            if hit_registered:
                self.game_manager.ui_manager.show_hitmarker()
                self.asset_loader.play_sound("hitmarker", volume=0.16, pitch=self.rng.uniform(0.95, 1.05))
        return True

    def start_reload(self) -> bool:
        if self.reloading:
            return False
        if self.ammo_in_mag >= self.mag_size:
            return False
        if self.reserve_ammo <= 0:
            return False
        self.reloading = True
        self.reload_timer = self.reload_time * self.owner.get_reload_multiplier()
        self._play_reload_sound()
        return True

    def _finish_reload(self) -> None:
        needed = self.mag_size - self.ammo_in_mag
        refill = min(needed, self.reserve_ammo)
        self.ammo_in_mag += refill
        self.reserve_ammo -= refill
        self.reloading = False

    def _hitscan_fire(self, origin: Vec3, direction: Vec3, base_damage: float, crit_chance: float, crit_multiplier: float) -> bool:
        world_root = self.game_manager.world.root if self.game_manager.world and self.game_manager.world.root else scene
        hit = raycast(
            origin,
            direction,
            distance=self.range,
            ignore=[self.owner],
            traverse_target=world_root,
        )
        end_point = origin + direction * self.range
        did_hit_enemy = False

        if hit.hit:
            end_point = hit.world_point
            if hasattr(hit.entity, "take_damage"):
                owner_team = str(getattr(self.owner, "team_id", "") or "")
                target_team = str(getattr(hit.entity, "team_id", "") or "")
                if owner_team and target_team and owner_team == target_team:
                    self._spawn_impact(hit.world_point, hit.entity)
                    self._spawn_tracer(origin, end_point)
                    return False
                scaled_damage = float(base_damage)
                if self.rng.random() < crit_chance:
                    scaled_damage *= crit_multiplier
                    self.game_manager.ui_manager.show_hitmarker()
                if getattr(hit.entity, "is_boss", False) and hit.world_point.y > (hit.entity.world_y + 1.25):
                    scaled_damage *= 1.55
                    self.game_manager.ui_manager.show_hitmarker()
                hit.entity.take_damage(scaled_damage, self.owner)
                self.game_manager.on_player_hit_enemy(hit.entity, hit.world_point)
                if hasattr(self.owner, "on_damage_dealt"):
                    self.owner.on_damage_dealt(hit.entity, scaled_damage, hit.world_point, self)
                did_hit_enemy = True
            self._spawn_impact(hit.world_point, hit.entity)

        self._spawn_tracer(origin, end_point)
        return did_hit_enemy

    def _spawn_impact(self, world_point: Vec3, hit_entity=None) -> None:
        world_parent = self.game_manager.world.root if self.game_manager.world and self.game_manager.world.root else scene
        impact = Entity(
            parent=world_parent,
            model="sphere",
            scale=0.1,
            position=world_point,
            color=self.rarity_color,
        )
        impact.animate_scale(0.01, duration=0.08)
        destroy(impact, delay=0.09)
        for _ in range(3):
            shard = Entity(
                parent=world_parent,
                model="cube",
                scale=(0.02, 0.02, 0.02),
                position=world_point,
                color=self.rarity_color.tint(0.1),
            )
            scatter = Vec3(self.rng.uniform(-0.2, 0.2), self.rng.uniform(0.04, 0.22), self.rng.uniform(-0.2, 0.2))
            shard.animate_position(world_point + scatter, duration=0.08)
            shard.animate_scale(0.001, duration=0.1)
            destroy(shard, delay=0.11)
        self._play_impact_sound(hit_entity)

    def _spawn_muzzle_flash(self) -> None:
        part_nodes = getattr(self.view_model, "part_nodes", {})
        muzzle = part_nodes.get("muzzle") if part_nodes else None
        muzzle_pos = (0.18, -0.15, 0.56) if not muzzle else (muzzle.x, muzzle.y, muzzle.z + 0.12)
        flash = Entity(
            parent=self.view_model,
            model="quad",
            position=muzzle_pos,
            rotation=(0, 0, self.rng.uniform(-20, 20)),
            scale=(0.08, 0.12),
            color=self.config["muzzle_color"].tint(0.05),
        )
        flash.animate_scale((0.001, 0.001), duration=0.07)
        destroy(flash, delay=0.08)

    def _update_viewmodel_pose(self, frame_dt: float) -> None:
        bob_x = 0.0
        bob_y = 0.0
        if self.owner and self.owner.is_moving:
            self.bob_time += frame_dt * (10.5 if self.owner.is_sprinting else 8.7)
            bob_x = 0.013 * math.sin(self.bob_time)
            bob_y = 0.009 * math.cos(self.bob_time * 2.0)
        else:
            self.bob_time = 0.0
        idle_x = 0.003 * math.sin(self.idle_time * 1.6)
        idle_y = 0.003 * math.cos(self.idle_time * 1.4)
        reload_drop = -0.12 * self.reload_blend
        self.view_model.position = (
            0.33 + bob_x + idle_x + (self.recoil_yaw * 0.0022),
            -0.29 + bob_y + idle_y + reload_drop,
            0.58 - (self.recoil_pitch * 0.0024),
        )
        self.view_model.rotation_x = 9 + self.recoil_pitch + (8.0 * self.reload_blend)
        self.view_model.rotation_y = 194 + self.recoil_yaw - (3.5 * self.reload_blend)
        self.view_model.rotation_z = self.recoil_roll + (10.0 * self.reload_blend)

    def _animate_weapon_parts(self) -> None:
        part_nodes = getattr(self.view_model, "part_nodes", {})
        if not part_nodes:
            return

        slide = part_nodes.get("slide")
        if slide:
            if not hasattr(slide, "_base_z"):
                slide._base_z = slide.z
            slide.z = slide._base_z - (self.shot_anim * 0.05) - (0.02 * self.reload_blend)
            slide.y = 0.045 + (0.002 * math.sin(self.idle_time * 8.0))

        coil = part_nodes.get("coil")
        if coil:
            if not hasattr(coil, "_base_scale"):
                coil._base_scale = coil.scale
            coil.scale = coil._base_scale * (1.0 + self.shot_anim * 0.16)
            coil.color = self.rarity_color.tint(0.05)

        scope = part_nodes.get("scope")
        if scope:
            if not hasattr(scope, "_base_y"):
                scope._base_y = scope.y
            scope.y = scope._base_y + (0.002 * math.sin(self.idle_time * 6.5))
            scope.rotation_x = 3.0 * self.reload_blend

        magazine = part_nodes.get("magazine")
        if magazine:
            if not hasattr(magazine, "_base_y"):
                magazine._base_y = magazine.y
            magazine.y = magazine._base_y - (0.06 * self.reload_blend)
            magazine.rotation_z = -15.0 * self.reload_blend

    def _spawn_tracer(self, start: Vec3, end: Vec3) -> None:
        world_parent = self.game_manager.world.root if self.game_manager.world and self.game_manager.world.root else scene
        segment = end - start
        length = max(0.01, segment.length())
        tracer = Entity(
            parent=world_parent,
            model="cube",
            color=self.config["tracer_color"],
            scale=(0.011, 0.011, length),
            position=(start + end) * 0.5,
        )
        tracer.look_at(end)
        tracer.animate_scale((0.001, 0.001, 0.001), duration=0.06)
        destroy(tracer, delay=0.07)

    def _apply_spread(self, direction: Vec3, spread_deg: float, right_vector: Vec3 = None, up_vector: Vec3 = None) -> Vec3:
        spread_factor = spread_deg * 0.01
        right = right_vector if right_vector is not None else camera.right
        up = up_vector if up_vector is not None else camera.up
        spread_offset = right * self.rng.uniform(-spread_factor, spread_factor)
        spread_offset += up * self.rng.uniform(-spread_factor, spread_factor)
        return (direction + spread_offset).normalized()

    def _resolve_fire_basis(self):
        if hasattr(self.owner, "get_fire_basis"):
            basis = self.owner.get_fire_basis()
            if isinstance(basis, tuple) and len(basis) == 4:
                origin, forward, right, up = basis
                return Vec3(origin), Vec3(forward).normalized(), Vec3(right), Vec3(up)
        origin = camera.world_position + camera.forward * 0.4
        return origin, camera.forward.normalized(), camera.right, camera.up

    def _play_shot_sound(self) -> None:
        shotgun_like = self.weapon_id in ("shotgun",)
        sniper_like = self.weapon_id in ("sniper",)
        volume = 0.24 if not shotgun_like else 0.3
        if sniper_like:
            volume = 0.32
        self.asset_loader.play_sound(
            self.config["sound"],
            volume=volume,
            pitch=self.rng.uniform(0.96, 1.04),
        )

    def _play_reload_sound(self) -> None:
        self.asset_loader.play_sound("reload", volume=0.2)

    def _play_impact_sound(self, hit_entity) -> None:
        if hit_entity and hasattr(hit_entity, "take_damage"):
            self.asset_loader.play_sound("hitmarker", volume=0.11, pitch=self.rng.uniform(0.9, 1.02))
            return
        material = getattr(hit_entity, "material_type", "solid")
        if material == "metal":
            self.asset_loader.play_sound("ui_click", volume=0.08, pitch=self.rng.uniform(0.82, 0.95))
        elif material == "wood":
            self.asset_loader.play_sound("reload", volume=0.07, pitch=self.rng.uniform(1.25, 1.42))
        elif material == "flesh":
            self.asset_loader.play_sound("hitmarker", volume=0.1, pitch=self.rng.uniform(0.82, 0.93))
        else:
            self.asset_loader.play_sound("ui_click", volume=0.07, pitch=self.rng.uniform(1.08, 1.22))

    def destroy(self) -> None:
        if self.view_model:
            destroy(self.view_model)
            self.view_model = None
