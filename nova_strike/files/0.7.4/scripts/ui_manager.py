import math

from ursina import Button, Entity, Text, camera, color, destroy, invoke, lerp, mouse

from scripts.utils import clamp01


class UIManager:
    SKILL_COLOR_LOCKED = color.rgba(86, 92, 108, 230)
    SKILL_COLOR_LOCKED_HI = color.rgba(102, 108, 124, 242)
    SKILL_COLOR_AVAILABLE = color.rgba(82, 132, 210, 236)
    SKILL_COLOR_AVAILABLE_HI = color.rgba(104, 154, 232, 246)
    SKILL_COLOR_UNLOCKED = color.rgba(76, 166, 112, 236)
    SKILL_COLOR_UNLOCKED_HI = color.rgba(94, 188, 128, 246)

    def __init__(self, game_manager) -> None:
        self.game_manager = game_manager
        self.root = Entity(parent=camera.ui)
        self.toast_text = None
        self.hitmarker_timer = 0.0
        self.display_health_ratio = 1.0
        self.dialogue_callback = None
        self.map_open = False
        self.inventory_open = False
        self.skill_tree_open = False
        self.map_anim_time = 0.0
        self.theme_skin_id = None
        self.current_theme = {}
        self._pause_menu_hidden_by_skill_tree = False
        self._hud_hidden_by_skill_tree = False
        self._state_paused_by_skill_tree = False
        self._toast_generation = 0

        self._build_hud()
        self._build_inventory_panel()
        self._build_tactical_map()
        self._build_pause_menu()
        self._build_game_over_menu()
        self._build_damage_overlay()
        self._build_dialogue_ui()
        self._apply_character_theme()

    def _build_hud(self) -> None:
        self.hud = Entity(parent=self.root, enabled=False)

        self.health_label = Text(parent=self.hud, text="HEALTH", position=(-0.84, 0.45), scale=0.65, color=color.white)
        self.health_bg = Entity(
            parent=self.hud,
            model="quad",
            color=color.rgba(20, 20, 30, 190),
            scale=(0.32, 0.032),
            position=(-0.62, 0.45),
        )
        self.health_fill = Entity(
            parent=self.health_bg,
            model="quad",
            color=color.rgb(112, 235, 140),
            scale=(1.0, 0.75),
            position=(-0.5, 0),
            origin=(-0.5, 0),
        )
        self.health_value = Text(parent=self.hud, text="100", position=(-0.46, 0.444), scale=0.63, color=color.white)

        self.weapon_text = Text(parent=self.hud, text="VX Rifle", position=(0.56, 0.43), scale=0.67, color=color.white)
        self.ammo_text = Text(parent=self.hud, text="30 / 180", position=(0.69, 0.387), scale=0.74, color=color.rgb(220, 245, 255))
        self.coins_text = Text(parent=self.hud, text="COINS 0", position=(0.6, 0.325), scale=0.62, color=color.rgb(255, 224, 132))
        self.mode_text = Text(parent=self.hud, text="MISSION", position=(-0.86, 0.37), scale=0.52, color=color.rgb(180, 210, 245))

        self.objective_text = Text(parent=self.hud, text="", position=(-0.86, -0.36), scale=0.52, color=color.rgb(230, 240, 255))
        self.quest_text = Text(parent=self.hud, text="", position=(-0.86, -0.43), scale=0.43, color=color.rgb(178, 208, 235))
        self.interact_prompt = Text(parent=self.hud, text="", position=(-0.2, -0.28), scale=0.56, color=color.rgb(245, 245, 215), enabled=False)

        self.crosshair = Text(parent=self.hud, text="+", origin=(0, 0), position=(0, 0), scale=1.25, color=color.white)
        self.hitmarker = Text(parent=self.hud, text="x", origin=(0, 0), position=(0, 0), scale=1.2, color=color.rgba(255, 255, 255, 0))
        self.inventory_hint = Text(parent=self.hud, text="[I] Inventory", position=(0.74, -0.47), scale=0.45, color=color.rgb(178, 198, 226))
        self.perk_text = Text(parent=self.hud, text="", position=(-0.84, 0.3), scale=0.46, color=color.rgb(178, 240, 210))

        self.mini_map_root = Entity(parent=self.hud, position=(0.73, 0.25))
        self.mini_map_frame = Entity(parent=self.mini_map_root, model="quad", scale=(0.32, 0.24), color=color.rgba(10, 18, 28, 210))
        self.mini_map_canvas = Entity(parent=self.mini_map_root, model="quad", scale=(0.28, 0.2), color=color.rgb(28, 38, 54))
        for i in range(-2, 3):
            Entity(parent=self.mini_map_canvas, model="quad", scale=(0.004, 0.98), x=i * 0.12, color=color.rgba(140, 170, 205, 65))
            Entity(parent=self.mini_map_canvas, model="quad", scale=(0.98, 0.004), y=i * 0.1, color=color.rgba(140, 170, 205, 65))
        self.mini_player_marker = Entity(parent=self.mini_map_canvas, model="quad", scale=(0.035, 0.035), color=color.rgb(70, 210, 255), z=-0.01)
        self.mini_player_dir = Entity(parent=self.mini_player_marker, model="quad", scale=(0.012, 0.04), y=0.03, color=color.rgb(220, 255, 255), z=-0.01)
        self.mini_objective_marker = Entity(parent=self.mini_map_canvas, model="quad", scale=(0.04, 0.04), color=color.rgb(255, 228, 86), z=-0.01, enabled=False)
        self.mini_enemy_markers = []
        for _ in range(10):
            marker = Entity(parent=self.mini_map_canvas, model="quad", scale=(0.022, 0.022), color=color.rgb(255, 126, 126), z=-0.01, enabled=False)
            self.mini_enemy_markers.append(marker)
        self.mini_npc_markers = []
        for _ in range(6):
            marker = Entity(parent=self.mini_map_canvas, model="quad", scale=(0.022, 0.022), color=color.rgb(255, 180, 96), z=-0.01, enabled=False)
            self.mini_npc_markers.append(marker)

        self.always_hud_entities = [
            self.health_label,
            self.health_bg,
            self.health_fill,
            self.health_value,
            self.perk_text,
            self.mini_map_root,
        ]
        self.inventory_hud_entities = [
            self.weapon_text,
            self.ammo_text,
            self.coins_text,
            self.mode_text,
            self.objective_text,
            self.quest_text,
        ]
        for entity in self.always_hud_entities + self.inventory_hud_entities:
            entity.enabled = False

    def _build_inventory_panel(self) -> None:
        self.inventory_panel = Entity(parent=self.root, enabled=False, y=-0.01)
        self.inv_bg_main = Entity(parent=self.inventory_panel, model="quad", scale=(1.56, 0.95), color=color.rgba(8, 16, 28, 214))
        self.inv_bg_header = Entity(parent=self.inventory_panel, model="quad", y=0.365, scale=(1.56, 0.11), color=color.rgba(18, 30, 48, 238))
        self.inv_bg_left = Entity(parent=self.inventory_panel, model="quad", x=-0.31, y=-0.01, scale=(0.63, 0.83), color=color.rgba(13, 24, 38, 228))
        self.inv_bg_right = Entity(parent=self.inventory_panel, model="quad", x=0.3, y=-0.01, scale=(0.86, 0.83), color=color.rgba(16, 28, 44, 228))
        self.inv_title = Text(parent=self.inventory_panel, text="INVENTORY", x=-0.72, y=0.333, scale=1.02, color=color.rgb(220, 238, 255))
        self.inv_hint = Text(parent=self.inventory_panel, text="Press I to close", x=0.48, y=0.333, scale=0.62, color=color.rgb(176, 198, 226))

        self.inv_stats_text = Text(parent=self.inventory_panel, x=-0.59, y=0.22, scale=0.72, color=color.rgb(228, 238, 252), text="")
        self.inv_objective_text = Text(parent=self.inventory_panel, x=-0.59, y=-0.08, scale=0.58, color=color.rgb(185, 206, 232), text="")
        self.inv_weapons_title = Text(parent=self.inventory_panel, x=-0.59, y=-0.325, scale=0.64, color=color.rgb(225, 237, 255), text="CLICK WEAPON CARD TO EQUIP")

        self.inventory_cards = []
        card_layout = [
            (-0.02, 0.135),
            (0.245, 0.135),
            (0.51, 0.135),
            (0.115, -0.195),
            (0.38, -0.195),
        ]
        for index, (x_pos, y_pos) in enumerate(card_layout):
            card = Button(
                parent=self.inventory_panel,
                model="quad",
                position=(x_pos, y_pos),
                scale=(0.235, 0.285),
                color=color.rgba(28, 44, 64, 235),
                highlight_color=color.rgba(54, 84, 116, 245),
                pressed_color=color.rgba(24, 36, 52, 245),
                text="",
            )
            card.slot_index = index
            card.base_color = card.color
            card.preview_frame = Entity(parent=card, model="quad", y=0.02, scale=(0.91, 0.63), color=color.rgba(34, 52, 75, 220))
            card.preview_anchor = Entity(parent=card, y=0.012, z=-0.19)
            card.preview_model = None
            card.preview_key = ""
            card.spin_speed = 26 + (index * 5)
            card.name_text = Text(parent=card, text="", y=0.12, scale=0.7, color=color.rgb(228, 238, 255))
            card.rarity_text = Text(parent=card, text="", y=0.085, scale=0.62, color=color.rgb(195, 210, 230))
            card.ammo_text = Text(parent=card, text="", y=-0.115, scale=0.57, color=color.rgb(198, 214, 232))
            card.slot_text = Text(parent=card, text=f"S{index + 1}", x=-0.09, y=-0.115, scale=0.52, color=color.rgb(168, 186, 210))
            card.on_click = lambda i=index: self._on_inventory_card_click(i)
            card.on_mouse_enter = lambda c=card: self._inventory_card_hover(c, True)
            card.on_mouse_exit = lambda c=card: self._inventory_card_hover(c, False)
            self.inventory_cards.append(card)

    def _build_tactical_map(self) -> None:
        self.map_overlay = Entity(parent=self.root, enabled=False)
        Entity(parent=self.map_overlay, model="quad", scale=(2.0, 1.2), color=color.rgba(0, 0, 0, 185))
        Entity(parent=self.map_overlay, model="quad", scale=(1.5, 0.98), color=color.rgba(10, 18, 30, 235))
        Text(parent=self.map_overlay, text="TACTICAL MAP", y=0.43, scale=1.0, color=color.rgb(230, 242, 255))
        Text(parent=self.map_overlay, text="Press M to close", y=0.38, scale=0.5, color=color.rgb(190, 210, 235))

        self.map_canvas = Entity(
            parent=self.map_overlay,
            model="quad",
            scale=(1.28, 0.74),
            y=-0.02,
            color=color.rgb(28, 38, 54),
        )
        for i in range(-4, 5):
            x = i * 0.15
            y = i * 0.09
            Entity(parent=self.map_canvas, model="quad", scale=(0.003, 0.98), x=x, color=color.rgba(140, 170, 205, 75))
            Entity(parent=self.map_canvas, model="quad", scale=(0.98, 0.003), y=y, color=color.rgba(140, 170, 205, 75))

        self.map_player_marker = Entity(
            parent=self.map_canvas,
            model="quad",
            scale=(0.035, 0.035),
            color=color.rgb(70, 210, 255),
            z=-0.01,
        )
        self.map_player_dir = Entity(
            parent=self.map_player_marker,
            model="quad",
            scale=(0.012, 0.04),
            y=0.03,
            color=color.rgb(220, 255, 255),
            z=-0.01,
        )
        self.map_objective_marker = Entity(
            parent=self.map_canvas,
            model="quad",
            scale=(0.045, 0.045),
            color=color.rgb(255, 228, 86),
            z=-0.01,
            enabled=False,
        )
        self.map_goal_arrow = Entity(
            parent=self.map_player_marker,
            model="quad",
            scale=(0.014, 0.06),
            y=0.058,
            color=color.rgb(255, 236, 134),
            z=-0.02,
            enabled=False,
        )
        self.map_landmark_markers = []
        for _ in range(12):
            marker = Entity(
                parent=self.map_canvas,
                model="quad",
                scale=(0.022, 0.022),
                color=color.rgb(148, 186, 230),
                z=-0.01,
                enabled=False,
            )
            self.map_landmark_markers.append(marker)
        self.map_quest_markers = []
        for _ in range(4):
            marker = Entity(
                parent=self.map_canvas,
                model="quad",
                scale=(0.032, 0.032),
                color=color.rgb(255, 160, 95),
                z=-0.01,
                enabled=False,
            )
            self.map_quest_markers.append(marker)

        Text(parent=self.map_overlay, text="Blue: You   Gold: Objective   Orange: Quest Giver   Steel: Landmarks", y=-0.44, scale=0.45, color=color.rgb(200, 220, 245))

    def _build_pause_menu(self) -> None:
        self.pause_menu = Entity(parent=self.root, enabled=False)
        self.pause_bg = Entity(parent=self.pause_menu, model="quad", color=color.rgba(0, 0, 0, 170), scale=(2.0, 1.2))
        self.pause_card = Entity(parent=self.pause_menu, model="quad", color=color.rgba(16, 26, 42, 235), scale=(0.64, 0.62), y=-0.02)
        self.pause_title = Text(parent=self.pause_menu, text="PAUSED", y=0.24, scale=1.35, color=color.rgb(220, 240, 255))

        self.pause_resume_button = Button(
            parent=self.pause_menu,
            text="Resume",
            y=0.12,
            scale=(0.26, 0.07),
            color=color.rgb(90, 130, 170),
            on_click=self.game_manager.resume_game,
        )
        self.pause_skill_button = Button(
            parent=self.pause_menu,
            text="Skill Tree",
            y=0.015,
            scale=(0.26, 0.07),
            color=color.rgb(96, 124, 176),
            on_click=self._toggle_skill_tree_panel,
        )
        self.pause_settings_button = Button(
            parent=self.pause_menu,
            text="Settings",
            y=-0.13,
            scale=(0.26, 0.07),
            color=color.rgb(90, 130, 170),
            on_click=lambda: self.game_manager.show_settings_menu(return_state="paused"),
        )
        self.pause_menu_button = Button(
            parent=self.pause_menu,
            text="Main Menu",
            y=-0.24,
            scale=(0.26, 0.07),
            color=color.rgb(140, 95, 95),
            on_click=self.game_manager.return_to_main_menu,
        )
        self.checkpoint_hint = Text(
            parent=self.pause_menu,
            text="[T] Skill Tree   [F5] Save   [F9] Load",
            y=-0.33,
            scale=0.48,
            color=color.rgb(182, 206, 232),
        )
        self._build_skill_tree_panel()

    def _build_game_over_menu(self) -> None:
        self.game_over_menu = Entity(parent=self.root, enabled=False)
        Entity(parent=self.game_over_menu, model="quad", color=color.rgba(0, 0, 0, 195), scale=(2.0, 1.2))
        self.game_over_title = Text(
            parent=self.game_over_menu,
            text="MISSION FAILED",
            y=0.24,
            scale=1.5,
            color=color.rgb(255, 170, 170),
        )
        self.game_over_subtitle = Text(
            parent=self.game_over_menu,
            text="",
            y=0.12,
            scale=0.86,
            color=color.rgb(220, 225, 240),
        )
        Button(
            parent=self.game_over_menu,
            text="Restart",
            y=-0.02,
            scale=(0.25, 0.07),
            color=color.rgb(90, 130, 170),
            on_click=self.game_manager.restart_gameplay,
        )
        Button(
            parent=self.game_over_menu,
            text="Main Menu",
            y=-0.13,
            scale=(0.25, 0.07),
            color=color.rgb(140, 95, 95),
            on_click=self.game_manager.return_to_main_menu,
        )

    def _build_damage_overlay(self) -> None:
        self.damage_overlay = Entity(
            parent=self.root,
            model="quad",
            color=color.rgba(255, 40, 40, 0),
            scale=(2, 2),
            enabled=False,
        )

    def _build_dialogue_ui(self) -> None:
        self.dialogue_panel = Entity(parent=self.root, enabled=False)
        Entity(parent=self.dialogue_panel, model="quad", color=color.rgba(8, 16, 25, 215), scale=(1.35, 0.42), y=-0.28)
        self.dialogue_speaker = Text(parent=self.dialogue_panel, text="", x=-0.58, y=-0.13, scale=0.75, color=color.rgb(190, 225, 255))
        self.dialogue_text = Text(parent=self.dialogue_panel, text="", x=-0.58, y=-0.22, scale=0.53, color=color.rgb(235, 240, 255))
        self.dialogue_button_1 = Button(
            parent=self.dialogue_panel,
            text="Close",
            x=0.32,
            y=-0.29,
            scale=(0.22, 0.06),
            color=color.rgb(75, 116, 152),
            on_click=lambda: self._select_dialogue_action_by_index(0),
        )
        self.dialogue_button_2 = Button(
            parent=self.dialogue_panel,
            text="",
            x=0.58,
            y=-0.29,
            scale=(0.22, 0.06),
            color=color.rgb(80, 142, 112),
            enabled=False,
            on_click=lambda: self._select_dialogue_action_by_index(1),
        )
        self.dialogue_action_ids = ["close", "close"]

    def _toggle_upgrade_panel(self) -> None:
        # Legacy compatibility hook. Upgrades are now handled by the skill tree.
        self.open_skill_tree_panel()

    def refresh_upgrade_panel(self) -> None:
        # Kept for compatibility with older call sites.
        self.refresh_skill_tree_panel()

    def _build_skill_tree_panel(self) -> None:
        self.skill_tree_panel = Entity(parent=self.root, enabled=False)
        self.skill_tree_backdrop = Entity(parent=self.skill_tree_panel, model="quad", position=(0.0, -0.01), scale=(2.0, 1.2), color=color.rgba(0, 0, 0, 214))
        self.skill_tree_frame = Entity(parent=self.skill_tree_panel, model="quad", position=(0.0, -0.01), scale=(1.88, 1.03), color=color.rgba(6, 12, 24, 250))
        self.skill_tree_header = Entity(parent=self.skill_tree_panel, model="quad", position=(0.0, 0.41), scale=(1.88, 0.108), color=color.rgba(24, 52, 88, 248))
        self.skill_tree_glow_top = Entity(parent=self.skill_tree_panel, model="quad", position=(0.0, 0.356), scale=(1.88, 0.008), color=color.rgba(102, 212, 255, 154))
        self.skill_grid_area = Entity(parent=self.skill_tree_panel, model="quad", position=(-0.36, -0.04), scale=(1.33, 0.87), color=color.rgba(8, 16, 30, 228))
        self.skill_grid_area_inner = Entity(parent=self.skill_grid_area, model="quad", scale=(0.97, 0.94), color=color.rgba(6, 11, 22, 235))
        self.skill_detail_card = Entity(parent=self.skill_tree_panel, model="quad", x=0.66, y=-0.04, scale=(0.5, 0.87), color=color.rgba(12, 22, 38, 246))
        self.skill_detail_glow = Entity(parent=self.skill_detail_card, model="quad", y=0.39, scale=(1.0, 0.012), color=color.rgba(110, 220, 255, 130))

        self.skill_tree_title = Text(parent=self.skill_tree_panel, text="SKILL TREE", x=-0.82, y=0.366, scale=0.96, color=color.rgb(232, 245, 255))
        self.skill_tree_info = Text(parent=self.skill_tree_panel, text="", x=-0.82, y=0.312, scale=0.72, color=color.rgb(186, 210, 236))
        self.skill_tree_hint = Text(
            parent=self.skill_tree_panel,
            text="Press T to close",
            x=0.72,
            y=0.366,
            scale=0.68,
            color=color.rgb(180, 205, 234),
        )
        self.skill_tree_coin_text = Text(parent=self.skill_tree_panel, text="", x=0.42, y=0.312, scale=0.84, color=color.rgb(255, 224, 132))
        self.skill_tree_legend = Text(parent=self.skill_tree_panel, text="Node Status", x=-0.82, y=0.251, scale=0.64, color=color.rgb(184, 210, 236))
        self.legend_locked_sw = Entity(parent=self.skill_tree_panel, model="quad", x=-0.7, y=0.258, scale=(0.022, 0.022), color=self.SKILL_COLOR_LOCKED)
        self.legend_locked_tx = Text(parent=self.skill_tree_panel, text="Locked", x=-0.681, y=0.249, scale=0.6, color=color.rgb(205, 212, 224))
        self.legend_available_sw = Entity(parent=self.skill_tree_panel, model="quad", x=-0.55, y=0.258, scale=(0.022, 0.022), color=self.SKILL_COLOR_AVAILABLE)
        self.legend_available_tx = Text(parent=self.skill_tree_panel, text="Available", x=-0.531, y=0.249, scale=0.6, color=color.rgb(205, 212, 224))
        self.legend_unlocked_sw = Entity(parent=self.skill_tree_panel, model="quad", x=-0.35, y=0.258, scale=(0.022, 0.022), color=self.SKILL_COLOR_UNLOCKED)
        self.legend_unlocked_tx = Text(parent=self.skill_tree_panel, text="Unlocked", x=-0.331, y=0.249, scale=0.6, color=color.rgb(205, 212, 224))
        self.legend_help_text = Text(
            parent=self.skill_tree_panel,
            text="Hover a node to read exact effect and prerequisites. Click any blue node to unlock.",
            x=-0.82,
            y=0.21,
            scale=0.53,
            color=color.rgb(168, 198, 228),
        )
        self.skill_branch_left = Text(parent=self.skill_tree_panel, text="STEALTH", x=-0.72, y=-0.44, scale=0.5, color=color.rgb(152, 218, 200))
        self.skill_branch_mid = Text(parent=self.skill_tree_panel, text="CORE", x=-0.35, y=-0.44, scale=0.5, color=color.rgb(162, 208, 245))
        self.skill_branch_right = Text(parent=self.skill_tree_panel, text="COMBAT", x=-0.03, y=-0.44, scale=0.5, color=color.rgb(238, 198, 165))

        self.skill_detail_title = Text(parent=self.skill_detail_card, text="Skill Details", x=-0.22, y=0.34, scale=1.08, color=color.rgb(232, 244, 255))
        self.skill_detail_cost = Text(parent=self.skill_detail_card, text="", x=-0.22, y=0.27, scale=0.94, color=color.rgb(255, 224, 132))
        self.skill_detail_status = Text(parent=self.skill_detail_card, text="", x=-0.22, y=0.215, scale=0.82, color=color.rgb(184, 214, 240))
        self.skill_detail_desc = Text(parent=self.skill_detail_card, text="", x=-0.22, y=0.115, scale=0.74, color=color.rgb(230, 238, 252))
        self.skill_effects_title = Text(parent=self.skill_detail_card, text="Effects", x=-0.22, y=0.0, scale=0.68, color=color.rgb(160, 206, 245))
        self.skill_detail_effects = Text(parent=self.skill_detail_card, text="", x=-0.22, y=-0.082, scale=0.72, color=color.rgb(176, 212, 244))
        self.skill_require_title = Text(parent=self.skill_detail_card, text="Requirements", x=-0.22, y=-0.245, scale=0.68, color=color.rgb(160, 206, 245))
        self.skill_detail_hint = Text(parent=self.skill_detail_card, text="", x=-0.22, y=-0.312, scale=0.64, color=color.rgb(168, 198, 228))
        self.skill_tree_nodes_cache = []
        self.skill_tree_unlocked_cache = set()
        self.skill_connection_lines = []

        self.skill_node_buttons = []
        for index in range(24):
            btn = Button(
                parent=self.skill_tree_panel,
                model="circle",
                text="",
                scale=(0.082, 0.082),
                x=0,
                y=0,
                color=color.rgba(56, 68, 86, 218),
                highlight_color=color.rgba(92, 126, 176, 238),
                pressed_color=color.rgba(44, 58, 76, 236),
                text_size=0.01,
            )
            btn.node_id = None
            btn.cost = 0
            btn.node_index = index
            btn.base_scale = (btn.scale_x, btn.scale_y)
            btn.ring = Entity(parent=btn, model="circle", scale=(1.14, 1.14), color=color.rgba(112, 160, 220, 84), z=0.01, ignore=True)
            btn.core = Entity(parent=btn, model="circle", scale=(0.78, 0.78), color=color.rgba(18, 26, 38, 188), z=-0.01, ignore=True)
            btn.label_text = Text(parent=btn, text="", y=0.004, z=-0.03, origin=(0, 0), scale=1.06, color=color.rgb(228, 236, 248), ignore=True)
            btn.cost_text = Text(parent=btn, text="", y=-0.026, z=-0.031, origin=(0, 0), scale=0.88, color=color.rgb(198, 210, 228), ignore=True)
            btn.on_click = lambda b=btn: self._on_skill_node_click(b)
            btn.on_mouse_enter = lambda b=btn: self._on_skill_node_enter(b)
            btn.on_mouse_exit = lambda b=btn: self._on_skill_node_exit(b)
            self.skill_node_buttons.append(btn)

    def _clear_skill_connection_lines(self) -> None:
        for line in getattr(self, "skill_connection_lines", []):
            if line:
                destroy(line)
        self.skill_connection_lines = []

    def _draw_skill_connections(self, node_positions, unlocked_ids) -> None:
        self._clear_skill_connection_lines()
        for node in self.skill_tree_nodes_cache:
            if node.node_id not in node_positions:
                continue
            end_x, end_y = node_positions[node.node_id]
            for req_id in node.prereqs:
                if req_id not in node_positions:
                    continue
                start_x, start_y = node_positions[req_id]
                dx = end_x - start_x
                dy = end_y - start_y
                length = max(0.001, math.sqrt(dx * dx + dy * dy))
                angle = -math.degrees(math.atan2(dx, dy))
                is_active_path = req_id in unlocked_ids and node.node_id in unlocked_ids
                glow_color = color.rgba(96, 236, 164, 95) if is_active_path else color.rgba(112, 168, 236, 48)
                line_color = color.rgba(86, 196, 136, 188) if is_active_path else color.rgba(94, 140, 196, 142)
                glow = Entity(
                    parent=self.skill_tree_panel,
                    model="quad",
                    position=(start_x + dx * 0.5, start_y + dy * 0.5, -0.02),
                    scale=(0.011, length + 0.005),
                    rotation=(0, 0, angle),
                    color=glow_color,
                    ignore=True,
                )
                line = Entity(
                    parent=self.skill_tree_panel,
                    model="quad",
                    position=(start_x + dx * 0.5, start_y + dy * 0.5, -0.021),
                    scale=(0.0043, length),
                    rotation=(0, 0, angle),
                    color=line_color,
                    ignore=True,
                )
                self.skill_connection_lines.append(glow)
                self.skill_connection_lines.append(line)

    def _layout_skill_nodes(self, nodes) -> dict:
        if not nodes:
            return {}

        tier_y = {1: -0.29, 2: -0.18, 3: -0.07, 4: 0.04, 5: 0.15, 6: 0.25}
        tier_groups = {}
        for node in nodes:
            tier = max(1, int(getattr(node, "tier", 1)))
            tier_groups.setdefault(tier, []).append(node)

        node_positions = {}
        for tier, row_nodes in tier_groups.items():
            row_nodes.sort(key=lambda item: (self._branch_sort_key(self._get_skill_branch(item)), item.name))
            count = len(row_nodes)
            row_y = tier_y.get(tier, -0.31 + (tier * 0.1))
            x_min, x_max = -0.76, 0.05
            if count <= 1:
                x_positions = [(x_min + x_max) * 0.5]
            else:
                x_positions = [x_min + ((x_max - x_min) * (idx / float(max(1, count - 1)))) for idx in range(count)]
            for idx, node in enumerate(row_nodes):
                node_positions[node.node_id] = (x_positions[idx], row_y)
        return node_positions

    def _branch_sort_key(self, branch: str) -> int:
        return {"left": 0, "core": 1, "right": 2}.get(branch, 1)

    def _get_skill_branch(self, node) -> str:
        text = f"{getattr(node, 'node_id', '')} {getattr(node, 'name', '')}".lower()
        if "capstone" in text:
            return "core"
        left_keywords = ("cloak", "ghost", "phase", "nano", "wraith", "shadow", "entropy", "cool", "mist", "silent")
        right_keywords = ("damage", "crit", "ambush", "assassin", "blood", "fire", "needle", "breach", "kinetic", "tempo")
        if any(token in text for token in left_keywords):
            return "left"
        if any(token in text for token in right_keywords):
            return "right"
        return "core"

    def _get_node_display_label(self, node_name: str) -> str:
        cleaned = str(node_name).strip()
        if not cleaned:
            return "Skill"
        words = [w for w in cleaned.replace("-", " ").split() if w]
        suffix = ""
        if words and words[-1] in ("II", "III", "IV"):
            suffix = words[-1]
            words = words[:-1]
        acronym = "".join(word[0].upper() for word in words[:3]) if words else cleaned[:2].upper()
        return f"{acronym}{suffix}"

    def _toggle_skill_tree_panel(self) -> None:
        if not hasattr(self, "skill_tree_panel"):
            return
        if self.skill_tree_open:
            self.close_skill_tree_panel()
        else:
            self.open_skill_tree_panel()

    def _is_multiplayer_context(self) -> bool:
        match_settings = getattr(self.game_manager, "match_settings", None)
        return bool(match_settings and getattr(match_settings, "is_multiplayer", False))

    def _refresh_pause_menu_context(self) -> None:
        multiplayer = self._is_multiplayer_context()
        if hasattr(self, "pause_skill_button"):
            self.pause_skill_button.enabled = not multiplayer
        if hasattr(self, "pause_resume_button") and hasattr(self, "pause_settings_button") and hasattr(self, "pause_menu_button"):
            if multiplayer:
                self.pause_resume_button.y = 0.1
                self.pause_settings_button.y = -0.02
                self.pause_menu_button.y = -0.14
            else:
                self.pause_resume_button.y = 0.12
                self.pause_settings_button.y = -0.13
                self.pause_menu_button.y = -0.24
        if hasattr(self, "checkpoint_hint"):
            if multiplayer:
                self.checkpoint_hint.text = "Checkpoints disabled in multiplayer"
                self.checkpoint_hint.y = -0.25
            else:
                self.checkpoint_hint.text = "[T] Skill Tree   [F5] Save   [F9] Load"
                self.checkpoint_hint.y = -0.33

    def open_skill_tree_panel(self) -> None:
        if not hasattr(self, "skill_tree_panel"):
            return
        if self._is_multiplayer_context():
            self.show_toast("Skill tree disabled in multiplayer", duration=1.4)
            return
        if self.map_open:
            self._set_map_visibility(False)
        self._set_inventory_visibility(False)
        self._state_paused_by_skill_tree = False
        if self.game_manager.state == "playing":
            self._state_paused_by_skill_tree = True
            self.game_manager.state = "paused"
        self._hud_hidden_by_skill_tree = False
        if self.hud.enabled:
            self._hud_hidden_by_skill_tree = True
            self.hud.enabled = False
        self._pause_menu_hidden_by_skill_tree = bool(self.pause_menu.enabled)
        if self._pause_menu_hidden_by_skill_tree:
            self.pause_menu.enabled = False
        self.skill_tree_open = True
        self.skill_tree_panel.enabled = True
        self.crosshair.enabled = False
        self.interact_prompt.enabled = False
        self.refresh_skill_tree_panel()

    def close_skill_tree_panel(self) -> None:
        if not hasattr(self, "skill_tree_panel"):
            return
        self.skill_tree_open = False
        self.skill_tree_panel.enabled = False
        if self._pause_menu_hidden_by_skill_tree and self.game_manager.state == "paused":
            self.pause_menu.enabled = True
        self._pause_menu_hidden_by_skill_tree = False
        if self._state_paused_by_skill_tree and self.game_manager.state == "paused":
            self.game_manager.state = "playing"
            if hasattr(self.game_manager, "_set_game_mouse_mode"):
                self.game_manager._set_game_mouse_mode()
        if self._hud_hidden_by_skill_tree and self.game_manager.state == "playing":
            self.hud.enabled = True
            for entity in self.always_hud_entities:
                entity.enabled = True
            for entity in self.inventory_hud_entities:
                entity.enabled = self.inventory_open
        self._state_paused_by_skill_tree = False
        self._hud_hidden_by_skill_tree = False
        self.crosshair.enabled = self.hud.enabled and not self.map_open
        self.interact_prompt.enabled = self.hud.enabled and bool(self.interact_prompt.text) and not self.map_open and not self.inventory_open

    def is_skill_tree_open(self) -> bool:
        return bool(self.skill_tree_open and hasattr(self, "skill_tree_panel") and self.skill_tree_panel.enabled)

    def refresh_skill_tree_panel(self) -> None:
        if not hasattr(self, "skill_tree_panel"):
            return
        skin_id = self.game_manager.get_skill_tree_skin_id() if hasattr(self.game_manager, "get_skill_tree_skin_id") else "striker"
        nodes = self.game_manager.get_skill_tree_nodes() if hasattr(self.game_manager, "get_skill_tree_nodes") else []
        unlocked_ids = self.game_manager.get_unlocked_skill_ids() if hasattr(self.game_manager, "get_unlocked_skill_ids") else set()
        self.skill_tree_nodes_cache = list(nodes)
        self.skill_tree_unlocked_cache = set(unlocked_ids)
        self._apply_character_theme(skin_id)
        skin_name = skin_id.replace("_", " ").title()
        self.skill_tree_title.text = f"SKILL TREE - {skin_name}"
        self.skill_tree_info.text = f"{len(unlocked_ids)}/{len(nodes)} unlocked"
        self.skill_tree_coin_text.text = f"Coins: {self.game_manager.progression_manager.get_coins()}"
        node_positions = self._layout_skill_nodes(nodes)
        self._draw_skill_connections(node_positions, unlocked_ids)

        for index, button in enumerate(self.skill_node_buttons):
            if index >= len(nodes):
                button.enabled = False
                button.node_id = None
                button.scale = button.base_scale
                button.label_text.text = ""
                button.cost_text.text = ""
                continue
            node = nodes[index]
            button.enabled = True
            button.node_id = node.node_id
            button.cost = node.cost
            if node.node_id in node_positions:
                button.position = node_positions[node.node_id]
            button.text = ""
            prereq_ready = all(req in unlocked_ids for req in node.prereqs)
            is_unlocked = node.node_id in unlocked_ids

            button.label_text.text = self._get_node_display_label(node.name)
            button.cost_text.text = f"{node.cost}c"
            if is_unlocked:
                button.color = self.SKILL_COLOR_UNLOCKED
                button.highlight_color = self.SKILL_COLOR_UNLOCKED_HI
                button.ring.color = color.rgba(88, 220, 144, 165)
                button.core.color = color.rgba(22, 64, 44, 228)
                button.label_text.color = color.rgb(228, 248, 238)
                button.cost_text.color = color.rgb(198, 248, 214)
            elif prereq_ready:
                button.color = self.SKILL_COLOR_AVAILABLE
                button.highlight_color = self.SKILL_COLOR_AVAILABLE_HI
                button.ring.color = color.rgba(118, 196, 255, 160)
                button.core.color = color.rgba(24, 46, 78, 228)
                button.label_text.color = color.rgb(234, 242, 255)
                button.cost_text.color = color.rgb(188, 214, 248)
            else:
                button.color = self.SKILL_COLOR_LOCKED
                button.highlight_color = self.SKILL_COLOR_LOCKED_HI
                button.ring.color = color.rgba(132, 148, 170, 118)
                button.core.color = color.rgba(32, 36, 46, 224)
                button.label_text.color = color.rgb(214, 220, 232)
                button.cost_text.color = color.rgb(184, 194, 210)
        focus_node = None
        for node in nodes:
            if all(req in unlocked_ids for req in node.prereqs) and node.node_id not in unlocked_ids:
                focus_node = node
                break
        if not focus_node:
            for node in nodes:
                if node.node_id in unlocked_ids:
                    focus_node = node
                    break
        if not focus_node and nodes:
            focus_node = nodes[0]
        self._set_skill_detail(focus_node)

    def _on_skill_node_click(self, button) -> None:
        node_id = getattr(button, "node_id", None)
        if not node_id:
            return
        self.game_manager.unlock_skill_node(node_id)

    def _on_skill_node_enter(self, button) -> None:
        self._on_skill_node_hover(button)
        if not getattr(button, "enabled", False):
            return
        button.animate_scale((button.base_scale[0] * 1.08, button.base_scale[1] * 1.08), duration=0.08)
        if hasattr(button, "ring"):
            button.ring.animate_scale((1.28, 1.28), duration=0.08)

    def _on_skill_node_exit(self, button) -> None:
        if not getattr(button, "enabled", False):
            return
        button.animate_scale(button.base_scale, duration=0.08)
        if hasattr(button, "ring"):
            button.ring.animate_scale((1.18, 1.18), duration=0.08)

    def _on_skill_node_hover(self, button) -> None:
        node_id = getattr(button, "node_id", None)
        if not node_id:
            self._set_skill_detail(None)
            return
        node = None
        for current in self.skill_tree_nodes_cache:
            if current.node_id == node_id:
                node = current
                break
        self._set_skill_detail(node)

    def _set_skill_detail(self, node) -> None:
        if not node:
            self.skill_detail_title.text = "Skill Details"
            self.skill_detail_cost.text = ""
            self.skill_detail_status.text = ""
            self.skill_detail_desc.text = "Move your mouse over any node.\nThe full description appears here."
            self.skill_detail_effects.text = ""
            self.skill_detail_hint.text = "Click blue nodes to unlock.\nGreen nodes are already active."
            return
        unlocked = node.node_id in self.skill_tree_unlocked_cache
        prereq_ready = all(req in self.skill_tree_unlocked_cache for req in node.prereqs)
        if unlocked:
            status = "Unlocked"
            status_color = color.rgb(176, 238, 194)
        elif prereq_ready:
            status = "Available"
            status_color = color.rgb(170, 210, 255)
        else:
            status = "Locked"
            status_color = color.rgb(208, 212, 224)
        self.skill_detail_title.text = node.name
        self.skill_detail_cost.text = f"Cost: {node.cost} coins"
        if prereq_ready and not unlocked and self.game_manager.progression_manager.get_coins() < node.cost:
            status = "Available (need more coins)"
            status_color = color.rgb(255, 214, 145)
        self.skill_detail_status.text = f"Tier {node.tier} - {status}"
        self.skill_detail_status.color = status_color
        self.skill_detail_desc.text = self._wrap_text(node.description, max_chars=30, max_lines=3)
        self.skill_detail_effects.text = self._format_effect_summary(node.effects)
        if node.prereqs:
            node_name_map = {item.node_id: item.name for item in self.skill_tree_nodes_cache}
            readable = ", ".join(node_name_map.get(req, req.replace("_", " ").title()) for req in node.prereqs[:3])
            self.skill_detail_hint.text = self._wrap_text(f"Requires: {readable}", max_chars=30, max_lines=2)
        else:
            self.skill_detail_hint.text = "No prerequisites - starter skill."

    def _format_skill_label(self, name: str, max_len: int = 14) -> str:
        label = str(name).strip()
        if len(label) <= max_len:
            return label
        words = [w for w in label.split(" ") if w]
        if len(words) >= 2:
            first = words[0][:max_len]
            second = " ".join(words[1:])
            if len(second) > max_len:
                second = f"{second[:max_len - 1]}."
            return f"{first}\n{second}"
        return f"{label[:max_len - 1]}."

    def _format_effect_summary(self, effects: dict) -> str:
        if not effects:
            return "No direct bonus."
        pretty = {
            "speed_mult": "Movement Speed",
            "sprint_mult": "Sprint Speed",
            "jump_bonus": "Jump Height",
            "reload_mult": "Reload Time",
            "recoil_mult": "Recoil",
            "spread_mult": "Accuracy",
            "damage_mult": "Weapon Damage",
            "fire_rate_mult": "Fire Rate",
            "health_bonus": "Max Health",
            "regen_rate_bonus": "Health Regen",
            "ability_cooldown_mult": "Ability Cooldown",
            "ability_duration_bonus": "Ability Duration",
            "crit_chance": "Crit Chance",
            "crit_damage_mult": "Crit Damage",
            "dodge_chance": "Dodge Chance",
            "damage_reduction": "Damage Reduction",
            "coin_mult": "Coin Gain",
            "lifesteal_bonus": "Lifesteal",
        }
        lines = []
        for key, value in list(effects.items())[:4]:
            label = pretty.get(str(key), str(key).replace("_", " ").title())
            value_f = float(value)
            if "cooldown" in str(key) and value_f < 1:
                text_value = f"-{(1.0 - value_f) * 100:.0f}%"
            elif abs(value_f) < 1:
                text_value = f"+{value_f * 100:.0f}%"
            else:
                text_value = f"+{value_f:.2f}".rstrip("0").rstrip(".")
            lines.append(f"- {label}: {text_value}")
        return "\n".join(lines)

    def _wrap_text(self, text: str, max_chars: int = 32, max_lines: int = 3) -> str:
        words = [word for word in str(text).split() if word]
        if not words:
            return ""
        lines = []
        current = words[0]
        overflow = False
        for word_index, word in enumerate(words[1:], start=1):
            candidate = f"{current} {word}"
            if len(candidate) <= max_chars:
                current = candidate
            else:
                lines.append(current)
                current = word
                if len(lines) >= max_lines - 1:
                    overflow = word_index < len(words) - 1
                    break
        if len(lines) < max_lines:
            lines.append(current)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            overflow = True
        if overflow:
            lines[-1] = f"{lines[-1].rstrip('.')}."
        return "\n".join(lines)

    def _get_theme_for_skin(self, skin_id: str):
        themes = {
            "striker": {
                "panel": color.rgba(14, 26, 46, 238),
                "header": color.rgba(24, 56, 104, 246),
                "accent": color.rgb(94, 178, 255),
                "accent_soft": color.rgb(178, 220, 255),
                "unlocked": color.rgba(74, 166, 114, 238),
                "unlocked_hi": color.rgba(90, 188, 128, 250),
                "available": color.rgba(72, 130, 188, 238),
                "available_hi": color.rgba(92, 154, 212, 250),
                "locked": color.rgba(56, 72, 96, 212),
                "locked_hi": color.rgba(72, 90, 114, 234),
            },
            "phantom": {
                "panel": color.rgba(12, 30, 38, 238),
                "header": color.rgba(22, 88, 96, 246),
                "accent": color.rgb(108, 230, 212),
                "accent_soft": color.rgb(196, 252, 244),
                "unlocked": color.rgba(72, 178, 124, 238),
                "unlocked_hi": color.rgba(88, 202, 140, 250),
                "available": color.rgba(64, 140, 112, 238),
                "available_hi": color.rgba(84, 164, 134, 250),
                "locked": color.rgba(50, 72, 66, 212),
                "locked_hi": color.rgba(64, 88, 82, 234),
            },
            "vanguard": {
                "panel": color.rgba(42, 22, 14, 238),
                "header": color.rgba(86, 42, 28, 246),
                "accent": color.rgb(255, 156, 108),
                "accent_soft": color.rgb(255, 220, 188),
                "unlocked": color.rgba(188, 132, 80, 238),
                "unlocked_hi": color.rgba(208, 148, 96, 250),
                "available": color.rgba(168, 96, 66, 238),
                "available_hi": color.rgba(194, 114, 84, 250),
                "locked": color.rgba(94, 70, 58, 212),
                "locked_hi": color.rgba(114, 84, 72, 234),
            },
        }
        return themes.get(skin_id, themes["striker"])

    def _apply_character_theme(self, skin_id: str = None) -> None:
        if skin_id is None:
            if hasattr(self.game_manager, "get_skill_tree_skin_id"):
                skin_id = self.game_manager.get_skill_tree_skin_id()
            else:
                skin_id = "striker"
        self.theme_skin_id = skin_id
        self.current_theme = self._get_theme_for_skin(skin_id)
        theme = self.current_theme

        if hasattr(self, "skill_tree_frame"):
            self.skill_tree_backdrop.color = color.rgba(0, 0, 0, 205)
            self.skill_tree_frame.color = color.rgba(6, 12, 24, 250)
            self.skill_tree_header.color = theme["header"]
            self.skill_tree_glow_top.color = theme["accent"]
            self.skill_grid_area.color = color.rgba(8, 16, 30, 228)
            self.skill_grid_area_inner.color = color.rgba(6, 11, 22, 235)
            self.skill_detail_card.color = color.rgba(12, 22, 38, 246)
            self.skill_detail_glow.color = theme["accent"]
            self.skill_tree_title.color = theme["accent_soft"]
            self.skill_tree_info.color = theme["accent_soft"]
            self.skill_tree_hint.color = theme["accent_soft"]
            self.skill_tree_legend.color = theme["accent_soft"]
            self.skill_tree_coin_text.color = color.rgb(255, 224, 132)
            self.skill_detail_title.color = theme["accent_soft"]
            self.skill_effects_title.color = theme["accent_soft"]
            self.skill_require_title.color = theme["accent_soft"]
            self.skill_detail_hint.color = theme["accent_soft"]
            self.skill_branch_left.color = color.rgb(152, 218, 200)
            self.skill_branch_mid.color = color.rgb(162, 208, 245)
            self.skill_branch_right.color = color.rgb(238, 198, 165)

        if hasattr(self, "inv_bg_main"):
            self.inv_bg_main.color = color.rgba(8, 16, 28, 214)
            self.inv_bg_header.color = theme["header"]
            self.inv_bg_left.color = theme["panel"]
            self.inv_bg_right.color = theme["panel"]
            self.inv_title.color = theme["accent_soft"]
            self.inv_hint.color = theme["accent_soft"]

        if hasattr(self, "pause_card"):
            self.pause_card.color = theme["panel"]
            self.pause_title.color = theme["accent_soft"]
            self.pause_skill_button.color = theme["available"]

    def show_hud(self) -> None:
        self.hud.enabled = True
        self.pause_menu.enabled = False
        self.dialogue_panel.enabled = False
        self.game_over_menu.enabled = False
        self._refresh_pause_menu_context()
        for entity in self.always_hud_entities:
            entity.enabled = True
        self.close_skill_tree_panel()
        self._set_inventory_visibility(False)

    def hide_hud(self) -> None:
        self.hud.enabled = False
        for entity in self.always_hud_entities:
            entity.enabled = False
        self._hud_hidden_by_skill_tree = False
        self._state_paused_by_skill_tree = False
        self.close_skill_tree_panel()
        self._set_inventory_visibility(False)
        self._clear_inventory_card_previews()

    def show_pause_menu(self) -> None:
        self._refresh_pause_menu_context()
        self.pause_menu.enabled = True
        self.close_skill_tree_panel()
        self._set_inventory_visibility(False)

    def hide_pause_menu(self) -> None:
        self.pause_menu.enabled = False
        self.close_skill_tree_panel()

    def show_game_over(self, title: str, subtitle: str) -> None:
        self.game_over_title.text = title
        self.game_over_subtitle.text = subtitle
        self.game_over_menu.enabled = True
        self.hud.enabled = False
        self.pause_menu.enabled = False
        self.dialogue_panel.enabled = False
        self._hud_hidden_by_skill_tree = False
        self._state_paused_by_skill_tree = False
        self.close_skill_tree_panel()
        self._set_inventory_visibility(False)
        self._set_map_visibility(False)

    def hide_game_over(self) -> None:
        self.game_over_menu.enabled = False

    def update_hud(self, player) -> None:
        if not player or not self.hud.enabled:
            return
        if self.theme_skin_id != player.skin.skin_id:
            self._apply_character_theme(player.skin.skin_id)
        health_ratio = clamp01(player.health / max(1.0, player.health_max))
        self.display_health_ratio = lerp(self.display_health_ratio, health_ratio, min(1.0, 8.5 * self.game_manager.dt))
        self.health_fill.scale_x = self.display_health_ratio
        self.health_fill.color = (
            color.rgb(112, 235, 140)
            if self.display_health_ratio > 0.5
            else color.rgb(255, 201, 110)
            if self.display_health_ratio > 0.25
            else color.rgb(255, 120, 120)
        )
        self.health_value.text = f"{int(player.health)} / {int(player.health_max)}"
        self.weapon_text.text = player.current_weapon.display_name
        self.weapon_text.color = player.current_weapon.rarity_color
        self.ammo_text.text = f"{player.current_weapon.ammo_in_mag} / {player.current_weapon.reserve_ammo}"
        self.coins_text.text = f"COINS {self.game_manager.progression_manager.get_coins()}"
        mode_label = self.game_manager.match_settings.display_name if getattr(self.game_manager, "match_settings", None) else (
            "Free Roam" if self.game_manager.game_mode == "free_roam" else "Mission Mode"
        )
        self.mode_text.text = mode_label.upper()
        perk_labels = player.get_active_perk_labels() if hasattr(player, "get_active_perk_labels") else []
        self.perk_text.text = "Perks: " + (", ".join(perk_labels[:2]) if perk_labels else "None")

        objectives = self.game_manager.get_objective_lines()
        self.objective_text.text = objectives[0] if objectives else ""
        self.quest_text.text = "\n".join(objectives[1:3]) if len(objectives) > 1 else ""
        self._refresh_inventory_contents(player, objectives)
        self._update_minimap(player)

        if self.hitmarker_timer > 0:
            self.hitmarker_timer -= self.game_manager.dt
            alpha = int(255 * clamp01(self.hitmarker_timer / 0.12))
            self.hitmarker.color = color.rgba(255, 255, 255, alpha)
        else:
            self.hitmarker.color = color.rgba(255, 255, 255, 0)

        if self.map_open:
            self._update_tactical_map(player)

    def show_hitmarker(self) -> None:
        self.hitmarker_timer = 0.12
        self.hitmarker.scale = 1.2
        self.hitmarker.animate_scale(1.34, duration=0.05)
        self.hitmarker.animate_scale(1.2, duration=0.05, delay=0.05)

    def set_interact_prompt(self, text: str) -> None:
        self.interact_prompt.text = text
        self.interact_prompt.enabled = self.hud.enabled and bool(text) and not self.map_open and not self.inventory_open and not self.skill_tree_open

    def flash_damage(self) -> None:
        self.damage_overlay.enabled = True
        self.damage_overlay.color = color.rgba(255, 60, 60, 118)
        self.damage_overlay.animate_color(color.rgba(255, 60, 60, 0), duration=0.26)
        invoke(self._hide_damage_overlay, delay=0.27)

    def _hide_damage_overlay(self) -> None:
        self.damage_overlay.enabled = False

    def show_dialogue(self, dialogue_data, on_choice_callback) -> None:
        self.dialogue_callback = on_choice_callback
        self.close_skill_tree_panel()
        self.dialogue_panel.enabled = True
        self.dialogue_speaker.text = dialogue_data.speaker
        self.dialogue_text.text = "\n".join(dialogue_data.lines)

        choices = dialogue_data.choices[:2]
        if choices:
            self.dialogue_button_1.text = choices[0].label
            self.dialogue_button_1.enabled = True
            self.dialogue_action_ids[0] = choices[0].action_id
        else:
            self.dialogue_button_1.text = "Close"
            self.dialogue_button_1.enabled = True
            self.dialogue_action_ids[0] = "close"

        if len(choices) > 1:
            self.dialogue_button_2.text = choices[1].label
            self.dialogue_button_2.enabled = True
            self.dialogue_action_ids[1] = choices[1].action_id
        else:
            self.dialogue_button_2.enabled = False
            self.dialogue_button_2.text = ""
            self.dialogue_action_ids[1] = "close"

    def close_dialogue(self) -> None:
        self.dialogue_panel.enabled = False
        self.dialogue_callback = None
        self._set_inventory_visibility(False)

    def _select_dialogue_action_by_index(self, index: int) -> None:
        if not self.dialogue_callback:
            self.close_dialogue()
            return
        index = max(0, min(1, index))
        action_id = self.dialogue_action_ids[index]
        self.dialogue_callback(action_id)

    def hide_all(self) -> None:
        self.hud.enabled = False
        self.pause_menu.enabled = False
        self._hud_hidden_by_skill_tree = False
        self._state_paused_by_skill_tree = False
        self.close_skill_tree_panel()
        self.game_over_menu.enabled = False
        self.damage_overlay.enabled = False
        self.dialogue_panel.enabled = False
        self.interact_prompt.enabled = False
        self._set_inventory_visibility(False)
        self._set_map_visibility(False)
        self._clear_inventory_card_previews()

    def show_toast(self, message: str, duration: float = 1.7) -> None:
        self._toast_generation += 1
        generation = int(self._toast_generation)
        if self.toast_text:
            destroy(self.toast_text)
            self.toast_text = None
        self.toast_text = Text(
            parent=self.root,
            text=str(message),
            y=-0.44,
            scale=0.78,
            background=True,
            color=color.rgb(235, 240, 255),
        )
        invoke(self._clear_toast, generation=generation, delay=max(0.05, float(duration)))

    def _clear_toast(self, generation: int = -1) -> None:
        if int(generation) != int(self._toast_generation):
            return
        if self.toast_text:
            destroy(self.toast_text)
            self.toast_text = None

    def toggle_tactical_map(self) -> None:
        if self.game_manager.state != "playing":
            return
        self._set_map_visibility(not self.map_open)
        if self.map_open:
            self.show_toast("Map Open - Press M to close", duration=1.0)

    def _set_map_visibility(self, enabled: bool) -> None:
        self.map_open = bool(enabled)
        self.map_overlay.enabled = self.map_open
        if self.map_open:
            self._set_inventory_visibility(False)
            self.close_skill_tree_panel()
        self.crosshair.enabled = self.hud.enabled and not self.map_open and not self.skill_tree_open
        self.interact_prompt.enabled = self.hud.enabled and bool(self.interact_prompt.text) and not self.map_open and not self.inventory_open and not self.skill_tree_open
        if not self.map_open:
            self.map_goal_arrow.enabled = False

    def toggle_inventory(self) -> None:
        if self.game_manager.state != "playing":
            return
        if self.map_open:
            return
        if self.skill_tree_open:
            self.close_skill_tree_panel()
        self._set_inventory_visibility(not self.inventory_open)

    def _set_inventory_visibility(self, enabled: bool) -> None:
        self.inventory_open = bool(enabled) and self.hud.enabled and not self.map_open
        self.inventory_panel.enabled = self.inventory_open
        for entity in self.inventory_hud_entities:
            entity.enabled = self.inventory_open
        for entity in self.always_hud_entities:
            entity.enabled = self.hud.enabled
        self.crosshair.enabled = self.hud.enabled and not self.map_open and not self.skill_tree_open
        self.interact_prompt.enabled = self.hud.enabled and bool(self.interact_prompt.text) and not self.map_open and not self.inventory_open and not self.skill_tree_open
        if self.inventory_open:
            self.inventory_hint.text = "[I] Close Inventory"
        else:
            self.inventory_hint.text = "[I] Inventory"

    def _refresh_inventory_contents(self, player, objectives) -> None:
        if not self.inventory_panel.enabled:
            return
        active_perks = player.get_active_perk_labels() if hasattr(player, "get_active_perk_labels") else []
        ability_line = f"Ability: {player.get_ability_status_line()}"
        if self._is_multiplayer_context():
            ability_line = "Ability: Disabled in Multiplayer"
        self.inv_stats_text.text = (
            f"Health: {int(player.health)} / {int(player.health_max)}\n"
            f"Coins: {self.game_manager.progression_manager.get_coins()}\n"
            f"{self.game_manager.get_profile_label()}\n"
            f"Operative: {player.skin.display_name}\n"
            f"Mode: {(self.game_manager.match_settings.display_name.upper() if getattr(self.game_manager, 'match_settings', None) else ('FREE ROAM' if self.game_manager.game_mode == 'free_roam' else 'MISSION MODE'))}\n"
            f"{ability_line}\n"
            f"Perks: {', '.join(active_perks) if active_perks else 'None'}\n"
            f"Current: {player.current_weapon.display_name}\n"
            f"Ammo: {player.current_weapon.ammo_in_mag} / {player.current_weapon.reserve_ammo}"
        )
        if objectives:
            self.inv_objective_text.text = "Objectives:\n" + "\n".join(objectives[:4])
        else:
            self.inv_objective_text.text = "Objectives:\nNone"

        self._refresh_inventory_cards(player)

    def _refresh_inventory_cards(self, player) -> None:
        preview_tuning = {
            "rifle": {"scale": 0.36, "y": -0.016, "yaw": 206},
            "shotgun": {"scale": 0.38, "y": -0.02, "yaw": 204},
            "pistol": {"scale": 0.41, "y": -0.012, "yaw": 208},
            "smg": {"scale": 0.38, "y": -0.014, "yaw": 210},
            "sniper": {"scale": 0.31, "y": -0.024, "yaw": 202},
            "lmg": {"scale": 0.33, "y": -0.026, "yaw": 200},
        }
        for idx, card in enumerate(self.inventory_cards):
            if idx >= len(player.weapons):
                card.base_color = color.rgba(24, 38, 54, 185)
                card.color = card.base_color
                card.name_text.text = "EMPTY"
                card.rarity_text.text = ""
                card.ammo_text.text = ""
                card.preview_frame.color = color.rgba(30, 46, 66, 170)
                if card.preview_model:
                    destroy(card.preview_model)
                    card.preview_model = None
                card.preview_key = ""
                continue

            weapon = player.weapons[idx]
            attachment_key = ",".join(sorted(getattr(weapon, "attachments", [])))
            card_key = f"{weapon.weapon_id}:{weapon.rarity}:{attachment_key}"
            if card.preview_key != card_key:
                if card.preview_model:
                    destroy(card.preview_model)
                card.preview_model = self.game_manager.asset_loader.load_weapon_model(
                    weapon_id=weapon.weapon_id,
                    parent=card.preview_anchor,
                    rarity=weapon.rarity,
                    attachments=getattr(weapon, "attachments", []),
                )
                tune = preview_tuning.get(weapon.weapon_id, {"scale": 0.36, "y": -0.015, "yaw": 205})
                card.preview_model.scale = tune["scale"]
                card.preview_model.rotation = (8, tune["yaw"], 0)
                card.preview_model.y = tune["y"]
                card.preview_model.z = -0.22
                card.preview_key = card_key

            if card.preview_model:
                card.preview_model.rotation_y += card.spin_speed * self.game_manager.dt

            is_active = idx == player.active_weapon_index
            card.base_color = color.rgba(58, 88, 124, 245) if is_active else color.rgba(28, 44, 64, 235)
            card.color = card.base_color
            card.preview_frame.color = color.rgba(56, 86, 122, 235) if is_active else color.rgba(34, 52, 75, 220)
            attach_count = len(getattr(weapon, "attachments", []))
            card.name_text.text = f"{weapon.base_display_name}{' +' + str(attach_count) if attach_count else ''}"
            card.rarity_text.text = weapon.rarity_label
            card.rarity_text.color = weapon.rarity_color
            card.ammo_text.text = f"{weapon.ammo_in_mag}/{weapon.reserve_ammo}"

    def _clear_inventory_card_previews(self) -> None:
        for card in getattr(self, "inventory_cards", []):
            preview = getattr(card, "preview_model", None)
            if preview:
                try:
                    destroy(preview)
                except Exception:
                    pass
            card.preview_model = None
            card.preview_key = ""

    def _on_inventory_card_click(self, slot_index: int) -> None:
        self.game_manager.select_inventory_weapon(slot_index)

    def _inventory_card_hover(self, card, hovered: bool) -> None:
        if not self.inventory_open:
            return
        if hovered:
            card.animate_color(color.rgba(68, 104, 146, 245), duration=0.08)
        else:
            card.animate_color(card.base_color, duration=0.08)

    def is_mouse_over_inventory(self) -> bool:
        if not self.inventory_open:
            return False
        hovered = mouse.hovered_entity
        depth = 0
        while hovered is not None and depth < 9:
            if hovered == self.inventory_panel:
                return True
            if hovered in self.inventory_cards:
                return True
            hovered = getattr(hovered, "parent", None)
            depth += 1
        return False

    def is_mouse_over_skill_tree(self) -> bool:
        if not self.skill_tree_open:
            return False
        hovered = mouse.hovered_entity
        depth = 0
        while hovered is not None and depth < 10:
            if hovered == self.skill_tree_panel:
                return True
            if hovered in getattr(self, "skill_node_buttons", []):
                return True
            hovered = getattr(hovered, "parent", None)
            depth += 1
        return False

    def _update_minimap(self, player) -> None:
        if not self.hud.enabled or not self.game_manager.world:
            return
        world = self.game_manager.world
        half_extent = world.get_map_half_extent() if hasattr(world, "get_map_half_extent") else 120.0

        px, py = self._world_to_map_xy(player.world_position, half_extent)
        self.mini_player_marker.position = (px, py)
        self.mini_player_marker.rotation_z = -player.rotation_y

        objective = world.objective_target if hasattr(world, "objective_target") else None
        if objective is not None:
            ox, oy = self._world_to_map_xy(objective, half_extent)
            self.mini_objective_marker.position = (ox, oy)
            self.mini_objective_marker.enabled = True
        else:
            self.mini_objective_marker.enabled = False

        visible_enemies = [enemy for enemy in self.game_manager.enemies if enemy and not getattr(enemy, "dead", False)][: len(self.mini_enemy_markers)]
        for i, marker in enumerate(self.mini_enemy_markers):
            if i < len(visible_enemies):
                ex, ey = self._world_to_map_xy(visible_enemies[i].world_position, half_extent)
                marker.position = (ex, ey)
                marker.enabled = True
            else:
                marker.enabled = False

        visible_npcs = [npc for npc in self.game_manager.npcs if npc][: len(self.mini_npc_markers)]
        for i, marker in enumerate(self.mini_npc_markers):
            if i < len(visible_npcs):
                nx, ny = self._world_to_map_xy(visible_npcs[i].world_position, half_extent)
                marker.position = (nx, ny)
                marker.enabled = True
            else:
                marker.enabled = False

    def _world_to_map_xy(self, world_position, half_extent: float):
        if not world_position:
            return 0.0, 0.0
        nx = max(-1.0, min(1.0, world_position.x / half_extent))
        nz = max(-1.0, min(1.0, world_position.z / half_extent))
        return nx * 0.48, nz * 0.48

    def _update_tactical_map(self, player) -> None:
        world = self.game_manager.world
        if not world:
            return
        self.map_anim_time += self.game_manager.dt
        half_extent = world.get_map_half_extent() if hasattr(world, "get_map_half_extent") else (145.0 if self.game_manager.game_mode == "free_roam" else 60.0)

        px, py = self._world_to_map_xy(player.world_position, half_extent)
        self.map_player_marker.position = (px, py)
        self.map_player_marker.rotation_z = -player.rotation_y

        objective = world.objective_target if hasattr(world, "objective_target") else None
        if objective is not None:
            ox, oy = self._world_to_map_xy(objective, half_extent)
            pulse = 1.0 + 0.18 * abs(math.sin(self.map_anim_time * 4.6))
            self.map_objective_marker.position = (ox, oy)
            self.map_objective_marker.scale = (0.045 * pulse, 0.045 * pulse)
            self.map_objective_marker.enabled = True

            delta_x = ox - px
            delta_y = oy - py
            dist = max(0.0001, math.sqrt((delta_x * delta_x) + (delta_y * delta_y)))
            if dist > 0.02:
                self.map_goal_arrow.enabled = True
                self.map_goal_arrow.rotation_z = -math.degrees(math.atan2(delta_x, delta_y))
                self.map_goal_arrow.scale_y = min(0.09, 0.03 + dist * 0.08)
            else:
                self.map_goal_arrow.enabled = False
        else:
            self.map_objective_marker.enabled = False
            self.map_goal_arrow.enabled = False

        locations = world.locations if hasattr(world, "locations") else {}
        location_positions = list(locations.values())[: len(self.map_landmark_markers)]
        for i, marker in enumerate(self.map_landmark_markers):
            if i < len(location_positions):
                lx, ly = self._world_to_map_xy(location_positions[i], half_extent)
                marker.position = (lx, ly)
                marker.enabled = True
            else:
                marker.enabled = False

        quest_positions = self.game_manager.get_active_quest_giver_positions() if hasattr(self.game_manager, "get_active_quest_giver_positions") else []
        for i, marker in enumerate(self.map_quest_markers):
            if i < len(quest_positions):
                qx, qy = self._world_to_map_xy(quest_positions[i], half_extent)
                marker.position = (qx, qy)
                marker.enabled = True
            else:
                marker.enabled = False
