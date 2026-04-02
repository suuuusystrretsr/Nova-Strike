import math
import random
from typing import Dict, List, Optional, Tuple

from ursina import AmbientLight, DirectionalLight, Entity, Vec2, Vec3, application, color, destroy, distance
from scripts.map_system import MapRegistry


class ExplosiveBarrel(Entity):
    def __init__(self, world, position, blast_radius: float = 6.5, damage: float = 42.0) -> None:
        super().__init__(
            parent=world.root,
            model="cube",
            position=position,
            scale=(0.9, 1.25, 0.9),
            color=color.rgb(155, 72, 58),
            collider="box",
        )
        self.material_type = "metal"
        self.world = world
        self.max_health = 38.0
        self.health = self.max_health
        self.blast_radius = float(blast_radius)
        self.damage = float(damage)
        self.destroyed = False
        self._phase = world.rng.uniform(0.0, 6.28)

        self.band = Entity(
            parent=self,
            model="cube",
            scale=(1.03, 0.15, 1.03),
            y=0.2,
            color=color.rgb(58, 42, 40),
        )
        self.core = Entity(
            parent=self,
            model="sphere",
            scale=0.22,
            y=0.32,
            z=0.18,
            color=color.rgb(255, 186, 98),
        )

    def update(self) -> None:
        if self.destroyed:
            return
        dt = max(0.0, float(getattr(self.world.game_manager, "frame_dt", 1.0 / 60.0))) if self.world and self.world.game_manager else 1.0 / 60.0
        self._phase += dt
        pulse = 1.0 + 0.1 * math.sin(self._phase * 4.2)
        self.core.scale = 0.22 * pulse
        self.core.color = color.rgb(255, 178 + int(42 * abs(math.sin(self._phase * 2.4))), 98)

    def take_damage(self, amount: float, _source=None) -> None:
        if self.destroyed:
            return
        self.health -= max(0.0, float(amount))
        self.color = color.rgb(185, 88, 70)
        self.animate_color(color.rgb(155, 72, 58), duration=0.12)
        if self.health <= 0:
            self.explode()

    def explode(self) -> None:
        if self.destroyed:
            return
        self.destroyed = True
        world = self.world
        gm = world.game_manager
        center = Vec3(self.world_position)

        flash = Entity(parent=world.root, model="sphere", position=center + Vec3(0, 0.35, 0), scale=0.2, color=color.rgba(255, 196, 120, 220))
        flash.animate_scale(self.blast_radius * 0.55, duration=0.12)
        flash.animate_color(color.rgba(255, 160, 90, 0), duration=0.16)
        destroy(flash, delay=0.18)
        for _ in range(11):
            shard = Entity(
                parent=world.root,
                model="cube",
                position=center + Vec3(0, 0.4, 0),
                scale=(0.07, 0.07, 0.07),
                color=color.rgb(236, 170, 120),
            )
            drift = Vec3(world.rng.uniform(-1.4, 1.4), world.rng.uniform(0.25, 1.8), world.rng.uniform(-1.4, 1.4))
            shard.animate_position(center + drift, duration=0.18)
            shard.animate_scale(0.001, duration=0.2)
            destroy(shard, delay=0.21)

        if gm and gm.camera_controller:
            gm.camera_controller.add_shake(1.2)
        if gm and gm.asset_loader:
            gm.asset_loader.play_sound("shotgun_shot", volume=0.22, pitch=world.rng.uniform(0.84, 0.96))

        if gm:
            for player in gm.get_active_players(alive_only=True):
                player_dist = distance(center, player.world_position)
                if player_dist > self.blast_radius:
                    continue
                falloff = max(0.15, 1.0 - (player_dist / max(0.001, self.blast_radius)))
                player.take_damage(self.damage * falloff)
                player.vertical_velocity = max(player.vertical_velocity, 3.2 * falloff)

        if gm:
            for enemy in list(gm.enemies):
                if not enemy or getattr(enemy, "dead", False):
                    continue
                d = distance(center, enemy.world_position)
                if d > self.blast_radius:
                    continue
                falloff = max(0.2, 1.0 - (d / max(0.001, self.blast_radius)))
                enemy.take_damage(self.damage * 1.35 * falloff)
                enemy.vertical_velocity = max(enemy.vertical_velocity, 2.4 * falloff)

        for barrel in list(world.explosive_props):
            if barrel is self or barrel.destroyed:
                continue
            if distance(center, barrel.world_position) <= self.blast_radius * 0.92:
                barrel.take_damage(9999)

        if self in world.explosive_props:
            world.explosive_props.remove(self)
        destroy(self)


