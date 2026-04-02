from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

from .json_store import load_json, write_json_atomic
from .models import GameConfig, LaunchConfig
from .paths import AppPaths
from .registry import GameRegistry
from .security import ensure_developer_key, sign_payload, verify_signature


def ensure_default_setup(paths: AppPaths, default_game_path: str | None = None) -> None:
    paths.ensure()
    secret = ensure_developer_key(paths)
    registry = GameRegistry(paths)

    if default_game_path:
        game_path = Path(default_game_path).expanduser().resolve()
        if game_path.exists():
            current_version = detect_game_version(game_path)
            game = registry.get_game("nova_strike")
            if game is None:
                game = build_default_nova_strike_config(paths, game_path, current_version)
                registry.save_game(game)
            else:
                game.install_dir = str(game_path)
                game.local_version = current_version or game.local_version
                registry.save_game(game)

            channel_path = paths.repository_dir / "nova_strike" / "channel.json"
            channel_payload = load_json(channel_path, default={})
            latest = str(channel_payload.get("latest_version", "")).strip() if isinstance(channel_payload, dict) else ""
            needs_signature_refresh = True
            if isinstance(channel_payload, dict):
                signature = str(channel_payload.get("signature", "")).strip().lower()
                unsigned = {k: v for k, v in channel_payload.items() if k != "signature"}
                if signature and verify_signature(unsigned, signature, secret):
                    needs_signature_refresh = False
            if not channel_path.exists() or needs_signature_refresh or _version_key(game.local_version) > _version_key(latest):
                build_local_repository_snapshot(
                    paths=paths,
                    game_id="nova_strike",
                    version=game.local_version,
                    game_root=game_path,
                    developer_secret=secret,
                )


def build_default_nova_strike_config(paths: AppPaths, game_root: Path, version: str) -> GameConfig:
    python_exe = game_root / ".venv" / "Scripts" / "python.exe"
    if python_exe.exists():
        executable = str(python_exe)
        args = ["main.py"]
    else:
        executable = "py"
        args = [str(game_root / "main.py")]
    channel_path = (paths.repository_dir / "nova_strike" / "channel.json").resolve()
    return GameConfig(
        game_id="nova_strike",
        display_name="Nova Strike",
        install_dir=str(game_root),
        local_version=version or "0.0.0",
        update_source=channel_path.as_uri(),
        channel="stable",
        description="Primary build integrated into Update Studios.",
        launch=LaunchConfig(
            executable=executable,
            args=args,
            cwd=str(game_root),
            env={},
        ),
    )


def build_local_repository_snapshot(
    paths: AppPaths,
    game_id: str,
    version: str,
    game_root: Path,
    developer_secret: str,
) -> None:
    include_files = list(_iter_baseline_files(game_root))
    repo_root = paths.repository_dir / game_id
    files_root = repo_root / "files" / version
    files_root.mkdir(parents=True, exist_ok=True)

    manifest_entries: list[dict] = []
    for source_file in include_files:
        rel = source_file.relative_to(game_root).as_posix()
        payload = source_file.read_bytes()
        digest = hashlib.sha256(payload).hexdigest().lower()
        target = files_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        manifest_entries.append(
            {
                "path": rel,
                "sha256": digest,
                "size": len(payload),
                "url": f"files/{version}/{rel}",
            }
        )

    manifest_payload = {
        "game_id": game_id,
        "version": version,
        "files": manifest_entries,
        "remove": [],
    }
    manifest_payload["signature"] = sign_payload({k: v for k, v in manifest_payload.items() if k != "signature"}, developer_secret)
    manifests_dir = repo_root / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(manifests_dir / f"{version}.json", manifest_payload)

    channel_payload = {
        "game_id": game_id,
        "latest_version": version,
        "manifest": f"manifests/{version}.json",
    }
    channel_payload["signature"] = sign_payload({k: v for k, v in channel_payload.items() if k != "signature"}, developer_secret)
    write_json_atomic(repo_root / "channel.json", channel_payload)


def detect_game_version(game_root: Path) -> str:
    versions_dir = game_root / "GAME VERSIONS"
    if not versions_dir.exists():
        return "0.0.0"
    candidates: list[str] = []
    for file in versions_dir.glob("version_*.txt"):
        match = re.match(r"version_(.+)\.txt$", file.name, re.IGNORECASE)
        if not match:
            continue
        version = match.group(1).strip()
        if version:
            candidates.append(version)
    if not candidates:
        return "0.0.0"
    candidates.sort(key=_version_key)
    return candidates[-1]


def _iter_baseline_files(game_root: Path) -> Iterable[Path]:
    direct_files = (
        game_root / "main.py",
        game_root / "requirements.txt",
        game_root / "README.md",
    )
    for file in direct_files:
        if file.exists() and file.is_file():
            yield file

    scripts_dir = game_root / "scripts"
    if scripts_dir.exists():
        for file in sorted(scripts_dir.glob("*.py")):
            if file.is_file():
                yield file


def _version_key(version: str) -> tuple:
    text = str(version or "").strip().lower()
    nums = [int(token) for token in re.findall(r"\d+", text)]
    if not nums:
        nums = [0]
    while len(nums) < 4:
        nums.append(0)
    prerelease = -1 if any(tag in text for tag in ("alpha", "beta", "rc", "pre")) else 0
    return tuple(nums + [prerelease])
