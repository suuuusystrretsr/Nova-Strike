import math
import random
from collections import deque

from ursina import Entity, Vec3, color, destroy, raycast, scene


class Bullet(Entity):
    def __init__(
        self,
        game_manager,
        owner,
        origin,
        direction,
        speed: float,
        damage: float,
        lifetime: float = 3.0,
        bullet_color=color.azure,
    ) -> None:
        world_parent = game_manager.world.root if game_manager.world and game_manager.world.root else scene
        super().__init__(
            parent=world_parent,
            model="sphere",
            scale=0.08,
            position=origin,
            color=bullet_color,
            collider="sphere",
        )
        self.game_manager = game_manager
        self.rng = getattr(game_manager, "rng", random)
        self.owner = owner
        self.direction = direction.normalized()
        self.speed = speed
        self.damage = damage
        self.lifetime = lifetime
        self.age = 0.0
        self.base_scale = 0.08
        self.spin_speed = 520.0
        current_cfg = game_manager.graphics_manager.get_current_config() if game_manager and game_manager.graphics_manager else {}
        self.effects_enabled = bool(current_cfg.get("effects_enabled", True))
        base_r = int(max(0, min(255, bullet_color.r * 255)))
        base_g = int(max(0, min(255, bullet_color.g * 255)))
        base_b = int(max(0, min(255, bullet_color.b * 255)))

        self.trail_segments = []
        trail_len = 7 if self.effects_enabled else 4
        segment_count = 5 if self.effects_enabled else 2
        self.trail_positions = deque(maxlen=trail_len)
        for _ in range(self.trail_positions.maxlen):
            self.trail_positions.append(Vec3(origin))
        for i in range(segment_count):
            segment = Entity(
                parent=world_parent,
                model="sphere",
                scale=max(0.01, 0.045 - i * 0.007),
                position=origin,
                color=color.rgba(
                    min(255, base_r + 25),
                    min(255, base_g + 25),
                    min(255, base_b + 25),
                    max(25, 125 - i * 20),
                ),
            )
            self.trail_segments.append(segment)

    def update(self) -> None:
        if self.game_manager.state != "playing":
            return
        fixed_dt = max(1e-4, float(getattr(self.game_manager, "fixed_dt", 1.0 / 60.0)))
        sim_steps = int(getattr(self.game_manager, "simulation_steps", 1))
        for _ in range(sim_steps):
            if not self.enabled:
                break
            self._simulate_step(fixed_dt)

    def _simulate_step(self, dt: float) -> None:
        self.age += dt
        step_distance = self.speed * dt
        world_root = self.game_manager.world.root if self.game_manager.world and self.game_manager.world.root else scene
        hit = raycast(
            self.world_position,
            self.direction,
            distance=step_distance + 0.05,
            ignore=[self, self.owner],
            traverse_target=world_root,
        )

        if hit.hit:
            target = hit.entity
            if hasattr(target, "take_damage"):
                owner_team = str(getattr(self.owner, "team_id", "") or "")
                target_team = str(getattr(target, "team_id", "") or "")
                if owner_team and target_team and owner_team == target_team:
                    self._impact_flash(hit.world_point)
                    self._play_impact_sound(target)
                    self._destroy_self()
                    return
                final_damage = self.damage
                if getattr(target, "is_boss", False) and hit.world_point.y > (target.world_y + 1.25):
                    final_damage *= 1.55
                target.take_damage(final_damage, self.owner)
                local_player = self.game_manager.get_local_player() if hasattr(self.game_manager, "get_local_player") else None
                if self.owner == local_player:
                    self.game_manager.on_player_hit_enemy(target, hit.world_point)
                    self.game_manager.ui_manager.show_hitmarker()
                    self.game_manager.asset_loader.play_sound("hitmarker", volume=0.16, pitch=self.rng.uniform(0.95, 1.05))
                if hasattr(self.owner, "on_damage_dealt"):
                    self.owner.on_damage_dealt(target, final_damage, hit.world_point, None)
            self._impact_flash(hit.world_point)
            self._play_impact_sound(target)
            self._destroy_self()
            return

        self.position += self.direction * step_distance
        self.rotation_z += self.spin_speed * dt
        pulse = 1.0 + 0.16 * math.sin(self.age * 40.0)
        self.scale = self.base_scale * pulse

        if self.trail_segments:
            self.trail_positions.appendleft(Vec3(self.world_position))
            for i, segment in enumerate(self.trail_segments):
                index = min(len(self.trail_positions) - 1, i + 1)
                segment.position = self.trail_positions[index]

        self.lifetime -= dt
        if self.lifetime <= 0:
            self._destroy_self()

    def _impact_flash(self, world_point) -> None:
        world_parent = self.game_manager.world.root if self.game_manager.world and self.game_manager.world.root else scene
        spark = Entity(
            parent=world_parent,
            model="sphere",
            scale=0.12,
            position=world_point,
            color=color.rgba(255, 220, 140, 180),
        )
        spark.animate_scale(0.01, duration=0.1)
        destroy(spark, delay=0.11)
        particle_count = 6 if self.effects_enabled else 2
        for _ in range(particle_count):
            particle = Entity(
                parent=world_parent,
                model="cube",
                scale=(0.018, 0.018, 0.018),
                position=world_point,
                color=color.rgba(255, 210, 120, 180),
            )
            drift = Vec3(
                self.rng.uniform(-0.18, 0.18),
                self.rng.uniform(0.04, 0.24),
                self.rng.uniform(-0.18, 0.18),
            )
            particle.animate_position(world_point + drift, duration=0.11)
            particle.animate_scale(0.001, duration=0.11)
            destroy(particle, delay=0.12)

    def _destroy_self(self) -> None:
        for segment in self.trail_segments:
            destroy(segment)
        self.trail_segments = []
        destroy(self)

    def _play_impact_sound(self, hit_entity) -> None:
        if hit_entity and hasattr(hit_entity, "take_damage"):
            self.game_manager.asset_loader.play_sound("hitmarker", volume=0.1, pitch=self.rng.uniform(0.88, 1.0))
            return
        material = getattr(hit_entity, "material_type", "solid")
        if material == "metal":
            self.game_manager.asset_loader.play_sound("ui_click", volume=0.08, pitch=self.rng.uniform(0.8, 0.95))
        elif material == "wood":
            self.game_manager.asset_loader.play_sound("reload", volume=0.06, pitch=self.rng.uniform(1.2, 1.45))
        else:
            self.game_manager.asset_loader.play_sound("ui_click", volume=0.06, pitch=self.rng.uniform(1.05, 1.18))
