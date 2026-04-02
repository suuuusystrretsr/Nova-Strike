import math
import random

from ursina import Entity, Vec3, color, destroy, distance, raycast, scene


class Enemy(Entity):
    def __init__(
        self,
        game_manager,
        position,
        behavior_mode: str = "mission",
        variant: str = "",
        is_boss: bool = False,
        boss_tier: int = 1,
    ) -> None:
        self.rng = getattr(game_manager, "rng", random)
        self.variant = variant if variant in ("raider", "stalker", "brute") else self.rng.choice(["raider", "stalker", "brute"])
        self.is_boss = bool(is_boss)
        self.boss_tier = max(1, int(boss_tier))
        variant_scale = {"raider": 1.0, "stalker": 0.92, "brute": 1.12}.get(self.variant, 1.0)
        scale_variation = self.rng.uniform(0.95, 1.07)
        collider_scale = variant_scale * scale_variation
        if self.is_boss:
            collider_scale *= 1.55 + (0.07 * self.boss_tier)

        super().__init__(
            parent=game_manager.world.root if game_manager.world else scene,
            position=position,
            collider="box",
            scale=(0.76 * collider_scale, 1.78 * collider_scale, 0.76 * collider_scale),
        )
        self.game_manager = game_manager
        self.team_id = "hostile"
        self.behavior_mode = behavior_mode
        self.collider_half_height = self.scale_y * 0.5
        self.visual_foot_offset = 0.08

        self.visual_root = Entity(
            parent=self,
            scale=(
                1.0 / max(0.001, self.scale_x),
                1.0 / max(0.001, self.scale_y),
                1.0 / max(0.001, self.scale_z),
            ),
        )
        self.model_root = self.game_manager.asset_loader.load_enemy_model(parent=self.visual_root, variant=self.variant)
        self.model_root.scale *= 1.16 if self.is_boss else 0.93
        self._align_visual_to_collider()
        self.model_root.material_type = "flesh"

        if self.is_boss:
            self._attach_boss_ornaments()
            self.display_name = f"Warbringer Mk.{self.boss_tier}"
        else:
            self.display_name = {"raider": "Raider", "stalker": "Stalker", "brute": "Brute"}.get(self.variant, "Raider")

        base_health = {"raider": 78, "stalker": 62, "brute": 110}.get(self.variant, 78)
        if self.is_boss:
            base_health = int(base_health * (4.2 + self.boss_tier * 0.75))
        self.max_health = base_health
        self.health = float(self.max_health)
        self.dead = False

        self.roam_speed = {"raider": 2.45, "stalker": 3.0, "brute": 1.95}.get(self.variant, 2.45)
        self.chase_speed = {"raider": 4.0, "stalker": 4.5, "brute": 3.25}.get(self.variant, 4.0)
        self.attack_range = {"raider": 2.2, "stalker": 1.95, "brute": 2.5}.get(self.variant, 2.2)
        self.detect_range = 34.0 if behavior_mode == "free_roam" else 30.0
        self.attack_damage = {"raider": 11.0, "stalker": 9.0, "brute": 15.0}.get(self.variant, 11.0)
        self.attack_cooldown = self.rng.uniform(0.85, 1.25)
        if self.is_boss:
            self.roam_speed *= 1.05
            self.chase_speed *= 1.06 + (0.05 * self.boss_tier)
            self.attack_range += 0.9
            self.detect_range += 14.0
            self.attack_damage *= 1.85 + (0.17 * self.boss_tier)
            self.attack_cooldown = 1.15
        self.attack_timer = self.rng.uniform(0.05, 0.6)

        self.vertical_velocity = 0.0
        self.gravity = 19.0
        self.grounded = False
        self.ground_snap_tolerance = 0.65

        self.state = "roam"
        self.roam_target = self._pick_roam_target()
        self.last_seen_player_pos = Vec3(self.roam_target)
        self.decision_interval = self.rng.uniform(0.11, 0.2)
        if self.is_boss:
            self.decision_interval = 0.08
        self.decision_timer = self.rng.uniform(0.02, self.decision_interval)
        self.current_target = self.roam_target
        self._collision_ignores_cache = [self]
        self._collision_cache_timer = 0.0

        self.is_moving = False
        self.anim_time = self.rng.uniform(0, 6.28)
        self.anim_move_blend = 0.0
        self.attack_anim = 0.0
        self.hit_reaction = 0.0
        self.dodge_timer = 0.0
        self.dodge_direction = 0.0
        self.dodge_cooldown = self.rng.uniform(0.75, 1.4)

        self.boss_phase = 1
        self.boss_ability_timer = self.rng.uniform(4.2, 6.8)
        self.boss_enrage = 0.0

        self.coin_reward = {"raider": 7, "stalker": 9, "brute": 15}.get(self.variant, 8)
        self.drop_weapon_pool = {
            "raider": ("smg", "rifle", "pistol"),
            "stalker": ("sniper", "pistol", "smg"),
            "brute": ("lmg", "shotgun", "rifle"),
        }.get(self.variant, ("rifle", "pistol"))
        if self.is_boss:
            self.coin_reward = int(45 + self.boss_tier * 22)
            self.drop_weapon_pool = ("rifle", "shotgun", "smg", "sniper", "lmg", "pistol")
        self._stabilize_spawn()
        self._snap_to_ground(force=True)

    def _attach_boss_ornaments(self) -> None:
        self.boss_core = Entity(
            parent=self.model_root,
            model="sphere",
            scale=0.48,
            y=1.56,
            color=color.rgba(255, 200, 130, 210),
        )
        self.boss_halo = Entity(
            parent=self.model_root,
            model="cube",
            scale=(1.4, 0.08, 1.4),
            y=1.45,
            color=color.rgba(255, 150, 95, 120),
        )
        self.boss_spike_left = Entity(
            parent=self.model_root,
            model="cube",
            scale=(0.16, 0.66, 0.16),
            x=-0.54,
            y=1.15,
            color=color.rgb(210, 132, 98),
        )
        self.boss_spike_right = Entity(
            parent=self.model_root,
            model="cube",
            scale=(0.16, 0.66, 0.16),
            x=0.54,
            y=1.15,
            color=color.rgb(210, 132, 98),
        )

    def update(self) -> None:
        if self.dead or self.game_manager.state != "playing":
            return

        player = self.game_manager.get_enemy_target_for(self) if hasattr(self.game_manager, "get_enemy_target_for") else None
        if not player:
            player = self.game_manager.get_local_player() if hasattr(self.game_manager, "get_local_player") else None
        if not player or not player.alive:
            return

        frame_dt = max(0.0, float(getattr(self.game_manager, "frame_dt", 1.0 / 60.0)))
        fixed_dt = max(1e-4, float(getattr(self.game_manager, "fixed_dt", 1.0 / 60.0)))
        sim_steps = int(getattr(self.game_manager, "simulation_steps", 1))

        for _ in range(sim_steps):
            self.anim_time += fixed_dt
            self.attack_anim = max(0.0, self.attack_anim - fixed_dt * 4.6)
            self.hit_reaction = max(0.0, self.hit_reaction - fixed_dt * 5.4)
            self.attack_timer -= fixed_dt
            self.decision_timer -= fixed_dt
            self.dodge_timer = max(0.0, self.dodge_timer - fixed_dt)
            self.dodge_cooldown = max(0.0, self.dodge_cooldown - fixed_dt)
            self._collision_cache_timer -= fixed_dt

            if self.is_boss:
                self._update_boss_state(fixed_dt, player)

            self._update_vertical(fixed_dt)

            if self.decision_timer <= 0:
                self.decision_timer = self.decision_interval
                self._refresh_behavior(player)

            if self.state == "attack":
                self._face_target(player.world_position)
                self._attack(player)
                self.is_moving = False
            elif self.state in ("chase", "search"):
                self._face_target(self.current_target)
                if not self.is_boss:
                    self._attempt_dodge(player, fixed_dt)
                self.is_moving = self._move_towards(self.current_target, self.chase_speed, fixed_dt)
            else:
                self._roam(fixed_dt)

        self._animate_model(frame_dt if frame_dt > 0 else fixed_dt)

    def _update_boss_state(self, dt: float, player) -> None:
        health_ratio = self.health / max(1.0, self.max_health)
        new_phase = 1 if health_ratio > 0.66 else 2 if health_ratio > 0.33 else 3
        if new_phase != self.boss_phase:
            self.boss_phase = new_phase
            self.boss_enrage = 0.35 * (self.boss_phase - 1)
            self.game_manager.ui_manager.show_toast(f"Boss Enraged: Phase {self.boss_phase}")

        self.chase_speed = (4.1 + 0.38 * self.boss_phase) * (1.0 + 0.12 * self.boss_tier)
        self.attack_cooldown = max(0.48, 1.15 - 0.18 * (self.boss_phase - 1))
        self.boss_ability_timer -= dt
        if self.boss_ability_timer <= 0:
            self._boss_shockwave(player)
            self.boss_ability_timer = self.rng.uniform(4.0, 6.4) - (self.boss_phase - 1) * 0.55

        if hasattr(self, "boss_halo"):
            pulse = 1.0 + 0.2 * abs(math.sin(self.anim_time * (3.4 + self.boss_phase)))
            self.boss_halo.scale = (1.4 * pulse, 0.08, 1.4 * pulse)
            self.boss_halo.rotation_y += 110 * dt
        if hasattr(self, "boss_core"):
            glow = 200 + int(40 * abs(math.sin(self.anim_time * 5.8)))
            self.boss_core.color = color.rgba(255, glow, 140, 210)

    def _boss_shockwave(self, player) -> None:
        center = self.world_position + Vec3(0, 0.6, 0)
        ring = Entity(
            parent=self.game_manager.world.root if self.game_manager.world and self.game_manager.world.root else scene,
            model="sphere",
            position=center,
            scale=(0.6, 0.12, 0.6),
            color=color.rgba(255, 142, 110, 150),
        )
        shock_radius = 5.2 + self.boss_phase * 1.2
        ring.animate_scale((shock_radius, 0.15, shock_radius), duration=0.22)
        ring.animate_color(color.rgba(255, 142, 110, 0), duration=0.26)
        destroy(ring, delay=0.28)
        self.game_manager.asset_loader.play_sound("shotgun_shot", volume=0.2, pitch=self.rng.uniform(0.82, 0.9))
        if self.game_manager.camera_controller:
            self.game_manager.camera_controller.add_shake(0.7)
        if distance(center, player.world_position) <= shock_radius:
            player.take_damage(8.0 + self.boss_phase * 4.0, self)
            player.vertical_velocity = max(player.vertical_velocity, 4.4)

    def take_damage(self, amount: float, _source=None) -> None:
        if self.dead:
            return
        dmg = float(amount)
        if self.is_boss:
            dmg *= 0.92 - min(0.18, self.boss_phase * 0.04)
        self.health -= dmg
        self.hit_reaction = min(1.0, self.hit_reaction + (0.36 if self.is_boss else 0.55))
        hit_color = color.rgb(255, 120, 120) if not self.is_boss else color.rgb(255, 164, 120)
        self.model_root.color = hit_color
        self.model_root.animate_color(color.white, duration=0.1)
        if self.health <= 0:
            self._die()

    def _align_visual_to_collider(self) -> None:
        foot_level = float(getattr(self.model_root, "foot_level", -1.22))
        model_scale_y = float(getattr(self.model_root, "scale_y", 1.0))
        desired_foot = -self.collider_half_height + self.visual_foot_offset
        self.visual_root.y = desired_foot
        self.model_root.y = -(foot_level * model_scale_y)

    def _die(self) -> None:
        if self.dead:
            return
        self.dead = True
        self.collider = None
        world_parent = self.game_manager.world.root if self.game_manager.world and self.game_manager.world.root else scene
        death_style = "boss_burst" if self.is_boss else self.rng.choice(["collapse", "shatter", "launch"])

        if death_style == "collapse":
            self.animate_rotation_x(self.rng.uniform(75, 110), duration=0.22)
            self.animate_y(self.y - 0.55, duration=0.22)
            self.animate_scale((0.25, 0.2, 0.25), duration=0.26)
        elif death_style == "launch":
            self.animate_rotation_y(self.rotation_y + self.rng.uniform(-220, 220), duration=0.24)
            self.animate_y(self.y + self.rng.uniform(0.18, 0.45), duration=0.12)
            self.animate_y(self.y - 0.68, duration=0.22, delay=0.12)
            self.animate_scale((0.18, 0.18, 0.18), duration=0.28)
        elif death_style == "boss_burst":
            core_count = 22
            for _ in range(core_count):
                shard = Entity(
                    parent=world_parent,
                    model="cube",
                    scale=(0.06, 0.06, 0.06),
                    position=self.world_position + Vec3(0, 1.1, 0),
                    color=color.rgba(255, 165, 120, 190),
                )
                drift = Vec3(self.rng.uniform(-1.3, 1.3), self.rng.uniform(0.15, 1.25), self.rng.uniform(-1.3, 1.3))
                shard.animate_position(shard.position + drift, duration=0.25)
                shard.animate_scale(0.001, duration=0.28)
                destroy(shard, delay=0.3)
            self.animate_scale((0.14, 0.14, 0.14), duration=0.3)
            self.animate_y(self.y - 0.92, duration=0.3)
            self.game_manager.asset_loader.play_sound("shotgun_shot", volume=0.28, pitch=0.76)
            if self.game_manager.camera_controller:
                self.game_manager.camera_controller.add_shake(1.05)
        else:  # shatter
            for _ in range(8):
                shard = Entity(
                    parent=world_parent,
                    model="cube",
                    scale=(0.032, 0.032, 0.032),
                    position=self.world_position + Vec3(0, 0.82, 0),
                    color=color.rgba(255, 130, 130, 180),
                )
                drift = Vec3(self.rng.uniform(-0.42, 0.42), self.rng.uniform(0.08, 0.5), self.rng.uniform(-0.42, 0.42))
                shard.animate_position(shard.position + drift, duration=0.16)
                shard.animate_scale(0.001, duration=0.18)
                destroy(shard, delay=0.19)
            self.animate_scale((0.2, 0.2, 0.2), duration=0.2)
            self.animate_y(self.y - 0.55, duration=0.2)

        self.game_manager.on_enemy_killed(self, self.coin_reward)
        destroy(self, delay=0.32 if self.is_boss else 0.24)

    def _attack(self, player) -> None:
        if self.attack_timer > 0:
            return
        if distance(self.world_position, player.world_position) > self.attack_range + 0.35:
            return
        if not self._can_see_player(player):
            return
        self.attack_timer = self.attack_cooldown
        self.attack_anim = 1.0
        world_parent = self.game_manager.world.root if self.game_manager.world and self.game_manager.world.root else scene
        slash_color = color.rgba(255, 120, 120, 135) if not self.is_boss else color.rgba(255, 172, 112, 165)
        swipe = Entity(
            parent=world_parent,
            model="sphere",
            scale=0.2 if not self.is_boss else 0.34,
            position=self.world_position + Vec3(0, 1.0, 0),
            color=slash_color,
        )
        swipe.animate_scale(0.01, duration=0.08)
        destroy(swipe, delay=0.09)
        final_damage = self.attack_damage * (1.0 + self.boss_enrage * 0.6)
        player.take_damage(final_damage, self)

    def _roam(self, dt: float) -> None:
        if distance(self.position, self.roam_target) < 1.3:
            self.roam_target = self._pick_roam_target()
            self.current_target = self.roam_target
        self._face_target(self.roam_target)
        self.is_moving = self._move_towards(self.roam_target, self.roam_speed, dt)

    def _refresh_behavior(self, player) -> None:
        if hasattr(player, "is_detectable") and not player.is_detectable():
            self.state = "roam"
            if distance(self.position, self.roam_target) < 1.2:
                self.roam_target = self._pick_roam_target()
            self.current_target = self.roam_target
            return

        player_distance = distance(self.world_position, player.world_position)
        can_see_player = self._can_see_player(player)

        if player_distance <= self.attack_range and can_see_player:
            self.state = "attack"
            self.current_target = Vec3(player.world_position)
            self.last_seen_player_pos = Vec3(player.world_position)
            return

        if player_distance <= self.detect_range and can_see_player:
            self.state = "chase"
            self.current_target = Vec3(player.world_position)
            self.last_seen_player_pos = Vec3(player.world_position)
            return

        if player_distance <= self.detect_range * (1.35 if self.is_boss else 1.25) and not can_see_player:
            self.state = "search"
            self.current_target = Vec3(self.last_seen_player_pos)
            if distance(self.position, self.current_target) < 1.5:
                self.state = "roam"
                self.roam_target = self._pick_roam_target()
                self.current_target = self.roam_target
            return

        self.state = "roam"
        if distance(self.position, self.roam_target) < 1.2:
            self.roam_target = self._pick_roam_target()
        self.current_target = self.roam_target

    def _attempt_dodge(self, player, dt: float) -> None:
        if self.dodge_timer > 0:
            strafe = self.right * self.dodge_direction * self.chase_speed * 0.56 * dt
            start = Vec3(self.position)
            self.x += strafe.x
            self.z += strafe.z
            if self.intersects(ignore=self._get_movement_collision_ignores()).hit:
                self.position = start
            return

        if self.dodge_cooldown > 0:
            return
        if distance(self.world_position, player.world_position) > 11:
            return
        if self.rng.random() < 0.16:
            self.dodge_timer = self.rng.uniform(0.2, 0.4)
            self.dodge_direction = self.rng.choice([-1.0, 1.0])
            self.dodge_cooldown = self.rng.uniform(0.75, 1.3)

    def _move_towards(self, target: Vec3, speed: float, dt: float) -> bool:
        direction = target - self.position
        direction.y = 0
        if direction.length() <= 0.01:
            return False
        direction = direction.normalized()
        step = direction * speed * dt
        sub_steps = max(1, int(max(abs(step.x), abs(step.z)) / 0.14) + 1)
        sub_step = step / sub_steps
        ignore_entities = self._get_movement_collision_ignores()
        moved = False
        for _ in range(sub_steps):
            start_x = self.x
            start_z = self.z
            self.x += sub_step.x
            if self.intersects(ignore=ignore_entities).hit:
                self.x = start_x
            self.z += sub_step.z
            if self.intersects(ignore=ignore_entities).hit:
                self.z = start_z
            moved = moved or abs(self.x - start_x) > 0.0001 or abs(self.z - start_z) > 0.0001
        return moved

    def _get_movement_collision_ignores(self):
        if self._collision_cache_timer <= 0:
            ignores = [self]
            if self.game_manager.world and hasattr(self.game_manager.world, "get_walkable_surfaces"):
                ignores.extend(self.game_manager.world.get_walkable_surfaces())
            ignores.extend(self.game_manager.enemies)
            ignores.extend(self.game_manager.npcs)
            ignores.extend(self.game_manager.pickups)
            self._collision_ignores_cache = ignores
            self._collision_cache_timer = 0.22
        return self._collision_ignores_cache

    def _face_target(self, target: Vec3) -> None:
        flat_target = Vec3(target.x, self.y, target.z)
        self.look_at(flat_target)
        self.rotation_x = 0
        self.rotation_z = 0

    def _pick_roam_target(self) -> Vec3:
        if not self.game_manager.world:
            return Vec3(self.rng.uniform(-20, 20), 1.1, self.rng.uniform(-20, 20))
        target = self.game_manager.world.get_random_spawn_point(self.position, min_distance=5.0)
        target.y = max(target.y, 1.1)
        return target

    def _world_root(self):
        if self.game_manager.world and self.game_manager.world.root:
            return self.game_manager.world.root
        return scene

    def _stabilize_spawn(self) -> None:
        base_x = float(self.x)
        base_y = float(self.y)
        base_z = float(self.z)
        ignore_entities = [self]
        if self.game_manager.world and hasattr(self.game_manager.world, "get_walkable_surfaces"):
            ignore_entities.extend(self.game_manager.world.get_walkable_surfaces())
        lateral_offsets = [
            Vec3(0, 0, 0),
            Vec3(1.2, 0, 0),
            Vec3(-1.2, 0, 0),
            Vec3(0, 0, 1.2),
            Vec3(0, 0, -1.2),
            Vec3(1.8, 0, 1.8),
            Vec3(-1.8, 0, 1.8),
            Vec3(1.8, 0, -1.8),
            Vec3(-1.8, 0, -1.8),
        ]
        for lateral in lateral_offsets:
            self.x = base_x + lateral.x
            self.z = base_z + lateral.z
            for y_offset in (0.0, 0.3, 0.65, 1.0, 1.4, 2.0):
                self.y = base_y + y_offset
                if not self.intersects(ignore=ignore_entities).hit:
                    return
        self.x = base_x
        self.z = base_z
        self.y = base_y + 2.0

    def _snap_to_ground(self, force: bool = False) -> bool:
        floor_y = self.game_manager.world.ground_level if self.game_manager.world else 0.0
        floor_target = floor_y + self.collider_half_height
        probe = raycast(
            self.world_position + Vec3(0, self.collider_half_height + 0.3, 0),
            Vec3(0, -1, 0),
            distance=self.collider_half_height + 1.65,
            ignore=[self],
            traverse_target=self._world_root(),
        )
        if probe.hit:
            target_y = max(floor_target, probe.world_point.y + self.collider_half_height)
            can_snap = force or (self.vertical_velocity <= 0 and (self.y - target_y) <= self.ground_snap_tolerance)
            if can_snap:
                self.y = target_y
                self.vertical_velocity = 0.0
                self.grounded = True
                return True

        if self.y <= floor_target:
            self.y = floor_target
            self.vertical_velocity = 0.0
            self.grounded = True
            return True
        return False

    def _update_vertical(self, dt: float) -> None:
        if self._snap_to_ground(force=False):
            return
        self.grounded = False
        self.vertical_velocity -= self.gravity * dt
        self.y += self.vertical_velocity * dt
        self._snap_to_ground(force=False)

    def _animate_model(self, dt: float) -> None:
        part_nodes = getattr(self.model_root, "part_nodes", None)
        if not part_nodes:
            return

        target_blend = 1.0 if self.is_moving else 0.0
        blend_speed = 8.0 if target_blend > self.anim_move_blend else 5.4
        self.anim_move_blend += (target_blend - self.anim_move_blend) * min(1.0, dt * blend_speed)

        stride_speed = 2.0 + 7.2 * self.anim_move_blend
        if self.is_boss:
            stride_speed *= 0.84
        stride = math.sin(self.anim_time * stride_speed)
        stride_cos = math.cos(self.anim_time * stride_speed)
        bob = 0.012 * math.sin(self.anim_time * 1.2) + 0.028 * self.anim_move_blend * abs(stride)
        attack_slam = self.attack_anim * (30.0 if self.is_boss else 24.0)
        hit_stagger = self.hit_reaction * 11.0

        torso = part_nodes.get("torso")
        chest = part_nodes.get("chest")
        head = part_nodes.get("head")
        left_arm = part_nodes.get("left_arm")
        right_arm = part_nodes.get("right_arm")
        left_leg = part_nodes.get("left_leg")
        right_leg = part_nodes.get("right_leg")
        left_shoulder = part_nodes.get("left_shoulder")
        right_shoulder = part_nodes.get("right_shoulder")

        leg_amp = (7.0 + 24.0 * self.anim_move_blend) * (0.84 if self.is_boss else 1.0)
        arm_amp = (5.0 + 19.0 * self.anim_move_blend) * (1.2 if self.is_boss else 1.0)

        if torso:
            torso.y = 0.34 + bob
            torso.rotation_z = 2.0 * self.anim_move_blend * stride * 0.5
        if chest:
            chest.rotation_x = -2.1 + 2.2 * self.anim_move_blend * stride * 0.55 - hit_stagger
            chest.rotation_y = 1.8 * self.anim_move_blend * stride_cos * 0.25
        if head:
            head.rotation_y = 2.8 * stride_cos * 0.25
            head.rotation_x = -1.2 + (self.attack_anim * 5.5) - (self.hit_reaction * 5.0)
        if left_leg:
            left_leg.rotation_x = leg_amp * stride
        if right_leg:
            right_leg.rotation_x = -leg_amp * stride
        if left_arm:
            left_arm.rotation_x = -(arm_amp * stride) - attack_slam
        if right_arm:
            right_arm.rotation_x = (arm_amp * stride) - (attack_slam * 0.62) - (self.hit_reaction * 7.0)
        if left_shoulder:
            left_shoulder.rotation_z = -3.2 * self.anim_move_blend * stride
        if right_shoulder:
            right_shoulder.rotation_z = 3.2 * self.anim_move_blend * stride

    def export_runtime_state(self) -> dict:
        return {
            "position": [float(self.x), float(self.y), float(self.z)],
            "rotation_y": float(self.rotation_y),
            "health": float(self.health),
            "max_health": float(self.max_health),
            "state": str(self.state),
            "variant": str(self.variant),
            "is_boss": bool(self.is_boss),
            "boss_tier": int(self.boss_tier),
        }

    def _can_see_player(self, player) -> bool:
        if hasattr(player, "is_detectable") and not player.is_detectable():
            return False
        direction = player.world_position - self.world_position
        distance_to_player = direction.length()
        if distance_to_player <= 0.001:
            return True
        direction = direction.normalized()
        hit = raycast(
            self.world_position + Vec3(0, 1.0, 0),
            direction,
            distance=distance_to_player,
            ignore=[self],
            traverse_target=self._world_root(),
        )
        if not hit.hit:
            return True
        return hit.entity == player
