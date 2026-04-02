from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from ursina import Vec3, distance


@dataclass(frozen=True)
class StoryMission:
    mission_id: str
    title: str
    description: str
    giver_npc: str
    objective_type: str
    target: int
    reward: int
    location_name: Optional[str] = None
    item_type: Optional[str] = None


@dataclass(frozen=True)
class SideQuestTemplate:
    quest_id: str
    title: str
    description: str
    giver_npc: str
    objective_type: str
    target: int
    reward: int
    location_name: Optional[str] = None
    item_type: Optional[str] = None


@dataclass(frozen=True)
class DialogueChoice:
    label: str
    action_id: str


@dataclass(frozen=True)
class DialogueData:
    speaker: str
    lines: List[str]
    choices: List[DialogueChoice]


class QuestSystem:
    def __init__(self, progression_manager, mode: str, notify: Optional[Callable[[str], None]] = None) -> None:
        self.progression_manager = progression_manager
        self.mode = mode
        self.notify = notify or (lambda _msg: None)

        self.story_missions: List[StoryMission] = self._build_story_chain()
        self.side_templates: List[SideQuestTemplate] = self._build_side_templates()
        self.story_index = min(self.progression_manager.get_story_index(), len(self.story_missions))
        self.story_active = False
        self.story_progress = 0.0
        self.story_objective_complete = False

        self.active_side_quests: Dict[str, dict] = {}
        self.side_counter = 0

    def _build_story_chain(self) -> List[StoryMission]:
        return [
            StoryMission(
                mission_id="story_01",
                title="First Contact",
                description="Eliminate hostile scouts near the city edge.",
                giver_npc="handler_aria",
                objective_type="eliminate",
                target=6,
                reward=80,
            ),
            StoryMission(
                mission_id="story_02",
                title="Relay Reboot",
                description="Reach the relay tower and secure the uplink.",
                giver_npc="handler_aria",
                objective_type="reach",
                target=1,
                reward=95,
                location_name="relay_tower",
            ),
            StoryMission(
                mission_id="story_03",
                title="Data Recovery",
                description="Collect data cores scattered around the old district.",
                giver_npc="engineer_voss",
                objective_type="collect",
                target=3,
                reward=110,
                item_type="data_core",
            ),
            StoryMission(
                mission_id="story_04",
                title="Last Stand",
                description="Hold the perimeter by eliminating a full assault group.",
                giver_npc="handler_aria",
                objective_type="eliminate",
                target=12,
                reward=180,
            ),
        ]

    def _build_side_templates(self) -> List[SideQuestTemplate]:
        return [
            SideQuestTemplate(
                quest_id="sq_hunt",
                title="Street Sweep",
                description="Eliminate nearby hostiles.",
                giver_npc="quartermaster_rynn",
                objective_type="eliminate",
                target=5,
                reward=65,
            ),
            SideQuestTemplate(
                quest_id="sq_delivery",
                title="Scout Route",
                description="Reach the canyon gate and report the path status.",
                giver_npc="scout_nia",
                objective_type="reach",
                target=1,
                reward=60,
                location_name="canyon_gate",
            ),
            SideQuestTemplate(
                quest_id="sq_salvage",
                title="Parts Request",
                description="Collect salvage canisters from the scrapyard.",
                giver_npc="engineer_voss",
                objective_type="collect",
                target=2,
                reward=75,
                item_type="salvage",
            ),
        ]

    def has_story_available(self) -> bool:
        return self.mode == "free_roam" and self.story_index < len(self.story_missions)

    def get_current_story(self) -> Optional[StoryMission]:
        if not self.has_story_available():
            return None
        return self.story_missions[self.story_index]

    def build_dialogue_for_npc(self, npc_id: str, npc_name: str) -> DialogueData:
        lines: List[str] = []
        choices: List[DialogueChoice] = []

        if self.mode != "free_roam":
            return DialogueData(
                speaker=npc_name,
                lines=["Mission zone is active. We can brief again in Free Roam."],
                choices=[DialogueChoice(label="Close", action_id="close")],
            )

        story = self.get_current_story()
        if story and story.giver_npc == npc_id:
            if not self.story_active and not self.story_objective_complete:
                lines.append(f"Primary Mission: {story.title}")
                lines.append(story.description)
                choices.append(DialogueChoice(label="Accept Mission", action_id="accept_story"))
            elif self.story_active and not self.story_objective_complete:
                lines.append(f"Current objective: {story.description}")
                lines.append(self._build_progress_line(story, self.story_progress))
                choices.append(DialogueChoice(label="Close", action_id="close"))
            elif self.story_objective_complete:
                lines.append("Objective complete. Good work, operative.")
                lines.append(f"Ready to turn in '{story.title}'?")
                choices.append(DialogueChoice(label="Turn In", action_id="turn_in_story"))

        side_for_npc = self._find_active_side_for_npc(npc_id)
        if side_for_npc:
            lines.append(f"Side Quest: {side_for_npc['template'].title}")
            lines.append(self._build_progress_line(side_for_npc["template"], side_for_npc["progress"]))
            if side_for_npc["completed"]:
                choices.append(DialogueChoice(label="Claim Reward", action_id=f"turn_in_side:{side_for_npc['id']}"))
        else:
            template = self._find_side_template_for_npc(npc_id)
            if template:
                lines.append(f"Side Objective: {template.description}")
                choices.append(DialogueChoice(label="Accept Side Quest", action_id=f"accept_side:{template.quest_id}"))

        if not lines:
            lines = ["No new assignments right now. Keep your guard up."]
        if not choices:
            choices.append(DialogueChoice(label="Close", action_id="close"))

        # Keep UI layout compact and readable.
        return DialogueData(speaker=npc_name, lines=lines[:4], choices=choices[:2])

    def handle_dialogue_action(self, action_id: str) -> str:
        if action_id == "close":
            return ""
        if action_id == "accept_story":
            story = self.get_current_story()
            if story and not self.story_active and not self.story_objective_complete:
                self.story_active = True
                self.story_progress = 0.0
                self.story_objective_complete = False
                msg = f"Story Started: {story.title}"
                self.notify(msg)
                return msg
            return ""
        if action_id == "turn_in_story":
            story = self.get_current_story()
            if story and self.story_objective_complete:
                self.progression_manager.add_coins(story.reward)
                self.story_index += 1
                self.progression_manager.set_story_index(self.story_index)
                self.story_active = False
                self.story_progress = 0.0
                self.story_objective_complete = False
                msg = f"Story Complete: +{story.reward} coins"
                self.notify(msg)
                return msg
            return ""
        if action_id.startswith("accept_side:"):
            quest_id = action_id.split(":", 1)[1]
            template = self._find_side_template_by_id(quest_id)
            if not template:
                return ""
            existing = self._find_active_side_for_npc(template.giver_npc)
            if existing:
                return ""
            self.side_counter += 1
            active_id = f"{quest_id}_{self.side_counter}"
            self.active_side_quests[active_id] = {
                "id": active_id,
                "template": template,
                "progress": 0.0,
                "completed": False,
            }
            msg = f"Side Quest Accepted: {template.title}"
            self.notify(msg)
            return msg
        if action_id.startswith("turn_in_side:"):
            active_id = action_id.split(":", 1)[1]
            quest = self.active_side_quests.get(active_id)
            if not quest or not quest["completed"]:
                return ""
            reward = quest["template"].reward
            self.progression_manager.add_coins(reward)
            del self.active_side_quests[active_id]
            msg = f"Side Quest Complete: +{reward} coins"
            self.notify(msg)
            return msg
        return ""

    def on_enemy_killed(self, amount: int = 1) -> None:
        self._increment_objective("eliminate", None, amount)

    def on_item_collected(self, item_type: str, amount: int = 1) -> None:
        self._increment_objective("collect", item_type, amount)

    def update(self, dt: float, player_position: Vec3, world) -> None:
        story = self.get_current_story()
        if self.story_active and story and not self.story_objective_complete:
            if story.objective_type == "reach" and story.location_name:
                location_pos = world.get_location_position(story.location_name)
                if location_pos and distance(player_position, location_pos) <= 3.2:
                    self.story_progress = story.target
                    self.story_objective_complete = True
                    self.notify("Story Objective Complete - Return to quest giver")

        for quest in self.active_side_quests.values():
            if quest["completed"]:
                continue
            template = quest["template"]
            if template.objective_type == "reach" and template.location_name:
                location_pos = world.get_location_position(template.location_name)
                if location_pos and distance(player_position, location_pos) <= 3.2:
                    quest["progress"] = template.target
                    quest["completed"] = True
                    self.notify(f"Side Objective Complete - Return to {template.giver_npc}")

    def get_tracker_lines(self) -> List[str]:
        lines: List[str] = []
        if self.mode != "free_roam":
            return lines

        story = self.get_current_story()
        if story:
            status = "Talk to quest giver"
            if self.story_active:
                status = self._build_progress_line(story, self.story_progress)
            elif self.story_objective_complete:
                status = "Return to quest giver"
            lines.append(f"Story - {story.title}: {status}")
        else:
            lines.append("Story - Complete")

        for quest in self.active_side_quests.values():
            template = quest["template"]
            prefix = "Done" if quest["completed"] else "Side"
            lines.append(f"{prefix} - {template.title}: {self._build_progress_line(template, quest['progress'])}")
        return lines[:4]

    def _build_progress_line(self, objective, progress: float) -> str:
        if objective.objective_type == "reach":
            return "Reach target location"
        current = int(min(objective.target, progress))
        return f"{current}/{objective.target}"

    def _increment_objective(self, objective_type: str, item_type: Optional[str], amount: int) -> None:
        story = self.get_current_story()
        if self.story_active and story and not self.story_objective_complete and story.objective_type == objective_type:
            if objective_type == "collect" and story.item_type != item_type:
                pass
            else:
                self.story_progress += amount
                if self.story_progress >= story.target:
                    self.story_progress = story.target
                    self.story_objective_complete = True
                    self.notify("Story Objective Complete - Return to quest giver")

        for quest in self.active_side_quests.values():
            if quest["completed"]:
                continue
            template = quest["template"]
            if template.objective_type != objective_type:
                continue
            if objective_type == "collect" and template.item_type != item_type:
                continue
            quest["progress"] += amount
            if quest["progress"] >= template.target:
                quest["progress"] = template.target
                quest["completed"] = True
                self.notify(f"Side Objective Complete - {template.title}")

    def _find_side_template_by_id(self, quest_id: str) -> Optional[SideQuestTemplate]:
        for template in self.side_templates:
            if template.quest_id == quest_id:
                return template
        return None

    def _find_side_template_for_npc(self, npc_id: str) -> Optional[SideQuestTemplate]:
        for template in self.side_templates:
            if template.giver_npc == npc_id:
                return template
        return None

    def _find_active_side_for_npc(self, npc_id: str):
        for quest in self.active_side_quests.values():
            if quest["template"].giver_npc == npc_id:
                return quest
        return None
