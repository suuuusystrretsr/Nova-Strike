from pathlib import Path
from typing import Optional

from ursina import Audio, Entity, color


class AssetLoader:
    def __init__(self) -> None:
        self.asset_root = Path(__file__).resolve().parent.parent / "assets"
        self.models_dir = self.asset_root / "models"
        self.textures_dir = self.asset_root / "textures"
        self.audio_dir = self.asset_root / "audio"
        self.ui_dir = self.asset_root / "ui"
        self.master_volume = 1.0
        self.loop_channels = {}
        self._ensure_directories()

    def set_master_volume(self, value: float) -> None:
        self.master_volume = max(0.0, min(1.0, float(value)))
        for channel in list(self.loop_channels.values()):
            if channel:
                channel.volume = self.master_volume * 0.18

    def _ensure_directories(self) -> None:
        for path in (
            self.asset_root,
            self.models_dir,
            self.textures_dir,
            self.audio_dir,
            self.ui_dir,
            self.models_dir / "players",
            self.models_dir / "enemies",
            self.models_dir / "weapons",
            self.models_dir / "npcs",
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _find_audio_file(self, sound_name: str) -> Optional[Path]:
        for extension in (".ogg", ".wav", ".mp3"):
            candidate = self.audio_dir / f"{sound_name}{extension}"
            if candidate.exists():
                return candidate
        return None

    # ------------------------------
    # REPLACEABLE ASSET ZONE: Player
    # ------------------------------
    def load_player_model(self, skin, parent: Optional[Entity] = None) -> Entity:
        custom_model = self.models_dir / "players" / f"{skin.skin_id}.glb"
        if custom_model.exists():
            return Entity(parent=parent, model=str(custom_model), scale=1.0, color=color.white)
        return self._build_procedural_humanoid(
            parent=parent,
            base_color=skin.primary_color,
            armor_color=skin.secondary_color,
            accent_color=skin.accent_color,
            helmet_style=skin.helmet_style,
            accessory_style=skin.accessory_style,
            silhouette="player",
        )

    # -----------------------------
    # REPLACEABLE ASSET ZONE: Enemy
    # -----------------------------
    def load_enemy_model(self, parent: Optional[Entity] = None, variant: str = "raider") -> Entity:
        custom_model = self.models_dir / "enemies" / f"{variant}.glb"
        if custom_model.exists():
            return Entity(parent=parent, model=str(custom_model), scale=1.0)

        palettes = {
            "raider": (color.rgb(210, 86, 86), color.rgb(128, 44, 44), color.rgb(245, 175, 165)),
            "stalker": (color.rgb(180, 116, 220), color.rgb(98, 62, 145), color.rgb(220, 200, 255)),
            "brute": (color.rgb(205, 132, 72), color.rgb(124, 80, 44), color.rgb(255, 224, 178)),
        }
        base, armor, accent = palettes.get(variant, palettes["raider"])
        body = self._build_procedural_humanoid(
            parent=parent,
            base_color=base,
            armor_color=armor,
            accent_color=accent,
            helmet_style="rounded",
            accessory_style="shoulder",
            silhouette="enemy",
        )
        if variant == "brute":
            body.scale = 1.12
        if variant == "stalker":
            body.scale = 0.92
        return body

    # ---------------------------
    # REPLACEABLE ASSET ZONE: NPC
    # ---------------------------
    def load_npc_model(self, role: str, parent: Optional[Entity] = None) -> Entity:
        custom_model = self.models_dir / "npcs" / f"{role}.glb"
        if custom_model.exists():
            return Entity(parent=parent, model=str(custom_model), scale=1.0)

        role_palette = {
            "commander": (color.rgb(72, 146, 255), color.rgb(40, 72, 134), color.rgb(232, 245, 255)),
            "trader": (color.rgb(255, 178, 92), color.rgb(125, 80, 42), color.rgb(255, 240, 185)),
            "engineer": (color.rgb(90, 224, 168), color.rgb(34, 96, 68), color.rgb(210, 255, 230)),
            "scout": (color.rgb(212, 152, 255), color.rgb(96, 70, 142), color.rgb(242, 220, 255)),
        }
        base, armor, accent = role_palette.get(role, role_palette["commander"])
        accessory = "antenna" if role in ("engineer", "scout") else "backpack"
        helmet = "visor" if role == "commander" else "rounded"
        return self._build_procedural_humanoid(
            parent=parent,
            base_color=base,
            armor_color=armor,
            accent_color=accent,
            helmet_style=helmet,
            accessory_style=accessory,
            silhouette="npc",
        )

    def _build_procedural_humanoid(
        self,
        parent: Optional[Entity],
        base_color,
        armor_color,
        accent_color,
        helmet_style: str,
        accessory_style: str,
        silhouette: str,
    ) -> Entity:
        root = Entity(parent=parent)
        s = 1.0
        if silhouette == "enemy":
            s = 1.04
        elif silhouette == "npc":
            s = 0.99

        torso = Entity(
            parent=root,
            model="cube",
            scale=(0.62 * s, 0.82 * s, 0.4 * s),
            y=0.34 * s,
            color=base_color,
            texture="white_cube",
        )
        chest = Entity(
            parent=root,
            model="cube",
            scale=(0.62 * s, 0.31 * s, 0.39 * s),
            y=0.8 * s,
            color=armor_color,
            texture="white_cube",
        )
        Entity(
            parent=root,
            model="cube",
            scale=(0.56 * s, 0.2 * s, 0.34 * s),
            y=-0.03 * s,
            color=base_color.tint(-0.1),
            texture="white_cube",
        )
        Entity(
            parent=root,
            model="cube",
            scale=(0.56 * s, 0.06 * s, 0.36 * s),
            y=0.52 * s,
            color=accent_color.tint(-0.2),
            texture="white_cube",
        )
        Entity(
            parent=root,
            model="cube",
            scale=(0.5 * s, 0.07 * s, 0.08 * s),
            y=0.78 * s,
            z=0.24 * s,
            color=accent_color,
            texture="white_cube",
        )
        Entity(
            parent=root,
            model="cube",
            scale=(0.18 * s, 0.16 * s, 0.07 * s),
            x=-0.2 * s,
            y=0.1 * s,
            z=0.24 * s,
            color=armor_color.tint(-0.22),
            texture="white_cube",
        )
        Entity(
            parent=root,
            model="cube",
            scale=(0.18 * s, 0.16 * s, 0.07 * s),
            x=0.2 * s,
            y=0.1 * s,
            z=0.24 * s,
            color=armor_color.tint(-0.22),
            texture="white_cube",
        )
        Entity(
            parent=root,
            model="cube",
            scale=(0.2 * s, 0.16 * s, 0.08 * s),
            y=0.42 * s,
            z=-0.24 * s,
            color=armor_color.tint(-0.14),
            texture="white_cube",
        )

        left_shoulder = Entity(
            parent=root,
            model="sphere",
            scale=0.19 * s,
            x=-0.43 * s,
            y=0.82 * s,
            color=armor_color.tint(0.04),
            texture="white_cube",
        )
        right_shoulder = Entity(
            parent=root,
            model="sphere",
            scale=0.19 * s,
            x=0.43 * s,
            y=0.82 * s,
            color=armor_color.tint(0.04),
            texture="white_cube",
        )

        left_arm = Entity(
            parent=root,
            model="cube",
            scale=(0.19 * s, 0.4 * s, 0.19 * s),
            x=-0.45 * s,
            y=0.5 * s,
            color=armor_color,
            texture="white_cube",
        )
        right_arm = Entity(
            parent=root,
            model="cube",
            scale=(0.19 * s, 0.4 * s, 0.19 * s),
            x=0.45 * s,
            y=0.5 * s,
            color=armor_color,
            texture="white_cube",
        )
        Entity(
            parent=left_arm,
            model="cube",
            scale=(0.94, 0.74, 0.94),
            y=-0.36,
            color=base_color.tint(-0.14),
            texture="white_cube",
        )
        Entity(
            parent=right_arm,
            model="cube",
            scale=(0.94, 0.74, 0.94),
            y=-0.36,
            color=base_color.tint(-0.14),
            texture="white_cube",
        )
        Entity(
            parent=left_arm,
            model="cube",
            scale=(0.86, 0.24, 1.02),
            y=0.33,
            color=accent_color.tint(-0.16),
            texture="white_cube",
        )
        Entity(
            parent=right_arm,
            model="cube",
            scale=(0.86, 0.24, 1.02),
            y=0.33,
            color=accent_color.tint(-0.16),
            texture="white_cube",
        )

        left_leg = Entity(
            parent=root,
            model="cube",
            scale=(0.23 * s, 0.56 * s, 0.26 * s),
            x=-0.19 * s,
            y=-0.49 * s,
            color=base_color.tint(-0.2),
            texture="white_cube",
        )
        right_leg = Entity(
            parent=root,
            model="cube",
            scale=(0.23 * s, 0.56 * s, 0.26 * s),
            x=0.19 * s,
            y=-0.49 * s,
            color=base_color.tint(-0.2),
            texture="white_cube",
        )
        Entity(
            parent=left_leg,
            model="cube",
            scale=(0.88, 0.74, 0.9),
            y=-0.42,
            color=armor_color.tint(-0.2),
            texture="white_cube",
        )
        Entity(
            parent=right_leg,
            model="cube",
            scale=(0.88, 0.74, 0.9),
            y=-0.42,
            color=armor_color.tint(-0.2),
            texture="white_cube",
        )
        Entity(
            parent=left_leg,
            model="cube",
            scale=(1.2, 0.23, 1.16),
            y=-0.94,
            z=0.08,
            color=accent_color.tint(-0.14),
            texture="white_cube",
        )
        Entity(
            parent=right_leg,
            model="cube",
            scale=(1.2, 0.23, 1.16),
            y=-0.94,
            z=0.08,
            color=accent_color.tint(-0.14),
            texture="white_cube",
        )

        head = Entity(
            parent=root,
            model="sphere",
            scale=(0.39 * s, 0.36 * s, 0.39 * s),
            y=1.18 * s,
            color=base_color.tint(0.11),
            texture="white_cube",
        )
        helmet_shell = Entity(
            parent=root,
            model="cube",
            scale=(0.44 * s, 0.16 * s, 0.33 * s),
            y=1.0 * s,
            color=base_color.tint(0.08),
            texture="white_cube",
        )
        visor = (0.34, 0.12, 0.04) if helmet_style == "visor" else (0.26, 0.08, 0.04)
        Entity(
            parent=root,
            model="cube",
            scale=(visor[0] * s, visor[1] * s, visor[2] * s),
            y=1.16 * s,
            z=0.21 * s,
            color=accent_color,
            texture="white_cube",
        )
        Entity(
            parent=root,
            model="cube",
            scale=(0.24 * s, 0.05 * s, 0.08 * s),
            y=1.0 * s,
            z=0.2 * s,
            color=accent_color.tint(-0.12),
            texture="white_cube",
        )

        if accessory_style == "backpack":
            Entity(
                parent=root,
                model="cube",
                scale=(0.38 * s, 0.52 * s, 0.17 * s),
                y=0.28 * s,
                z=-0.29 * s,
                color=armor_color.tint(-0.08),
                texture="white_cube",
            )
            Entity(
                parent=root,
                model="cube",
                scale=(0.32 * s, 0.1 * s, 0.05 * s),
                y=0.5 * s,
                z=-0.39 * s,
                color=accent_color.tint(-0.06),
                texture="white_cube",
            )
        elif accessory_style == "shoulder":
            Entity(
                parent=root,
                model="cube",
                scale=(0.24 * s, 0.13 * s, 0.3 * s),
                x=-0.45 * s,
                y=0.87 * s,
                color=accent_color,
                texture="white_cube",
            )
            Entity(
                parent=root,
                model="cube",
                scale=(0.24 * s, 0.13 * s, 0.3 * s),
                x=0.45 * s,
                y=0.87 * s,
                color=accent_color,
                texture="white_cube",
            )
        elif accessory_style == "antenna":
            Entity(
                parent=root,
                model="cube",
                scale=(0.05 * s, 0.44 * s, 0.05 * s),
                x=0.14 * s,
                y=1.36 * s,
                color=accent_color,
                texture="white_cube",
            )
            Entity(
                parent=root,
                model="sphere",
                scale=0.1 * s,
                x=0.14 * s,
                y=1.6 * s,
                color=accent_color,
                texture="white_cube",
            )

        root.part_nodes = {
            "torso": torso,
            "chest": chest,
            "head": head,
            "helmet": helmet_shell,
            "left_shoulder": left_shoulder,
            "right_shoulder": right_shoulder,
            "left_arm": left_arm,
            "right_arm": right_arm,
            "left_leg": left_leg,
            "right_leg": right_leg,
        }
        # Used by gameplay entities to align visuals to collider feet.
        root.foot_level = -1.24 * s
        root.body_height = 2.52 * s
        return root

    # ------------------------------
    # REPLACEABLE ASSET ZONE: Weapon
    # ------------------------------
    def load_weapon_model(
        self,
        weapon_id: str,
        parent: Optional[Entity] = None,
        rarity: str = "common",
        attachments: Optional[list] = None,
    ) -> Entity:
        alias = {"pulse_rifle": "rifle", "plasma_launcher": "shotgun"}.get(weapon_id, weapon_id)
        custom_model = self.models_dir / "weapons" / f"{alias}.glb"
        if custom_model.exists():
            return Entity(parent=parent, model=str(custom_model), scale=0.2)

        rarity_key = str(rarity or "").lower()
        rarity_palette = {
            "common": color.rgb(188, 196, 205),
            "uncommon": color.rgb(112, 220, 142),
            "rare": color.rgb(96, 168, 255),
            "epic": color.rgb(188, 126, 255),
            "legendary": color.rgb(255, 196, 92),
        }
        rarity_accent = rarity_palette.get(rarity_key, rarity_palette["common"])

        root = Entity(parent=parent)
        if alias == "rifle":
            self._build_rifle(root, rarity_accent)
        elif alias == "shotgun":
            self._build_shotgun(root, rarity_accent)
        elif alias == "smg":
            self._build_smg(root, rarity_accent)
        elif alias == "sniper":
            self._build_sniper(root, rarity_accent)
        elif alias == "lmg":
            self._build_lmg(root, rarity_accent)
        else:
            self._build_pistol(root, rarity_accent)
        self._add_attachment_visuals(root, alias, rarity_accent, attachments or [])
        return root

    def _add_attachment_visuals(self, root: Entity, weapon_id: str, rarity_accent, attachments: list) -> None:
        if not attachments:
            return
        part_nodes = getattr(root, "part_nodes", {})
        core = part_nodes.get("core")
        if not core:
            return

        if "scope" in attachments and "scope" not in part_nodes:
            Entity(parent=root, model="cube", scale=(0.08, 0.05, 0.2), y=0.13, z=0.02, color=rarity_accent.tint(0.06))
            Entity(parent=root, model="sphere", scale=0.05, y=0.13, z=0.12, color=rarity_accent.tint(0.12))
        if "silencer" in attachments:
            muzzle = part_nodes.get("muzzle")
            attach_parent = muzzle if muzzle else root
            Entity(parent=attach_parent, model="cube", scale=(0.8, 0.78, 1.45), z=0.16, color=color.rgb(52, 60, 74))
        if "extended_mag" in attachments:
            magazine = part_nodes.get("magazine")
            if magazine:
                Entity(parent=magazine, model="cube", scale=(0.78, 0.82, 0.82), y=-0.55, color=color.rgb(58, 70, 86))
        if "stabilizer" in attachments:
            Entity(parent=root, model="cube", scale=(0.16, 0.03, 0.26), y=-0.04, z=0.26, color=rarity_accent.tint(-0.12))
        if "drum" in attachments and weapon_id in ("lmg", "smg", "rifle"):
            magazine = part_nodes.get("magazine")
            if magazine:
                Entity(parent=magazine, model="sphere", scale=0.92, y=-0.12, z=-0.06, color=rarity_accent.tint(-0.2))

    def _build_rifle(self, root: Entity, rarity_accent) -> None:
        base = color.rgb(72, 84, 104)
        accent = rarity_accent
        core = Entity(parent=root, model="cube", scale=(0.18, 0.1, 0.56), color=base)
        muzzle = Entity(parent=root, model="cube", scale=(0.085, 0.07, 0.2), z=0.43, color=base.tint(-0.25))
        slide = Entity(parent=root, model="cube", scale=(0.12, 0.05, 0.25), y=0.048, z=0.14, color=base.tint(0.08))
        scope = Entity(parent=root, model="cube", scale=(0.07, 0.05, 0.16), y=0.118, z=-0.03, color=base.tint(0.12))
        Entity(parent=scope, model="cube", scale=(0.035, 0.02, 0.015), z=0.095, color=accent)
        magazine = Entity(parent=root, model="cube", scale=(0.09, 0.15, 0.17), y=-0.13, z=-0.02, color=base.tint(-0.3))
        Entity(parent=root, model="cube", scale=(0.14, 0.03, 0.52), y=0.078, color=base.tint(-0.2))
        Entity(parent=root, model="cube", scale=(0.025, 0.02, 0.5), x=0.07, y=0.02, color=accent.tint(0.12))
        Entity(parent=root, model="cube", scale=(0.025, 0.02, 0.5), x=-0.07, y=0.02, color=accent.tint(0.12))
        Entity(parent=root, model="cube", scale=(0.06, 0.03, 0.07), y=-0.04, z=0.24, color=accent.tint(0.08))
        root.part_nodes = {"core": core, "muzzle": muzzle, "slide": slide, "scope": scope, "magazine": magazine}

    def _build_shotgun(self, root: Entity, rarity_accent) -> None:
        base = color.rgb(88, 120, 95)
        accent = rarity_accent
        core = Entity(parent=root, model="cube", scale=(0.2, 0.11, 0.52), color=base)
        muzzle = Entity(parent=root, model="cube", scale=(0.09, 0.08, 0.26), z=0.42, color=base.tint(-0.24))
        slide = Entity(parent=root, model="cube", scale=(0.12, 0.06, 0.22), y=0.05, z=0.14, color=base.tint(0.1))
        chamber = Entity(parent=root, model="sphere", scale=0.14, z=0.21, color=accent)
        magazine = Entity(parent=root, model="cube", scale=(0.1, 0.18, 0.2), y=-0.14, z=-0.03, color=base.tint(-0.3))
        Entity(parent=root, model="cube", scale=(0.14, 0.04, 0.26), y=-0.05, z=0.22, color=base.tint(-0.18))
        Entity(parent=root, model="cube", scale=(0.035, 0.07, 0.14), x=0.1, z=0.25, color=accent)
        Entity(parent=root, model="cube", scale=(0.035, 0.07, 0.14), x=-0.1, z=0.25, color=accent)
        Entity(parent=root, model="cube", scale=(0.06, 0.06, 0.12), y=0.07, z=-0.2, color=accent.tint(-0.08))
        root.part_nodes = {"core": core, "muzzle": muzzle, "slide": slide, "coil": chamber, "magazine": magazine}

    def _build_pistol(self, root: Entity, rarity_accent) -> None:
        base = color.rgb(86, 88, 96)
        accent = rarity_accent
        core = Entity(parent=root, model="cube", scale=(0.12, 0.09, 0.34), color=base)
        muzzle = Entity(parent=root, model="cube", scale=(0.06, 0.05, 0.13), z=0.23, color=base.tint(-0.25))
        slide = Entity(parent=root, model="cube", scale=(0.1, 0.04, 0.2), y=0.05, z=0.06, color=base.tint(0.12))
        magazine = Entity(parent=root, model="cube", scale=(0.08, 0.16, 0.12), y=-0.13, z=-0.03, color=base.tint(-0.3))
        Entity(parent=root, model="cube", scale=(0.04, 0.02, 0.18), y=0.08, color=accent)
        Entity(parent=root, model="cube", scale=(0.03, 0.03, 0.08), x=0.04, y=0.01, z=-0.06, color=accent.tint(0.06))
        root.part_nodes = {"core": core, "muzzle": muzzle, "slide": slide, "magazine": magazine}

    def _build_smg(self, root: Entity, rarity_accent) -> None:
        base = color.rgb(66, 80, 94)
        accent = rarity_accent
        core = Entity(parent=root, model="cube", scale=(0.16, 0.1, 0.5), color=base)
        muzzle = Entity(parent=root, model="cube", scale=(0.07, 0.06, 0.18), z=0.38, color=base.tint(-0.22))
        slide = Entity(parent=root, model="cube", scale=(0.1, 0.045, 0.22), y=0.05, z=0.1, color=base.tint(0.11))
        stock = Entity(parent=root, model="cube", scale=(0.14, 0.07, 0.18), z=-0.32, color=base.tint(-0.28))
        magazine = Entity(parent=root, model="cube", scale=(0.08, 0.2, 0.12), y=-0.16, z=-0.03, color=base.tint(-0.25))
        Entity(parent=root, model="cube", scale=(0.022, 0.02, 0.46), x=0.06, y=0.017, color=accent.tint(0.08))
        Entity(parent=root, model="cube", scale=(0.022, 0.02, 0.46), x=-0.06, y=0.017, color=accent.tint(0.08))
        Entity(parent=stock, model="cube", scale=(0.5, 0.55, 0.55), z=-0.56, color=accent.tint(-0.25))
        root.part_nodes = {"core": core, "muzzle": muzzle, "slide": slide, "magazine": magazine}

    def _build_sniper(self, root: Entity, rarity_accent) -> None:
        base = color.rgb(56, 70, 88)
        accent = rarity_accent
        core = Entity(parent=root, model="cube", scale=(0.15, 0.085, 0.74), color=base)
        muzzle = Entity(parent=root, model="cube", scale=(0.06, 0.06, 0.2), z=0.52, color=base.tint(-0.25))
        slide = Entity(parent=root, model="cube", scale=(0.1, 0.05, 0.26), y=0.046, z=0.18, color=base.tint(0.1))
        scope = Entity(parent=root, model="cube", scale=(0.08, 0.05, 0.34), y=0.12, z=0.05, color=base.tint(0.12))
        Entity(parent=scope, model="sphere", scale=0.05, z=0.21, color=accent)
        Entity(parent=scope, model="sphere", scale=0.05, z=-0.21, color=accent)
        magazine = Entity(parent=root, model="cube", scale=(0.08, 0.13, 0.12), y=-0.12, z=0.03, color=base.tint(-0.3))
        Entity(parent=root, model="cube", scale=(0.14, 0.05, 0.34), y=-0.04, z=0.16, color=accent.tint(-0.2))
        Entity(parent=root, model="cube", scale=(0.16, 0.07, 0.26), y=-0.11, z=-0.27, color=base.tint(-0.3))
        root.part_nodes = {"core": core, "muzzle": muzzle, "slide": slide, "scope": scope, "magazine": magazine}

    def _build_lmg(self, root: Entity, rarity_accent) -> None:
        base = color.rgb(84, 92, 106)
        accent = rarity_accent
        core = Entity(parent=root, model="cube", scale=(0.2, 0.115, 0.62), color=base)
        muzzle = Entity(parent=root, model="cube", scale=(0.09, 0.08, 0.22), z=0.47, color=base.tint(-0.25))
        slide = Entity(parent=root, model="cube", scale=(0.13, 0.06, 0.24), y=0.05, z=0.14, color=base.tint(0.08))
        magazine = Entity(parent=root, model="cube", scale=(0.12, 0.22, 0.22), y=-0.16, z=-0.02, color=base.tint(-0.3))
        drum = Entity(parent=magazine, model="sphere", scale=0.9, y=-0.05, z=-0.04, color=accent.tint(-0.15))
        scope = Entity(parent=root, model="cube", scale=(0.075, 0.045, 0.19), y=0.122, z=-0.06, color=base.tint(0.1))
        Entity(parent=scope, model="cube", scale=(0.45, 0.5, 0.12), z=0.55, color=accent)
        Entity(parent=root, model="cube", scale=(0.19, 0.04, 0.56), y=0.083, color=base.tint(-0.2))
        Entity(parent=root, model="cube", scale=(0.1, 0.17, 0.2), y=-0.14, z=-0.24, color=base.tint(-0.3))
        root.part_nodes = {"core": core, "muzzle": muzzle, "slide": slide, "scope": scope, "magazine": magazine, "coil": drum}

    def play_sound(self, sound_name: str, volume: float = 0.5, pitch: float = 1.0):
        audio_path = self._find_audio_file(sound_name)
        if not audio_path:
            return None
        return Audio(str(audio_path), autoplay=True, volume=volume * self.master_volume, pitch=pitch)

    def start_loop(self, channel_id: str, sound_name: str, volume: float = 0.18):
        self.stop_loop(channel_id)
        audio_path = self._find_audio_file(sound_name)
        if not audio_path:
            return None
        audio = Audio(str(audio_path), autoplay=True, loop=True, volume=volume * self.master_volume)
        self.loop_channels[channel_id] = audio
        return audio

    def stop_loop(self, channel_id: str) -> None:
        channel = self.loop_channels.get(channel_id)
        if not channel:
            return
        try:
            channel.stop()
        except Exception:
            pass
        self.loop_channels[channel_id] = None
