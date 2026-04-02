import time as pytime

from ursina import AmbientLight, Button, DirectionalLight, Entity, Func, Slider, Text, application, camera, color, destroy, scene, time


class MenuButton(Button):
    def __init__(self, **kwargs) -> None:
        default_text_color = kwargs.pop("text_color", color.white)
        defaults = {
            "scale": (0.32, 0.07),
            "color": color.rgb(75, 105, 135),
            "highlight_color": color.rgb(105, 145, 185),
            "pressed_color": color.rgb(58, 86, 120),
            "text_size": 0.83,
        }
        for key, value in defaults.items():
            kwargs.setdefault(key, value)
        super().__init__(**kwargs)
        if getattr(self, "text_entity", None):
            self.text_entity.color = default_text_color
        self.base_scale = (self.scale_x, self.scale_y)
        self.base_color = self.color

    def on_mouse_enter(self):
        self.animate_scale((self.base_scale[0] * 1.04, self.base_scale[1] * 1.04), duration=0.08)
        self.animate_color(self.highlight_color, duration=0.08)

    def on_mouse_exit(self):
        self.animate_scale(self.base_scale, duration=0.08)
        self.animate_color(self.base_color, duration=0.08)


class MenuManager:
    PREVIEW_ACTOR_SCALE = (0.74, 1.86, 0.74)
    PREVIEW_MODEL_SCALE = 0.92
    PREVIEW_FOOT_OFFSET = 0.03

    def __init__(self, game_manager) -> None:
        self.game_manager = game_manager
        self.root = Entity(parent=camera.ui)
        self.settings_return_state = "menu"
        self.selected_skin_id = self.game_manager.skin_system.selected_skin_id
        self.settings_buttons = {}
        self.skin_buttons = {}
        self.multiplayer_hint = None
        self.multiplayer_click_hint = None
        self.net_mode_text = None
        self.net_endpoint_text = None
        self.net_host_btn = None
        self.net_join_btn = None
        self.ctf_size_text = None
        self.ctf_size_buttons = {}
        self.multiplayer_mode_buttons = {}
        self.multiplayer_selection_text = None
        self.selected_multiplayer_mode_id = ""
        self._last_multiplayer_click_mode_id = ""
        self._last_multiplayer_click_ts = 0.0
        self._multiplayer_double_click_window = 0.33
        self.display_mode_label = None
        self.display_mode_button = None

        self.skin_preview_stage = Entity(parent=scene, enabled=False)
        self.skin_preview_models = {}
        self.skin_preview_pedestals = {}
        self.skin_preview_spinners = []
        self._preview_lights = []
        self._skin_preview_ready = False
        self._skin_defs = []

        self._build_main_menu()
        self._build_mode_menu()
        self._build_multiplayer_mode_menu()
        self._build_settings_menu()
        self._build_skin_menu()
        self.hide_all()

    def _build_main_menu(self) -> None:
        self.main_menu = Entity(parent=self.root, enabled=False)
        Entity(parent=self.main_menu, model="quad", color=color.rgba(7, 12, 22, 220), scale=(2, 1.2))
        Text(parent=self.main_menu, text="NOVA STRIKE", y=0.33, scale=1.6, color=color.rgb(210, 236, 255))
        Text(parent=self.main_menu, text="Combat Sandbox", y=0.24, scale=0.62, color=color.rgb(176, 202, 230))
        Text(
            parent=self.main_menu,
            text="WASD Move   Mouse Look   V Camera   Q Ability   T Skill Tree   I Inventory   M Map",
            y=-0.33,
            scale=0.48,
            color=color.rgb(165, 178, 205),
        )

        MenuButton(parent=self.main_menu, text="Single Player", y=0.12, on_click=self.game_manager.show_mode_select)

        multiplayer_btn = MenuButton(parent=self.main_menu, text="Multiplayer", y=0.01, on_click=self._multiplayer_click)
        multiplayer_btn.on_mouse_enter = Func(self._on_multiplayer_enter, multiplayer_btn)
        multiplayer_btn.on_mouse_exit = Func(self._on_multiplayer_exit, multiplayer_btn)

        self.multiplayer_hint = Text(
            parent=self.main_menu,
            text="Multiplayer Available",
            y=-0.06,
            scale=0.66,
            color=color.rgb(255, 220, 140),
            enabled=False,
        )
        self.multiplayer_click_hint = Text(
            parent=self.main_menu,
            text="",
            y=-0.25,
            scale=0.62,
            color=color.rgb(235, 240, 255),
        )

        MenuButton(parent=self.main_menu, text="Settings", y=-0.1, on_click=lambda: self.game_manager.show_settings_menu("menu"))
        MenuButton(parent=self.main_menu, text="Quit", y=-0.21, color=color.rgb(130, 80, 80), on_click=self.game_manager.quit_game)

    def _build_mode_menu(self) -> None:
        self.mode_menu = Entity(parent=self.root, enabled=False)
        Entity(parent=self.mode_menu, model="quad", color=color.rgba(8, 12, 24, 225), scale=(2, 1.2))
        Text(parent=self.mode_menu, text="Single Player", y=0.31, scale=1.18, color=color.rgb(210, 235, 255))
        Text(
            parent=self.mode_menu,
            text="Pick a solo mode.",
            y=0.21,
            scale=0.46,
            color=color.rgb(176, 204, 235),
        )

        MenuButton(
            parent=self.mode_menu,
            text="Mission Mode",
            y=0.08,
            on_click=lambda: self.game_manager.select_mode_and_open_skin("mission"),
        )
        MenuButton(
            parent=self.mode_menu,
            text="Free Roam",
            y=-0.01,
            on_click=lambda: self.game_manager.select_mode_and_open_skin("free_roam"),
        )
        MenuButton(
            parent=self.mode_menu,
            text="Reset Mission Progress",
            y=-0.14,
            scale=(0.3, 0.052),
            color=color.rgb(132, 84, 84),
            highlight_color=color.rgb(160, 101, 101),
            pressed_color=color.rgb(106, 64, 64),
            on_click=self.game_manager.reset_mission_progress,
        )
        MenuButton(
            parent=self.mode_menu,
            text="Reset Free Roam Progress",
            y=-0.22,
            scale=(0.3, 0.052),
            color=color.rgb(118, 86, 74),
            highlight_color=color.rgb(146, 109, 94),
            pressed_color=color.rgb(96, 67, 58),
            on_click=self.game_manager.reset_free_roam_progress,
        )
        MenuButton(parent=self.mode_menu, text="Back", y=-0.3, scale=(0.2, 0.055), on_click=self.game_manager.show_main_menu)

    def _build_multiplayer_mode_menu(self) -> None:
        self.multiplayer_mode_menu = Entity(parent=self.root, enabled=False)
        Entity(parent=self.multiplayer_mode_menu, model="quad", color=color.rgba(8, 12, 24, 225), scale=(2, 1.2))
        Text(parent=self.multiplayer_mode_menu, text="Multiplayer", y=0.31, scale=1.18, color=color.rgb(210, 235, 255))
        Text(
            parent=self.multiplayer_mode_menu,
            text="Pick a multiplayer mode.\nSingle-click to select, double-click to open.",
            y=0.21,
            scale=0.46,
            color=color.rgb(176, 204, 235),
        )

        mode_buttons = (
            ("ctf", "Capture The Flag", 0.08),
            ("battle_royale", "Battle Royale", -0.01),
            ("duel_1v1", "1v1 Duel", -0.1),
        )
        for mode_id, label, y_pos in mode_buttons:
            button = MenuButton(
                parent=self.multiplayer_mode_menu,
                text=label,
                y=y_pos,
                on_click=Func(self._on_multiplayer_mode_click, mode_id),
            )
            self.multiplayer_mode_buttons[mode_id] = button

        self.multiplayer_selection_text = Text(
            parent=self.multiplayer_mode_menu,
            text="",
            y=-0.22,
            scale=0.4,
            color=color.rgb(196, 222, 248),
        )
        MenuButton(
            parent=self.multiplayer_mode_menu,
            text="Back",
            y=-0.5,
            scale=(0.2, 0.055),
            on_click=self.game_manager.show_main_menu,
        )

        self.net_mode_text = Text(
            parent=self.multiplayer_mode_menu,
            text="",
            x=0.32,
            y=0.12,
            scale=0.44,
            color=color.rgb(212, 232, 255),
        )
        self.net_endpoint_text = Text(
            parent=self.multiplayer_mode_menu,
            text="",
            x=0.32,
            y=0.07,
            scale=0.4,
            color=color.rgb(176, 204, 235),
        )
        self.net_host_btn = MenuButton(
            parent=self.multiplayer_mode_menu,
            text="Host",
            x=0.34,
            y=-0.01,
            scale=(0.15, 0.05),
            on_click=Func(self._start_selected_multiplayer_mode, "host"),
        )
        self.net_join_btn = MenuButton(
            parent=self.multiplayer_mode_menu,
            text="Join",
            x=0.52,
            y=-0.01,
            scale=(0.15, 0.05),
            on_click=Func(self._start_selected_multiplayer_mode, "client"),
        )
        self.ctf_size_text = Text(
            parent=self.multiplayer_mode_menu,
            text="",
            x=0.32,
            y=-0.1,
            scale=0.38,
            color=color.rgb(206, 228, 250),
        )
        ctf_sizes = (1, 2, 3, 4)
        for idx, size in enumerate(ctf_sizes):
            button = MenuButton(
                parent=self.multiplayer_mode_menu,
                text=f"{size}v{size}",
                x=0.32 + (idx * 0.1),
                y=-0.16,
                scale=(0.085, 0.045),
                on_click=Func(self._set_ctf_team_size, size),
            )
            self.ctf_size_buttons[size] = button

    def _build_settings_menu(self) -> None:
        self.settings_menu = Entity(parent=self.root, enabled=False)
        Entity(parent=self.settings_menu, model="quad", color=color.rgba(8, 10, 18, 220), scale=(2, 1.2))
        Text(parent=self.settings_menu, text="Settings", y=0.33, scale=1.2, color=color.rgb(210, 235, 255))
        Text(parent=self.settings_menu, text="Graphics Preset", y=0.22, scale=0.64, color=color.rgb(190, 210, 235))

        for i, preset in enumerate(("LOW", "MEDIUM", "HIGH", "ULTRA")):
            button = MenuButton(
                parent=self.settings_menu,
                text=preset,
                y=0.13 - i * 0.08,
                scale=(0.2, 0.055),
                on_click=Func(self._select_graphics_preset, preset),
            )
            self.settings_buttons[preset] = button

        self.sensitivity_label = Text(parent=self.settings_menu, text="Sensitivity", x=0.1, y=0.16, scale=0.54, color=color.rgb(205, 228, 250))
        self.fov_label = Text(parent=self.settings_menu, text="FOV", x=0.1, y=0.03, scale=0.54, color=color.rgb(205, 228, 250))
        self.volume_label = Text(parent=self.settings_menu, text="Volume", x=0.1, y=-0.1, scale=0.54, color=color.rgb(205, 228, 250))
        self.display_mode_label = Text(
            parent=self.settings_menu,
            text="Display Mode",
            x=0.1,
            y=-0.22,
            scale=0.54,
            color=color.rgb(205, 228, 250),
        )
        self.display_mode_button = MenuButton(
            parent=self.settings_menu,
            text="Borderless Fullscreen",
            x=0.38,
            y=-0.23,
            scale=(0.22, 0.055),
            on_click=self._cycle_display_mode,
        )

        self.sensitivity_slider = Slider(
            parent=self.settings_menu,
            min=0.3,
            max=2.2,
            default=self.game_manager.settings_manager.get_mouse_sensitivity(),
            dynamic=True,
            x=0.27,
            y=0.15,
            scale=0.58,
        )
        self.fov_slider = Slider(
            parent=self.settings_menu,
            min=70,
            max=110,
            default=self.game_manager.settings_manager.get_fov(),
            dynamic=True,
            x=0.27,
            y=0.02,
            scale=0.58,
        )
        self.volume_slider = Slider(
            parent=self.settings_menu,
            min=0.0,
            max=1.0,
            default=self.game_manager.settings_manager.get_master_volume(),
            dynamic=True,
            x=0.27,
            y=-0.11,
            scale=0.58,
        )

        self.sensitivity_slider.on_value_changed = self._on_sensitivity_slider
        self.fov_slider.on_value_changed = self._on_fov_slider
        self.volume_slider.on_value_changed = self._on_volume_slider

        self.profile_label = Text(parent=self.settings_menu, text="", x=0.1, y=-0.32, scale=0.54, color=color.rgb(205, 228, 250))
        MenuButton(
            parent=self.settings_menu,
            text="Prev",
            x=0.26,
            y=-0.33,
            scale=(0.11, 0.05),
            on_click=Func(self._cycle_profile, -1),
        )
        MenuButton(
            parent=self.settings_menu,
            text="Next",
            x=0.5,
            y=-0.33,
            scale=(0.11, 0.05),
            on_click=Func(self._cycle_profile, 1),
        )

        MenuButton(parent=self.settings_menu, text="Back", y=-0.43, on_click=self._back_from_settings)

    def _build_skin_menu(self) -> None:
        self.skin_menu = Entity(parent=self.root, enabled=False)
        self.skin_menu_bg = Entity(parent=self.skin_menu, model="quad", color=color.rgba(8, 14, 24, 235), scale=(2, 1.2))
        self.skin_title = Text(parent=self.skin_menu, text="Select Your Operative", y=0.36, scale=1.2, color=color.rgb(215, 236, 255))
        Text(parent=self.skin_menu, text="3D preview updates with your selection", y=0.3, scale=0.5, color=color.rgb(170, 195, 225))

        skins = self.game_manager.skin_system.get_all_skins()
        self._skin_defs = list(skins)
        x_positions = [-0.48, 0.0, 0.48]

        for x_pos, skin in zip(x_positions, skins):
            card = Entity(
                parent=self.skin_menu,
                position=(x_pos, -0.08),
                scale=(0.26, 0.19),
                model="quad",
                color=color.rgba(20, 28, 45, 220),
            )
            Text(parent=card, text=skin.display_name, y=0.14, scale=0.66, color=color.white)
            Text(parent=card, text=skin.skin_id.upper(), y=0.04, scale=0.4, color=color.rgb(168, 190, 220))

            button = MenuButton(
                parent=card,
                text="Choose",
                y=-0.07,
                scale=(0.18, 0.06),
                on_click=Func(self.select_skin, skin.skin_id),
            )
            self.skin_buttons[skin.skin_id] = button

        self.skin_description = Text(parent=self.skin_menu, text="", y=-0.28, scale=0.68, color=color.rgb(200, 220, 245))
        self.start_button = MenuButton(parent=self.skin_menu, text="Start Game", y=-0.36, on_click=self.game_manager.start_gameplay)
        MenuButton(
            parent=self.skin_menu,
            text="Back",
            x=-0.64,
            y=-0.36,
            scale=(0.17, 0.06),
            on_click=self.game_manager.show_mode_menu_for_current_selection,
        )

    def _ensure_skin_preview_ready(self) -> None:
        if self._skin_preview_ready:
            return
        self._build_skin_preview_stage(self._skin_defs)
        self._skin_preview_ready = True

    def _build_skin_preview_stage(self, skins) -> None:
        Entity(parent=self.skin_preview_stage, model="cube", position=(0, -0.72, 6.8), scale=(9.5, 0.2, 5.8), color=color.rgb(32, 43, 61))
        Entity(parent=self.skin_preview_stage, model="cube", position=(0, 1.9, 9.2), scale=(9.5, 4.8, 0.2), color=color.rgb(16, 24, 40))
        self._rebuild_preview_lights()

        preview_positions = [-2.6, 0.0, 2.6]
        for i, (x_pos, skin) in enumerate(zip(preview_positions, skins)):
            pedestal = Entity(
                parent=self.skin_preview_stage,
                model="cube",
                position=(x_pos, -0.2, 6.8),
                scale=(1.45, 0.52, 1.45),
                color=color.rgb(70, 85, 108),
            )

            pedestal_top_y = pedestal.y + (pedestal.scale_y * 0.5)
            actor_half_height = self.PREVIEW_ACTOR_SCALE[1] * 0.5
            actor_y = pedestal_top_y + actor_half_height - self.PREVIEW_FOOT_OFFSET + 0.02

            actor = Entity(
                parent=self.skin_preview_stage,
                position=(x_pos, actor_y, 6.8),
                scale=self.PREVIEW_ACTOR_SCALE,
            )
            visual_root = Entity(
                parent=actor,
                scale=(
                    1.0 / max(0.001, self.PREVIEW_ACTOR_SCALE[0]),
                    1.0 / max(0.001, self.PREVIEW_ACTOR_SCALE[1]),
                    1.0 / max(0.001, self.PREVIEW_ACTOR_SCALE[2]),
                ),
            )
            model = self.game_manager.asset_loader.load_player_model(skin, parent=visual_root)
            model.scale = self.PREVIEW_MODEL_SCALE
            model.y = self._get_aligned_model_y(model, actor_half_height)
            actor.rotation_y = 160

            self.skin_preview_pedestals[skin.skin_id] = pedestal
            self.skin_preview_models[skin.skin_id] = actor
            self.skin_preview_spinners.append((actor, 18 + i * 7))

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

    def _register_preview_light(self, light_entity) -> None:
        self._preview_lights.append((light_entity, self._extract_light_node(light_entity)))

    def _rebuild_preview_lights(self) -> None:
        if self._preview_lights:
            return
        key = DirectionalLight(parent=self.skin_preview_stage, rotation=(35, -20, 0), color=color.rgba(255, 245, 232, 255))
        fill = AmbientLight(parent=self.skin_preview_stage, color=color.rgba(105, 105, 120, 255))
        self._register_preview_light(key)
        self._register_preview_light(fill)

    def _clear_preview_lights(self) -> None:
        render_root = self._get_render_root()
        for light_entity, light_np in self._preview_lights:
            if light_np:
                try:
                    if render_root:
                        render_root.clearLight(light_np)
                except Exception:
                    pass
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
        self._preview_lights = []

    def _get_render_root(self):
        base = getattr(application, "base", None)
        if base is not None and hasattr(base, "render"):
            return base.render
        return None

    def _get_aligned_model_y(self, model: Entity, actor_half_height: float) -> float:
        foot_level = float(getattr(model, "foot_level", -1.22))
        model_scale_y = float(getattr(model, "scale_y", 1.0))
        desired_foot = -actor_half_height + self.PREVIEW_FOOT_OFFSET
        return desired_foot - (foot_level * model_scale_y)

    def hide_all(self) -> None:
        self.main_menu.enabled = False
        self.mode_menu.enabled = False
        self.multiplayer_mode_menu.enabled = False
        self.settings_menu.enabled = False
        self.skin_menu.enabled = False
        self.skin_preview_stage.enabled = False
        self._clear_preview_lights()

    def _should_enforce_character_lock(self) -> bool:
        mode = self.game_manager.mode_registry.resolve_mode(self.game_manager.mode_id)
        return not mode.is_multiplayer

    def show_title(self) -> None:
        # Legacy alias: title screen was removed; route to main menu.
        self.show_main_menu()

    def show_main_menu(self) -> None:
        self.hide_all()
        self.main_menu.enabled = True
        self.multiplayer_click_hint.text = ""

    def show_mode_menu(self) -> None:
        self.hide_all()
        self.mode_menu.enabled = True

    def show_multiplayer_mode_menu(self) -> None:
        self.hide_all()
        self.multiplayer_mode_menu.enabled = True
        self._last_multiplayer_click_mode_id = ""
        self._last_multiplayer_click_ts = 0.0
        self._ensure_multiplayer_mode_selection()
        self._refresh_multiplayer_connection_panel()
        self._refresh_ctf_team_size_panel()

    def show_settings_menu(self, return_state: str) -> None:
        self.hide_all()
        self.settings_return_state = return_state
        self.settings_menu.enabled = True
        self._refresh_graphics_buttons()
        self.sensitivity_slider.value = self.game_manager.settings_manager.get_mouse_sensitivity()
        self.fov_slider.value = self.game_manager.settings_manager.get_fov()
        self.volume_slider.value = self.game_manager.settings_manager.get_master_volume()
        self._refresh_slider_labels()
        self._refresh_display_mode_button()
        self._refresh_profile_label()

    def show_skin_menu(self) -> None:
        self.hide_all()
        self.skin_menu.enabled = True
        self._ensure_skin_preview_ready()
        self._rebuild_preview_lights()
        self.skin_preview_stage.enabled = True
        locked_skin_id = self.game_manager.progression_manager.get_locked_skin_id() if self._should_enforce_character_lock() else None
        if locked_skin_id:
            self.select_skin(locked_skin_id, force=True)
        else:
            self.select_skin(self.game_manager.skin_system.selected_skin_id, force=True)
        resolved_mode = self.game_manager.mode_registry.resolve_mode(self.game_manager.mode_id)
        self.skin_title.text = f"Select Your Operative - {resolved_mode.display_name}"
        if resolved_mode.mode_id == "mission_pve":
            self.start_button.text = "Start Mission"
        elif resolved_mode.mode_id == "free_roam_pve":
            self.start_button.text = "Start Free Roam"
        else:
            self.start_button.text = f"Start {self.game_manager.get_multiplayer_connection_mode_label()}"
        for current_id, button in self.skin_buttons.items():
            if locked_skin_id and current_id != locked_skin_id:
                button.enabled = False
                button.base_color = color.rgb(60, 70, 85)
                button.color = button.base_color
            else:
                button.enabled = True
        if locked_skin_id:
            locked_skin = self.game_manager.skin_system.get_skin(locked_skin_id)
            self.skin_description.text = f"{locked_skin.display_name} locked for this profile (reset progress to change)"

    def select_skin(self, skin_id: str, force: bool = False) -> None:
        locked_skin_id = self.game_manager.progression_manager.get_locked_skin_id() if self._should_enforce_character_lock() else None
        if locked_skin_id and skin_id != locked_skin_id and not force:
            self.game_manager.ui_manager.show_toast("Operative is locked for this profile")
            return
        self.selected_skin_id = skin_id
        self.game_manager.skin_system.select_skin(skin_id)
        chosen = self.game_manager.skin_system.get_skin(skin_id)
        if not locked_skin_id or force:
            self.skin_description.text = f"{chosen.display_name} selected"
        self._apply_skin_menu_theme(chosen.skin_id)

        for current_id, button in self.skin_buttons.items():
            if current_id == skin_id:
                button.base_color = color.rgb(96, 158, 110)
                button.color = button.base_color
            else:
                button.base_color = color.rgb(75, 105, 135)
                button.color = button.base_color

        for current_id, pedestal in self.skin_preview_pedestals.items():
            pedestal.color = color.rgb(90, 145, 102) if current_id == skin_id else color.rgb(70, 85, 108)

    def _apply_skin_menu_theme(self, skin_id: str) -> None:
        themes = {
            "striker": color.rgba(12, 28, 58, 235),
            "phantom": color.rgba(10, 46, 34, 235),
            "vanguard": color.rgba(54, 26, 14, 235),
        }
        self.skin_menu_bg.color = themes.get(skin_id, color.rgba(8, 14, 24, 235))

    def _set_multiplayer_hint(self, enabled: bool) -> None:
        self.multiplayer_hint.enabled = enabled

    def _on_multiplayer_enter(self, button: MenuButton) -> None:
        self._set_multiplayer_hint(True)
        button.animate_scale((button.base_scale[0] * 1.04, button.base_scale[1] * 1.04), duration=0.08)
        button.animate_color(button.highlight_color, duration=0.08)

    def _on_multiplayer_exit(self, button: MenuButton) -> None:
        self._set_multiplayer_hint(False)
        button.animate_scale(button.base_scale, duration=0.08)
        button.animate_color(button.base_color, duration=0.08)

    def _multiplayer_click(self) -> None:
        self.multiplayer_click_hint.text = "Single-click a mode to select, double-click to open, or use Host/Join."
        self.game_manager.show_multiplayer_mode_select()
        self.game_manager.ui_manager.show_toast("Single-click mode to select, double-click to open, or Host/Join")

    def _set_multiplayer_connection_mode(self, mode: str) -> None:
        self.game_manager.set_multiplayer_connection_mode(mode)
        self._refresh_multiplayer_connection_panel()

    def _start_selected_multiplayer_mode(self, mode: str) -> None:
        self._set_multiplayer_connection_mode(mode)
        self._launch_selected_multiplayer_mode()

    def _ensure_multiplayer_mode_selection(self) -> None:
        mode = self.game_manager.mode_registry.resolve_mode(self.game_manager.mode_id)
        if mode.is_multiplayer:
            preferred_mode_id = mode.mode_id
        elif self.selected_multiplayer_mode_id:
            preferred_mode_id = self.selected_multiplayer_mode_id
        else:
            preferred_mode_id = "ctf"
        self._set_selected_multiplayer_mode(preferred_mode_id, show_feedback=False)

    def _set_selected_multiplayer_mode(self, mode_id: str, show_feedback: bool = False) -> str:
        resolved = self.game_manager.mode_registry.resolve_mode(mode_id)
        if not resolved.is_multiplayer:
            resolved = self.game_manager.mode_registry.resolve_mode("ctf")

        self.selected_multiplayer_mode_id = resolved.mode_id
        if resolved.mode_id == "ctf":
            self.game_manager.configure_match(resolved.mode_id, team_size=self.game_manager.get_ctf_team_size_preference())
        else:
            self.game_manager.configure_match(resolved.mode_id)
        self._refresh_multiplayer_mode_selection()

        if show_feedback:
            self.game_manager.ui_manager.show_toast(f"{resolved.display_name} selected. Double-click to open.", duration=1.5)
        return resolved.mode_id

    def _refresh_multiplayer_mode_selection(self) -> None:
        resolved = self.game_manager.mode_registry.resolve_mode(self.selected_multiplayer_mode_id or "ctf")
        selected_mode_id = resolved.mode_id
        for mode_id, button in self.multiplayer_mode_buttons.items():
            is_selected = mode_id == selected_mode_id
            button.base_color = color.rgb(96, 158, 110) if is_selected else color.rgb(75, 105, 135)
            button.color = button.base_color
        if self.multiplayer_selection_text:
            self.multiplayer_selection_text.text = f"Selected: {resolved.display_name}"

        ctf_selected = selected_mode_id == "ctf"
        if self.ctf_size_text:
            self.ctf_size_text.enabled = ctf_selected
        for button in self.ctf_size_buttons.values():
            button.enabled = ctf_selected

    def _on_multiplayer_mode_click(self, mode_id: str) -> None:
        click_time = pytime.perf_counter()
        selected_mode_id = self._set_selected_multiplayer_mode(mode_id, show_feedback=False)
        is_double_click = (
            self._last_multiplayer_click_mode_id == selected_mode_id
            and (click_time - self._last_multiplayer_click_ts) <= self._multiplayer_double_click_window
        )
        self._last_multiplayer_click_mode_id = selected_mode_id
        self._last_multiplayer_click_ts = click_time

        if is_double_click:
            self._launch_selected_multiplayer_mode()
            return
        resolved = self.game_manager.mode_registry.resolve_mode(selected_mode_id)
        self.game_manager.ui_manager.show_toast(f"{resolved.display_name} selected. Double-click to open.", duration=1.5)

    def _launch_selected_multiplayer_mode(self) -> None:
        selected_mode_id = self._set_selected_multiplayer_mode(self.selected_multiplayer_mode_id or "ctf", show_feedback=False)
        if selected_mode_id == "ctf":
            self.game_manager.select_mode_and_open_skin(selected_mode_id, team_size=self.game_manager.get_ctf_team_size_preference())
            return
        self.game_manager.select_mode_and_open_skin(selected_mode_id)

    def _refresh_multiplayer_connection_panel(self) -> None:
        if not self.net_mode_text or not self.net_endpoint_text:
            return
        label = self.game_manager.get_multiplayer_connection_mode_label()
        endpoint = self.game_manager.get_multiplayer_endpoint_label()
        self.net_mode_text.text = f"Multiplayer: {label}"
        self.net_endpoint_text.text = f"Server: {endpoint}"
        host_selected = self.game_manager.multiplayer_connection_mode == "host"
        if self.net_host_btn:
            self.net_host_btn.base_color = color.rgb(96, 158, 110) if host_selected else color.rgb(75, 105, 135)
            self.net_host_btn.color = self.net_host_btn.base_color
        if self.net_join_btn:
            self.net_join_btn.base_color = color.rgb(96, 158, 110) if not host_selected else color.rgb(75, 105, 135)
            self.net_join_btn.color = self.net_join_btn.base_color

    def _set_ctf_team_size(self, team_size: int) -> None:
        self.game_manager.set_ctf_team_size_preference(team_size)
        if self.selected_multiplayer_mode_id == "ctf":
            self.game_manager.configure_match("ctf", team_size=team_size)
        self._refresh_ctf_team_size_panel()

    def _refresh_ctf_team_size_panel(self) -> None:
        if not self.ctf_size_text:
            return
        selected = int(self.game_manager.get_ctf_team_size_preference())
        self.ctf_size_text.text = f"CTF Team Size: {selected}v{selected}"
        for size, button in self.ctf_size_buttons.items():
            is_active = int(size) == selected
            button.base_color = color.rgb(96, 158, 110) if is_active else color.rgb(75, 105, 135)
            button.color = button.base_color

    def _select_graphics_preset(self, preset: str) -> None:
        self.game_manager.apply_graphics_preset(preset)
        self._refresh_graphics_buttons()

    def _refresh_graphics_buttons(self) -> None:
        active = self.game_manager.graphics_manager.current_preset
        for preset, button in self.settings_buttons.items():
            if preset == active:
                button.base_color = color.rgb(96, 158, 110)
                button.color = button.base_color
            else:
                button.base_color = color.rgb(75, 105, 135)
                button.color = button.base_color

    def _on_sensitivity_slider(self) -> None:
        self.game_manager.settings_manager.set_mouse_sensitivity(self.sensitivity_slider.value)
        self._refresh_slider_labels()

    def _on_fov_slider(self) -> None:
        self.game_manager.settings_manager.set_fov(self.fov_slider.value)
        self._refresh_slider_labels()

    def _on_volume_slider(self) -> None:
        self.game_manager.settings_manager.set_master_volume(self.volume_slider.value)
        self.game_manager.refresh_audio_settings()
        self._refresh_slider_labels()

    def _cycle_display_mode(self) -> None:
        self.game_manager.cycle_display_mode(1)
        self._refresh_display_mode_button()

    def _refresh_slider_labels(self) -> None:
        self.sensitivity_label.text = f"Sensitivity: {self.game_manager.settings_manager.get_mouse_sensitivity():.2f}"
        self.fov_label.text = f"FOV: {self.game_manager.settings_manager.get_fov():.0f}"
        self.volume_label.text = f"Volume: {int(self.game_manager.settings_manager.get_master_volume() * 100)}%"

    def _refresh_display_mode_button(self) -> None:
        if not self.display_mode_button:
            return
        mode_label = self.game_manager.get_display_mode_label()
        self.display_mode_button.text = mode_label

    def _cycle_profile(self, direction: int) -> None:
        self.game_manager.cycle_profile(direction)
        self._refresh_profile_label()

    def _refresh_profile_label(self) -> None:
        self.profile_label.text = f"Profile: {self.game_manager.get_profile_label()}"

    def _back_from_settings(self) -> None:
        self.game_manager.close_settings_menu(self.settings_return_state)

    def update(self) -> None:
        if not self.skin_menu.enabled or not self.skin_preview_stage.enabled:
            return
        for pivot, speed in self.skin_preview_spinners:
            pivot.rotation_y += speed * time.dt
