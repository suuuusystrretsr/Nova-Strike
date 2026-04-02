from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class SkillNode:
    node_id: str
    name: str
    description: str
    cost: int
    tier: int
    prereqs: Tuple[str, ...]
    effects: Dict[str, float]


def _node(
    node_id: str,
    name: str,
    description: str,
    cost: int,
    tier: int,
    prereqs=None,
    effects=None,
) -> SkillNode:
    return SkillNode(
        node_id=node_id,
        name=name,
        description=description,
        cost=int(cost),
        tier=int(tier),
        prereqs=tuple(prereqs or ()),
        effects=dict(effects or {}),
    )


SKILL_TREES: Dict[str, List[SkillNode]] = {
    "striker": [
        _node("striker_boots_1", "Runner's Stance", "Move faster.", 90, 1, effects={"speed_mult": 0.06}),
        _node("striker_boots_2", "Momentum Steps", "More movement speed.", 120, 1, effects={"speed_mult": 0.07}),
        _node("striker_sprint_1", "Sprint Burst", "Faster sprint speed.", 110, 1, effects={"sprint_mult": 0.1}),
        _node("striker_jump_1", "Knee Springs", "Jump higher.", 105, 1, effects={"jump_bonus": 0.7}),
        _node("striker_reload_1", "Quick Hands", "Reload a bit faster.", 95, 1, effects={"reload_mult": 0.95}),
        _node("striker_recoil_1", "Grip Drill", "Reduce recoil.", 100, 1, effects={"recoil_mult": 0.92}),
        _node("striker_damage_1", "Aggressive Form", "Increase weapon damage.", 130, 2, prereqs=("striker_boots_1",), effects={"damage_mult": 0.08}),
        _node("striker_fire_1", "Rapid Trigger", "Increase fire rate.", 135, 2, prereqs=("striker_reload_1",), effects={"fire_rate_mult": 0.08}),
        _node("striker_spread_1", "Laser Tracking", "Tighter spread.", 140, 2, prereqs=("striker_recoil_1",), effects={"spread_mult": 0.88}),
        _node("striker_health_1", "Cardio Core", "Increase max health.", 135, 2, prereqs=("striker_sprint_1",), effects={"health_bonus": 18}),
        _node("striker_jump_2", "Air Control", "Even higher jump.", 145, 2, prereqs=("striker_jump_1",), effects={"jump_bonus": 0.95}),
        _node("striker_regen_1", "Combat Breath", "Increase health regen.", 140, 2, prereqs=("striker_boots_2",), effects={"regen_rate_bonus": 2.2}),
        _node("striker_dash_1", "Hard Acceleration", "Boost movement speed.", 170, 3, prereqs=("striker_boots_2", "striker_sprint_1"), effects={"speed_mult": 0.11}),
        _node("striker_dash_2", "Overclocked Legs", "Further sprint bonus.", 180, 3, prereqs=("striker_dash_1",), effects={"sprint_mult": 0.14}),
        _node("striker_ability_1", "Jump Protocol", "Lower double-jump cooldown.", 185, 3, prereqs=("striker_jump_2",), effects={"ability_cooldown_mult": 0.9}),
        _node("striker_ability_2", "Aerial Rhythm", "Further lower ability cooldown.", 210, 4, prereqs=("striker_ability_1",), effects={"ability_cooldown_mult": 0.86}),
        _node("striker_crit_1", "Precision Pulse", "Gain crit chance.", 180, 3, prereqs=("striker_spread_1",), effects={"crit_chance": 0.06}),
        _node("striker_crit_2", "Weakspot Drill", "Gain crit damage.", 220, 4, prereqs=("striker_crit_1",), effects={"crit_damage_mult": 0.2}),
        _node("striker_damage_2", "Kinetic Focus", "More weapon damage.", 210, 4, prereqs=("striker_damage_1",), effects={"damage_mult": 0.1}),
        _node("striker_damage_3", "Execution Tempo", "High weapon damage boost.", 260, 5, prereqs=("striker_damage_2", "striker_fire_1"), effects={"damage_mult": 0.12}),
        _node("striker_survive_1", "Slip Reflex", "Chance to dodge incoming damage.", 230, 4, prereqs=("striker_health_1",), effects={"dodge_chance": 0.08}),
        _node("striker_survive_2", "Adaptive Guard", "Reduce incoming damage.", 240, 4, prereqs=("striker_survive_1",), effects={"damage_reduction": 0.08}),
        _node("striker_eco_1", "Scavenger Run", "Gain bonus coins.", 175, 3, prereqs=("striker_boots_1",), effects={"coin_mult": 0.12}),
        _node("striker_capstone", "Blitz Mastery", "Major all-round boost.", 320, 6, prereqs=("striker_damage_3", "striker_ability_2", "striker_survive_2"), effects={"speed_mult": 0.08, "fire_rate_mult": 0.08, "crit_chance": 0.05, "damage_mult": 0.08}),
    ],
    "vanguard": [
        _node("vanguard_plate_1", "Armor Weave", "Increase max health.", 95, 1, effects={"health_bonus": 20}),
        _node("vanguard_plate_2", "Reactive Plating", "Increase max health further.", 130, 1, effects={"health_bonus": 22}),
        _node("vanguard_guard_1", "Impact Guard", "Reduce incoming damage.", 115, 1, effects={"damage_reduction": 0.06}),
        _node("vanguard_guard_2", "Impact Guard II", "More incoming damage reduction.", 145, 2, prereqs=("vanguard_guard_1",), effects={"damage_reduction": 0.07}),
        _node("vanguard_regen_1", "Field Recovery", "Increase regen rate.", 120, 1, effects={"regen_rate_bonus": 2.5}),
        _node("vanguard_damage_1", "Heavy Hands", "Increase weapon damage.", 130, 1, effects={"damage_mult": 0.07}),
        _node("vanguard_recoil_1", "Stability Frame", "Reduce recoil.", 120, 2, prereqs=("vanguard_plate_1",), effects={"recoil_mult": 0.9}),
        _node("vanguard_reload_1", "Efficient Cycle", "Reload faster.", 125, 2, prereqs=("vanguard_damage_1",), effects={"reload_mult": 0.94}),
        _node("vanguard_speed_1", "March Protocol", "Slight move speed boost.", 125, 2, prereqs=("vanguard_plate_2",), effects={"speed_mult": 0.05}),
        _node("vanguard_speed_2", "Assault Drive", "Slight sprint boost.", 130, 2, prereqs=("vanguard_speed_1",), effects={"sprint_mult": 0.08}),
        _node("vanguard_ability_1", "Overdrive Cooling", "Lower ability cooldown.", 175, 3, prereqs=("vanguard_guard_2",), effects={"ability_cooldown_mult": 0.9}),
        _node("vanguard_ability_2", "Overdrive Sustain", "Increase ability duration.", 185, 3, prereqs=("vanguard_ability_1",), effects={"ability_duration_bonus": 0.8}),
        _node("vanguard_ability_3", "Overdrive Sustain II", "Further duration bonus.", 215, 4, prereqs=("vanguard_ability_2",), effects={"ability_duration_bonus": 1.1}),
        _node("vanguard_fire_1", "Suppression Tempo", "Increase fire rate.", 165, 3, prereqs=("vanguard_reload_1",), effects={"fire_rate_mult": 0.07}),
        _node("vanguard_spread_1", "Controlled Burst", "Tighter spread.", 170, 3, prereqs=("vanguard_recoil_1",), effects={"spread_mult": 0.9}),
        _node("vanguard_crit_1", "Target Break", "Gain crit chance.", 180, 3, prereqs=("vanguard_spread_1",), effects={"crit_chance": 0.05}),
        _node("vanguard_crit_2", "Breach Shot", "Gain crit damage.", 220, 4, prereqs=("vanguard_crit_1",), effects={"crit_damage_mult": 0.22}),
        _node("vanguard_damage_2", "Siege Rhythm", "More weapon damage.", 215, 4, prereqs=("vanguard_damage_1", "vanguard_fire_1"), effects={"damage_mult": 0.1}),
        _node("vanguard_hp_3", "Titan Frame", "Large max health bonus.", 230, 4, prereqs=("vanguard_plate_2", "vanguard_regen_1"), effects={"health_bonus": 30}),
        _node("vanguard_guard_3", "Bastion Protocol", "High incoming damage reduction.", 260, 5, prereqs=("vanguard_guard_2", "vanguard_hp_3"), effects={"damage_reduction": 0.1}),
        _node("vanguard_lifesteal", "War Sustain", "Gain lifesteal bonus.", 240, 4, prereqs=("vanguard_damage_2",), effects={"lifesteal_bonus": 0.07}),
        _node("vanguard_jump_1", "Thruster Stride", "Increase jump height.", 170, 3, prereqs=("vanguard_speed_2",), effects={"jump_bonus": 0.6}),
        _node("vanguard_eco_1", "Contract Bonus", "Gain bonus coins.", 180, 3, prereqs=("vanguard_plate_1",), effects={"coin_mult": 0.1}),
        _node("vanguard_capstone", "Fortress Prime", "Major tank/offense boost.", 340, 6, prereqs=("vanguard_guard_3", "vanguard_ability_3", "vanguard_damage_2"), effects={"damage_mult": 0.1, "health_bonus": 35, "damage_reduction": 0.08, "fire_rate_mult": 0.05}),
    ],
    "phantom": [
        _node("phantom_cloak_1", "Cloak Matrix", "Increase cloak duration.", 95, 1, effects={"ability_duration_bonus": 0.7}),
        _node("phantom_cloak_2", "Cloak Matrix II", "Increase cloak duration more.", 130, 2, prereqs=("phantom_cloak_1",), effects={"ability_duration_bonus": 0.9}),
        _node("phantom_cool_1", "Entropy Sink", "Lower ability cooldown.", 120, 1, effects={"ability_cooldown_mult": 0.92}),
        _node("phantom_cool_2", "Entropy Sink II", "Lower ability cooldown more.", 155, 2, prereqs=("phantom_cool_1",), effects={"ability_cooldown_mult": 0.88}),
        _node("phantom_speed_1", "Silent Step", "Increase move speed.", 105, 1, effects={"speed_mult": 0.06}),
        _node("phantom_speed_2", "Silent Step II", "Increase move speed more.", 140, 2, prereqs=("phantom_speed_1",), effects={"speed_mult": 0.08}),
        _node("phantom_damage_1", "Ambush Wire", "Increase damage.", 130, 2, prereqs=("phantom_speed_1",), effects={"damage_mult": 0.08}),
        _node("phantom_damage_2", "Ambush Wire II", "Increase damage further.", 180, 3, prereqs=("phantom_damage_1",), effects={"damage_mult": 0.1}),
        _node("phantom_crit_1", "Ghost Aim", "Gain critical chance.", 145, 2, prereqs=("phantom_damage_1",), effects={"crit_chance": 0.08}),
        _node("phantom_crit_2", "Ghost Aim II", "Gain critical chance further.", 190, 3, prereqs=("phantom_crit_1",), effects={"crit_chance": 0.09}),
        _node("phantom_crit_3", "Assassin Protocol", "Gain crit damage.", 240, 4, prereqs=("phantom_crit_2",), effects={"crit_damage_mult": 0.28}),
        _node("phantom_reload_1", "Fluid Motion", "Reload faster.", 125, 2, prereqs=("phantom_speed_2",), effects={"reload_mult": 0.93}),
        _node("phantom_fire_1", "Needle Tempo", "Increase fire rate.", 170, 3, prereqs=("phantom_reload_1",), effects={"fire_rate_mult": 0.1}),
        _node("phantom_spread_1", "Stability Veil", "Reduce spread.", 165, 3, prereqs=("phantom_reload_1",), effects={"spread_mult": 0.88}),
        _node("phantom_recoil_1", "Pulse Dampener", "Reduce recoil.", 160, 3, prereqs=("phantom_spread_1",), effects={"recoil_mult": 0.86}),
        _node("phantom_ghost_1", "Ghost Body", "Reduce incoming damage.", 170, 3, prereqs=("phantom_cloak_2",), effects={"damage_reduction": 0.07}),
        _node("phantom_ghost_2", "Ghost Body II", "Further damage reduction.", 210, 4, prereqs=("phantom_ghost_1",), effects={"damage_reduction": 0.08}),
        _node("phantom_regen_1", "Nano Mist", "Increase regen.", 175, 3, prereqs=("phantom_ghost_1",), effects={"regen_rate_bonus": 2.4}),
        _node("phantom_hp_1", "Shadow Reserve", "Increase max health.", 180, 3, prereqs=("phantom_regen_1",), effects={"health_bonus": 18}),
        _node("phantom_evasion_1", "Phase Drift", "Chance to dodge damage.", 225, 4, prereqs=("phantom_ghost_2",), effects={"dodge_chance": 0.11}),
        _node("phantom_life_1", "Blood Echo", "Gain lifesteal bonus.", 230, 4, prereqs=("phantom_damage_2",), effects={"lifesteal_bonus": 0.09}),
        _node("phantom_jump_1", "Wraith Leap", "Increase jump height.", 170, 3, prereqs=("phantom_speed_2",), effects={"jump_bonus": 0.7}),
        _node("phantom_eco_1", "Shadow Contracts", "Gain bonus coins.", 185, 3, prereqs=("phantom_speed_1",), effects={"coin_mult": 0.12}),
        _node("phantom_capstone", "Night Sovereign", "Major stealth/offense boost.", 350, 6, prereqs=("phantom_crit_3", "phantom_cool_2", "phantom_evasion_1"), effects={"damage_mult": 0.11, "crit_chance": 0.07, "ability_duration_bonus": 1.2, "speed_mult": 0.07}),
    ],
}


SKILL_NODE_MAPS: Dict[str, Dict[str, SkillNode]] = {
    skin_id: {node.node_id: node for node in nodes}
    for skin_id, nodes in SKILL_TREES.items()
}

