# Update Studios

External launcher and updater for one or more games.

## Features
- Detects installed games from `data/games/installed/*.json`
- Launches games from one place
- Checks for updates before launch (optional)
- Downloads only changed files from a manifest
- Verifies hashes before applying files
- Uses staged update + rollback-safe apply
- Supports signed developer drop packages in `studio_drop/incoming`

## Run
```powershell
cd C:\UpdateStudios
python UpdateStudios.py
```

## Developer Drop Folder
Incoming folder:
`C:\UpdateStudios\studio_drop\incoming`

Supported signed payload kinds:
- `game_registration`
- `game_update_source`
- `game_remove`

Supported signed package directories:
- `update_bundle`

Package directory format:
```text
studio_drop/incoming/<your_package>/
  package.json    # signed envelope (payload + signature)
  manifest.json   # update manifest body
  files/          # files referenced by manifest
```

## Developer Tools
Sign payload envelope:
```powershell
python developer_tools\sign_package.py --root C:\UpdateStudios --payload payload.json
```

Publish repository manifest:
```powershell
python developer_tools\build_manifest.py --root C:\UpdateStudios --game-id nova_strike --version 0.7.0 --game-dir C:\path\to\game
```
