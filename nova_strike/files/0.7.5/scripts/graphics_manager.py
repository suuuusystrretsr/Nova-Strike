from ursina import Vec2, camera, color, scene


class GraphicsManager:
    PRESETS = {
        "LOW": {
            "shadows": False,
            "shadow_resolution": 512,
            "sun_strength": 0.82,
            "ambient_strength": 0.52,
            "render_distance": 125,
            "fog_density": (90, 130),
            "effects_enabled": False,
        },
        "MEDIUM": {
            "shadows": True,
            "shadow_resolution": 512,
            "sun_strength": 0.98,
            "ambient_strength": 0.64,
            "render_distance": 180,
            "fog_density": (120, 185),
            "effects_enabled": True,
        },
        "HIGH": {
            "shadows": True,
            "shadow_resolution": 896,
            "sun_strength": 1.1,
            "ambient_strength": 0.72,
            "render_distance": 240,
            "fog_density": (165, 245),
            "effects_enabled": True,
        },
        "ULTRA": {
            "shadows": True,
            "shadow_resolution": 1024,
            "sun_strength": 1.25,
            "ambient_strength": 0.8,
            "render_distance": 310,
            "fog_density": (200, 320),
            "effects_enabled": True,
        },
    }

    def __init__(self, settings_manager) -> None:
        self.settings_manager = settings_manager
        initial = self.settings_manager.get_graphics_preset().upper()
        self.current_preset = initial if initial in self.PRESETS else "MEDIUM"

    def get_current_config(self):
        return self.PRESETS[self.current_preset]

    def apply_current(self, world=None) -> None:
        self.apply_preset(self.current_preset, world=world, save=False)

    def apply_preset(self, preset: str, world=None, save: bool = True) -> None:
        preset = preset.upper()
        if preset not in self.PRESETS:
            preset = "MEDIUM"
        self.current_preset = preset
        cfg = self.PRESETS[preset]

        camera.clip_plane_far = cfg["render_distance"]
        scene.fog_color = color.rgb(86, 132, 186)
        scene.fog_density = cfg["fog_density"]

        if world:
            # Shadow mode is applied when creating a new world to avoid Panda/Ursina
            # NodePath assertion crashes when toggling shadows on stale scene internals.
            if hasattr(world, "apply_graphics_config"):
                world.apply_graphics_config(cfg, allow_shadow_change=False)
            else:
                if getattr(world, "sun", None):
                    sun_r = min(255, int(255 * cfg["sun_strength"]))
                    sun_g = min(255, int(240 * cfg["sun_strength"]))
                    sun_b = min(255, int(220 * cfg["sun_strength"]))
                    world.sun.color = color.rgba(
                        sun_r,
                        sun_g,
                        sun_b,
                        255,
                    )
                    if hasattr(world.sun, "shadow_map_resolution"):
                        resolution = int(cfg["shadow_resolution"])
                        world.sun.shadow_map_resolution = Vec2(resolution, resolution)

                if getattr(world, "ambient", None):
                    ambient_value = int(190 * cfg["ambient_strength"])
                    world.ambient.color = color.rgba(ambient_value, ambient_value, ambient_value, 255)

                world.set_effect_quality(cfg["effects_enabled"])

        if save:
            self.settings_manager.set_graphics_preset(preset)
