from dataclasses import dataclass
from typing import Dict, List

from ursina import color


@dataclass(frozen=True)
class SkinDefinition:
    skin_id: str
    display_name: str
    primary_color: object
    secondary_color: object
    accent_color: object
    helmet_style: str
    accessory_style: str


class SkinSystem:
    def __init__(self, settings_manager) -> None:
        self.settings_manager = settings_manager
        self.skins: Dict[str, SkinDefinition] = {
            "striker": SkinDefinition(
                skin_id="striker",
                display_name="Striker",
                primary_color=color.rgb(65, 155, 255),
                secondary_color=color.rgb(20, 50, 120),
                accent_color=color.rgb(220, 245, 255),
                helmet_style="rounded",
                accessory_style="backpack",
            ),
            "vanguard": SkinDefinition(
                skin_id="vanguard",
                display_name="Vanguard",
                primary_color=color.rgb(255, 120, 80),
                secondary_color=color.rgb(115, 45, 40),
                accent_color=color.rgb(255, 230, 195),
                helmet_style="visor",
                accessory_style="shoulder",
            ),
            "phantom": SkinDefinition(
                skin_id="phantom",
                display_name="Phantom",
                primary_color=color.rgb(90, 230, 170),
                secondary_color=color.rgb(30, 85, 55),
                accent_color=color.rgb(200, 255, 230),
                helmet_style="angular",
                accessory_style="antenna",
            ),
        }
        chosen = self.settings_manager.get_selected_skin()
        self.selected_skin_id = chosen if chosen in self.skins else "striker"

    def get_all_skins(self) -> List[SkinDefinition]:
        return list(self.skins.values())

    def get_skin(self, skin_id: str) -> SkinDefinition:
        return self.skins.get(skin_id, self.skins["striker"])

    def get_selected_skin(self) -> SkinDefinition:
        return self.get_skin(self.selected_skin_id)

    def select_skin(self, skin_id: str) -> None:
        if skin_id not in self.skins:
            return
        self.selected_skin_id = skin_id
        self.settings_manager.set_selected_skin(skin_id)

