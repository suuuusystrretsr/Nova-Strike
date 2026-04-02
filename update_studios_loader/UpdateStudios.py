import os
from pathlib import Path

from update_studios.bootstrap import ensure_default_setup
from update_studios.paths import AppPaths
from update_studios.service import LoaderService
from update_studios.ui import LoaderUI


def _detect_default_game_path(app_root: Path) -> str | None:
    candidates = [
        app_root.parent,
        Path.cwd(),
    ]
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except Exception:
            continue
        if (resolved / "main.py").exists() and (resolved / "scripts").exists():
            return str(resolved)
    return None


def main() -> None:
    app_root = Path(__file__).resolve().parent
    configured_root = str(os.environ.get("UPDATE_STUDIOS_ROOT", "") or "").strip()
    root_path = Path(configured_root).expanduser() if configured_root else None
    paths = AppPaths.create(root=root_path)
    try:
        paths.ensure()
    except Exception:
        # Development fallback: if system root is unavailable, keep data beside the loader.
        paths = AppPaths.create(root=app_root)
        paths.ensure()
    ensure_default_setup(paths, default_game_path=_detect_default_game_path(app_root))
    service = LoaderService(paths)
    ui = LoaderUI(service)
    ui.run()


if __name__ == "__main__":
    main()
