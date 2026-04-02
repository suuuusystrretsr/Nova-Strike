import math
import random

from ursina import Entity, Vec3, camera, clamp, color, destroy, held_keys, mouse, raycast, scene

from scripts.net_state import PlayerActionState, PlayerSyncState, Vec3State, WeaponSyncState
from scripts.weapon import Weapon, normalize_rarity, normalize_weapon_id, rarity_rank


TEAM_COLOR_OVERRIDES = {
    "team_a": color.rgb(96, 174, 255),
    "team_b": color.rgb(255, 116, 116),
}


class Player(Entity):
    HEADSHOT_DAMAGE_MULTIPLIER = 1.5

    def __init__(
        self,
        game_manager,
        skin,
        asset_loader,
        settings_manager,
        position=(0, 2, 0),
        local_controlled: bool = True,
        player_id: str = "player",
        team_id: str = "",
    ) -> None:
        super().__init__(
            parent=game_manager.world.root if game_manager.world else scene,
            position=position,
            collider="box",
            scale=(0.74, 1.86, 0.74),
        )
        self.game_manager = game_manager
        self.rng = getattr(game_manager, "rng", random)
        self.is_local_controlled = bool(local_controlled)
        self.player_id = str(player_id or "player")
        self.team_id = str(team_id or "")
        self.asset_loader = asset_loader
        self.settings_manager = settings_manager
        self.skin = skin
        self.collider_half_height = self.scale_y * 0.5
        self.headshot_height_ratio = 0.66

        # Visual root uses inverse scale so collider scaling does not stretch the model.
        self.visual_root = Entity(
            parent=self,
            scale=(
                1.0 / max(0.001, self.scale_x),
                1.0 / max(0.001, self.scale_y),
                1.0 / max(0.001, self.scale_z),
            ),
        )
        self.model_root = self.asset_loader.load_player_model(self.skin, parent=self.visual_root)
        self.model_root.scale = 0.92
        self._align_visual_to_collider()

        self.health_max_base = 100
        base_health_bonus = 0 if self._is_multiplayer_match() else self.game_manager.progression_manager.get_health_bonus()
        self.health_max = self.health_max_base + base_health_bonus
        self.health = float(self.health_max)
        self.alive = True

        self.base_walk_speed = 6.4
        self.base_sprint_speed = 9.8
        self.base_jump_force = 8.9
        self.walk_speed = self.base_walk_speed
        self.sprint_speed = self.base_sprint_speed
        self.jump_force = self.base_jump_force
        self.gravity = 23.5
        self.vertical_velocity = 0.0
        self.horizontal_velocity = Vec3(0, 0, 0)
        self.grounded = False
        self.ground_snap_tolerance = 0.7
        self.coyote_time = 0.12
        self.coyote_timer = 0.0
        self.jump_lock_timer = 0.0
        self.is_moving = False
        self.is_sprinting = False

        self.ability_id = self.skin.skin_id
        self.ability_active = False
        self.ability_timer = 0.0
        self.ability_cooldown_timer = 0.0
        self.ability_move_multiplier = 1.0
        self.is_invisible = False
        self.base_phantom_duration = 3.0
        self.base_phantom_cooldown = 18.0
        self.base_phantom_speed_multiplier = 1.65
        self.base_vanguard_duration = 5.0
        self.base_vanguard_cooldown = 30.0
        self.base_vanguard_speed_multiplier = 5.0
        self.base_striker_double_jump_cooldown = 15.0
        self.phantom_duration = self.base_phantom_duration
        self.phantom_cooldown = self.base_phantom_cooldown
        self.phantom_speed_multiplier = self.base_phantom_speed_multiplier
        self.vanguard_duration = self.base_vanguard_duration
        self.vanguard_cooldown = self.base_vanguard_cooldown
        self.vanguard_speed_multiplier = self.base_vanguard_speed_multiplier
        self.striker_double_jump_cooldown = self.base_striker_double_jump_cooldown
        self.striker_double_jump_timer = 0.0
        self.can_air_jump = True
        self.external_speed_multiplier = 1.0
        self.external_speed_timer = 0.0
        self.skill_effects = {}
        self.active_perks = {}
        self.perk_defs = {
            "lifesteal": {"label": "Lifesteal", "duration": 18.0},
            "ricochet": {"label": "Ricochet", "duration": 16.0},
            "haste": {"label": "Haste", "duration": 20.0},
            "fortify": {"label": "Fortify", "duration": 20.0},
        }
        self._perk_toast_timer = 0.0

        self.look_sensitivity = self.settings_manager.get_mouse_sensitivity()
        self.look_smoothness = 19.0
        self.look_speed_x = 188.0
        self.look_speed_y = 170.0
        self.smoothed_mouse_x = 0.0
        self.smoothed_mouse_y = 0.0
        self.pitch = 0.0
        self.camera_height = 1.6
        self.remote_input_state = PlayerActionState()
        self.remote_state_flags = {}
        self.network_target_position = Vec3(self.world_position)
        self.network_target_velocity = Vec3(0, 0, 0)
        self.network_target_rotation_y = float(self.rotation_y)
        self.network_target_pitch = float(self.pitch)
        self.network_interp_speed = 12.0
        self.network_last_timestamp = 0.0

        self.recoil_pitch = 0.0
        self.recoil_yaw = 0.0
        self.anim_time = 0.0
        self.anim_move_blend = 0.0
        self.footstep_timer = 0.0
        self.footstep_interval = 0.36
        self.max_weapon_slots = 5
        self._collision_ignores_cache = [self]
        self._collision_cache_timer = 0.0

        self.regen_delay = 4.0
        self.regen_timer = 0.0
        self.base_regen_rate = 11.0
        self.regen_rate = self.base_regen_rate
        self.refresh_skill_tree_bonuses(initial=True)

        self.weapons = [
            Weapon(owner=self, game_manager=self.game_manager, asset_loader=self.asset_loader, weapon_id="rifle", rarity="common"),
            Weapon(owner=self, game_manager=self.game_manager, asset_loader=self.asset_loader, weapon_id="shotgun", rarity="common"),
            Weapon(owner=self, game_manager=self.game_manager, asset_loader=self.asset_loader, weapon_id="pistol", rarity="common"),
        ]
        self.active_weapon_index = 0
        self.current_weapon.equip(True)
        self._apply_team_visual()
        self._stabilize_spawn()

    @property
    def current_weapon(self) -> Weapon:
        return self.weapons[self.active_weapon_index]

    def _is_multiplayer_match(self) -> bool:
        match_settings = getattr(self.game_manager, "match_settings", None)
        return bool(match_settings and getattr(match_settings, "is_multiplayer", False))

    def update(self) -> None:
        if not self.alive:
            return
        if self.game_manager.state != "playing":
            for weapon in self.weapons:
                if getattr(weapon, "view_model", None):
                    weapon.view_model.enabled = False
            return

        frame_dt = max(0.0, float(getattr(self.game_manager, "frame_dt", 1.0 / 60.0)))
        fixed_dt = max(1e-4, float(getattr(self.game_manager, "fixed_dt", 1.0 / 60.0)))
        sim_steps = int(getattr(self.game_manager, "simulation_steps", 1))

        if self.is_local_controlled and self.game_manager.ui_manager.map_open:
            for weapon in self.weapons:
                if getattr(weapon, "view_model", None):
                    weapon.view_model.enabled = False
            return

        self._collision_cache_timer -= frame_dt
        is_first_person = not self.game_manager.camera_controller or self.game_manager.camera_controller.mode == "first_person"

        if not self.is_local_controlled:
            for weapon in self.weapons:
                if getattr(weapon, "view_model", None):
                    weapon.view_model.enabled = False
            self._update_remote_interpolation(frame_dt)
            self._animate_model(frame_dt)
            return

        if self.is_local_controlled:
            self._update_look(frame_dt)

        for _ in range(sim_steps):
            self._update_ability_timers(fixed_dt)
            self._update_movement(fixed_dt)
            self._update_gravity(fixed_dt)
            self._update_regen(fixed_dt)
            self._handle_auto_fire()
            self._update_footsteps(fixed_dt)
            for weapon in self.weapons:
                weapon.fixed_update(fixed_dt)

        self._animate_model(frame_dt)
        for i, weapon in enumerate(self.weapons):
            weapon.render_update(frame_dt, allow_view=(i == self.active_weapon_index and is_first_person))

    def handle_input(self, key: str) -> None:
        if not self.is_local_controlled:
            return
        if not self.alive or self.game_manager.state != "playing":
            return
        if self.game_manager.ui_manager.map_open:
            return

        normalized_key = key.strip().lower()

        if normalized_key in ("space", "space down"):
            self._try_jump()
        elif normalized_key == "q":
            if self._is_multiplayer_match():
                return
            self._activate_ability()
        elif normalized_key == "r":
            self.current_weapon.start_reload()
        elif normalized_key == "left mouse down":
            self.current_weapon.trigger_pull()

    def switch_weapon(self, index: int) -> None:
        if index < 0 or index >= len(self.weapons):
            return
        if index == self.active_weapon_index:
            return
        self.current_weapon.equip(False)
        self.active_weapon_index = index
        self.current_weapon.equip(True)

    def acquire_weapon_drop(self, weapon_id: str, rarity: str, attachments=None) -> str:
        normalized_id = normalize_weapon_id(weapon_id)
        normalized_rarity = normalize_rarity(rarity)

        existing_index = None
        for idx, weapon in enumerate(self.weapons):
            if weapon.weapon_id == normalized_id:
                existing_index = idx
                break

        if existing_index is not None:
            existing = self.weapons[existing_index]
            new_attach_count = len(attachments) if isinstance(attachments, (list, tuple)) else 0
            existing_attach_count = len(getattr(existing, "attachments", []))
            is_strictly_better = rarity_rank(normalized_rarity) > rarity_rank(existing.rarity) or (
                rarity_rank(normalized_rarity) == rarity_rank(existing.rarity) and new_attach_count > existing_attach_count
            )
            if not is_strictly_better:
                ammo_bonus = max(2, existing.mag_size // 5)
                existing.add_reserve_ammo(ammo_bonus)
                return f"{existing.display_name} ammo +{ammo_bonus}"
            replacement = Weapon(
                owner=self,
                game_manager=self.game_manager,
                asset_loader=self.asset_loader,
                weapon_id=normalized_id,
                rarity=normalized_rarity,
                attachments=attachments,
            )
            replacement.reserve_ammo = max(existing.reserve_ammo, replacement.reserve_ammo)
            replacement.ammo_in_mag = replacement.mag_size
            old_name = existing.display_name
            self._replace_weapon_at(existing_index, replacement, equip_now=True)
            return f"Upgraded: {old_name} -> {replacement.display_name}"

        new_weapon = Weapon(
            owner=self,
            game_manager=self.game_manager,
            asset_loader=self.asset_loader,
            weapon_id=normalized_id,
            rarity=normalized_rarity,
            attachments=attachments,
        )
        if len(self.weapons) < self.max_weapon_slots:
            self.weapons.append(new_weapon)
            self.switch_weapon(len(self.weapons) - 1)
            attach_note = f" [{', '.join(new_weapon.attachment_labels)}]" if new_weapon.attachment_labels else ""
            return f"Picked up {new_weapon.display_name}{attach_note} (Slot {len(self.weapons)})"

        replaced_name = self.current_weapon.display_name
        self._replace_weapon_at(self.active_weapon_index, new_weapon, equip_now=True)
        return f"Replaced {replaced_name} with {new_weapon.display_name}"

    def _replace_weapon_at(self, index: int, new_weapon: Weapon, equip_now: bool) -> None:
        old_weapon = self.weapons[index]
        old_weapon.equip(False)
        old_weapon.destroy()
        self.weapons[index] = new_weapon
        if equip_now:
            self.active_weapon_index = index
            new_weapon.equip(True)

    def take_damage(self, amount: float, _source=None) -> None:
        if not self.alive:
            return
        if (not self.is_local_controlled) and getattr(getattr(self.game_manager, "match_settings", None), "is_multiplayer", False):
            return
        if self.rng.random() < self.get_dodge_chance():
            if self.is_local_controlled:
                self.game_manager.ui_manager.show_toast("Dodged!", duration=0.45)
            return
        final_damage = float(amount) * self.get_incoming_damage_multiplier()
        self.health = max(0.0, self.health - final_damage)
        self.regen_timer = self.regen_delay
        if self.is_local_controlled:
            self.game_manager.ui_manager.flash_damage()
        if self.is_local_controlled and self.game_manager.camera_controller:
            self.game_manager.camera_controller.add_shake(0.55)
        if self.health <= 0:
            self._die()

    def is_headshot(self, hit_point) -> bool:
        if hit_point is None:
            return False
        try:
            hit_y = float(hit_point.y)
        except Exception:
            return False
        threshold = float(self.world_y) + (float(self.collider_half_height) * float(self.headshot_height_ratio))
        return hit_y >= threshold

    def set_first_person(self, enabled: bool) -> None:
        if self.model_root:
            self.model_root.enabled = not enabled
        for weapon in self.weapons:
            if getattr(weapon, "view_model", None):
                weapon.view_model.enabled = enabled and weapon.active and self.game_manager.state == "playing"

    def apply_view_recoil(self, strength: float) -> None:
        self.recoil_pitch += 0.45 * strength
        self.recoil_yaw += 0.22 * strength

    def get_damage_multiplier(self) -> float:
        if self._is_multiplayer_match():
            mult = 1.0
        else:
            mult = self.game_manager.progression_manager.get_damage_multiplier()
        if self.has_perk("haste"):
            mult *= 1.08
        return mult

    def get_reload_multiplier(self) -> float:
        if self._is_multiplayer_match():
            mult = 1.0
        else:
            mult = self.game_manager.progression_manager.get_reload_multiplier()
        if self.has_perk("haste"):
            mult *= 0.9
        return mult

    def get_crit_chance(self) -> float:
        return max(0.0, min(0.65, float(self.skill_effects.get("crit_chance", 0.0))))

    def get_crit_multiplier(self) -> float:
        return 1.5 + float(self.skill_effects.get("crit_damage_mult", 0.0))

    def get_recoil_multiplier(self) -> float:
        return max(0.45, float(self.skill_effects.get("recoil_mult", 1.0)))

    def get_spread_multiplier(self) -> float:
        return max(0.5, float(self.skill_effects.get("spread_mult", 1.0)))

    def get_coin_multiplier(self) -> float:
        return max(1.0, 1.0 + float(self.skill_effects.get("coin_mult", 0.0)))

    def get_dodge_chance(self) -> float:
        return max(0.0, min(0.5, float(self.skill_effects.get("dodge_chance", 0.0))))

    def refresh_max_health_from_upgrades(self) -> None:
        self.refresh_skill_tree_bonuses()

    def refresh_skill_tree_bonuses(self, initial: bool = False) -> None:
        if self._is_multiplayer_match():
            self.skill_effects = {}
            self.walk_speed = self.base_walk_speed
            self.sprint_speed = self.base_sprint_speed
            self.jump_force = self.base_jump_force
            self.regen_rate = self.base_regen_rate
            self.phantom_duration = self.base_phantom_duration
            self.phantom_cooldown = self.base_phantom_cooldown
            self.phantom_speed_multiplier = self.base_phantom_speed_multiplier
            self.vanguard_duration = self.base_vanguard_duration
            self.vanguard_cooldown = self.base_vanguard_cooldown
            self.vanguard_speed_multiplier = self.base_vanguard_speed_multiplier
            self.striker_double_jump_cooldown = self.base_striker_double_jump_cooldown
            self._deactivate_active_ability()
            self.ability_cooldown_timer = 0.0
            self.striker_double_jump_timer = 0.0
            self.can_air_jump = True
            old_max = self.health_max
            self.health_max = float(self.health_max_base)
            if not initial and self.health_max > old_max:
                self.health += self.health_max - old_max
            self.health = min(self.health, self.health_max)
            return

        progression = self.game_manager.progression_manager
        self.skill_effects = progression.get_skill_effect_totals(self.skin.skin_id)

        speed_bonus = float(self.skill_effects.get("speed_mult", 0.0))
        sprint_bonus = float(self.skill_effects.get("sprint_mult", 0.0))
        self.walk_speed = self.base_walk_speed * (1.0 + speed_bonus)
        self.sprint_speed = self.base_sprint_speed * (1.0 + speed_bonus + sprint_bonus)
        self.jump_force = self.base_jump_force + float(self.skill_effects.get("jump_bonus", 0.0))
        self.regen_rate = self.base_regen_rate + float(self.skill_effects.get("regen_rate_bonus", 0.0))

        ability_cool_mult = progression.get_ability_cooldown_multiplier(self.ability_id)
        ability_cool_mult *= float(self.skill_effects.get("ability_cooldown_mult", 1.0))
        ability_dur_bonus = progression.get_ability_duration_bonus(self.ability_id) + float(self.skill_effects.get("ability_duration_bonus", 0.0))

        self.phantom_duration = self.base_phantom_duration + ability_dur_bonus
        self.phantom_cooldown = max(3.0, self.base_phantom_cooldown * ability_cool_mult)
        self.phantom_speed_multiplier = self.base_phantom_speed_multiplier + progression.get_ability_upgrade_level("phantom") * 0.05
        self.vanguard_duration = self.base_vanguard_duration + ability_dur_bonus
        self.vanguard_cooldown = max(10.0, self.base_vanguard_cooldown * ability_cool_mult)
        self.vanguard_speed_multiplier = self.base_vanguard_speed_multiplier + progression.get_ability_upgrade_level("vanguard") * 0.18
        self.striker_double_jump_cooldown = max(5.0, self.base_striker_double_jump_cooldown * ability_cool_mult)

        if not initial:
            old_max = self.health_max
            self.health_max = self.health_max_base + progression.get_health_bonus()
            if self.health_max > old_max:
                self.health += self.health_max - old_max
            self.health = min(self.health, self.health_max)

    def _align_visual_to_collider(self) -> None:
        foot_level = float(getattr(self.model_root, "foot_level", -1.22))
        model_scale_y = float(getattr(self.model_root, "scale_y", 1.0))
        desired_foot = -self.collider_half_height + 0.03
        self.model_root.y = desired_foot - (foot_level * model_scale_y)

    def _stabilize_spawn(self) -> None:
        base_x = float(self.x)
        base_y = float(self.y)
        base_z = float(self.z)
        ignore_entities = [self]
        if self.game_manager.world and hasattr(self.game_manager.world, "get_walkable_surfaces"):
            ignore_entities.extend(self.game_manager.world.get_walkable_surfaces())
        lateral_offsets = [
            Vec3(0, 0, 0),
            Vec3(1.4, 0, 0),
            Vec3(-1.4, 0, 0),
            Vec3(0, 0, 1.4),
            Vec3(0, 0, -1.4),
            Vec3(2.0, 0, 2.0),
            Vec3(-2.0, 0, 2.0),
            Vec3(2.0, 0, -2.0),
            Vec3(-2.0, 0, -2.0),
        ]
        for lateral in lateral_offsets:
            self.x = base_x + lateral.x
            self.z = base_z + lateral.z
            for y_offset in (0.0, 0.3, 0.6, 1.0, 1.4, 1.9, 2.5):
                self.y = base_y + y_offset
                if not self.intersects(ignore=ignore_entities).hit:
                    self._snap_to_ground(force=True)
                    return
        self.x = base_x
        self.z = base_z
        self.y = base_y + 2.5
        self._snap_to_ground(force=True)

    def _die(self) -> None:
        self.alive = False
        self._deactivate_active_ability()
        self.disable()
        for weapon in self.weapons:
            if getattr(weapon, "view_model", None):
                weapon.view_model.enabled = False
        if self.is_local_controlled:
            self.game_manager.on_player_died()

    def set_remote_action_state(self, action_state: PlayerActionState) -> None:
        if not isinstance(action_state, PlayerActionState):
            return
        self.remote_input_state = action_state

    def _sample_action_state(self) -> PlayerActionState:
        if not self.is_local_controlled:
            return self.remote_input_state
        return PlayerActionState(
            move_x=float(held_keys["d"] - held_keys["a"]),
            move_z=float(held_keys["w"] - held_keys["s"]),
            sprint=bool(held_keys["shift"]),
            jump=bool(held_keys["space"]),
            fire=bool(held_keys["left mouse"]),
            reload=bool(self.current_weapon.reloading),
            ability=bool(self.ability_active),
            aim=bool(getattr(self.game_manager.camera_controller, "mode", "first_person") == "first_person"),
        )

    def _update_remote_interpolation(self, dt: float) -> None:
        blend = min(1.0, max(0.0, dt * self.network_interp_speed))
        to_target = self.network_target_position - self.world_position
        self.world_position += to_target * blend

        yaw_target = float(self.network_target_rotation_y)
        yaw_delta = ((yaw_target - float(self.rotation_y) + 180.0) % 360.0) - 180.0
        self.rotation_y += yaw_delta * blend
        self.pitch += (float(self.network_target_pitch) - float(self.pitch)) * blend

        self.horizontal_velocity = Vec3(self.network_target_velocity.x, 0.0, self.network_target_velocity.z)
        self.vertical_velocity = float(self.network_target_velocity.y)
        self.grounded = bool(self.remote_state_flags.get("grounded", True))
        self.is_sprinting = bool(self.remote_input_state.sprint) and self.horizontal_velocity.length() > 0.2
        self.is_moving = self.horizontal_velocity.length() > 0.2

    def _update_look(self, dt: float) -> None:
        self.look_sensitivity = self.settings_manager.get_mouse_sensitivity()
        raw_x = mouse.velocity[0] * self.look_sensitivity
        raw_y = mouse.velocity[1] * self.look_sensitivity
        blend = min(1.0, dt * self.look_smoothness)
        self.smoothed_mouse_x += (raw_x - self.smoothed_mouse_x) * blend
        self.smoothed_mouse_y += (raw_y - self.smoothed_mouse_y) * blend

        self.recoil_pitch = max(0.0, self.recoil_pitch - 8.0 * dt)
        self.recoil_yaw = self.recoil_yaw * (1.0 - min(1.0, 9.0 * dt))
        self.rotation_y += (self.smoothed_mouse_x * self.look_speed_x) + self.recoil_yaw
        self.pitch = clamp(self.pitch - self.smoothed_mouse_y * self.look_speed_y - self.recoil_pitch, -85, 85)

    def _update_movement(self, dt: float) -> None:
        action_state = self._sample_action_state()
        input_x = action_state.move_x
        input_z = action_state.move_z
        movement = Vec3(input_x, 0, input_z)

        self.is_moving = movement.length() > 0.01
        if movement.length() > 1:
            movement = movement.normalized()

        local_direction = self.right * movement.x + self.forward * movement.z
        local_direction.y = 0
        if local_direction.length() > 0:
            local_direction = local_direction.normalized()

        self.is_sprinting = self.is_moving and self.grounded and bool(action_state.sprint)
        speed = self.sprint_speed if self.is_sprinting else self.walk_speed
        speed *= self.ability_move_multiplier
        speed *= self.external_speed_multiplier
        speed *= self.get_speed_multiplier()
        self.horizontal_velocity = local_direction * speed
        step = local_direction * speed * dt
        self._move_with_collisions(step, self._get_movement_collision_ignores())

    def _move_with_collisions(self, move: Vec3, ignore_entities) -> None:
        if move.length() <= 0.0001:
            return
        sub_steps = max(1, int(max(abs(move.x), abs(move.z)) / 0.14) + 1)
        step = move / sub_steps

        for _ in range(sub_steps):
            start_x = self.x
            start_z = self.z
            self.x += step.x
            if self.intersects(ignore=ignore_entities).hit:
                self.x = start_x
            self.z += step.z
            if self.intersects(ignore=ignore_entities).hit:
                self.z = start_z

    def _get_movement_collision_ignores(self):
        if self._collision_cache_timer <= 0:
            ignores = [self]
            if self.game_manager.world and hasattr(self.game_manager.world, "get_walkable_surfaces"):
                ignores.extend(self.game_manager.world.get_walkable_surfaces())
            # Keep player movement smooth around dynamic actors.
            ignores.extend(self.game_manager.enemies)
            ignores.extend(self.game_manager.npcs)
            ignores.extend(self.game_manager.pickups)
            for other_player in getattr(self.game_manager, "players", {}).values():
                if not other_player or other_player is self:
                    continue
                ignores.append(other_player)
            self._collision_ignores_cache = ignores
            self._collision_cache_timer = 0.2
        return self._collision_ignores_cache

    def _world_root(self):
        if self.game_manager.world and self.game_manager.world.root:
            return self.game_manager.world.root
        return scene

    def _ground_probe(self, extra_distance: float = 1.25):
        origin = self.world_position + Vec3(0, self.collider_half_height + 0.35, 0)
        return raycast(
            origin,
            Vec3(0, -1, 0),
            distance=self.collider_half_height + extra_distance,
            ignore=[self],
            traverse_target=self._world_root(),
        )

    def _snap_to_ground(self, force: bool = False) -> bool:
        floor_y = self.game_manager.world.ground_level if self.game_manager.world else 0.0
        floor_target = floor_y + self.collider_half_height
        ground_hit = self._ground_probe(extra_distance=1.7)
        if ground_hit.hit:
            target_y = max(floor_target, ground_hit.world_point.y + self.collider_half_height)
            can_snap = force or (self.vertical_velocity <= 0 and (self.y - target_y) <= self.ground_snap_tolerance)
            if can_snap:
                self.y = target_y
                self.vertical_velocity = 0.0
                self.grounded = True
                self.can_air_jump = True
                return True

        if self.y <= floor_target:
            self.y = floor_target
            self.vertical_velocity = 0.0
            self.grounded = True
            self.can_air_jump = True
            return True
        return False

    def _update_gravity(self, dt: float) -> None:
        self.jump_lock_timer = max(0.0, self.jump_lock_timer - dt)
        if self.jump_lock_timer <= 0.0:
            snapped = self._snap_to_ground(force=False)
            if snapped and self.vertical_velocity <= 0:
                self.coyote_timer = self.coyote_time
                return

        self.coyote_timer = max(0.0, self.coyote_timer - dt)
        self.grounded = False
        if self.vertical_velocity > 0:
            head_origin = self.world_position + Vec3(0, self.collider_half_height - 0.06, 0)
            head_hit = raycast(
                head_origin,
                Vec3(0, 1, 0),
                distance=max(0.2, self.vertical_velocity * dt + 0.06),
                ignore=[self],
                traverse_target=self._world_root(),
            )
            if head_hit.hit:
                self.vertical_velocity = 0.0

        self.vertical_velocity -= self.gravity * dt
        self.y += self.vertical_velocity * dt
        if self.jump_lock_timer <= 0.0 or self.vertical_velocity <= 0.0:
            self._snap_to_ground(force=False)

    def _try_jump(self) -> None:
        if not self.grounded:
            self._snap_to_ground(force=False)
            if not self.grounded:
                near_ground = self._ground_probe(extra_distance=1.0)
                if near_ground.hit and self.vertical_velocity <= 2.5:
                    self.grounded = True
                    self.coyote_timer = max(self.coyote_timer, 0.08)
        can_ground_jump = self.grounded or (self.coyote_timer > 0.0)
        if can_ground_jump:
            self.vertical_velocity = self.jump_force
            self.grounded = False
            self.coyote_timer = 0.0
            self.jump_lock_timer = 0.1
            self.can_air_jump = True
            self.y += 0.03
            return
        if (not self._is_multiplayer_match()) and self.ability_id == "striker" and self.can_air_jump and self.striker_double_jump_timer <= 0:
            self.vertical_velocity = self.jump_force * 0.94
            self.can_air_jump = False
            self.jump_lock_timer = 0.06
            self.striker_double_jump_timer = self.striker_double_jump_cooldown
            self.asset_loader.play_sound("ui_click", volume=0.11, pitch=1.12)
            self.game_manager.ui_manager.show_toast("Striker: Double Jump")
            if self.game_manager.challenge_manager:
                self.game_manager.challenge_manager.on_ability_cast(1)

    def _update_regen(self, dt: float) -> None:
        if self.health >= self.health_max:
            return
        if self.regen_timer > 0:
            self.regen_timer -= dt
            return
        self.health = min(self.health_max, self.health + self.regen_rate * dt)

    def _animate_model(self, dt: float) -> None:
        part_nodes = getattr(self.model_root, "part_nodes", None)
        if not part_nodes:
            return

        target_blend = 1.0 if self.is_moving and self.grounded else 0.0
        blend_speed = 9.0 if target_blend > self.anim_move_blend else 6.0
        self.anim_move_blend += (target_blend - self.anim_move_blend) * min(1.0, dt * blend_speed)

        pace = 2.2 + (8.0 * self.anim_move_blend * (1.1 if self.is_sprinting else 1.0))
        self.anim_time += dt * pace
        stride = math.sin(self.anim_time)
        stride_cos = math.cos(self.anim_time)
        idle_breath = math.sin(self.anim_time * 0.42)

        arm_amp = 4.0 + 22.0 * self.anim_move_blend
        leg_amp = 6.0 + 28.0 * self.anim_move_blend
        bob = 0.015 * idle_breath + 0.03 * self.anim_move_blend * abs(stride)

        torso = part_nodes.get("torso")
        chest = part_nodes.get("chest")
        head = part_nodes.get("head")
        left_arm = part_nodes.get("left_arm")
        right_arm = part_nodes.get("right_arm")
        left_leg = part_nodes.get("left_leg")
        right_leg = part_nodes.get("right_leg")
        left_shoulder = part_nodes.get("left_shoulder")
        right_shoulder = part_nodes.get("right_shoulder")

        if torso:
            torso.y = 0.34 + bob
            torso.rotation_z = 2.4 * self.anim_move_blend * stride * 0.4
        if chest:
            chest.rotation_x = -1.4 + (1.8 * idle_breath) + (3.2 * self.anim_move_blend * stride * 0.45)
            chest.rotation_y = 2.6 * self.anim_move_blend * stride_cos * 0.3
        if head:
            head.rotation_y = 2.2 * idle_breath + (2.1 * self.anim_move_blend * stride_cos * 0.2)
            head.rotation_x = -1.0 + (self.recoil_pitch * 0.35)
        if left_leg:
            left_leg.rotation_x = leg_amp * stride
        if right_leg:
            right_leg.rotation_x = -leg_amp * stride
        if left_arm:
            left_arm.rotation_x = -(arm_amp * stride) - (self.recoil_pitch * 0.16)
        if right_arm:
            right_arm.rotation_x = (arm_amp * stride) - (self.recoil_pitch * 0.28)
        if left_shoulder:
            left_shoulder.rotation_z = -3.6 * self.anim_move_blend * stride
        if right_shoulder:
            right_shoulder.rotation_z = 3.6 * self.anim_move_blend * stride

    def _handle_auto_fire(self) -> None:
        action_state = self._sample_action_state()
        if bool(action_state.fire) and self.current_weapon.automatic:
            self.current_weapon.trigger_pull()

    def _update_footsteps(self, dt: float) -> None:
        if not self.grounded or not self.is_moving:
            self.footstep_timer = 0.0
            return
        interval = self.footstep_interval * (0.76 if self.is_sprinting else 1.0)
        self.footstep_timer -= dt
        if self.footstep_timer > 0:
            return
        self.footstep_timer = interval
        self.asset_loader.play_sound("footstep", volume=0.08 if self.is_sprinting else 0.06)

    def _activate_ability(self) -> None:
        if self._is_multiplayer_match():
            return
        if self.ability_id == "phantom":
            self._activate_phantom()
        elif self.ability_id == "vanguard":
            self._activate_vanguard()
        elif self.ability_id == "striker":
            if self.striker_double_jump_timer > 0:
                self.game_manager.ui_manager.show_toast(f"Double Jump cooldown {self.striker_double_jump_timer:.1f}s", duration=0.75)
            else:
                self.game_manager.ui_manager.show_toast("Double Jump ready: press SPACE mid-air", duration=0.9)

    def _activate_phantom(self) -> None:
        if self._is_multiplayer_match():
            return
        if self.ability_active or self.ability_cooldown_timer > 0:
            return
        self.ability_active = True
        self.ability_timer = self.phantom_duration
        self.ability_cooldown_timer = self.phantom_cooldown
        self.is_invisible = True
        self.ability_move_multiplier = self.phantom_speed_multiplier
        if self.model_root:
            self.model_root.alpha = 0.28
        self.asset_loader.play_sound("ui_click", volume=0.12, pitch=0.88)
        self.game_manager.ui_manager.show_toast("Phantom: Cloak engaged")
        if self.game_manager.challenge_manager:
            self.game_manager.challenge_manager.on_ability_cast(1)

    def _activate_vanguard(self) -> None:
        if self._is_multiplayer_match():
            return
        if self.ability_active or self.ability_cooldown_timer > 0:
            return
        self.ability_active = True
        self.ability_timer = self.vanguard_duration
        self.ability_cooldown_timer = self.vanguard_cooldown
        self.ability_move_multiplier = self.vanguard_speed_multiplier
        self.asset_loader.play_sound("ui_click", volume=0.12, pitch=0.95)
        self.game_manager.ui_manager.show_toast("Vanguard: Overdrive")
        if self.game_manager.challenge_manager:
            self.game_manager.challenge_manager.on_ability_cast(1)

    def _deactivate_active_ability(self) -> None:
        self.ability_active = False
        self.ability_timer = 0.0
        self.ability_move_multiplier = 1.0
        if self.is_invisible:
            self.is_invisible = False
            if self.model_root:
                self.model_root.alpha = 1.0

    def _update_ability_timers(self, dt: float) -> None:
        self._perk_toast_timer = max(0.0, self._perk_toast_timer - dt)
        if self._is_multiplayer_match():
            self.ability_cooldown_timer = 0.0
            self.striker_double_jump_timer = 0.0
            if self.ability_active or self.is_invisible or self.ability_move_multiplier != 1.0:
                self._deactivate_active_ability()
        else:
            if self.ability_cooldown_timer > 0:
                self.ability_cooldown_timer = max(0.0, self.ability_cooldown_timer - dt)
            if self.striker_double_jump_timer > 0:
                self.striker_double_jump_timer = max(0.0, self.striker_double_jump_timer - dt)
        if self.external_speed_timer > 0:
            self.external_speed_timer = max(0.0, self.external_speed_timer - dt)
            if self.external_speed_timer <= 0:
                self.external_speed_multiplier = 1.0
        for perk_id in list(self.active_perks.keys()):
            self.active_perks[perk_id] = max(0.0, self.active_perks[perk_id] - dt)
            if self.active_perks[perk_id] <= 0:
                del self.active_perks[perk_id]
        if not self.ability_active:
            return
        self.ability_timer -= dt
        if self.ability_timer <= 0:
            self._deactivate_active_ability()

    def apply_external_speed_boost(self, multiplier: float, duration: float) -> None:
        multiplier = max(1.0, float(multiplier))
        duration = max(0.0, float(duration))
        if duration <= 0:
            return
        self.external_speed_multiplier = max(self.external_speed_multiplier, multiplier)
        self.external_speed_timer = max(self.external_speed_timer, duration)

    def is_detectable(self) -> bool:
        return self.alive and not self.is_invisible

    def get_ability_status_line(self) -> str:
        if self._is_multiplayer_match():
            return "Disabled in Multiplayer"
        if self.ability_id == "phantom":
            if self.ability_active:
                return f"Phantom Cloak: {self.ability_timer:.1f}s"
            if self.ability_cooldown_timer > 0:
                return f"Phantom Cloak CD: {self.ability_cooldown_timer:.1f}s"
            return "Phantom Cloak: READY (Q)"
        if self.ability_id == "vanguard":
            if self.ability_active:
                return f"Overdrive: {self.ability_timer:.1f}s"
            if self.ability_cooldown_timer > 0:
                return f"Overdrive CD: {self.ability_cooldown_timer:.1f}s"
            return "Overdrive: READY (Q)"
        if self.striker_double_jump_timer > 0:
            return f"Double Jump CD: {self.striker_double_jump_timer:.1f}s"
        return "Double Jump: READY"

    def has_perk(self, perk_id: str) -> bool:
        return self.active_perks.get(perk_id, 0.0) > 0.0

    def add_perk(self, perk_id: str, duration: float = 0.0) -> None:
        if perk_id not in self.perk_defs:
            return
        base_duration = self.perk_defs[perk_id]["duration"]
        duration = max(base_duration, float(duration) if duration > 0 else base_duration)
        self.active_perks[perk_id] = max(self.active_perks.get(perk_id, 0.0), duration)
        if self.is_local_controlled and self._perk_toast_timer <= 0:
            self.game_manager.ui_manager.show_toast(f"Perk Activated: {self.perk_defs[perk_id]['label']}")
            self._perk_toast_timer = 0.8

    def get_speed_multiplier(self) -> float:
        return 1.22 if self.has_perk("haste") else 1.0

    def get_fire_rate_multiplier(self) -> float:
        perk_mult = 1.18 if self.has_perk("haste") else 1.0
        return perk_mult * (1.0 + float(self.skill_effects.get("fire_rate_mult", 0.0)))

    def get_incoming_damage_multiplier(self) -> float:
        incoming = 0.72 if self.has_perk("fortify") else 1.0
        incoming *= max(0.45, 1.0 - float(self.skill_effects.get("damage_reduction", 0.0)))
        return incoming

    def get_active_perk_labels(self):
        labels = []
        for perk_id, timer in self.active_perks.items():
            if timer <= 0:
                continue
            label = self.perk_defs.get(perk_id, {}).get("label", perk_id.title())
            labels.append(f"{label} {timer:.0f}s")
        return labels

    def on_damage_dealt(self, target, damage: float, hit_point, _weapon) -> None:
        lifesteal_ratio = float(self.skill_effects.get("lifesteal_bonus", 0.0))
        if self.has_perk("lifesteal"):
            lifesteal_ratio += 0.18
        if lifesteal_ratio > 0:
            heal = max(1.0, float(damage) * lifesteal_ratio)
            self.health = min(self.health_max, self.health + heal)
        if self.has_perk("ricochet") and self.rng.random() < 0.26:
            nearby = None
            nearest = 999.0
            for enemy in self.game_manager.enemies:
                if enemy is target or not enemy or getattr(enemy, "dead", False):
                    continue
                d = (enemy.world_position - hit_point).length()
                if d < 7.2 and d < nearest:
                    nearest = d
                    nearby = enemy
            if nearby:
                ricochet_damage = max(2.0, float(damage) * 0.42)
                nearby.take_damage(ricochet_damage, self)
                self.game_manager.ui_manager.show_hitmarker()
                self.asset_loader.play_sound("hitmarker", volume=0.12, pitch=1.18)

    def get_fire_basis(self):
        if self.is_local_controlled and self.game_manager and self.game_manager.camera_controller:
            return (
                camera.world_position + camera.forward * 0.4,
                camera.forward.normalized(),
                camera.right,
                camera.up,
            )
        forward = self.forward.normalized() if self.forward.length() > 0.0001 else Vec3(0, 0, 1)
        right = self.right.normalized() if self.right.length() > 0.0001 else Vec3(1, 0, 0)
        up = Vec3(0, 1, 0)
        origin = self.world_position + Vec3(0, self.camera_height, 0) + forward * 0.4
        return origin, forward, right, up

    def build_action_state(self) -> PlayerActionState:
        sampled = self._sample_action_state()
        return PlayerActionState(
            move_x=float(sampled.move_x),
            move_z=float(sampled.move_z),
            sprint=bool(self.is_sprinting),
            jump=bool(sampled.jump),
            fire=bool(sampled.fire),
            reload=bool(self.current_weapon.reloading),
            ability=bool(self.ability_active) and not self._is_multiplayer_match(),
            aim=bool(getattr(self.game_manager.camera_controller, "mode", "first_person") == "first_person"),
        )

    def get_velocity_vector(self) -> Vec3:
        return Vec3(self.horizontal_velocity.x, self.vertical_velocity, self.horizontal_velocity.z)

    def build_network_state(self, player_id: str, sequence: int, timestamp: float) -> PlayerSyncState:
        velocity = self.get_velocity_vector()
        return PlayerSyncState(
            player_id=player_id,
            sequence=int(sequence),
            timestamp=float(timestamp),
            position=Vec3State(float(self.x), float(self.y), float(self.z)),
            velocity=Vec3State(float(velocity.x), float(velocity.y), float(velocity.z)),
            rotation_y=float(self.rotation_y),
            pitch=float(self.pitch),
            health=float(self.health),
            health_max=float(self.health_max),
            alive=bool(self.alive),
            active_weapon_index=int(self.active_weapon_index),
            skin_id=str(self.skin.skin_id),
            team_id=str(self.team_id or ""),
            weapons=[
                WeaponSyncState(
                    weapon_id=weapon.weapon_id,
                    rarity=weapon.rarity,
                    ammo_in_mag=weapon.ammo_in_mag,
                    reserve_ammo=weapon.reserve_ammo,
                    reloading=weapon.reloading,
                )
                for weapon in self.weapons
            ],
            actions=self.build_action_state(),
            state_flags={
                "grounded": bool(self.grounded),
                "invisible": bool(self.is_invisible),
                "ability_active": bool(self.ability_active),
            },
        )

    def apply_network_state(self, state: PlayerSyncState) -> None:
        if not state:
            return
        self.network_last_timestamp = max(self.network_last_timestamp, float(state.timestamp))
        self.network_target_position = Vec3(state.position.x, state.position.y, state.position.z)
        self.network_target_velocity = Vec3(state.velocity.x, state.velocity.y, state.velocity.z)
        self.network_target_rotation_y = float(state.rotation_y)
        self.network_target_pitch = float(state.pitch)
        self.health_max = max(1.0, float(state.health_max))
        self.health = max(0.0, min(self.health_max, float(state.health)))
        self.alive = bool(state.alive)
        self.remote_state_flags = dict(state.state_flags or {})
        if self.is_local_controlled and str(state.team_id or ""):
            self.team_id = str(state.team_id)
            self._apply_team_visual()
        elif (not self.is_local_controlled) and str(state.team_id or "") and str(state.team_id) != self.team_id:
            self.team_id = str(state.team_id)
            self._apply_team_visual()
        self.set_remote_action_state(state.actions)

    def _apply_team_visual(self) -> None:
        if not self.model_root:
            return
        team_key = str(self.team_id or "").lower()
        tint = TEAM_COLOR_OVERRIDES.get(team_key)
        nodes = getattr(self.model_root, "part_nodes", {})
        left_shoulder = nodes.get("left_shoulder") if isinstance(nodes, dict) else None
        right_shoulder = nodes.get("right_shoulder") if isinstance(nodes, dict) else None
        visor = nodes.get("helmet") if isinstance(nodes, dict) else None

        if tint and left_shoulder and right_shoulder:
            left_shoulder.color = tint.tint(-0.08)
            right_shoulder.color = tint.tint(-0.08)
            if visor:
                visor.color = tint.tint(0.05)
            return

        if tint and not (left_shoulder and right_shoulder):
            self.model_root.color = tint.tint(-0.05)
            return

    def export_runtime_state(self) -> dict:
        velocity = self.get_velocity_vector()
        return {
            "position": [float(self.x), float(self.y), float(self.z)],
            "rotation_y": float(self.rotation_y),
            "pitch": float(self.pitch),
            "health": float(self.health),
            "velocity": [float(velocity.x), float(velocity.y), float(velocity.z)],
            "ability_cooldown": float(self.ability_cooldown_timer),
            "striker_jump_cd": float(self.striker_double_jump_timer),
            "active_weapon_index": int(self.active_weapon_index),
            "weapons": [weapon.get_save_data() for weapon in self.weapons],
        }

    def restore_runtime_state(self, state: dict) -> None:
        if not isinstance(state, dict):
            return
        position = state.get("position", [])
        if isinstance(position, list) and len(position) == 3:
            self.position = Vec3(float(position[0]), float(position[1]), float(position[2]))
        self.rotation_y = float(state.get("rotation_y", self.rotation_y))
        self.pitch = float(state.get("pitch", self.pitch))
        self.health = max(1.0, min(self.health_max, float(state.get("health", self.health_max))))
        velocity = state.get("velocity", [])
        if isinstance(velocity, list) and len(velocity) == 3:
            try:
                self.horizontal_velocity = Vec3(float(velocity[0]), 0.0, float(velocity[2]))
                self.vertical_velocity = float(velocity[1])
            except (TypeError, ValueError):
                self.horizontal_velocity = Vec3(0, 0, 0)
                self.vertical_velocity = 0.0
        else:
            self.horizontal_velocity = Vec3(0, 0, 0)
            self.vertical_velocity = 0.0
        self.ability_cooldown_timer = max(0.0, float(state.get("ability_cooldown", 0.0)))
        self.striker_double_jump_timer = max(0.0, float(state.get("striker_jump_cd", 0.0)))

        weapon_states = state.get("weapons", [])
        if isinstance(weapon_states, list) and weapon_states:
            for weapon in self.weapons:
                weapon.destroy()
            self.weapons = []
            for weapon_state in weapon_states[: self.max_weapon_slots]:
                if not isinstance(weapon_state, dict):
                    continue
                restored = Weapon(
                    owner=self,
                    game_manager=self.game_manager,
                    asset_loader=self.asset_loader,
                    weapon_id=weapon_state.get("weapon_id", "rifle"),
                    rarity=weapon_state.get("rarity", "common"),
                    attachments=weapon_state.get("attachments", []),
                )
                restored.ammo_in_mag = max(0, min(restored.mag_size, int(weapon_state.get("ammo_in_mag", restored.mag_size))))
                restored.reserve_ammo = max(0, min(restored.reserve_cap, int(weapon_state.get("reserve_ammo", restored.reserve_ammo))))
                self.weapons.append(restored)
            if not self.weapons:
                self.weapons = [
                    Weapon(owner=self, game_manager=self.game_manager, asset_loader=self.asset_loader, weapon_id="rifle", rarity="common")
                ]
        self.active_weapon_index = max(0, min(len(self.weapons) - 1, int(state.get("active_weapon_index", 0))))
        for i, weapon in enumerate(self.weapons):
            weapon.equip(i == self.active_weapon_index)
        # Robustly recover from stale checkpoints that may place the player inside geometry.
        self._stabilize_spawn()

    def destroy(self) -> None:
        self._deactivate_active_ability()
        for weapon in self.weapons:
            weapon.destroy()
        destroy(self)