class World:
    def __init__(
        self,
        asset_loader,
        mode: str = "mission",
        mode_id: str = "mission_pve",
        map_id: Optional[str] = None,
        graphics_config: Optional[dict] = None,
        biome_theme: Optional[str] = None,
        rng=None,
    ) -> None:
        self.asset_loader = asset_loader
        self.mode = mode
        self.mode_id = str(mode_id or "")
        self.map_registry = MapRegistry()
        self.rng = rng if rng else random
        self.map_id = self._resolve_map_id(map_id)
        self.map_spec = self.map_registry.get(self.map_id)
        self.world_layout = self.map_spec.world_layout if self.map_spec else self.mode
        self.mode = self.world_layout
        self.graphics_config = graphics_config or {}
        self.biome_theme = biome_theme or self._pick_biome_theme()
        self.root = Entity(name=f"world_root_{self.map_id}")
        self.effect_entities: List[Entity] = []
        self.spawn_points: List[Vec3] = []
        self.player_spawn_points: List[Vec3] = []
        self.walkable_surfaces: List[Entity] = []
        self.locations: Dict[str, Vec3] = {}
        self.npc_spawns: List[dict] = []
        self.collectible_spawns: List[Tuple[Vec3, str]] = []
        self.objective_marker = None
        self.objective_target = None
        self.game_manager = None

        self.sun = None
        self.fill_light = None
        self.ambient = None
        self._sun_light_np = None
        self._fill_light_np = None
        self._ambient_light_np = None
        self.sky = None
        self.ground_level = 0.0
        self.map_half_extent = 150.0
        self.safe_player_spawn = Vec3(0, 3.0, 0)
        self.effect_phase = self.rng.uniform(0.0, 7.0)
        self.runtime = 0.0
        self.visual_time = 0.0
        self.jump_pads: List[dict] = []
        self.speed_gates: List[dict] = []
        self.hazard_zones: List[dict] = []
        self.explosive_props: List[ExplosiveBarrel] = []
        self._jump_pad_cooldowns: Dict[tuple, float] = {}
        self._speed_gate_cooldowns: Dict[tuple, float] = {}
        self._hazard_tick: Dict[tuple, float] = {}
        self._cooldown_prune_timer = 0.0
        self._cooldown_prune_interval = 1.0
        self._cooldown_retention = 8.0
        self._last_player_pad_toast = -99.0
        self._last_player_gate_toast = -99.0

        self._build()

    def _resolve_map_id(self, requested_map_id: Optional[str]) -> str:
        if requested_map_id:
            requested = self.map_registry.get(str(requested_map_id))
            if requested and requested.supports_mode(self.mode_id):
                return requested.map_id
        fallback = self.map_registry.find_first_for_mode(self.mode_id)
        if fallback:
            return fallback.map_id
        return "mission_outpost_alpha"

    def _pick_biome_theme(self) -> str:
        mission_themes = ("frontier", "ashen", "neon")
        roam_themes = ("metro", "canyon", "verdant")
        options = roam_themes if self.world_layout == "free_roam" else mission_themes
        return self.rng.choice(options)

    def _theme_palette(self) -> Dict[str, tuple]:
        palettes = {
            "frontier": {"sky": (78, 132, 196), "ground": (72, 94, 80), "wall": (64, 73, 92)},
            "ashen": {"sky": (124, 108, 120), "ground": (92, 88, 86), "wall": (84, 82, 94)},
            "neon": {"sky": (58, 88, 170), "ground": (58, 76, 94), "wall": (72, 78, 116)},
            "metro": {"sky": (92, 146, 214), "ground": (70, 94, 76), "wall": (78, 96, 124)},
            "canyon": {"sky": (206, 156, 108), "ground": (128, 102, 84), "wall": (116, 94, 84)},
            "verdant": {"sky": (102, 164, 138), "ground": (72, 106, 82), "wall": (76, 104, 92)},
        }
        return palettes.get(self.biome_theme, palettes["frontier"])

    def _build(self) -> None:
        self._build_lighting()
        if self.world_layout == "free_roam":
            self._build_free_roam_map()
        else:
            self._build_mission_map()
        self._apply_map_variant()
        self.set_effect_quality(bool(self.graphics_config.get("effects_enabled", True)))

    def _build_lighting(self) -> None:
        cfg = self.graphics_config
        shadows_enabled = bool(cfg.get("shadows", False))
        shadow_resolution = int(cfg.get("shadow_resolution", 768))
        sun_strength = float(cfg.get("sun_strength", 1.0))
        ambient_strength = float(cfg.get("ambient_strength", 0.65))
        palette = self._theme_palette()

        sky_rgb = palette["sky"]
        sky_color = color.rgb(sky_rgb[0], sky_rgb[1], sky_rgb[2])
        self.sky = Entity(
            parent=self.root,
            model="sphere",
            double_sided=True,
            scale=900 if self.mode == "free_roam" else 450,
            color=sky_color,
        )

        self.sun = DirectionalLight(parent=self.root, shadows=shadows_enabled)
        self._sun_light_np = self._extract_light_node(self.sun)
        self.sun.rotation = (46, -38, 0)
        if hasattr(self.sun, "shadow_map_resolution"):
            self.sun.shadow_map_resolution = Vec2(shadow_resolution, shadow_resolution)

        sun_r = min(255, int(255 * sun_strength))
        sun_g = min(255, int(245 * sun_strength))
        sun_b = min(255, int(228 * sun_strength))
        self.sun.color = color.rgba(sun_r, sun_g, sun_b, 255)

        ambient_value = int(195 * ambient_strength)
        self.ambient = AmbientLight(parent=self.root, color=color.rgba(ambient_value, ambient_value, ambient_value, 255))
        self._ambient_light_np = self._extract_light_node(self.ambient)

        fill_strength = max(0.25, min(0.8, ambient_strength * 0.78))
        fill_value = int(170 * fill_strength)
        self.fill_light = DirectionalLight(parent=self.root, shadows=False)
        self._fill_light_np = self._extract_light_node(self.fill_light)
        self.fill_light.rotation = (20, 138, 0)
        self.fill_light.color = color.rgba(fill_value, fill_value, min(255, fill_value + 20), 255)

    def _build_mission_map(self) -> None:
        palette = self._theme_palette()
        self.map_half_extent = 60.0
        self.safe_player_spawn = Vec3(0, 2.2, 0)
        self.player_spawn_points = [
            Vec3(0, 2.2, 0),
            Vec3(-6, 2.2, -4),
            Vec3(6, 2.2, -4),
            Vec3(0, 2.2, -9),
        ]
        self.locations["extraction_point"] = Vec3(0, 0.2, 42)

        main_ground = Entity(
            parent=self.root,
            model="cube",
            texture="white_cube",
            texture_scale=(36, 36),
            color=color.rgb(*palette["ground"]),
            collider="box",
            scale=(110, 2, 110),
            y=-1.0,
        )
        main_ground.material_type = "wood" if self.biome_theme in ("canyon", "verdant") else "solid"
        self._register_walkable_surface(main_ground)
        fallback_ground = Entity(
            parent=self.root,
            model="cube",
            color=color.rgb(52, 68, 55),
            collider="box",
            scale=(130, 2, 130),
            y=-6.0,
            visible=False,
        )
        self._register_walkable_surface(fallback_ground)

        wall_specs = [
            ((0, 4.2, 55), (110, 8.2, 1.8)),
            ((0, 4.2, -55), (110, 8.2, 1.8)),
            ((55, 4.2, 0), (1.8, 8.2, 110)),
            ((-55, 4.2, 0), (1.8, 8.2, 110)),
        ]
        for pos, scale in wall_specs:
            wall = Entity(
                parent=self.root,
                model="cube",
                texture="white_cube",
                texture_scale=(12, 2),
                position=pos,
                scale=scale,
                color=color.rgb(*palette["wall"]),
                collider="box",
            )
            wall.material_type = "metal"

        self._build_mission_structures()
        if self.mode_id == "mission_pve":
            self._build_mission_effects()
            self._build_mission_interactives()

        for angle in range(0, 360, 22):
            radians = math.radians(angle)
            ring = 35 + (angle % 2) * 7
            self.spawn_points.append(Vec3(ring * math.cos(radians), 1.2, ring * math.sin(radians)))

    def _build_mission_structures(self) -> None:
        pads = [(-20, -20), (20, -20), (-20, 20), (20, 20), (0, -28), (0, 28)]
        for x, z in pads:
            platform = Entity(
                parent=self.root,
                model="cube",
                position=(x, 1.1, z),
                scale=(7.8, 2.2, 7.8),
                color=color.rgb(102, 108, 125),
                texture="white_cube",
                texture_scale=(2, 2),
                collider="box",
            )
            platform.material_type = "metal"
            Entity(parent=platform, model="cube", position=(0, 1.1, 0), scale=(5.4, 0.24, 5.4), color=color.rgb(72, 82, 104))
            for ox, oz in ((-2.3, -2.3), (2.3, -2.3), (-2.3, 2.3), (2.3, 2.3)):
                Entity(
                    parent=platform,
                    model="cube",
                    position=(ox, 0.9, oz),
                    scale=(0.56, 0.9, 0.56),
                    color=color.rgb(132, 139, 154),
                    texture="white_cube",
                )

        structure_rng = random.Random(17)
        for _ in range(16):
            x = structure_rng.uniform(-46, 46)
            z = structure_rng.uniform(-46, 46)
            if abs(x) < 8 and abs(z) < 8:
                continue
            block = Entity(
                parent=self.root,
                model="cube",
                position=(x, structure_rng.uniform(0.65, 1.9), z),
                scale=(
                    structure_rng.uniform(1.1, 2.6),
                    structure_rng.uniform(1.2, 3.3),
                    structure_rng.uniform(1.1, 2.6),
                ),
                color=color.rgb(84, 92, 108),
                texture="white_cube",
                texture_scale=(2, 2),
                collider="box",
            )
            block.material_type = "metal"

    def _build_mission_effects(self) -> None:
        extraction = self.locations["extraction_point"]
        marker_base = Entity(
            parent=self.root,
            model="cube",
            position=extraction,
            scale=(2.6, 0.25, 2.6),
            color=color.rgb(70, 156, 216),
            collider=None,
        )
        beam = Entity(
            parent=self.root,
            model="cube",
            position=extraction + Vec3(0, 3.6, 0),
            scale=(0.35, 7.2, 0.35),
            color=color.rgba(120, 220, 255, 135),
            collider=None,
        )
        beam.is_orb_effect = False
        self.effect_entities.extend([marker_base, beam])

    def _build_free_roam_map(self) -> None:
        palette = self._theme_palette()
        self.map_half_extent = 145.0
        # Spawn outside the central hub volume; (0,3,0) was inside hub collider.
        self.safe_player_spawn = Vec3(0, 2.2, 18)
        self.player_spawn_points = [
            Vec3(0, 2.2, 18),
            Vec3(-7, 2.2, 17),
            Vec3(8, 2.2, 16),
            Vec3(0, 2.2, 24),
        ]
        self.locations = {
            "central_hub": Vec3(0, 0.2, 0),
            "relay_tower": Vec3(52, 0.2, -38),
            "canyon_gate": Vec3(-68, 0.2, 62),
            "scrapyard": Vec3(78, 0.2, 54),
            "old_district": Vec3(-58, 0.2, -54),
            "mission_board": Vec3(9, 0.2, 12),
        }

        main_ground = Entity(
            parent=self.root,
            model="cube",
            texture="white_cube",
            texture_scale=(64, 64),
            color=color.rgb(*palette["ground"]),
            collider="box",
            scale=(280, 2, 280),
            y=-1.0,
        )
        main_ground.material_type = "wood" if self.biome_theme in ("canyon", "verdant") else "solid"
        self._register_walkable_surface(main_ground)
        fallback_ground = Entity(
            parent=self.root,
            model="cube",
            color=color.rgb(52, 66, 55),
            collider="box",
            scale=(310, 2, 310),
            y=-7.0,
            visible=False,
        )
        self._register_walkable_surface(fallback_ground)

        self._build_roads()
        self._build_free_roam_structures()
        if self.mode_id == "free_roam_pve":
            self._build_location_markers()
        self._build_free_roam_spawns()
        if self.mode_id == "free_roam_pve":
            self._build_collectible_spawns()
            self._build_npc_spawns()
            self._build_free_roam_interactives()

    def _apply_map_variant(self) -> None:
        if self.map_id.startswith("duel_arena_"):
            self.map_half_extent = min(self.map_half_extent, 44.0)
            self.player_spawn_points = [Vec3(-12, 2.2, 0), Vec3(12, 2.2, 0)]
            self.safe_player_spawn = Vec3(-12, 2.2, 0)
            self.spawn_points = [
                Vec3(-10, 1.2, -8),
                Vec3(-10, 1.2, 8),
                Vec3(10, 1.2, -8),
                Vec3(10, 1.2, 8),
                Vec3(0, 1.2, -10),
                Vec3(0, 1.2, 10),
            ]
            return

        if self.map_id == "ctf_bastion_alpha":
            self.player_spawn_points = [Vec3(-20, 2.2, 0), Vec3(20, 2.2, 0)]
            self.safe_player_spawn = Vec3(-20, 2.2, 0)
            self.locations["team_a_flag"] = Vec3(-30, 0.2, 0)
            self.locations["team_b_flag"] = Vec3(30, 0.2, 0)
            return

        if self.map_id == "br_frontier_alpha":
            self.map_half_extent = max(self.map_half_extent, 165.0)
            if len(self.spawn_points) < 96:
                for _ in range(128):
                    x = self.rng.uniform(-self.map_half_extent + 6, self.map_half_extent - 6)
                    z = self.rng.uniform(-self.map_half_extent + 6, self.map_half_extent - 6)
                    self.spawn_points.append(Vec3(x, 1.2, z))

    def _build_roads(self) -> None:
        roads = [
            ((0, 0.04, 0), (240, 0.12, 12)),
            ((0, 0.04, 0), (12, 0.12, 240)),
            ((45, 0.04, -35), (140, 0.12, 10)),
            ((-55, 0.04, 50), (130, 0.12, 10)),
        ]
        for pos, scale in roads:
            road = Entity(
                parent=self.root,
                model="cube",
                position=pos,
                scale=scale,
                color=color.rgb(64, 67, 72),
            )
            road.material_type = "solid"
            long_axis_is_x = scale[0] >= scale[2]
            long_len = scale[0] if long_axis_is_x else scale[2]
            stripe_count = max(3, int(long_len // 24))
            for i in range(stripe_count):
                offset = -long_len * 0.45 + i * (long_len / stripe_count)
                stripe_pos = (pos[0] + offset, pos[1] + 0.08, pos[2]) if long_axis_is_x else (pos[0], pos[1] + 0.08, pos[2] + offset)
                stripe_scale = (2.2, 0.02, 0.34) if long_axis_is_x else (0.34, 0.02, 2.2)
                Entity(parent=self.root, model="cube", position=stripe_pos, scale=stripe_scale, color=color.rgb(240, 222, 142))

    def _build_free_roam_structures(self) -> None:
        hub = Entity(
            parent=self.root,
            model="cube",
            position=(0, 2.5, 0),
            scale=(16, 5, 16),
            color=color.rgb(106, 112, 130),
            texture="white_cube",
            texture_scale=(4, 2),
            collider="box",
        )
        hub.material_type = "metal"
        Entity(parent=hub, model="cube", position=(0, 2.3, 0), scale=(12, 0.35, 12), color=color.rgb(72, 82, 104))
        Entity(parent=hub, model="cube", position=(0, -1.5, 7.6), scale=(6.5, 2.2, 0.5), color=color.rgb(65, 80, 102))

        district_centers = [(-56, -52), (75, 52), (52, -38), (-68, 62)]
        for cx, cz in district_centers:
            for _ in range(7):
                x = cx + self.rng.uniform(-18, 18)
                z = cz + self.rng.uniform(-18, 18)
                h = self.rng.uniform(3.2, 8.4)
                building = Entity(
                    parent=self.root,
                    model="cube",
                    position=(x, h * 0.5, z),
                    scale=(self.rng.uniform(3, 6), h, self.rng.uniform(3, 6)),
                    color=color.rgb(
                        self.rng.randint(78, 106),
                        self.rng.randint(86, 112),
                        self.rng.randint(108, 136),
                    ),
                    texture="white_cube",
                    texture_scale=(2, 2),
                    collider="box",
                )
                building.material_type = "metal"
                Entity(
                    parent=building,
                    model="cube",
                    scale=(0.8, 0.1, 0.2),
                    y=0.1,
                    z=0.51,
                    color=color.rgb(182, 214, 242),
                )

        for _ in range(42):
            x = self.rng.uniform(-132, 132)
            z = self.rng.uniform(-132, 132)
            if abs(x) < 22 and abs(z) < 22:
                continue
            trunk = Entity(
                parent=self.root,
                model="cube",
                position=(x, 0.85, z),
                scale=(0.25, 1.7, 0.25),
                color=color.rgb(98, 77, 63),
            )
            trunk.material_type = "wood"
            canopy = Entity(
                parent=self.root,
                model="sphere",
                position=(x, 2.3, z),
                scale=self.rng.uniform(1.1, 1.8),
                color=color.rgb(
                    self.rng.randint(64, 96),
                    self.rng.randint(130, 166),
                    self.rng.randint(72, 108),
                ),
            )
            canopy.is_orb_effect = True
            self.effect_entities.append(canopy)
            trunk.collider = "box"

    def _build_location_markers(self) -> None:
        for name, pos in self.locations.items():
            base = Entity(
                parent=self.root,
                model="cube",
                position=pos,
                scale=(2.2, 0.2, 2.2),
                color=color.rgb(72, 112, 152),
                collider=None,
            )
            glow = Entity(
                parent=self.root,
                model="sphere",
                position=pos + Vec3(0, 1.9, 0),
                scale=0.7,
                color=color.rgba(145, 220, 255, 120),
                collider=None,
            )
            glow.is_orb_effect = True
            self.effect_entities.extend([base, glow])

    def _build_free_roam_spawns(self) -> None:
        for angle in range(0, 360, 12):
            radius = self.rng.uniform(28, 118)
            radians = math.radians(angle)
            x = radius * math.cos(radians)
            z = radius * math.sin(radians)
            self.spawn_points.append(Vec3(x, 1.2, z))

    def _build_collectible_spawns(self) -> None:
        salvage_points = [(-58, 0.8, -55), (-51, 0.8, -62), (80, 0.8, 56), (72, 0.8, 49), (86, 0.8, 63)]
        data_points = [(54, 0.8, -36), (50, 0.8, -43), (58, 0.8, -34), (-6, 0.8, 28), (19, 0.8, -20)]
        for p in salvage_points:
            self.collectible_spawns.append((Vec3(*p), "salvage"))
        for p in data_points:
            self.collectible_spawns.append((Vec3(*p), "data_core"))

    def _build_npc_spawns(self) -> None:
        self.npc_spawns = [
            # Keep all NPCs in the front plaza to avoid overlap with hub/building colliders.
            {"npc_id": "handler_aria", "display_name": "Handler Aria", "role": "commander", "position": Vec3(0, 1.2, 20.0)},
            {"npc_id": "quartermaster_rynn", "display_name": "Quartermaster Rynn", "role": "trader", "position": Vec3(-8.5, 1.2, 18.4)},
            {"npc_id": "engineer_voss", "display_name": "Engineer Voss", "role": "engineer", "position": Vec3(8.5, 1.2, 18.2)},
            {"npc_id": "scout_nia", "display_name": "Scout Nia", "role": "scout", "position": Vec3(0, 1.2, 27.0)},
        ]

    def _build_mission_interactives(self) -> None:
        self._add_jump_pad(position=Vec3(-30, 0.05, 0), forward=Vec3(1, 0, 0), launch_power=13.5, forward_boost=6.0)
        self._add_jump_pad(position=Vec3(30, 0.05, 0), forward=Vec3(-1, 0, 0), launch_power=13.5, forward_boost=6.0)
        self._add_jump_pad(position=Vec3(0, 0.05, -34), forward=Vec3(0, 0, 1), launch_power=12.8, forward_boost=5.0)
        self._add_speed_gate(position=Vec3(0, 0.4, 19), radius=2.25, boost_mult=2.05, duration=2.4)
        self._add_hazard_zone(position=Vec3(18, 0.04, 18), radius=4.0, tick_damage=6.0)
        self._add_hazard_zone(position=Vec3(-18, 0.04, -18), radius=4.0, tick_damage=6.0)
        self._add_explosive_barrel(Vec3(22, 0.62, 0))
        self._add_explosive_barrel(Vec3(-22, 0.62, 0))
        self._add_explosive_barrel(Vec3(0, 0.62, 26))

    def _build_free_roam_interactives(self) -> None:
        self._add_jump_pad(position=Vec3(8, 0.05, 30), forward=Vec3(0.4, 0, 1), launch_power=14.0, forward_boost=7.4)
        self._add_jump_pad(position=Vec3(-20, 0.05, 16), forward=Vec3(-1, 0, 0.2), launch_power=12.8, forward_boost=6.0)
        self._add_jump_pad(position=Vec3(52, 0.05, -26), forward=Vec3(0.2, 0, -1), launch_power=13.6, forward_boost=7.0)
        self._add_speed_gate(position=Vec3(0, 0.4, 42), radius=2.35, boost_mult=2.2, duration=2.8)
        self._add_speed_gate(position=Vec3(-56, 0.4, -44), radius=2.35, boost_mult=2.35, duration=2.4)
        self._add_hazard_zone(position=Vec3(75, 0.04, 52), radius=5.0, tick_damage=6.5)
        self._add_hazard_zone(position=Vec3(-64, 0.04, 61), radius=4.4, tick_damage=6.0)
        for pos in (Vec3(12, 0.62, 8), Vec3(-14, 0.62, 24), Vec3(46, 0.62, -34), Vec3(-58, 0.62, -48), Vec3(80, 0.62, 58)):
            self._add_explosive_barrel(pos)

    def _add_jump_pad(self, position: Vec3, forward: Vec3, launch_power: float, forward_boost: float) -> None:
        pad_base = Entity(
            parent=self.root,
            model="cube",
            position=position,
            scale=(2.1, 0.12, 2.1),
            color=color.rgb(58, 90, 130),
        )
        pad_base.material_type = "metal"
        pad_ring = Entity(
            parent=pad_base,
            model="cube",
            y=0.07,
            scale=(0.9, 0.08, 0.9),
            color=color.rgb(128, 228, 255),
        )
        pad_arrow = Entity(
            parent=pad_base,
            model="cube",
            position=(0, 0.11, 0.48),
            scale=(0.25, 0.08, 0.55),
            color=color.rgb(205, 245, 255),
        )
        pad_base.rotation_y = math.degrees(math.atan2(forward.x, forward.z))
        self.effect_entities.extend([pad_ring, pad_arrow])
        self.jump_pads.append(
            {
                "id": len(self.jump_pads),
                "base": pad_base,
                "ring": pad_ring,
                "arrow": pad_arrow,
                "position": Vec3(position.x, position.y + 0.2, position.z),
                "radius": 1.45,
                "power": launch_power,
                "forward_boost": forward_boost,
                "forward": Vec3(forward).normalized() if forward.length() > 0.001 else Vec3(0, 0, 1),
                "cooldown": 1.15,
            }
        )

    def _add_speed_gate(self, position: Vec3, radius: float, boost_mult: float, duration: float) -> None:
        left_pylon = Entity(parent=self.root, model="cube", position=position + Vec3(-1.2, 1.2, 0), scale=(0.42, 2.4, 0.42), color=color.rgb(86, 112, 170))
        right_pylon = Entity(parent=self.root, model="cube", position=position + Vec3(1.2, 1.2, 0), scale=(0.42, 2.4, 0.42), color=color.rgb(86, 112, 170))
        beam = Entity(parent=self.root, model="cube", position=position + Vec3(0, 1.05, 0), scale=(2.15, 2.0, 0.08), color=color.rgba(120, 220, 255, 120))
        left_pylon.material_type = "metal"
        right_pylon.material_type = "metal"
        beam.is_orb_effect = False
        self.effect_entities.append(beam)
        self.speed_gates.append(
            {
                "id": len(self.speed_gates),
                "position": Vec3(position),
                "radius": float(radius),
                "boost_mult": float(boost_mult),
                "duration": float(duration),
                "beam": beam,
                "left": left_pylon,
                "right": right_pylon,
                "cooldown": 2.4,
            }
        )

    def _add_hazard_zone(self, position: Vec3, radius: float, tick_damage: float) -> None:
        zone_base = Entity(
            parent=self.root,
            model="sphere",
            position=position,
            scale=(radius * 2.0, 0.12, radius * 2.0),
            color=color.rgba(215, 80, 105, 110),
        )
        zone_core = Entity(
            parent=self.root,
            model="sphere",
            position=position + Vec3(0, 0.28, 0),
            scale=(radius * 0.36, 0.26, radius * 0.36),
            color=color.rgba(255, 120, 120, 150),
        )
        zone_core.is_orb_effect = True
        self.effect_entities.append(zone_core)
        self.hazard_zones.append(
            {
                "id": len(self.hazard_zones),
                "position": Vec3(position),
                "radius": float(radius),
                "tick_damage": float(tick_damage),
                "tick_interval": 0.45,
                "base": zone_base,
                "core": zone_core,
            }
        )

    def _add_explosive_barrel(self, position: Vec3) -> None:
        barrel = ExplosiveBarrel(self, position)
        self.explosive_props.append(barrel)

    def set_objective_marker(self, target_position: Optional[Vec3], marker_color=color.rgba(120, 225, 255, 120)) -> None:
        if self.mode_id not in ("mission_pve", "free_roam_pve"):
            target_position = None
        if target_position and self.objective_target and (target_position - self.objective_target).length() < 0.02 and self.objective_marker:
            self.objective_marker.color = marker_color
            return
        if self.objective_marker:
            if self.objective_marker in self.effect_entities:
                self.effect_entities.remove(self.objective_marker)
            destroy(self.objective_marker)
            self.objective_marker = None
            self.objective_target = None
        if not target_position:
            return
        self.objective_marker = Entity(
            parent=self.root,
            model="cube",
            position=target_position + Vec3(0, 3.8, 0),
            scale=(0.45, 7.6, 0.45),
            color=marker_color,
            collider=None,
        )
        self.objective_marker.is_orb_effect = False
        self.effect_entities.append(self.objective_marker)
        self.objective_target = Vec3(target_position)

    def apply_graphics_config(self, cfg: dict, allow_shadow_change: bool = False) -> None:
        sun_strength = float(cfg.get("sun_strength", 1.0))
        ambient_strength = float(cfg.get("ambient_strength", 0.6))
        shadow_resolution = int(cfg.get("shadow_resolution", 512))

        if self.sun:
            if allow_shadow_change:
                try:
                    self.sun.shadows = bool(cfg.get("shadows", False))
                except Exception:
                    self.sun.shadows = False
            sun_r = min(255, int(255 * sun_strength))
            sun_g = min(255, int(245 * sun_strength))
            sun_b = min(255, int(228 * sun_strength))
            self.sun.color = color.rgba(sun_r, sun_g, sun_b, 255)
            if hasattr(self.sun, "shadow_map_resolution"):
                self.sun.shadow_map_resolution = Vec2(shadow_resolution, shadow_resolution)

        if self.ambient:
            ambient_value = int(195 * ambient_strength)
            self.ambient.color = color.rgba(ambient_value, ambient_value, ambient_value, 255)

        if self.fill_light:
            fill_strength = max(0.25, min(0.8, ambient_strength * 0.78))
            fill_value = int(170 * fill_strength)
            self.fill_light.color = color.rgba(fill_value, fill_value, min(255, fill_value + 20), 255)

        self.set_effect_quality(bool(cfg.get("effects_enabled", True)))

    def set_effect_quality(self, enabled: bool) -> None:
        for entity in self.effect_entities:
            entity.enabled = enabled

    def bind_gameplay(self, game_manager) -> None:
        self.game_manager = game_manager

    def update(self) -> None:
        frame_dt = max(0.0, float(getattr(self.game_manager, "frame_dt", 1.0 / 60.0))) if self.game_manager else 1.0 / 60.0
        sim_dt = max(0.0, float(getattr(self.game_manager, "sim_dt", frame_dt))) if self.game_manager else frame_dt
        self.runtime += sim_dt
        self.visual_time += frame_dt
        self.effect_phase += frame_dt
        for index, entity in enumerate(self.effect_entities):
            if not entity.enabled:
                continue
            if not hasattr(entity, "_base_scale"):
                entity._base_scale = Vec3(entity.scale_x, entity.scale_y, entity.scale_z)
            base = entity._base_scale
            pulse = 1.0 + 0.09 * math.sin(self.effect_phase * 2.4 + index * 0.4)
            if getattr(entity, "is_orb_effect", False):
                entity.scale = base * pulse
                entity.rotation_y += 14 * frame_dt
            else:
                entity.scale_x = base.x * (0.95 + 0.05 * pulse)
                entity.scale_y = base.y * (0.96 + 0.04 * pulse)
                entity.scale_z = base.z
        self._update_interactives(sim_dt)

    def _update_interactives(self, dt: float) -> None:
        if not self.game_manager or self.game_manager.state != "playing":
            return
        if self.mode_id not in ("mission_pve", "free_roam_pve"):
            return
        players = self.game_manager.get_active_players(alive_only=True) if hasattr(self.game_manager, "get_active_players") else []
        if not players:
            fallback = self.game_manager.get_local_player() if hasattr(self.game_manager, "get_local_player") else None
            if fallback and getattr(fallback, "alive", False):
                players = [fallback]
        enemies = self.game_manager.enemies
        self._cooldown_prune_timer -= max(0.0, float(dt))
        if self._cooldown_prune_timer <= 0.0:
            self._cooldown_prune_timer = self._cooldown_prune_interval
            self._prune_interactive_cooldowns()
        if not players and not enemies:
            return
        self._update_jump_pads(players, enemies, dt)
        self._update_speed_gates(players, dt)
        self._update_hazard_zones(players, enemies, dt)

    def _prune_interactive_cooldowns(self) -> None:
        cutoff = self.runtime - float(self._cooldown_retention)
        self._jump_pad_cooldowns = {
            key: stamp for key, stamp in self._jump_pad_cooldowns.items() if float(stamp) >= cutoff
        }
        self._speed_gate_cooldowns = {
            key: stamp for key, stamp in self._speed_gate_cooldowns.items() if float(stamp) >= cutoff
        }
        self._hazard_tick = {
            key: stamp for key, stamp in self._hazard_tick.items() if float(stamp) >= cutoff
        }

    def _actor_close_to_point(self, actor, center: Vec3, radius: float) -> bool:
        if not actor:
            return False
        delta = actor.world_position - center
        if abs(delta.y) > 2.1:
            return False
        return (delta.x * delta.x + delta.z * delta.z) <= (radius * radius)

    def _update_jump_pads(self, players, enemies, dt: float) -> None:
        for pad in self.jump_pads:
            pulse = 1.0 + 0.14 * math.sin(self.runtime * 8.2 + pad["id"])
            pad["ring"].scale = (0.9 * pulse, 0.08, 0.9 * pulse)
            pad["arrow"].rotation_y += 120 * dt

            candidates = []
            for player in players:
                if player and getattr(player, "alive", False):
                    candidates.append(player)
            for enemy in enemies:
                if enemy and not getattr(enemy, "dead", False):
                    candidates.append(enemy)

            for actor in candidates:
                if not self._actor_close_to_point(actor, pad["position"], pad["radius"]):
                    continue
                key = (pad["id"], id(actor))
                if self.runtime - self._jump_pad_cooldowns.get(key, -99.0) < pad["cooldown"]:
                    continue
                self._jump_pad_cooldowns[key] = self.runtime
                actor.vertical_velocity = max(actor.vertical_velocity, pad["power"])
                if hasattr(actor, "grounded"):
                    actor.grounded = False
                push = 0.08 * float(pad["forward_boost"])
                actor.x += pad["forward"].x * push
                actor.z += pad["forward"].z * push
                actor.y += 0.02
                local_player = self.game_manager.get_local_player() if hasattr(self.game_manager, "get_local_player") else None
                if actor == local_player:
                    actor.apply_external_speed_boost(multiplier=1.35, duration=1.5)
                    if self.game_manager.camera_controller:
                        self.game_manager.camera_controller.add_shake(0.22)
                    if self.runtime - self._last_player_pad_toast > 2.0:
                        self.game_manager.ui_manager.show_toast("Jump Pad!")
                        self._last_player_pad_toast = self.runtime

    def _update_speed_gates(self, players, dt: float) -> None:
        if not players:
            return
        for gate in self.speed_gates:
            gate["beam"].rotation_z += 140 * dt
            gate["beam"].color = color.rgba(120, 220, 255, 90 + int(50 * abs(math.sin(self.runtime * 5.8 + gate["id"]))))
            for player in players:
                if not player or not getattr(player, "alive", False):
                    continue
                if not self._actor_close_to_point(player, gate["position"], gate["radius"]):
                    continue
                key = (gate["id"], id(player))
                if self.runtime - self._speed_gate_cooldowns.get(key, -99.0) < gate["cooldown"]:
                    continue
                self._speed_gate_cooldowns[key] = self.runtime
                player.apply_external_speed_boost(multiplier=gate["boost_mult"], duration=gate["duration"])
                player.x += player.forward.x * 0.45
                player.z += player.forward.z * 0.45
                local_player = self.game_manager.get_local_player() if hasattr(self.game_manager, "get_local_player") else None
                if player == local_player and self.game_manager.camera_controller:
                    self.game_manager.camera_controller.add_shake(0.3)
                if player == local_player and self.runtime - self._last_player_gate_toast > 2.0:
                    self.game_manager.ui_manager.show_toast("Speed Gate Boost!")
                    self._last_player_gate_toast = self.runtime

    def _update_hazard_zones(self, players, enemies, dt: float) -> None:
        for zone in self.hazard_zones:
            zone["base"].rotation_y += 30 * dt
            zone["core"].y = zone["position"].y + 0.28 + 0.08 * math.sin(self.runtime * 3.4 + zone["id"])
            actors = []
            for player in players:
                if player and getattr(player, "alive", False):
                    actors.append(player)
            for enemy in enemies:
                if enemy and not getattr(enemy, "dead", False):
                    actors.append(enemy)

            for actor in actors:
                if not self._actor_close_to_point(actor, zone["position"], zone["radius"]):
                    continue
                key = (zone["id"], id(actor))
                tick_interval = zone["tick_interval"]
                if self.runtime - self._hazard_tick.get(key, -99.0) < tick_interval:
                    continue
                self._hazard_tick[key] = self.runtime
                actor.take_damage(zone["tick_damage"])
                local_player = self.game_manager.get_local_player() if hasattr(self.game_manager, "get_local_player") else None
                if actor == local_player and self.game_manager.camera_controller:
                    self.game_manager.camera_controller.add_shake(0.14)

    def get_random_spawn_point(self, player_pos: Vec3, min_distance: float = 12.0) -> Vec3:
        if not self.spawn_points:
            return Vec3(0, 1.2, 0)
        if player_pos is None:
            return Vec3(self.rng.choice(self.spawn_points))
        start_index = self.rng.randrange(len(self.spawn_points))
        for offset in range(len(self.spawn_points)):
            point = self.spawn_points[(start_index + offset) % len(self.spawn_points)]
            if distance(point, player_pos) >= min_distance:
                return point
        return Vec3(self.rng.choice(self.spawn_points))

    def get_location_position(self, location_name: str) -> Optional[Vec3]:
        return self.locations.get(location_name)

    def get_player_spawn_point(self, team_id: str = "") -> Vec3:
        if self.player_spawn_points:
            team = str(team_id or "").lower()
            if team in ("team_a", "red", "a"):
                return Vec3(self.player_spawn_points[0])
            if team in ("team_b", "blue", "b") and len(self.player_spawn_points) > 1:
                return Vec3(self.player_spawn_points[1])
            return Vec3(self.rng.choice(self.player_spawn_points))
        return Vec3(self.safe_player_spawn)

    def get_collectible_spawns(self) -> List[Tuple[Vec3, str]]:
        return list(self.collectible_spawns)

    def get_map_half_extent(self) -> float:
        return float(max(20.0, self.map_half_extent))

    def get_biome_theme(self) -> str:
        return str(self.biome_theme)

    def get_map_id(self) -> str:
        return str(self.map_id)

    def get_world_layout(self) -> str:
        return str(self.world_layout)

    def _register_walkable_surface(self, entity: Entity) -> None:
        entity.is_walkable_surface = True
        self.walkable_surfaces.append(entity)

    def get_walkable_surfaces(self) -> List[Entity]:
        return [surface for surface in self.walkable_surfaces if surface and getattr(surface, "enabled", False)]

    def _extract_light_node(self, light_entity):
        if not light_entity:
            return None
        try:
            light_np = light_entity.find("**/+Light")
            if light_np and not light_np.is_empty():
                return light_np
        except Exception:
            pass
        return None

    def _clear_render_light(self, light_entity, light_np) -> None:
        render_root = self._get_render_root()
        if light_np:
            try:
                if render_root:
                    render_root.clearLight(light_np)
            except Exception:
                pass
        elif light_entity:
            guessed_np = self._extract_light_node(light_entity)
            if guessed_np:
                try:
                    if render_root:
                        render_root.clearLight(guessed_np)
                except Exception:
                    pass
        if light_entity:
            try:
                light_entity.enabled = False
            except Exception:
                pass
            try:
                destroy(light_entity)
            except Exception:
                pass

    def _disable_entity_tree(self, root: Entity) -> None:
        if not root:
            return
        stack = [root]
        while stack:
            node = stack.pop()
            if not node:
                continue
            try:
                node.enabled = False
            except Exception:
                pass
            try:
                node.collider = None
            except Exception:
                pass
            try:
                children = list(getattr(node, "children", []))
            except Exception:
                children = []
            for child in children:
                if child:
                    stack.append(child)

    def _get_render_root(self):
        base = getattr(application, "base", None)
        if base is not None and hasattr(base, "render"):
            return base.render
        return None

    def destroy(self) -> None:
        for barrel in list(self.explosive_props):
            if barrel:
                destroy(barrel)
        self.explosive_props = []
        self._clear_render_light(self.sun, self._sun_light_np)
        self._clear_render_light(self.fill_light, self._fill_light_np)
        self._clear_render_light(self.ambient, self._ambient_light_np)
        self.sun = None
        self.fill_light = None
        self.ambient = None
        self._sun_light_np = None
        self._fill_light_np = None
        self._ambient_light_np = None
        if self.root:
            self._disable_entity_tree(self.root)
            destroy(self.root)
            self.root = None
        self.effect_entities = []
        self.spawn_points = []
        self.player_spawn_points = []
        self.walkable_surfaces = []
        self.jump_pads = []
        self.speed_gates = []
        self.hazard_zones = []
        self._jump_pad_cooldowns = {}
        self._speed_gate_cooldowns = {}
        self._hazard_tick = {}
        self._cooldown_prune_timer = 0.0
        self.objective_marker = None
        self.objective_target = None
        self.game_manager = None
