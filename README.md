# Nova Strike (Ursina 3D Shooter)

Nova Strike is a full playable 3D shooter built in Python with Ursina.

## Features
- Title screen, main menu, mode select, settings, and skin select.
- Full loop: `Title -> Menu -> Mode -> Skin -> Gameplay -> Death -> Restart/Menu`.
- Two separate playable modes:
  - `Mission Mode`: Wave combat + staged objectives (`survive`, `eliminate`, `reach`).
  - `Free Roam`: Open-world exploration with NPCs, roaming enemies, story, and side quests.
- Story system with ordered missions from NPCs.
- Side quests: eliminate enemies, reach locations, and collect items.
- Progression system:
  - Coins from enemy drops
  - Upgrade purchases (`damage`, `reload`, `health`)
  - Ability upgrades (`striker`, `vanguard`, `phantom`)
  - Massive character-specific skill trees with permanent unlocks
  - Character lock per profile (choose once, stays until reset)
  - Per-profile save slots (`PROFILE 1-3`)
  - Checkpoints (`F5` save, `F9` load)
- Combat upgrades:
  - Multiple weapon types (`rifle`, `shotgun`, `pistol`, `smg`, `sniper`, `lmg`)
  - Rarity tiers (`common` -> `legendary`)
  - Attachment rolls on dropped weapons
  - Recoil, spread, reload flow, hitmarkers, tracers
  - Camera shake on shooting and damage
- Daily/weekly challenge tracker with coin rewards.
- Perk drops (`lifesteal`, `ricochet`, `haste`, `fortify`).
- Mini-map + full tactical map (`M`).
- Character and enemy procedural models with animation.
- First-person and third-person camera with smooth transitions (`V`).
- HUD, pause menu, upgrades panel, dialogue panel, and game over screen.
- Graphics presets: `LOW`, `MEDIUM`, `HIGH`, `ULTRA`.
- Settings sliders: mouse sensitivity, FOV, and volume.
- Centralized replaceable asset loading system.

## Install
1. Open terminal in project root:
   - `C:\Users\goril\OneDrive\Desktop\game`
2. (Optional) Create and activate virtual environment:
   - `python -m venv .venv`
   - `.venv\Scripts\activate`
3. Install dependencies:
   - `pip install -r requirements.txt`

## Run
1. From project root:
   - `python main.py`
2. Click `Start Game`.
3. Choose `Mission Mode` or `Free Roam`.
4. Pick your skin and start.

## Controls
- `W A S D`: Move
- `Mouse`: Look
- `Shift`: Sprint
- `Space`: Jump
- `Left Mouse`: Fire
- `R`: Reload
- `I`: Toggle inventory (click weapon cards to equip)
- `V`: Toggle first-person / third-person
- `Q`: Character ability
- `E`: Interact with NPCs (Free Roam)
- `M`: Tactical map
- `F5`: Save checkpoint
- `F9`: Load checkpoint
- `U`: Pause menu shortcut
- `Esc`: Pause/Resume or back to menu (context-sensitive)

## Skill Tree
- Open pause menu (`Esc` or `U`) and click `Skill Tree`.
- Unlock nodes with coins.
- Each character has a unique large tree.
- Unlocks are permanent for that profile until progress reset.
- Character selection is locked after first gameplay start on that profile.

## Replaceable Assets
All models and sounds go through `scripts/asset_loader.py`.

Drop real assets in:
- `assets/models/players/`
- `assets/models/enemies/`
- `assets/models/weapons/`
- `assets/models/npcs/`
- `assets/textures/`
- `assets/audio/`
- `assets/ui/`

Procedural fallbacks are used when custom files are not present.

## Optional Audio Files
Supported placeholder names in `assets/audio/`:
- `rifle_shot.(ogg|wav|mp3)`
- `shotgun_shot.(ogg|wav|mp3)`
- `pistol_shot.(ogg|wav|mp3)`
- `reload.(ogg|wav|mp3)`
- `hitmarker.(ogg|wav|mp3)`
- `footstep.(ogg|wav|mp3)`
