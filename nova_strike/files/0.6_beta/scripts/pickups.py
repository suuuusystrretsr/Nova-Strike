import math
import random

from ursina import Entity, color, destroy

from scripts.weapon import RARITY_COLORS, RARITY_LABELS, WEAPON_LIBRARY, normalize_rarity, normalize_weapon_id


class BasePickup(Entity):
    def __init__(
        self,
        game_manager,
        position,
        kind: str,
        amount: int = 1,
        item_type: str = "",
        rarity: str = "common",
        attachment_ids=None,
        perk_id: str = "",
    ) -> None:
        model = "sphere" if kind in ("coin", "perk") else "cube"
        scale = 0.26 if kind == "coin" else 0.3 if kind == "perk" else 0.34
        if kind == "coin":
            tint = color.rgb(255, 225, 90)
        elif kind == "perk":
            tint = color.rgb(200, 168, 255)
        else:
            tint = color.rgb(120, 220, 255)
        super().__init__(
            parent=game_manager.world.root if game_manager.world and game_manager.world.root else None,
            model=model,
            position=position,
            scale=scale,
            color=tint,
        )
        self.game_manager = game_manager
        self.rng = getattr(game_manager, "rng", random)
        self.kind = kind
        self.amount = amount
        self.item_type = item_type
        self.rarity = normalize_rarity(rarity)
        self.attachment_ids = list(attachment_ids) if isinstance(attachment_ids, (list, tuple)) else []
        self.perk_id = str(perk_id or "")
        self.rarity_label = RARITY_LABELS[self.rarity]
        self.rarity_color = RARITY_COLORS[self.rarity]
        self.weapon_display_name = WEAPON_LIBRARY.get(normalize_weapon_id(self.item_type), {}).get("display_name", self.item_type)
        self.life = 22.0 if kind != "weapon" else 28.0
        self.spin_speed = self.rng.uniform(90, 170)
        self.bob_offset = self.rng.uniform(0, 6.28)
        self.start_y = self.y
        self.local_time = 0.0
        self.collected = False
        self.magnet_range = 3.6 if self.kind == "coin" else 3.0
        self.collect_range = 1.25 if self.kind == "coin" else 1.15
        self.weapon_model = None
        self.weapon_glow = None

        if self.kind == "weapon":
            self.model = None
            self.color = color.clear
            self.scale = 1.0
            self.collider = "sphere"
            self.magnet_range = 0.0
            self.collect_range = 1.15
            self.weapon_model = self.game_manager.asset_loader.load_weapon_model(
                weapon_id=self.item_type,
                parent=self,
                rarity=self.rarity,
                attachments=self.attachment_ids,
            )
            self.weapon_model.scale = 0.7
            self.weapon_model.rotation = (8, self.rng.uniform(0, 360), 0)
            self.weapon_model.y = 0.2
            self.weapon_glow = Entity(
                parent=self,
                model="sphere",
                scale=0.25,
                y=0.02,
                color=color.rgba(
                    int(self.rarity_color.r * 255),
                    int(self.rarity_color.g * 255),
                    int(self.rarity_color.b * 255),
                    65,
                ),
            )
            self.ring = Entity(
                parent=self,
                model="cube",
                scale=(0.72, 0.025, 0.72),
                y=-0.08,
                color=self.rarity_color.tint(-0.05),
            )
        elif self.kind == "perk":
            self.model = "sphere"
            self.scale = 0.3
            self.color = color.rgb(200, 168, 255)
            self.ring = Entity(
                parent=self,
                model="cube",
                scale=(0.62, 0.03, 0.62),
                y=-0.06,
                color=color.rgba(200, 168, 255, 160),
            )
            self.spark = Entity(
                parent=self,
                model="sphere",
                scale=0.18,
                y=0.12,
                color=color.rgba(240, 220, 255, 200),
            )
        elif self.kind != "coin":
            Entity(
                parent=self,
                model="cube",
                scale=(0.5, 0.07, 0.5),
                y=0.18,
                color=color.rgb(220, 245, 255),
            )

    def is_weapon_pickup(self) -> bool:
        return self.kind == "weapon"

    def get_display_name(self) -> str:
        if self.kind == "perk":
            return f"{self.perk_id.title()} Perk"
        if self.kind != "weapon":
            return self.item_type.replace("_", " ").title()
        if self.attachment_ids:
            return f"{self.rarity_label} {self.weapon_display_name} +{len(self.attachment_ids)}A"
        return f"{self.rarity_label} {self.weapon_display_name}"

    def update(self) -> None:
        if self.collected or self.game_manager.state != "playing":
            return
        dt = max(0.0, float(getattr(self.game_manager, "sim_dt", 0.0)))
        if dt <= 0.0:
            dt = max(0.0, float(getattr(self.game_manager, "frame_dt", 1.0 / 60.0)))
        self.local_time += dt
        self.rotation_y += self.spin_speed * dt
        self.life -= dt
        if self.life <= 0:
            self._cleanup()
            return

        if self.kind == "weapon":
            hover = 0.14 * math.sin(self.local_time * 2.1 + self.bob_offset)
            self.y = self.start_y + hover
            if self.weapon_model:
                self.weapon_model.rotation_y += 42.0 * dt
                self.weapon_model.rotation_z = 2.5 * math.sin(self.local_time * 2.7 + self.bob_offset)
            if self.weapon_glow:
                pulse = 1.0 + 0.18 * abs(math.sin(self.local_time * 5.1))
                self.weapon_glow.scale = 0.25 * pulse
            if hasattr(self, "ring") and self.ring:
                self.ring.rotation_y -= 95.0 * dt
            return
        if self.kind == "perk":
            hover = 0.16 * math.sin(self.local_time * 2.8 + self.bob_offset)
            self.y = self.start_y + hover
            self.rotation_y += self.spin_speed * dt * 0.65
            if hasattr(self, "ring") and self.ring:
                self.ring.rotation_y -= 130.0 * dt
            if hasattr(self, "spark") and self.spark:
                pulse = 1.0 + 0.24 * abs(math.sin(self.local_time * 6.0))
                self.spark.scale = 0.18 * pulse

        collectors = []
        if hasattr(self.game_manager, "get_pickup_collectors"):
            collectors = [c for c in self.game_manager.get_pickup_collectors() if c and getattr(c, "alive", False)]
        elif hasattr(self.game_manager, "get_local_player"):
            local = self.game_manager.get_local_player()
            if local and getattr(local, "alive", False):
                collectors = [local]

        if not collectors:
            self.y = self.start_y + 0.12 * math.sin(self.local_time * 2.7 + self.bob_offset)
            return

        player = min(collectors, key=lambda actor: (actor.world_position - self.world_position).length())

        target = player.world_position + (player.up * 0.38)
        to_player = target - self.world_position
        dist = to_player.length()
        horizontal_dist = (to_player.x**2 + to_player.z**2) ** 0.5

        if dist < self.magnet_range and dist > 0.001:
            pull_speed = min(11.5, 2.2 + (self.magnet_range - dist) * 5.1)
            self.world_position += to_player.normalized() * pull_speed * dt
            self.start_y = self.world_y
            self.y = self.world_y + 0.01 * math.sin(self.local_time * 11.0)
        else:
            self.y = self.start_y + 0.12 * math.sin(self.local_time * 2.7 + self.bob_offset)

        if dist <= self.collect_range or (horizontal_dist <= 0.95 and abs(to_player.y) <= 1.4):
            self.collect(collector=player)

    def collect(self, collector=None) -> None:
        if self.collected:
            return
        self.collected = True
        if self.kind == "coin":
            self.game_manager.collect_coin(self.amount, collector=collector)
        elif self.kind == "weapon":
            self.game_manager.collect_weapon(self.item_type, self.rarity, self.attachment_ids, collector=collector)
        elif self.kind == "perk":
            self.game_manager.collect_perk(self.perk_id, collector=collector)
        else:
            self.game_manager.collect_item(self.item_type, self.amount, collector=collector)
        self._cleanup()

    def _cleanup(self) -> None:
        if self in self.game_manager.pickups:
            self.game_manager.pickups.remove(self)
        destroy(self)
