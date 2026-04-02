import math
import random

from ursina import Entity, color


class NPC(Entity):
    def __init__(self, game_manager, npc_id: str, display_name: str, role: str, position) -> None:
        super().__init__(
            parent=game_manager.world.root if game_manager.world and game_manager.world.root else None,
            position=position,
            collider="box",
            scale=(0.78, 1.84, 0.78),
        )
        self.game_manager = game_manager
        self.rng = getattr(game_manager, "rng", random)
        self.npc_id = npc_id
        self.display_name = display_name
        self.role = role
        self.interaction_radius = 3.0
        self.collider_half_height = self.scale_y * 0.5
        self.anim_offset = self.rng.uniform(0, 6.28)
        self.local_time = 0.0

        self.model_root = self.game_manager.asset_loader.load_npc_model(role=role, parent=self)
        self.model_root.scale = 0.9
        foot_level = float(getattr(self.model_root, "foot_level", -1.22))
        self.model_base_y = (-self.collider_half_height + 0.03) - (foot_level * float(self.model_root.scale_y))
        self.model_root.y = self.model_base_y
        self.model_base_scale = self.model_root.scale

        self.quest_arrow_root = Entity(parent=self, y=2.55, enabled=False)
        self.quest_arrow_pivot = Entity(parent=self.quest_arrow_root)
        self.quest_beam = Entity(
            parent=self.quest_arrow_pivot,
            model="cube",
            scale=(0.12, 1.7, 0.12),
            y=0.86,
            color=color.rgba(255, 238, 110, 180),
        )
        self.quest_glow = Entity(
            parent=self.quest_arrow_pivot,
            model="sphere",
            scale=0.48,
            y=0.18,
            color=color.rgba(255, 246, 170, 200),
        )
        self.quest_ring = Entity(
            parent=self.quest_arrow_pivot,
            model="cube",
            scale=(0.64, 0.05, 0.64),
            y=0.1,
            color=color.rgba(255, 228, 96, 160),
        )
        self.quest_arrow_shaft = Entity(
            parent=self.quest_arrow_pivot,
            model="cube",
            scale=(0.2, 0.62, 0.2),
            y=0.22,
            color=color.rgb(255, 230, 88),
        )
        self.quest_arrow_head = Entity(
            parent=self.quest_arrow_pivot,
            model="cube",
            scale=(0.42, 0.42, 0.42),
            y=-0.22,
            rotation=(45, 0, 45),
            color=color.rgb(255, 252, 214),
        )
        self.quest_label = Entity(
            parent=self.quest_arrow_root,
            y=1.55,
            billboard=True,
        )
        self.quest_label_bg = Entity(
            parent=self.quest_label,
            model="quad",
            scale=(0.78, 0.22),
            color=color.rgba(20, 30, 40, 165),
        )
        self.quest_label_text = Entity(
            parent=self.quest_label,
            model="quad",
            color=color.rgba(255, 242, 150, 120),
            scale=(0.72, 0.16),
        )
        Entity(parent=self.quest_label, model="quad", scale=(0.06, 0.12), x=-0.16, color=color.rgba(20, 30, 40, 160))
        Entity(parent=self.quest_label, model="quad", scale=(0.06, 0.12), x=0, color=color.rgba(20, 30, 40, 160))
        Entity(parent=self.quest_label, model="quad", scale=(0.06, 0.12), x=0.16, color=color.rgba(20, 30, 40, 160))
        self.quest_arrow_phase = self.rng.uniform(0.0, 6.28)

    def update(self) -> None:
        if not self.enabled:
            return
        dt = max(0.0, float(getattr(self.game_manager, "frame_dt", 1.0 / 60.0)))
        self.local_time += dt
        t = self.local_time + self.anim_offset
        self.model_root.y = self.model_base_y + 0.02 * math.sin(t * 1.4)
        self.model_root.rotation_y = 5.0 * math.sin(t * 0.6)
        if hasattr(self.model_root, "part_nodes"):
            head = self.model_root.part_nodes.get("head")
            if head:
                head.rotation_y = 8.0 * math.sin(t * 0.8)

        if self.quest_arrow_root.enabled:
            bob = 0.18 * math.sin(t * 3.2 + self.quest_arrow_phase)
            self.quest_arrow_root.y = 2.7 + bob
            self.quest_arrow_pivot.rotation_y += 122.0 * dt
            pulse = 1.0 + 0.22 * math.sin(t * 5.4 + self.quest_arrow_phase)
            self.quest_glow.scale = 0.48 * pulse
            self.quest_beam.scale_y = 1.62 + 0.28 * abs(math.sin(t * 2.4))
            self.quest_ring.rotation_y -= 150.0 * dt
            self.quest_ring.scale_x = 0.58 + 0.14 * abs(math.sin(t * 4.2))
            self.quest_ring.scale_z = self.quest_ring.scale_x
            self.quest_label_bg.scale_x = 0.78 + 0.09 * abs(math.sin(t * 4.5))

    def is_player_in_range(self, player_position) -> bool:
        return (player_position - self.world_position).length() <= self.interaction_radius

    def get_prompt_text(self) -> str:
        return f"[E] Talk - {self.display_name}"

    def set_highlight(self, enabled: bool) -> None:
        self.model_root.scale = self.model_base_scale * (1.04 if enabled else 1.0)

    def set_quest_arrow(self, enabled: bool) -> None:
        self.quest_arrow_root.enabled = enabled
