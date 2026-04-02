# Payload Templates

Use these as starting points for signed packages.

## Game Registration
1. Edit `game_registration.payload.json`
2. Sign it:
   `python developer_tools\sign_package.py --root C:\UpdateStudios --payload templates\game_registration.payload.json`
3. Signed file is dropped into:
   `C:\UpdateStudios\studio_drop\incoming`

## Update Bundle Package Directory
Create:
```text
C:\UpdateStudios\studio_drop\incoming\my_update_bundle\
  package.json
  manifest.json
  files\...
```

Steps:
1. Copy `update_bundle.payload.json` into your package folder and adjust values.
2. Sign payload to `package.json`:
   `python developer_tools\sign_package.py --root C:\UpdateStudios --payload <payload_path> --out C:\UpdateStudios\studio_drop\incoming\my_update_bundle\package.json`
3. Put file contents inside `files\` matching `manifest.json` entries.
4. Start Update Studios. The package is imported automatically if signature is valid.
