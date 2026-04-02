import atexit
import json
import os
from pathlib import Path

from panda3d.core import AntialiasAttrib, loadPrcFileData
from ursina import Text, Ursina, application, camera, color, window

from scripts.color_compat import install_color_compat

install_color_compat()

from scripts.game_manager import GameManager


game_manager = None
runtime_lock_path = Path(__file__).resolve().parent / ".runtime.lock.json"


def _graceful_shutdown() -> None:
    global game_manager
    if not game_manager:
        _clear_runtime_lock()
        return
    try:
        game_manager.shutdown()
    except Exception:
        pass
    _clear_runtime_lock()


atexit.register(_graceful_shutdown)


def _is_pid_running(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return False
    except Exception:
        return False


def _write_runtime_lock() -> None:
    try:
        if runtime_lock_path.exists():
            existing = json.loads(runtime_lock_path.read_text(encoding="utf-8"))
            existing_pid = int(existing.get("pid", 0) or 0) if isinstance(existing, dict) else 0
            if existing_pid and existing_pid != os.getpid() and _is_pid_running(existing_pid):
                # Existing active lock from another process; keep it.
                return
    except Exception:
        pass
    payload = {"pid": int(os.getpid())}
    tmp = runtime_lock_path.with_suffix(runtime_lock_path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, runtime_lock_path)
    except OSError:
        pass
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def _clear_runtime_lock() -> None:
    try:
        if runtime_lock_path.exists():
            payload = json.loads(runtime_lock_path.read_text(encoding="utf-8"))
            existing_pid = int(payload.get("pid", 0) or 0) if isinstance(payload, dict) else 0
            if existing_pid and existing_pid != os.getpid() and _is_pid_running(existing_pid):
                return
            runtime_lock_path.unlink(missing_ok=True)
    except Exception:
        pass


def update():
    if game_manager:
        game_manager.update()


def input(key):
    if game_manager:
        game_manager.input(key)


def _configure_ui_font() -> None:
    """Use safe relative font ids to avoid absolute-path loader issues on Windows."""
    project_root = Path(__file__).resolve().parent
    ui_dir = project_root / "assets" / "ui"
    ui_dir.mkdir(parents=True, exist_ok=True)
    candidate_font_dirs = [
        project_root / ".venv" / "Lib" / "site-packages" / "ursina" / "fonts",
        project_root / ".venv" / "lib" / "site-packages" / "ursina" / "fonts",
    ]
    preferred_names = ["OpenSans-Regular.ttf", "VeraMono.ttf"]
    selected_name = "VeraMono.ttf"
    for font_name in preferred_names:
        asset_font = ui_dir / font_name
        root_font = project_root / font_name
        if not asset_font.exists():
            for font_dir in candidate_font_dirs:
                bundled_font = font_dir / font_name
                if bundled_font.exists():
                    try:
                        asset_font.write_bytes(bundled_font.read_bytes())
                        break
                    except OSError:
                        pass
        if asset_font.exists() and not root_font.exists():
            try:
                root_font.write_bytes(asset_font.read_bytes())
            except OSError:
                pass
        if root_font.exists():
            selected_name = font_name
            break

    # Keep this relative; absolute Windows paths can fail in Panda/Ursina font loader.
    Text.default_font = selected_name


def _get_primary_monitor_geometry():
    """Return (x, y, width, height) for the primary monitor, with safe fallback."""
    try:
        from screeninfo import get_monitors

        monitors = get_monitors()
        if monitors:
            primary = None
            for monitor in monitors:
                if getattr(monitor, "is_primary", False):
                    primary = monitor
                    break
            if primary is None:
                primary = monitors[0]
            return int(primary.x), int(primary.y), int(primary.width), int(primary.height)
    except Exception:
        pass
    return 0, 0, 1920, 1080


def main() -> None:
    global game_manager
    _write_runtime_lock()
    mon_x, mon_y, mon_w, mon_h = _get_primary_monitor_geometry()

    # Rendering baseline tuned for stability and cleaner text/UI rendering.
    loadPrcFileData("", f"win-origin {mon_x} {mon_y}")
    loadPrcFileData("", f"win-size {mon_w} {mon_h}")
    loadPrcFileData("", "dpi-aware 1")
    loadPrcFileData("", "undecorated 1")
    loadPrcFileData("", "fullscreen 0")
    loadPrcFileData("", "textures-auto-power-2 0")
    loadPrcFileData("", "framebuffer-multisample 1")
    loadPrcFileData("", "multisamples 4")
    loadPrcFileData("", "texture-anisotropic-degree 8")
    loadPrcFileData("", "text-page-size 8192 8192")
    loadPrcFileData("", "text-minfilter linear")
    loadPrcFileData("", "text-magfilter linear")
    application.development_mode = False
    app = Ursina(
        size=(mon_w, mon_h),
        borderless=True,
        fullscreen=False,
        vsync=True,
        editor_ui_enabled=False,
        icon="",
    )
    application.development_mode = False
    window.title = "Nova Strike"
    # Borderless fullscreen via startup config is more stable than resizing after launch.
    window.borderless = True
    window.fps_counter.enabled = False
    if hasattr(window, "entity_counter") and window.entity_counter:
        window.entity_counter.enabled = False
    if hasattr(window, "collider_counter") and window.collider_counter:
        window.collider_counter.enabled = False
    if hasattr(window, "cog_button") and window.cog_button:
        window.cog_button.enabled = False
    window.exit_button.visible = False
    window.color = color.rgb(14, 18, 30)
    camera.ui.enabled = True
    _configure_ui_font()
    Text.default_resolution = 320
    app.render.setAntialias(AntialiasAttrib.MAuto)
    camera.ui.setAntialias(AntialiasAttrib.MAuto)

    game_manager = GameManager(app)
    _original_quit = application.quit

    def _quit_with_shutdown(*args, **kwargs):
        _graceful_shutdown()
        return _original_quit(*args, **kwargs)

    application.quit = _quit_with_shutdown
    try:
        if hasattr(window, "exit_button") and getattr(window, "exit_button", None):
            window.exit_button.on_click = _graceful_shutdown
    except Exception:
        pass

    app.run()


if __name__ == "__main__":
    main()
