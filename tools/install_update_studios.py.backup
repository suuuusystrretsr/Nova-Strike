from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def copy_loader_template(source_root: Path, target_root: Path) -> None:
    target_root.mkdir(parents=True, exist_ok=True)
    for item in source_root.iterdir():
        destination = target_root / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


def write_start_script(target_root: Path, python_executable: str) -> None:
    start_script = target_root / "Start_Update_Studios.bat"
    start_script.write_text(
        "\n".join(
            [
                "@echo off",
                f'cd /d "{target_root}"',
                f'"{python_executable}" "{target_root / "UpdateStudios.py"}"',
                "pause",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Install Update Studios into C:\\UpdateStudios.")
    parser.add_argument("--target", default=r"C:\UpdateStudios", help="Install destination path.")
    parser.add_argument(
        "--game-path",
        default="",
        help="Default Nova Strike install path for bootstrap.",
    )
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    source_root = workspace_root / "update_studios_loader"
    if not source_root.exists():
        raise SystemExit(f"Missing loader template: {source_root}")

    target_root = Path(args.target).expanduser().resolve()
    copy_loader_template(source_root, target_root)
    write_start_script(target_root, sys.executable)

    sys.path.insert(0, str(target_root))
    from update_studios.bootstrap import ensure_default_setup  # pylint: disable=import-outside-toplevel
    from update_studios.paths import AppPaths  # pylint: disable=import-outside-toplevel

    default_game_path = str(args.game_path or "").strip()
    if not default_game_path:
        candidate = workspace_root.resolve()
        if (candidate / "main.py").exists() and (candidate / "scripts").exists():
            default_game_path = str(candidate)

    paths = AppPaths.create(root=target_root)
    ensure_default_setup(paths, default_game_path=default_game_path or None)
    print(f"Update Studios installed at: {target_root}")
    print(f"Start script: {target_root / 'Start_Update_Studios.bat'}")
    print(f"Drop folder: {paths.incoming_drop_dir}")


if __name__ == "__main__":
    main()
