import math
import uuid
from typing import Dict, Optional

from ursina import Vec3, application, camera, color, destroy, mouse, raycast, scene, time, window

from scripts.asset_loader import AssetLoader
from scripts.camera_controller import CameraController
from scripts.challenge_manager import ChallengeManager
from scripts.enemy import Enemy
from scripts.game_rng import GameRNG
from scripts.gamemode_system import GameModeRegistry, MatchSettings
from scripts.graphics_manager import GraphicsManager
from scripts.map_system import MapRegistry
from scripts.menu import MenuManager
from scripts.net_state import PlayerSyncState
from scripts.networking import SocketNetBridge
from scripts.npc import NPC
from scripts.pickups import BasePickup
from scripts.player import Player
from scripts.progression_manager import ProgressionManager
from scripts.quest_system import QuestSystem
from scripts.settings_manager import SettingsManager
from scripts.sim_scheduler import SimulationScheduler
from scripts.skin_system import SkinSystem
from scripts.skill_tree import SKILL_NODE_MAPS
from scripts.simulation_clock import SimulationClock
from scripts.ui_manager import UIManager
from scripts.weapon import ATTACHMENT_LIBRARY, RARITY_ORDER, roll_attachments
from scripts.world import World


class GameManager:
    DISPLAY_MODE_SEQUENCE = ("fullscreen", "borderless_fullscreen", "windowed")
    DISPLAY_MODE_LABELS = {
        "fullscreen": "Fullscreen",
        "borderless_fullscreen": "Borderless Fullscreen",
        "windowed": "Windowed",
    }

    def __init__(self, app) -> None:
        self.app = app
        self.state = "menu"
        self.transition_lock = False
        self.session_id = 0
        self.scheduler = SimulationScheduler()
        self.dt = 1 / 60
        self.frame_dt = 1 / 60
        self.fixed_dt = 1 / 60
        self.sim_dt = 1 / 60
        self.simulation_steps = 1
        self.sim_clock = SimulationClock(fixed_dt=1.0 / 60.0, max_frame_dt=0.1, max_substeps=5)
        self.rng = GameRNG()
        self.match_seed = self.rng.seed

        self.settings_manager = SettingsManager()
        self._active_display_mode = self._normalize_display_mode(self.settings_manager.get_display_mode())
        self._windowed_size = (1280, 720)
        self.progression_manager = ProgressionManager()
        self.challenge_manager = None
        self.asset_loader = AssetLoader()
        self.asset_loader.set_master_volume(self.settings_manager.get_master_volume())
        self.skin_system = SkinSystem(self.settings_manager)
        self.graphics_manager = GraphicsManager(self.settings_manager)

        self.mode_registry = GameModeRegistry()
        self.map_registry = MapRegistry()
        self.mode_id = self.mode_registry.get_default_singleplayer_mode_id()
        self.preferred_map_id: Optional[str] = None
        self.requested_team_size: Optional[int] = None
        self.requested_max_players: Optional[int] = None
        self.forced_match_seed: Optional[int] = None
        self.current_map_id = ""
        self.match_settings: MatchSettings = self.mode_registry.build_match_settings(
            mode_id=self.mode_id,
            map_id="mission_outpost_alpha",
        )
        self.game_mode = self.match_settings.legacy_world_mode

        self.ui_manager = UIManager(self)
        self.menu_manager = MenuManager(self)
        self.challenge_manager = ChallengeManager(self.progression_manager, notify=self.ui_manager.show_toast)
        self.enemy_wave = 1
        self.enemies = []
        self.npcs = []
        self.pickups = []
        self.quest_system = None
        self.free_roam_enemy_timer = 0.0
        self.auto_checkpoint_timer = 24.0
        self.current_dialogue_npc = None
        self.focused_weapon_pickup = None
        self.current_boss = None

        self.world = None
        self.player = None
        self.players: Dict[str, Player] = {}
        self.player_teams: Dict[str, str] = {}
        self.local_player_id = self._build_local_player_id()
        self.remote_player_states: Dict[str, PlayerSyncState] = {}
        self.remote_last_sequence: Dict[str, int] = {}
        self.remote_last_seen_time: Dict[str, float] = {}
        self.remote_state_timeout = 7.5
        self.server_team_assignments: Dict[str, str] = {}
        self.camera_controller = None

        # Networking foundation (inactive by default).
        self.network_bridge = SocketNetBridge()
        self.network_sequence = 0
        self.network_clock = 0.0
        self.network_send_accumulator = 0.0
        self.network_send_rate = 20.0
        self.multiplayer_connection_mode = "host"
        self.multiplayer_host = "127.0.0.1"
        self.multiplayer_port = 7777
        self.network_last_error_displayed = ""
        self.network_match_config: Dict[str, object] = {}
        self.network_match_config_received_at = -1.0
        self.network_config_broadcast_timer = 0.0
        self.network_config_broadcast_interval = 0.8
        self._shutdown_in_progress = False

        self.mission_stages = []
        self.mission_stage_index = 0
        self.mission_stage_progress = 0.0
        self.mission_completed = False
        self.mission_kill_counter = 0

        self._windowed_size = self._capture_window_size(default=self._windowed_size)
        self.apply_display_mode(notify=False)
        self._set_menu_mouse_mode()
        self.show_main_menu()

    def _build_local_player_id(self) -> str:
        return f"p_{uuid.uuid4().hex[:10]}"

    def _purge_stale_world_roots(self, keep_root=None) -> None:
        keep_root_name = str(getattr(keep_root, "name", "") or "")
        for entity in list(getattr(scene, "entities", [])):
            if not entity or entity is keep_root:
                continue
            name = str(getattr(entity, "name", "") or "")
            if not name.startswith("world_root_"):
                continue
            try:
                entity.enabled = False
            except Exception:
                pass
            try:
                entity.collider = None
            except Exception:
                pass
            destroy(entity)
        self._purge_stale_world_lights(keep_root_name=keep_root_name)

    def _node_has_world_root_ancestor(self, node_path, keep_root_name: str = "") -> bool:
        current = node_path
        depth = 0
        while current and not current.is_empty() and depth < 64:
            name = str(current.get_name() or "")
            if name.startswith("world_root_"):
                if keep_root_name and name == keep_root_name:
                    return False
                return True
            parent = current.get_parent()
            if not parent or parent.is_empty() or parent == current:
                break
            current = parent
            depth += 1
        return False

    def _purge_stale_world_lights(self, keep_root_name: str = "") -> None:
        render_root = self._get_render_root()
        if not render_root:
            return
        try:
            light_nodes = render_root.find_all_matches("**/+Light")
        except Exception:
            return
        try:
            total = int(light_nodes.get_num_paths())
        except Exception:
            total = 0
        for index in range(total):
            try:
                light_np = light_nodes.get_path(index)
            except Exception:
                continue
            if not light_np or light_np.is_empty():
                continue
            if not self._node_has_world_root_ancestor(light_np, keep_root_name=keep_root_name):
                continue
            try:
                render_root.clearLight(light_np)
            except Exception:
                pass

    def _get_render_root(self):
        base = getattr(application, "base", None)
        if base is not None and hasattr(base, "render"):
            return base.render
        return None

    def _normalize_display_mode(self, mode: Optional[str]) -> str:
        normalized = str(mode or "").strip().lower()
        if normalized in self.DISPLAY_MODE_SEQUENCE:
            return normalized
        return "borderless_fullscreen"

    def _capture_window_size(self, default=(1280, 720)) -> tuple[int, int]:
        try:
            current = getattr(window, "size", None)
            if current is not None:
                width = int(current[0])
                height = int(current[1])
                if width > 0 and height > 0:
                    return (width, height)
        except Exception:
            pass
        return (int(default[0]), int(default[1]))

    def _get_primary_monitor_geometry(self) -> tuple[int, int, int, int]:
        monitor = getattr(window, "main_monitor", None)
        if monitor is not None:
            try:
                return (
                    int(monitor.x),
                    int(monitor.y),
                    max(640, int(monitor.width)),
                    max(360, int(monitor.height)),
                )
            except Exception:
                pass
        width = max(640, int(self._windowed_size[0]))
        height = max(360, int(self._windowed_size[1]))
        return (0, 0, width, height)

    def get_display_mode_label(self, mode: Optional[str] = None) -> str:
        normalized = self._normalize_display_mode(mode if mode is not None else self.settings_manager.get_display_mode())
        return self.DISPLAY_MODE_LABELS.get(normalized, self.DISPLAY_MODE_LABELS["borderless_fullscreen"])

    def apply_display_mode(self, mode: Optional[str] = None, notify: bool = False) -> str:
        target_mode = self._normalize_display_mode(mode if mode is not None else self.settings_manager.get_display_mode())
        current_mode = self._normalize_display_mode(self._active_display_mode)
        if current_mode == "windowed":
            self._windowed_size = self._capture_window_size(default=self._windowed_size)

        monitor_x, monitor_y, monitor_w, monitor_h = self._get_primary_monitor_geometry()
        monitor_ready = getattr(window, "main_monitor", None) is not None
        if target_mode == "fullscreen" and not monitor_ready:
            target_mode = "borderless_fullscreen"

        try:
            if target_mode == "fullscreen":
                window.borderless = False
                window.fullscreen = True
            elif target_mode == "borderless_fullscreen":
                if bool(getattr(window, "fullscreen", False)):
                    window.fullscreen = False
                window.borderless = True
                window.position = (monitor_x, monitor_y)
                window.size = (monitor_w, monitor_h)
            else:
                if bool(getattr(window, "fullscreen", False)):
                    window.fullscreen = False
                window.borderless = False
                windowed_w = max(960, min(int(self._windowed_size[0]), int(monitor_w)))
                windowed_h = max(540, min(int(self._windowed_size[1]), int(monitor_h)))
                if windowed_w >= int(monitor_w) and windowed_h >= int(monitor_h):
                    windowed_w = max(960, int(monitor_w * 0.85))
                    windowed_h = max(540, int(monitor_h * 0.85))
                self._windowed_size = (windowed_w, windowed_h)
                window.size = self._windowed_size
                if hasattr(window, "center_on_screen"):
                    window.center_on_screen()
                self._windowed_size = self._capture_window_size(default=self._windowed_size)
        except Exception:
            target_mode = "borderless_fullscreen"
            try:
                if bool(getattr(window, "fullscreen", False)):
                    window.fullscreen = False
                window.borderless = True
                window.position = (monitor_x, monitor_y)
                window.size = (monitor_w, monitor_h)
            except Exception:
                pass

        self.settings_manager.set_display_mode(target_mode)
        self._active_display_mode = target_mode
        if notify:
            self.ui_manager.show_toast(f"Display Mode: {self.get_display_mode_label(target_mode)}", duration=1.5)
        return target_mode

    def cycle_display_mode(self, direction: int = 1) -> str:
        sequence = list(self.DISPLAY_MODE_SEQUENCE)
        current_mode = self._normalize_display_mode(self.settings_manager.get_display_mode())
        try:
            index = sequence.index(current_mode)
        except ValueError:
            index = sequence.index("borderless_fullscreen")
        step = 1 if int(direction) >= 0 else -1
        next_mode = sequence[(index + step) % len(sequence)]
        return self.apply_display_mode(mode=next_mode, notify=True)

    # --------------------
    # State/Flow Management
    # --------------------
    def show_title(self) -> None:
        # Legacy alias: title screen removed, now main menu is the first screen.
        self.show_main_menu()

    def show_main_menu(self) -> None:
        if self.network_bridge.is_active:
            self.stop_network()
        self.cleanup_gameplay()
        self.state = "menu"
        self.menu_manager.show_main_menu()
        self.ui_manager.hide_all()
        camera.position = (0, 7, -20)
        camera.rotation = (15, 0, 0)
        camera.fov = self.settings_manager.get_fov()
        self._set_menu_mouse_mode()

    def show_mode_select(self) -> None:
        if self.network_bridge.is_active:
            self.stop_network()
        self.cleanup_gameplay()
        self.state = "mode_select"
        self.menu_manager.show_mode_menu()
        self.ui_manager.hide_all()
        camera.position = (0, 6.4, -17)
        camera.rotation = (14, 0, 0)
        camera.fov = self.settings_manager.get_fov()
        self._set_menu_mouse_mode()

    def show_multiplayer_mode_select(self) -> None:
        if self.network_bridge.is_active:
            self.stop_network()
        self.cleanup_gameplay()
        self.state = "multiplayer_mode_select"
        self.menu_manager.show_multiplayer_mode_menu()
        self.ui_manager.hide_all()
        camera.position = (0, 6.4, -17)
        camera.rotation = (14, 0, 0)
        camera.fov = self.settings_manager.get_fov()
        self._set_menu_mouse_mode()

    def show_mode_menu_for_current_selection(self) -> None:
        resolved = self.mode_registry.resolve_mode(self.mode_id)
        if resolved.is_multiplayer:
            self.show_multiplayer_mode_select()
            return
        self.show_mode_select()

    def _should_enforce_character_lock(self, mode_id: Optional[str] = None) -> bool:
        resolved = self.mode_registry.resolve_mode(mode_id if mode_id is not None else self.mode_id)
        return not resolved.is_multiplayer

    def set_multiplayer_connection_mode(self, mode: str) -> None:
        normalized = str(mode or "").strip().lower()
        self.multiplayer_connection_mode = "host" if normalized == "host" else "client"
        if self.network_bridge.is_active:
            self.stop_network()
        self.ui_manager.show_toast(f"Multiplayer connection: {self.get_multiplayer_connection_mode_label()}")
        if self.state == "multiplayer_mode_select":
            self.menu_manager.show_multiplayer_mode_menu()

    def configure_network_target(self, host: str, port: int) -> None:
        self.multiplayer_host = str(host or "127.0.0.1").strip() or "127.0.0.1"
        try:
            self.multiplayer_port = max(1, min(65535, int(port)))
        except (TypeError, ValueError):
            self.multiplayer_port = 7777
        if self.network_bridge.is_active:
            self.stop_network()
        if self.state == "multiplayer_mode_select":
            self.menu_manager.show_multiplayer_mode_menu()

    def get_multiplayer_connection_mode_label(self) -> str:
        return "Host Server" if self.multiplayer_connection_mode == "host" else "Join Server"

    def get_multiplayer_endpoint_label(self) -> str:
        return f"{self.multiplayer_host}:{self.multiplayer_port}"

    def get_ctf_team_size_preference(self) -> int:
        ctf_mode = self.mode_registry.resolve_mode("ctf")
        requested = self.requested_team_size if self.requested_team_size is not None else 1
        return self.mode_registry.choose_team_size(ctf_mode, requested)

    def set_ctf_team_size_preference(self, team_size: int) -> None:
        ctf_mode = self.mode_registry.resolve_mode("ctf")
        resolved = self.mode_registry.choose_team_size(ctf_mode, team_size)
        self.requested_team_size = resolved
        if self.mode_id == "ctf":
            self.ui_manager.show_toast(f"CTF team size set to {resolved}v{resolved}", duration=1.4)
        if self.state == "multiplayer_mode_select":
            self.menu_manager.show_multiplayer_mode_menu()

    def _is_team_mode(self) -> bool:
        return bool(self.match_settings and self.match_settings.supports_teams)

    def _ensure_multiplayer_transport_ready(self) -> bool:
        if not self.match_settings or not self.match_settings.is_multiplayer:
            if self.network_bridge.is_active:
                self.stop_network()
            return True

        desired_mode = "server" if self.multiplayer_connection_mode == "host" else "client"
        same_transport = (
            self.network_bridge.is_active
            and self.network_bridge.mode == desired_mode
            and str(self.network_bridge.bind_host) == str(self.multiplayer_host)
            and int(self.network_bridge.bind_port) == int(self.multiplayer_port)
        )
        if same_transport:
            if desired_mode == "client" and not self.network_bridge.connection_ready:
                if getattr(self.network_bridge, "client_connecting", False):
                    self.ui_manager.show_toast("Still connecting to host...", duration=1.1)
                return False
            return True

        self.stop_network()
        if self.multiplayer_connection_mode == "host":
            return self.start_network_server(host=self.multiplayer_host, port=self.multiplayer_port)
        started = self.start_network_client(host=self.multiplayer_host, port=self.multiplayer_port)
        if not started:
            return False
        if not self.network_bridge.connection_ready:
            self.ui_manager.show_toast("Connecting to host... press Start once connected.", duration=1.6)
            return False
        return True

    def configure_match(
        self,
        mode_id: str,
        map_id: Optional[str] = None,
        team_size: Optional[int] = None,
        max_players: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> None:
        mode = self.mode_registry.resolve_mode(mode_id)
        self.mode_id = mode.mode_id
        self.preferred_map_id = str(map_id) if map_id else None
        if team_size is not None:
            self.requested_team_size = self.mode_registry.choose_team_size(mode, int(team_size))
        elif not mode.supports_teams:
            self.requested_team_size = None
        self.requested_max_players = int(max_players) if max_players is not None else None
        self.forced_match_seed = int(seed) if seed is not None else None
        self.game_mode = mode.legacy_world_mode

    def _resolve_match_settings(self) -> MatchSettings:
        mode = self.mode_registry.resolve_mode(self.mode_id)
        preferred_map_id = self.preferred_map_id
        requested_team_size = self.requested_team_size
        requested_max_players = self.requested_max_players

        if mode.is_multiplayer and self.multiplayer_connection_mode == "client" and self.network_match_config:
            host_mode = self.mode_registry.resolve_mode(str(self.network_match_config.get("mode_id", mode.mode_id)))
            if host_mode.is_multiplayer:
                mode = host_mode
                self.mode_id = mode.mode_id
            host_map = str(self.network_match_config.get("map_id", "") or "")
            if host_map:
                preferred_map_id = host_map
            host_team_size = self.network_match_config.get("team_size")
            if host_team_size is not None:
                requested_team_size = self.mode_registry.choose_team_size(mode, host_team_size)
            host_max_players = self.network_match_config.get("max_players")
            if host_max_players is not None:
                try:
                    requested_max_players = int(host_max_players)
                except (TypeError, ValueError):
                    pass

        map_id = self.map_registry.select_map_for_mode(mode, self.rng, preferred_map_id=preferred_map_id)
        self.current_map_id = map_id
        self.match_settings = self.mode_registry.build_match_settings(
            mode_id=mode.mode_id,
            map_id=map_id,
            requested_team_size=requested_team_size,
            requested_max_players=requested_max_players,
        )
        self.requested_team_size = self.match_settings.team_size if self.match_settings.supports_teams else None
        self.requested_max_players = self.match_settings.max_players if self.match_settings.is_multiplayer else None
        self.game_mode = self.match_settings.legacy_world_mode
        return self.match_settings

    def select_mode_and_open_skin(self, mode: str, team_size: Optional[int] = None) -> None:
        resolved = self.mode_registry.resolve_mode(mode)
        self.mode_id = resolved.mode_id
        self.game_mode = resolved.legacy_world_mode
        self.preferred_map_id = None
        if resolved.supports_teams:
            if team_size is not None:
                self.requested_team_size = self.mode_registry.choose_team_size(resolved, team_size)
            elif self.requested_team_size is None:
                self.requested_team_size = self.mode_registry.choose_team_size(resolved, 1)
            else:
                self.requested_team_size = self.mode_registry.choose_team_size(resolved, self.requested_team_size)
        else:
            self.requested_team_size = None
        self.requested_max_players = None
        self.forced_match_seed = None
        if not resolved.is_multiplayer and self.network_bridge.is_active:
            self.stop_network()
        locked_skin_id = self.progression_manager.get_locked_skin_id() if self._should_enforce_character_lock(resolved.mode_id) else None
        if locked_skin_id:
            self.skin_system.select_skin(locked_skin_id)
            self.state = "skin_select"
            locked_skin = self.skin_system.get_skin(locked_skin_id)
            self.ui_manager.show_toast(f"Operative locked: {locked_skin.display_name}")
            self.start_gameplay()
            return
        self.open_skin_select()

    def open_skin_select(self) -> None:
        if self.transition_lock:
            return
        self.state = "skin_select"
        self.menu_manager.show_skin_menu()
        self.ui_manager.hide_all()
        camera.position = (0, 1.7, -2.8)
        camera.rotation = (2, 0, 0)
        camera.fov = 70
        self._set_menu_mouse_mode()

    def start_gameplay(self) -> None:
        if self.transition_lock:
            return
        if self.state not in ("skin_select", "game_over"):
            return
        self.transition_lock = True
        try:
            seed_override = self.forced_match_seed
            if self.multiplayer_connection_mode == "client" and self.network_match_config:
                try:
                    host_seed = self.network_match_config.get("seed")
                    if host_seed is not None:
                        seed_override = int(host_seed)
                except (TypeError, ValueError):
                    seed_override = self.forced_match_seed
            self.match_seed = self.rng.reset(seed_override)
            self._resolve_match_settings()
            if not self._ensure_multiplayer_transport_ready():
                self.state = "skin_select"
                self.menu_manager.show_skin_menu()
                self.ui_manager.hide_all()
                self._set_menu_mouse_mode()
                return
            if self.match_settings.is_multiplayer and self.multiplayer_connection_mode == "client" and not self.network_match_config:
                self.state = "skin_select"
                self.menu_manager.show_skin_menu()
                self.ui_manager.hide_all()
                self._set_menu_mouse_mode()
                self.ui_manager.show_toast("Waiting for host match setup. Ask host to start first.", duration=2.4)
                return
            self.cleanup_gameplay()
            self._purge_stale_world_roots()
            self.state = "playing"
            self.session_id += 1
            self.scheduler.clear()
            self.enemy_wave = 1
            self.mission_stage_index = 0
            self.mission_stage_progress = 0.0
            self.mission_completed = False
            self.mission_kill_counter = 0
            self.network_clock = 0.0
            self.network_sequence = 0
            self.network_send_accumulator = 0.0
            self.remote_last_seen_time = {}
            self.server_team_assignments = {}
            self.network_config_broadcast_timer = 0.0

            self.menu_manager.hide_all()
            self.ui_manager.show_hud()
            self.ui_manager.set_interact_prompt("")

            current_cfg = self.graphics_manager.get_current_config()
            self.world = World(
                self.asset_loader,
                mode=self.game_mode,
                mode_id=self.match_settings.mode_id,
                map_id=self.current_map_id,
                graphics_config=current_cfg,
                rng=self.rng,
            )
            self.world.bind_gameplay(self)
            self.graphics_manager.apply_current(world=self.world)
            self._start_ambient_loop()

            selected_skin = self.skin_system.get_selected_skin()
            enforce_lock = self._should_enforce_character_lock(self.match_settings.mode_id if self.match_settings else self.mode_id)
            locked_skin_id = self.progression_manager.get_locked_skin_id() if enforce_lock else None
            if enforce_lock and locked_skin_id and selected_skin.skin_id != locked_skin_id:
                self.skin_system.select_skin(locked_skin_id)
                selected_skin = self.skin_system.get_selected_skin()
            elif enforce_lock:
                self.progression_manager.lock_skin_if_unset(selected_skin.skin_id)
            local_team_id = self._default_team_for_player(self.local_player_id)
            player_spawn = (
                self.world.get_player_spawn_point(team_id=local_team_id)
                if hasattr(self.world, "get_player_spawn_point")
                else self.world.safe_player_spawn
            )
            self.player = Player(
                game_manager=self,
                skin=selected_skin,
                asset_loader=self.asset_loader,
                settings_manager=self.settings_manager,
                position=player_spawn,
                local_controlled=True,
                player_id=self.local_player_id,
                team_id=local_team_id,
            )
            self.players = {self.local_player_id: self.player}
            self.player_teams = {self.local_player_id: local_team_id}
            self.remote_player_states = {}
            self.remote_last_sequence = {}
            self.remote_last_seen_time = {}
            self.camera_controller = CameraController(self.player, self)
            self.camera_controller.update()
            if self.network_bridge.mode == self.network_bridge.MODE_SERVER:
                if self._is_team_mode():
                    self.server_team_assignments[self.local_player_id] = local_team_id
                    self.network_bridge.queue_packet(
                        {
                            "type": "team_assignment",
                            "payload": {"player_id": self.local_player_id, "team_id": local_team_id},
                        }
                    )
                self._queue_match_config_packet()

            if self.mode_id == "free_roam_pve":
                self.quest_system = QuestSystem(self.progression_manager, mode=self.game_mode, notify=self.ui_manager.show_toast)
            else:
                self.quest_system = None
            self._start_runtime_mode()
            self._try_restore_checkpoint_for_mode()
            self.auto_checkpoint_timer = 24.0

            self._set_game_mouse_mode()
        except Exception:
            # Recover to menu instead of crashing the entire app.
            self.cleanup_gameplay()
            self.state = "menu"
            self.menu_manager.show_main_menu()
            self.ui_manager.show_toast("Failed to start gameplay. Returned to menu.")
        finally:
            self.transition_lock = False

    def restart_gameplay(self) -> None:
        if self.transition_lock:
            return
        self.ui_manager.hide_game_over()
        self.start_gameplay()

    def return_to_main_menu(self) -> None:
        self.show_main_menu()

    def show_settings_menu(self, return_state: str = "menu") -> None:
        self.state = "settings"
        self.menu_manager.show_settings_menu(return_state)
        self.ui_manager.hide_hud()
        self.ui_manager.hide_pause_menu()
        self.ui_manager.close_dialogue()
        self._set_menu_mouse_mode()

    def close_settings_menu(self, return_state: str) -> None:
        local_player = self.get_local_player()
        if return_state == "paused" and self.world and local_player and local_player.alive:
            self.state = "paused"
            self.menu_manager.hide_all()
            self.ui_manager.hide_hud()
            self.ui_manager.show_pause_menu()
            self._set_menu_mouse_mode()
            return
        if return_state == "skin_select":
            self.state = "skin_select"
            self.menu_manager.show_skin_menu()
            self._set_menu_mouse_mode()
            return
        if return_state == "mode_select":
            self.show_mode_select()
            return
        if return_state == "multiplayer_mode_select":
            self.show_multiplayer_mode_select()
            return
        self.show_main_menu()

    def apply_graphics_preset(self, preset: str) -> None:
        previous = self.graphics_manager.get_current_config()
        self.graphics_manager.apply_preset(preset, world=self.world)
        if self.world and bool(previous["shadows"]) != bool(self.graphics_manager.get_current_config()["shadows"]):
            self.ui_manager.show_toast("Shadow mode applies on next mission", duration=1.6)

    def refresh_audio_settings(self) -> None:
        self.asset_loader.set_master_volume(self.settings_manager.get_master_volume())

    def reset_mission_progress(self) -> None:
        self.progression_manager.reset_mission_progress()
        self.ui_manager.show_toast("Mission progress reset (operative + skill tree cleared)")
        if self.state == "mode_select":
            self.menu_manager.show_mode_menu()

    def reset_free_roam_progress(self) -> None:
        self.progression_manager.reset_free_roam_progress()
        self.ui_manager.show_toast("Free Roam progress reset (operative + skill tree cleared)")
        if self.state == "mode_select":
            self.menu_manager.show_mode_menu()

    def toggle_pause(self) -> None:
        if self.state == "playing":
            self.state = "paused"
            self.ui_manager.hide_hud()
            self.ui_manager.show_pause_menu()
            self.ui_manager.refresh_skill_tree_panel()
            self._set_menu_mouse_mode()
        elif self.state == "paused":
            self.resume_game()

    def resume_game(self) -> None:
        if self.state != "paused":
            return
        self.state = "playing"
        self.ui_manager.hide_pause_menu()
        self.ui_manager.show_hud()
        self._set_game_mouse_mode()

    # -------------
    # Gameplay Mode
    # -------------
    def _start_runtime_mode(self) -> None:
        if self.mode_id == "mission_pve":
            self._start_mission_mode()
            return
        if self.mode_id == "free_roam_pve":
            self._start_free_roam_mode()
            return
        # Multiplayer foundation mode: networking, player sync, and map/mode scaffolding.
        self.mission_stages = []
        self.current_boss = None
        self.free_roam_enemy_timer = 0.0
        self.ui_manager.show_toast(
            f"{self.match_settings.display_name} map loaded ({self.current_map_id}) - {self.get_multiplayer_connection_mode_label()}"
        )

    def _update_runtime_mode(self) -> None:
        if self.mode_id == "mission_pve":
            self._update_mission_mode()
        elif self.mode_id == "free_roam_pve":
            self._update_free_roam_mode()
        else:
            self._update_multiplayer_prep_mode()

    def _update_multiplayer_prep_mode(self) -> None:
        # Keep local-only prompts disabled for competitive modes.
        self.ui_manager.set_interact_prompt("")

    def _start_mission_mode(self) -> None:
        self.quest_system = None
        self.mission_stages = [
            {"type": "survive", "target": 45, "title": "Survive", "description": "Hold out against the assault"},
            {"type": "eliminate", "target": 22, "title": "Eliminate", "description": "Thin the hostile ranks"},
            {
                "type": "reach",
                "target": 1,
                "title": "Extract",
                "description": "Reach extraction point",
                "location": "extraction_point",
            },
        ]
        self.spawn_wave(self.enemy_wave)
        self._refresh_mission_marker()
        self.ui_manager.show_toast("Mission Started - Jump pads, speed gate, explosive barrels online")

    def _start_free_roam_mode(self) -> None:
        self.mission_stages = []
        self.current_boss = None
        self._spawn_npcs()
        self._spawn_free_roam_collectibles()
        for _ in range(4):
            self._spawn_free_roam_enemy()
        self.free_roam_enemy_timer = 6.0
        self._refresh_story_marker()
        self._update_quest_giver_arrows()
        self.ui_manager.show_toast("Free Roam Started - Explore jump pads, anomalies, and speed gates")

    def spawn_wave(self, wave_index: int) -> None:
        if self.state != "playing" or self.mode_id != "mission_pve":
            return
        local_player = self.get_local_player()
        if not self.world or not local_player:
            return
        is_boss_wave = wave_index > 0 and wave_index % 4 == 0
        enemy_count = min(10, 2 + wave_index + (wave_index // 2))
        if is_boss_wave:
            enemy_count = max(3, enemy_count - 2)
        for _ in range(enemy_count):
            spawn = self.world.get_random_spawn_point(local_player.world_position, min_distance=15.0)
            self.enemies.append(Enemy(self, spawn, behavior_mode="mission"))
        if is_boss_wave:
            spawn = self.world.get_random_spawn_point(local_player.world_position, min_distance=24.0)
            boss_tier = max(1, wave_index // 4)
            boss = Enemy(self, spawn, behavior_mode="mission", variant="brute", is_boss=True, boss_tier=boss_tier)
            self.current_boss = boss
            self.enemies.append(boss)
            self.ui_manager.show_toast(f"Boss Wave {wave_index}: {boss.display_name}")

    def _spawn_wave_if_current_session(self, wave_index: int, session_id: int) -> None:
        if session_id != self.session_id:
            return
        self.spawn_wave(wave_index)

    def _spawn_free_roam_enemy(self) -> None:
        if self.mode_id != "free_roam_pve":
            return
        local_player = self.get_local_player()
        if not self.world or not local_player:
            return
        spawn = self.world.get_random_spawn_point(local_player.world_position, min_distance=22.0)
        self.enemies.append(Enemy(self, spawn, behavior_mode="free_roam"))

    def _spawn_npcs(self) -> None:
        self.npcs = []
        for npc_data in self.world.npc_spawns:
            self.npcs.append(
                NPC(
                    game_manager=self,
                    npc_id=npc_data["npc_id"],
                    display_name=npc_data["display_name"],
                    role=npc_data["role"],
                    position=npc_data["position"],
                )
            )

    def _spawn_free_roam_collectibles(self) -> None:
        for position, item_type in self.world.get_collectible_spawns():
            jitter = Vec3(self.rng.uniform(-0.35, 0.35), 0, self.rng.uniform(-0.35, 0.35))
            spawn_pos = position + jitter
            self.pickups.append(BasePickup(self, spawn_pos, kind="item", amount=1, item_type=item_type))

    # --------------------
    # Event/Reward Handling
    # --------------------
    def on_enemy_killed(self, enemy: Enemy, coin_reward: int) -> None:
        if enemy in self.enemies:
            self.enemies.remove(enemy)
        if enemy == self.current_boss:
            self.current_boss = None
            self.progression_manager.add_boss_kill(1)
            if self.challenge_manager:
                self.challenge_manager.on_boss_killed(1)
            self.ui_manager.show_toast("Boss Eliminated!")

        self._spawn_coin_pickups(enemy.world_position + Vec3(0, 0.9, 0), coin_reward)
        self._try_spawn_weapon_drop(enemy)
        self._try_spawn_perk_drop(enemy)
        if self.challenge_manager:
            self.challenge_manager.on_enemy_killed(1)

        if self.mode_id == "mission_pve":
            self.mission_kill_counter += 1
            stage = self._get_current_mission_stage()
            if stage and stage["type"] == "eliminate":
                self.mission_stage_progress += 1

            if self.state == "playing" and len(self.enemies) == 0 and not self.mission_completed:
                self.enemy_wave += 1
                self.progression_manager.set_mission_best_wave(self.enemy_wave)
                self.ui_manager.show_toast(f"Wave {self.enemy_wave}")
                self.scheduler.schedule(
                    1.1,
                    self._spawn_wave_if_current_session,
                    self.enemy_wave,
                    self.session_id,
                    session_id=self.session_id,
                )
        else:
            if self.quest_system:
                self.quest_system.on_enemy_killed(1)

    def _spawn_coin_pickups(self, position, total_amount: int) -> None:
        pieces = max(1, min(4, total_amount // 5))
        remaining = total_amount
        for i in range(pieces):
            split = remaining // (pieces - i)
            remaining -= split
            offset = Vec3(
                self.rng.uniform(-0.45, 0.45),
                self.rng.uniform(0.0, 0.3),
                self.rng.uniform(-0.45, 0.45),
            )
            self.pickups.append(BasePickup(self, position + offset, kind="coin", amount=max(1, split)))

    def collect_coin(self, amount: int, collector: Optional[Player] = None) -> None:
        collector_player = collector if collector and getattr(collector, "alive", False) else self.get_local_player()
        if not collector_player or not collector_player.alive:
            return
        final_amount = max(1, int(amount))
        if hasattr(collector_player, "get_coin_multiplier"):
            final_amount = max(1, int(round(final_amount * collector_player.get_coin_multiplier())))
        # Economy is still local-profile based until multiplayer account state is introduced.
        if str(getattr(collector_player, "player_id", "")) != self.local_player_id:
            return
        self.progression_manager.add_coins(final_amount)
        if self.challenge_manager:
            self.challenge_manager.on_coin_collected(final_amount)
        if final_amount >= 3:
            self.ui_manager.show_toast(f"+{final_amount} coins", duration=0.8)

    def collect_item(self, item_type: str, amount: int, collector: Optional[Player] = None) -> None:
        collector_player = collector if collector and getattr(collector, "alive", False) else self.get_local_player()
        is_local_collector = bool(collector_player and str(getattr(collector_player, "player_id", "")) == self.local_player_id)
        if self.quest_system and is_local_collector:
            self.quest_system.on_item_collected(item_type, amount)
        if is_local_collector:
            self.ui_manager.show_toast(f"Collected {item_type.replace('_', ' ')}")
        if self.world:
            candidates = [p for p, p_type in self.world.get_collectible_spawns() if p_type == item_type]
            if candidates:
                respawn_pos = self.rng.choice(candidates) + Vec3(
                    self.rng.uniform(-0.5, 0.5),
                    0,
                    self.rng.uniform(-0.5, 0.5),
                )
                self.scheduler.schedule(
                    8.0,
                    self._spawn_collectible_pickup,
                    respawn_pos,
                    item_type,
                    self.session_id,
                    session_id=self.session_id,
                )

    def _spawn_collectible_pickup(self, position, item_type: str, session_id: int = None) -> None:
        if session_id is not None and session_id != self.session_id:
            return
        if self.state != "playing" or self.mode_id != "free_roam_pve":
            return
        self.pickups.append(BasePickup(self, position, kind="item", amount=1, item_type=item_type))

    def _try_spawn_weapon_drop(self, enemy: Enemy) -> None:
        if not enemy or self.state != "playing":
            return
        base_chance = 0.17 if self.mode_id == "mission_pve" else 0.21
        if self.mode_id == "mission_pve":
            base_chance += min(0.1, max(0.0, (self.enemy_wave - 1) * 0.013))
        if enemy.variant == "brute":
            base_chance += 0.08
        elif enemy.variant == "stalker":
            base_chance += 0.03
        if getattr(enemy, "is_boss", False):
            base_chance += 0.35

        if self.rng.random() > min(0.6, base_chance):
            return
        rarity = self._roll_weapon_rarity()
        pool = getattr(enemy, "drop_weapon_pool", ("rifle", "pistol", "shotgun"))
        weapon_id = self.rng.choice(tuple(pool))
        attachment_ids = roll_attachments(weapon_id, rarity, rng=self.rng)
        if getattr(enemy, "is_boss", False):
            extra_pool = [attachment_id for attachment_id, cfg in ATTACHMENT_LIBRARY.items() if weapon_id in cfg["weapon_types"]]
            self.rng.shuffle(extra_pool)
            for attachment_id in extra_pool:
                if attachment_id not in attachment_ids:
                    attachment_ids.append(attachment_id)
                if len(attachment_ids) >= 3:
                    break
        drop_pos = enemy.world_position + Vec3(0, 0.7, 0)
        self.pickups.append(
            BasePickup(
                self,
                drop_pos,
                kind="weapon",
                item_type=weapon_id,
                rarity=rarity,
                attachment_ids=attachment_ids,
            )
        )

    def _roll_weapon_rarity(self) -> str:
        weights = {
            "common": 58,
            "uncommon": 24,
            "rare": 11,
            "epic": 5,
            "legendary": 2,
        }
        if self.mode_id == "mission_pve":
            weights["rare"] += min(12, self.enemy_wave)
            weights["epic"] += max(0, self.enemy_wave - 4) // 2
            weights["legendary"] += max(0, self.enemy_wave - 7) // 3
        else:
            story_index = self.progression_manager.get_story_index()
            weights["rare"] += min(8, story_index * 2)
            weights["epic"] += max(0, story_index - 1)
            weights["legendary"] += max(0, story_index - 2)

        roll_table = []
        for rarity in RARITY_ORDER:
            roll_table.extend([rarity] * max(1, int(weights[rarity])))
        return self.rng.choice(roll_table) if roll_table else "common"

    def _try_spawn_perk_drop(self, enemy: Enemy) -> None:
        if not enemy or self.state != "playing":
            return
        chance = 0.09
        if self.mode_id == "mission_pve":
            chance += min(0.08, self.enemy_wave * 0.01)
        if getattr(enemy, "is_boss", False):
            chance += 0.5
        if self.rng.random() > min(0.75, chance):
            return
        perk_pool = ["lifesteal", "ricochet", "haste", "fortify"]
        perk_id = self.rng.choice(perk_pool)
        drop_pos = enemy.world_position + Vec3(self.rng.uniform(-0.2, 0.2), 0.85, self.rng.uniform(-0.2, 0.2))
        self.pickups.append(BasePickup(self, drop_pos, kind="perk", perk_id=perk_id))

    def collect_weapon(self, weapon_id: str, rarity: str, attachments=None, collector: Optional[Player] = None) -> None:
        collector_player = collector if collector and getattr(collector, "alive", False) else self.get_local_player()
        if not collector_player or not collector_player.alive:
            return
        result = collector_player.acquire_weapon_drop(weapon_id, rarity, attachments=attachments)
        is_local_collector = str(getattr(collector_player, "player_id", "")) == self.local_player_id
        if result and is_local_collector:
            self.ui_manager.show_toast(result, duration=1.4)
        if self.challenge_manager and is_local_collector:
            self.challenge_manager.on_weapon_pickup(1)
        if is_local_collector:
            for attachment_id in attachments or []:
                self.progression_manager.unlock_attachment(attachment_id)
            self.asset_loader.play_sound("ui_click", volume=0.14, pitch=self.rng.uniform(0.95, 1.05))

    def collect_perk(self, perk_id: str, collector: Optional[Player] = None) -> None:
        collector_player = collector if collector and getattr(collector, "alive", False) else self.get_local_player()
        if not collector_player or not collector_player.alive:
            return
        collector_player.add_perk(perk_id)
        if str(getattr(collector_player, "player_id", "")) == self.local_player_id:
            self.asset_loader.play_sound("ui_click", volume=0.16, pitch=self.rng.uniform(1.02, 1.12))

    def select_inventory_weapon(self, slot_index: int) -> None:
        local_player = self.get_local_player()
        if self.state != "playing" or not local_player:
            return
        local_player.switch_weapon(slot_index)

    def buy_upgrade(self, upgrade_id: str) -> None:
        self.ui_manager.show_toast("Use Skill Tree (T) for upgrades")

    def buy_ability_upgrade(self, ability_id: str) -> None:
        self.ui_manager.show_toast("Use Skill Tree (T) for upgrades")

    def get_skill_tree_skin_id(self) -> str:
        match_settings = getattr(self, "match_settings", None)
        if match_settings and match_settings.is_multiplayer:
            local_player = self.get_local_player()
            if local_player and hasattr(local_player, "skin"):
                return local_player.skin.skin_id
            return self.skin_system.get_selected_skin().skin_id
        locked_skin = self.progression_manager.get_locked_skin_id()
        if locked_skin:
            return locked_skin
        return self.skin_system.get_selected_skin().skin_id

    def get_skill_tree_nodes(self):
        match_settings = getattr(self, "match_settings", None)
        if match_settings and match_settings.is_multiplayer:
            return []
        skin_id = self.get_skill_tree_skin_id()
        return self.progression_manager.get_skill_tree_nodes(skin_id)

    def get_unlocked_skill_ids(self):
        match_settings = getattr(self, "match_settings", None)
        if match_settings and match_settings.is_multiplayer:
            return set()
        skin_id = self.get_skill_tree_skin_id()
        return set(self.progression_manager.get_unlocked_skill_ids(skin_id))

    def unlock_skill_node(self, node_id: str) -> None:
        match_settings = getattr(self, "match_settings", None)
        if match_settings and match_settings.is_multiplayer:
            self.ui_manager.show_toast("Skill tree disabled in multiplayer", duration=1.4)
            return
        skin_id = self.get_skill_tree_skin_id()
        if skin_id not in SKILL_NODE_MAPS:
            self.ui_manager.show_toast("Skill tree unavailable")
            return
        unlocked, message = self.progression_manager.unlock_skill(skin_id, node_id)
        self.ui_manager.show_toast(message)
        local_player = self.get_local_player()
        if unlocked and local_player and local_player.alive and local_player.skin.skin_id == skin_id:
            local_player.refresh_skill_tree_bonuses()
        self.ui_manager.refresh_skill_tree_panel()

    def on_weapon_fired(self, shake_amount: float) -> None:
        if self.camera_controller:
            self.camera_controller.add_shake(shake_amount)

    def on_player_hit_enemy(self, _enemy, _point) -> None:
        pass

    def on_player_died(self) -> None:
        if self.state != "playing":
            return
        self.state = "game_over"
        self._set_menu_mouse_mode()
        mode_text = self.match_settings.display_name if self.match_settings else ("Free Roam" if self.game_mode == "free_roam" else "Mission")
        if self.mode_id == "mission_pve":
            wave_text = f"Wave {self.enemy_wave}"
        elif self.mode_id == "free_roam_pve":
            wave_text = f"Coins {self.progression_manager.get_coins()}"
        else:
            wave_text = f"Map {self.current_map_id}"
        self.ui_manager.show_game_over("MISSION FAILED", f"{mode_text} - {wave_text}")

    def on_mission_complete(self) -> None:
        self.state = "game_over"
        self._set_menu_mouse_mode()
        self.progression_manager.set_mission_best_wave(self.enemy_wave)
        if self.challenge_manager:
            self.challenge_manager.on_mission_completed(1)
        self.ui_manager.show_game_over("MISSION COMPLETE", f"Waves survived: {self.enemy_wave}")

    # ----------------
    # Dialogue / Quest
    # ----------------
    def try_interact(self) -> None:
        local_player = self.get_local_player()
        if self.ui_manager.inventory_open:
            return
        if self.focused_weapon_pickup and self.focused_weapon_pickup in self.pickups:
            self.focused_weapon_pickup.collect(collector=local_player)
            self.focused_weapon_pickup = None
            return
        if self.mode_id != "free_roam_pve" or not local_player or not local_player.alive:
            return
        npc = self._get_nearest_npc(max_distance=3.1)
        if not npc:
            return
        if not self.quest_system:
            return

        dialogue = self.quest_system.build_dialogue_for_npc(npc.npc_id, npc.display_name)
        self.current_dialogue_npc = npc
        self.state = "dialogue"
        self._set_menu_mouse_mode()
        self.ui_manager.show_dialogue(dialogue, self.on_dialogue_action)
        self.ui_manager.set_interact_prompt("")
        self.ui_manager.hide_hud()

    def on_dialogue_action(self, action_id: str) -> None:
        if action_id:
            result = self.quest_system.handle_dialogue_action(action_id) if self.quest_system else ""
            if result:
                self.ui_manager.show_toast(result)
        self.close_dialogue()
        self._refresh_story_marker()

    def close_dialogue(self) -> None:
        if self.state != "dialogue":
            return
        self.current_dialogue_npc = None
        self.state = "playing"
        self.ui_manager.close_dialogue()
        self.ui_manager.show_hud()
        self._set_game_mouse_mode()

    # -------------------
    # Profiles/Checkpoints
    # -------------------
    def get_profile_label(self) -> str:
        return self.progression_manager.get_active_profile_id().replace("slot_", "PROFILE ")

    def cycle_profile(self, direction: int) -> None:
        profile_ids = self.progression_manager.list_profiles()
        current = self.progression_manager.get_active_profile_id()
        if current not in profile_ids:
            current = profile_ids[0]
        index = profile_ids.index(current)
        index = (index + (1 if direction >= 0 else -1)) % len(profile_ids)
        selected = profile_ids[index]
        self.progression_manager.set_active_profile(selected)
        self.challenge_manager = ChallengeManager(self.progression_manager, notify=self.ui_manager.show_toast)
        self.ui_manager.show_toast(f"Active {self.get_profile_label()}")

    def _supports_checkpoints(self) -> bool:
        return self.mode_id in ("mission_pve", "free_roam_pve")

    def save_checkpoint(self, silent: bool = False) -> None:
        if not self._supports_checkpoints():
            return
        local_player = self.get_local_player()
        if self.state != "playing" or not local_player or not local_player.alive:
            return
        payload = {
            "game_mode": self.game_mode,
            "mode_id": self.mode_id,
            "map_id": self.current_map_id,
            "player": local_player.export_runtime_state(),
            "enemy_wave": int(self.enemy_wave),
            "mission_stage_index": int(self.mission_stage_index),
            "mission_stage_progress": float(self.mission_stage_progress),
            "mission_completed": bool(self.mission_completed),
            "mission_kill_counter": int(self.mission_kill_counter),
        }
        self.progression_manager.save_checkpoint(self.game_mode, payload)
        if not silent:
            self.ui_manager.show_toast("Checkpoint Saved")

    def load_checkpoint(self) -> None:
        if not self._supports_checkpoints():
            self.ui_manager.show_toast("Checkpoints are disabled for this mode")
            return
        local_player = self.get_local_player()
        if self.state != "playing" or not local_player or not self.world:
            self.ui_manager.show_toast("Start a game before loading checkpoint")
            return
        payload = self.progression_manager.load_checkpoint(self.game_mode)
        if not payload:
            self.ui_manager.show_toast("No checkpoint for this mode")
            return
        try:
            self._restore_from_checkpoint_payload(payload)
            self.ui_manager.show_toast("Checkpoint Loaded")
        except Exception:
            self.progression_manager.clear_checkpoint(self.game_mode)
            self.ui_manager.show_toast("Checkpoint reset due to invalid save data")

    def _try_restore_checkpoint_for_mode(self) -> None:
        if not self._supports_checkpoints():
            return
        # Free Roam starts fresh by default; use F9 for manual restore.
        if self.mode_id == "free_roam_pve":
            return
        payload = self.progression_manager.load_checkpoint(self.game_mode)
        if not payload:
            return
        # Auto-resume if checkpoint data matches current selected mode.
        if payload.get("game_mode") != self.game_mode:
            return
        payload_mode_id = str(payload.get("mode_id", ""))
        if payload_mode_id and payload_mode_id != self.mode_id:
            return
        try:
            self._restore_from_checkpoint_payload(payload)
            self.ui_manager.show_toast("Checkpoint Restored")
        except Exception:
            self.progression_manager.clear_checkpoint(self.game_mode)
            self.ui_manager.show_toast("Checkpoint reset due to invalid save data")

    def _restore_from_checkpoint_payload(self, payload: dict) -> None:
        local_player = self.get_local_player()
        if not payload or not local_player:
            return
        self.enemy_wave = max(1, int(payload.get("enemy_wave", self.enemy_wave)))
        self.mission_stage_index = max(0, int(payload.get("mission_stage_index", self.mission_stage_index)))
        self.mission_stage_progress = max(0.0, float(payload.get("mission_stage_progress", self.mission_stage_progress)))
        self.mission_completed = bool(payload.get("mission_completed", False))
        self.mission_kill_counter = max(0, int(payload.get("mission_kill_counter", self.mission_kill_counter)))
        local_player.restore_runtime_state(payload.get("player", {}))

        for enemy in list(self.enemies):
            if enemy:
                destroy(enemy)
        self.enemies = []
        self.current_boss = None
        if self.mode_id == "mission_pve":
            self.spawn_wave(self.enemy_wave)
            self._refresh_mission_marker()
        else:
            for _ in range(4):
                self._spawn_free_roam_enemy()

    # ------
    # Update
    # ------
    def update(self) -> None:
        self.frame_dt = self.sim_clock.begin_frame(time.dt)
        self.dt = self.frame_dt
        self.fixed_dt = self.sim_clock.fixed_dt
        self.simulation_steps = self.sim_clock.consume_steps()
        self.sim_dt = self.fixed_dt * self.simulation_steps
        self.network_clock += self.frame_dt
        self.settings_manager.update()
        self.progression_manager.update()

        self.menu_manager.update()
        self._pump_network()
        local_player = self.get_local_player()

        if self.state == "playing" and self.sim_dt > 0:
            self.scheduler.update(self.sim_dt, current_session_id=self.session_id)

        # Failsafe: if we somehow end up paused with no visible pause/skill UI, recover to gameplay.
        if (
            self.state == "paused"
            and local_player
            and local_player.alive
            and not self.ui_manager.is_skill_tree_open()
            and not self.ui_manager.pause_menu.enabled
            and not self.ui_manager.dialogue_panel.enabled
        ):
            self.state = "playing"
            self.ui_manager.show_hud()
            self._set_game_mouse_mode()

        if self.state == "playing" and self.world:
            self.world.update()

        if self.state == "playing":
            if self.ui_manager.map_open and (not hasattr(self.ui_manager, "map_overlay") or not self.ui_manager.map_overlay.enabled):
                self.ui_manager._set_map_visibility(False)
            if self.ui_manager.inventory_open and (
                not hasattr(self.ui_manager, "inventory_panel") or not self.ui_manager.inventory_panel.enabled
            ):
                self.ui_manager._set_inventory_visibility(False)

        if self.state in ("playing", "paused") and local_player:
            self.ui_manager.update_hud(local_player)

        if self.state == "playing" and self.camera_controller:
            self.camera_controller.update()

        if self.state == "playing":
            self._update_runtime_mode()
            self._update_weapon_pickup_prompt()
            self.auto_checkpoint_timer -= self.sim_dt
            if self.auto_checkpoint_timer <= 0:
                self.auto_checkpoint_timer = 24.0
                self.save_checkpoint(silent=True)

    def _update_weapon_pickup_prompt(self) -> None:
        self.focused_weapon_pickup = None
        local_player = self.get_local_player()
        if not local_player or not local_player.alive or not self.world:
            return
        if self.ui_manager.map_open or self.ui_manager.inventory_open:
            return

        world_root = self.world.root if self.world and self.world.root else scene
        hit = raycast(
            camera.world_position,
            camera.forward,
            distance=4.8,
            ignore=[local_player],
            traverse_target=world_root,
        )
        if not hit.hit:
            if self.mode_id != "free_roam_pve":
                self.ui_manager.set_interact_prompt("")
            return

        entity = hit.entity
        resolved = None
        depth = 0
        while entity is not None and depth < 6:
            if entity in self.pickups and hasattr(entity, "is_weapon_pickup"):
                resolved = entity
                break
            entity = getattr(entity, "parent", None)
            depth += 1
        if not resolved or not resolved.is_weapon_pickup():
            if self.mode_id != "free_roam_pve":
                self.ui_manager.set_interact_prompt("")
            return

        self.focused_weapon_pickup = resolved
        prompt = f"[E] Pick Up {resolved.get_display_name()}"
        self.ui_manager.set_interact_prompt(prompt)

    def _update_mission_mode(self) -> None:
        stage = self._get_current_mission_stage()
        local_player = self.get_local_player()
        if not stage or self.mission_completed or not local_player:
            return

        if stage["type"] == "survive":
            self.mission_stage_progress += self.sim_dt
            if self.mission_stage_progress >= stage["target"]:
                self._advance_mission_stage()
        elif stage["type"] == "eliminate":
            if self.mission_stage_progress >= stage["target"]:
                self._advance_mission_stage()
        elif stage["type"] == "reach":
            location_name = stage.get("location", "")
            location_pos = self.world.get_location_position(location_name) if self.world else None
            if location_pos and (local_player.world_position - location_pos).length() <= 3.2:
                self._advance_mission_stage()

    def _update_free_roam_mode(self) -> None:
        local_player = self.get_local_player()
        if not local_player or not local_player.alive or not self.world:
            return
        self._update_npc_interaction_prompt()

        if self.quest_system:
            self.quest_system.update(self.sim_dt, local_player.world_position, self.world)

        self.free_roam_enemy_timer -= self.sim_dt
        max_enemies = 6
        if self.free_roam_enemy_timer <= 0 and len(self.enemies) < max_enemies:
            self._spawn_free_roam_enemy()
            self.free_roam_enemy_timer = self.rng.uniform(5.5, 8.0)

        self._refresh_story_marker()
        self._update_quest_giver_arrows()

    def _update_npc_interaction_prompt(self) -> None:
        closest = self._get_nearest_npc(max_distance=3.1)
        for npc in self.npcs:
            npc.set_highlight(npc == closest)
        if closest and self.state == "playing":
            self.ui_manager.set_interact_prompt(closest.get_prompt_text())
        else:
            self.ui_manager.set_interact_prompt("")

    def _get_nearest_npc(self, max_distance: float):
        local_player = self.get_local_player()
        if not local_player:
            return None
        nearest = None
        nearest_dist = max_distance
        for npc in self.npcs:
            d = (npc.world_position - local_player.world_position).length()
            if d <= nearest_dist:
                nearest = npc
                nearest_dist = d
        return nearest

    def _get_npc_position(self, npc_id: str):
        for npc in self.npcs:
            if npc.npc_id == npc_id:
                return npc.world_position
        return None

    def _get_current_mission_stage(self):
        if self.mission_stage_index >= len(self.mission_stages):
            return None
        return self.mission_stages[self.mission_stage_index]

    def _advance_mission_stage(self) -> None:
        stage = self._get_current_mission_stage()
        if stage:
            self.ui_manager.show_toast(f"Objective Complete: {stage['title']}")
        self.mission_stage_index += 1
        self.mission_stage_progress = 0.0
        self._refresh_mission_marker()
        if self.mission_stage_index >= len(self.mission_stages):
            self.mission_completed = True
            self.on_mission_complete()

    def _refresh_mission_marker(self) -> None:
        stage = self._get_current_mission_stage()
        if not stage or not self.world:
            if self.world:
                self.world.set_objective_marker(None)
            return
        if stage["type"] == "reach":
            pos = self.world.get_location_position(stage.get("location", ""))
            self.world.set_objective_marker(pos, marker_color=color.rgba(120, 225, 255, 125))
        else:
            self.world.set_objective_marker(None)

    def _refresh_story_marker(self) -> None:
        if self.mode_id != "free_roam_pve" or not self.world or not self.quest_system:
            return
        story = self.quest_system.get_current_story()
        if not story:
            self.world.set_objective_marker(None)
            return
        target_pos = None
        if self.quest_system.story_objective_complete:
            target_pos = self._get_npc_position(story.giver_npc)
        elif not self.quest_system.story_active:
            target_pos = self._get_npc_position(story.giver_npc)
        elif story.objective_type == "reach" and story.location_name:
            target_pos = self.world.get_location_position(story.location_name)
        elif story.objective_type == "collect" and story.item_type == "data_core":
            target_pos = self.world.get_location_position("old_district")
        elif story.objective_type == "eliminate":
            target_pos = self.world.get_location_position("mission_board")
        self.world.set_objective_marker(target_pos, marker_color=color.rgba(112, 240, 188, 120))

    def _update_quest_giver_arrows(self) -> None:
        if self.mode_id != "free_roam_pve" or not self.quest_system:
            for npc in self.npcs:
                npc.set_quest_arrow(False)
            return

        target_npc_ids = set()
        story = self.quest_system.get_current_story()
        if story and (self.quest_system.story_objective_complete or not self.quest_system.story_active):
            target_npc_ids.add(story.giver_npc)

        for quest in self.quest_system.active_side_quests.values():
            if quest.get("completed"):
                giver = quest["template"].giver_npc
                target_npc_ids.add(giver)

        for npc in self.npcs:
            npc.set_quest_arrow(npc.npc_id in target_npc_ids)

    def get_objective_lines(self):
        if self.mode_id == "mission_pve":
            biome = self.world.get_biome_theme().upper() if self.world and hasattr(self.world, "get_biome_theme") else "DEFAULT"
            lines = [f"Wave {self.enemy_wave} - Hostiles {len(self.enemies)} - {biome}"]
            if self.current_boss and not self.current_boss.dead:
                lines.append(f"Boss: {self.current_boss.display_name} ({int(max(0, self.current_boss.health))}/{int(self.current_boss.max_health)})")
            stage = self._get_current_mission_stage()
            if stage:
                if stage["type"] == "survive":
                    remaining = max(0, int(stage["target"] - self.mission_stage_progress))
                    lines.append(f"{stage['description']} ({remaining}s)")
                elif stage["type"] == "eliminate":
                    lines.append(f"{stage['description']} ({int(self.mission_stage_progress)}/{stage['target']})")
                elif stage["type"] == "reach":
                    lines.append(stage["description"])
            lines.append("Use jump pads, speed gates, and explosive barrels")
            if self.challenge_manager:
                lines.extend(self.challenge_manager.get_tracker_lines())
            return lines

        if self.mode_id == "free_roam_pve":
            biome = self.world.get_biome_theme().upper() if self.world and hasattr(self.world, "get_biome_theme") else "DEFAULT"
            lines = [f"Roaming Hostiles {len(self.enemies)} - {biome}"]
            if self.quest_system:
                lines.extend(self.quest_system.get_tracker_lines())
            lines.append("Explore jump pads, anomaly zones, and speed gates")
            if self.challenge_manager:
                lines.extend(self.challenge_manager.get_tracker_lines())
            return lines

        lines = [
            f"{self.match_settings.display_name}",
            f"Map: {self.current_map_id}",
            f"Lobby size: {int(self.match_settings.max_players)}",
            f"Players connected: {max(1, len(self.get_active_players(alive_only=False)))}",
            f"Network: {self.get_multiplayer_connection_mode_label()} ({self.get_multiplayer_endpoint_label()})",
        ]
        if self.challenge_manager:
            lines.extend(self.challenge_manager.get_tracker_lines())
        return lines

    def get_active_quest_giver_positions(self):
        positions = []
        if self.mode_id != "free_roam_pve" or not self.quest_system:
            return positions

        target_npc_ids = set()
        story = self.quest_system.get_current_story()
        if story and (self.quest_system.story_objective_complete or not self.quest_system.story_active):
            target_npc_ids.add(story.giver_npc)

        for quest in self.quest_system.active_side_quests.values():
            if quest.get("completed"):
                target_npc_ids.add(quest["template"].giver_npc)

        for npc in self.npcs:
            if npc.npc_id in target_npc_ids:
                positions.append(Vec3(npc.world_position))
        return positions

    def get_local_player(self):
        return self.players.get(self.local_player_id, self.player)

    def iter_known_player_states(self):
        local = self.get_local_player()
        if local:
            yield self.local_player_id, local
        for player_id, state in self.remote_player_states.items():
            yield player_id, state

    def get_active_players(self, alive_only: bool = True):
        result = []
        for player in self.players.values():
            if not player:
                continue
            if alive_only and not getattr(player, "alive", False):
                continue
            result.append(player)
        return result

    def _default_team_for_player(self, player_id: str) -> str:
        pid = str(player_id or "")
        if self.match_settings and self.match_settings.supports_teams:
            if pid == self.local_player_id:
                return "team_a" if self.multiplayer_connection_mode == "host" else ""
            return ""
        if self.match_settings and self.match_settings.is_multiplayer:
            return pid
        return "solo" if pid == self.local_player_id else ""

    def register_player(self, player_id: str, player: Player, team_id: str = "") -> None:
        if not player_id or not player:
            return
        pid = str(player_id)
        self.players[pid] = player
        assigned_team = str(team_id or "").strip()
        if not assigned_team:
            assigned_team = self._default_team_for_player(pid)
        if assigned_team:
            self.player_teams[pid] = assigned_team
        elif pid in self.player_teams:
            del self.player_teams[pid]
        player.team_id = assigned_team
        if hasattr(player, "_apply_team_visual"):
            player._apply_team_visual()

    def unregister_player(self, player_id: str) -> None:
        pid = str(player_id)
        if pid in self.players:
            del self.players[pid]
        if pid in self.player_teams:
            del self.player_teams[pid]

    def assign_player_team(self, player_id: str, team_id: str) -> None:
        pid = str(player_id)
        if pid not in self.players:
            return
        normalized_team = str(team_id or "")
        if normalized_team:
            self.player_teams[pid] = normalized_team
        elif pid in self.player_teams:
            del self.player_teams[pid]
        player = self.players.get(pid)
        if player is not None:
            player.team_id = normalized_team
            if hasattr(player, "_apply_team_visual"):
                player._apply_team_visual()

    def get_pickup_collectors(self):
        if self.match_settings and self.match_settings.is_multiplayer:
            local = self.get_local_player()
            return [local] if local and getattr(local, "alive", False) else []
        return self.get_active_players(alive_only=True)

    def get_enemy_target_for(self, enemy) -> Optional[Player]:
        candidates = []
        enemy_team = str(getattr(enemy, "team_id", "") or "")
        for player in self.get_active_players(alive_only=True):
            if hasattr(player, "is_detectable") and not player.is_detectable():
                continue
            player_team = str(getattr(player, "team_id", "") or self.player_teams.get(player.player_id, ""))
            if enemy_team and player_team and enemy_team == player_team:
                continue
            candidates.append(player)
        if not candidates:
            return None
        if not enemy:
            return candidates[0]
        nearest = candidates[0]
        nearest_distance = (nearest.world_position - enemy.world_position).length()
        for player in candidates[1:]:
            d = (player.world_position - enemy.world_position).length()
            if d < nearest_distance:
                nearest = player
                nearest_distance = d
        return nearest

    def _remove_remote_player_entity(self, player_id: str) -> None:
        pid = str(player_id or "")
        if not pid or pid == self.local_player_id:
            return
        entity = self.players.get(pid)
        if entity:
            if hasattr(entity, "destroy"):
                entity.destroy()
            else:
                destroy(entity)
        self.unregister_player(pid)
        if pid in self.remote_player_states:
            del self.remote_player_states[pid]
        if pid in self.remote_last_sequence:
            del self.remote_last_sequence[pid]
        if pid in self.remote_last_seen_time:
            del self.remote_last_seen_time[pid]
        if pid in self.server_team_assignments:
            del self.server_team_assignments[pid]

    def _clear_remote_players(self) -> None:
        for pid in list(self.players.keys()):
            if pid == self.local_player_id:
                continue
            self._remove_remote_player_entity(pid)

    def _spawn_remote_player_from_state(self, remote_state: PlayerSyncState) -> None:
        remote_player_id = str(remote_state.player_id or "")
        if not remote_player_id or remote_player_id == self.local_player_id:
            return
        if remote_player_id in self.players:
            return
        if not self.world:
            return
        max_players = int(self.match_settings.max_players) if self.match_settings else 128
        if len(self.players) >= max(2, max_players):
            return
        skin_id = str(remote_state.skin_id or "striker")
        remote_skin = self.skin_system.get_skin(skin_id)
        remote_team = str(remote_state.team_id or self.player_teams.get(remote_player_id, ""))
        if not remote_team:
            remote_team = self._default_team_for_player(remote_player_id)
        remote_player = Player(
            game_manager=self,
            skin=remote_skin,
            asset_loader=self.asset_loader,
            settings_manager=self.settings_manager,
            position=Vec3(remote_state.position.x, remote_state.position.y, remote_state.position.z),
            local_controlled=False,
            player_id=remote_player_id,
            team_id=remote_team,
        )
        self.register_player(remote_player_id, remote_player, team_id=remote_team)
        remote_player.apply_network_state(remote_state)
        self.remote_last_seen_time[remote_player_id] = float(self.network_clock)

    def _choose_least_populated_team(self) -> str:
        counts = {"team_a": 0, "team_b": 0}
        for team_id in self.player_teams.values():
            team_key = str(team_id or "").lower()
            if team_key in counts:
                counts[team_key] += 1
        if counts["team_a"] <= counts["team_b"]:
            return "team_a"
        return "team_b"

    def _assign_server_team_for_player(self, player_id: str) -> str:
        pid = str(player_id or "")
        if not pid:
            return ""
        if pid in self.server_team_assignments:
            return self.server_team_assignments[pid]
        if not self._is_team_mode():
            self.server_team_assignments[pid] = pid
            return pid
        assigned = self._choose_least_populated_team()
        self.server_team_assignments[pid] = assigned
        return assigned

    def _build_match_config_payload(self) -> dict:
        if not self.match_settings:
            return {}
        payload = {
            "mode_id": str(self.match_settings.mode_id),
            "map_id": str(self.current_map_id),
            "team_size": int(self.match_settings.team_size),
            "max_players": int(self.match_settings.max_players),
            "seed": int(self.match_seed),
        }
        return payload

    def _queue_match_config_packet(self) -> None:
        if not self.network_bridge.is_active:
            return
        if self.network_bridge.mode != self.network_bridge.MODE_SERVER:
            return
        if not self.match_settings or not self.match_settings.is_multiplayer:
            return
        payload = self._build_match_config_payload()
        if not payload:
            return
        self.network_match_config = dict(payload)
        self.network_match_config_received_at = float(self.network_clock)
        self.network_bridge.queue_packet({"type": "match_config", "payload": payload})

    def _handle_match_config_packet(self, payload: dict) -> None:
        if self.network_bridge.mode != self.network_bridge.MODE_CLIENT:
            return
        if not isinstance(payload, dict):
            return
        mode = self.mode_registry.resolve_mode(str(payload.get("mode_id", self.mode_id)))
        if not mode.is_multiplayer:
            return

        requested_map_id = str(payload.get("map_id", "") or "")
        map_id = self.map_registry.select_map_for_mode(mode, self.rng, preferred_map_id=requested_map_id or mode.default_map_id)

        team_size = self.mode_registry.choose_team_size(mode, payload.get("team_size", 1))
        try:
            requested_max_players = int(payload.get("max_players", mode.max_players))
        except (TypeError, ValueError):
            requested_max_players = int(mode.max_players)
        max_players = max(int(mode.min_players), min(int(mode.max_players), requested_max_players))
        if mode.supports_teams:
            max_players = max(int(mode.min_players), min(max_players, team_size * 2))

        seed_value: Optional[int] = None
        try:
            incoming_seed = payload.get("seed")
            if incoming_seed is not None:
                seed_value = int(incoming_seed)
        except (TypeError, ValueError):
            seed_value = None

        normalized = {
            "mode_id": mode.mode_id,
            "map_id": map_id,
            "team_size": int(team_size),
            "max_players": int(max_players),
            "seed": int(seed_value) if seed_value is not None else int(self.match_seed),
        }
        changed = normalized != self.network_match_config
        self.network_match_config = normalized
        self.network_match_config_received_at = float(self.network_clock)

        self.mode_id = mode.mode_id
        self.preferred_map_id = map_id
        self.requested_team_size = int(team_size) if mode.supports_teams else None
        self.requested_max_players = int(max_players)
        if seed_value is not None:
            self.forced_match_seed = int(seed_value)

        if changed and self.state in ("mode_select", "skin_select"):
            self.ui_manager.show_toast(f"Host match: {mode.display_name} on {map_id}", duration=2.0)
            if self.state == "mode_select":
                self.menu_manager.show_mode_menu()
            elif self.state == "skin_select":
                self.menu_manager.show_skin_menu()

    def _handle_team_assignment_packet(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            return
        player_id = str(payload.get("player_id", ""))
        team_id = str(payload.get("team_id", ""))
        if not player_id or not team_id:
            return
        self.player_teams[player_id] = team_id
        self.assign_player_team(player_id, team_id)
        if player_id == self.local_player_id:
            local_player = self.get_local_player()
            if local_player:
                local_player.team_id = team_id
                if hasattr(local_player, "_apply_team_visual"):
                    local_player._apply_team_visual()
                if self.state == "playing" and self.world and self._is_team_mode():
                    spawn = self.world.get_player_spawn_point(team_id=team_id)
                    local_player.position = spawn
                    if hasattr(local_player, "_stabilize_spawn"):
                        local_player._stabilize_spawn()

    def _prune_stale_remote_players(self) -> None:
        if not self.remote_last_seen_time:
            return
        cutoff = float(self.network_clock) - float(self.remote_state_timeout)
        stale_ids = [pid for pid, stamp in self.remote_last_seen_time.items() if float(stamp) < cutoff]
        for pid in stale_ids:
            self._remove_remote_player_entity(pid)

    def _display_network_error_if_needed(self) -> None:
        network_error = str(getattr(self.network_bridge, "last_error", "") or "").strip()
        if not network_error:
            return
        if network_error == self.network_last_error_displayed:
            return
        self.network_last_error_displayed = network_error
        self.ui_manager.show_toast(network_error, duration=2.2)

    # -----
    # Input
    # -----
    def input(self, key: str) -> None:
        if key == "escape":
            if self.ui_manager.is_skill_tree_open():
                self.ui_manager.close_skill_tree_panel()
                if self.state == "playing":
                    self._set_game_mouse_mode()
                else:
                    self._set_menu_mouse_mode()
                return
            if self.ui_manager.map_open:
                self.ui_manager.toggle_tactical_map()
                return
            if self.ui_manager.inventory_open:
                self.ui_manager.toggle_inventory()
                self._set_game_mouse_mode()
                return
            if self.state == "dialogue":
                self.close_dialogue()
                return
            if self.state == "playing":
                self.toggle_pause()
                return
            if self.state == "paused":
                self.resume_game()
                return
            if self.state in ("menu", "mode_select", "multiplayer_mode_select", "skin_select", "settings", "game_over"):
                self.show_main_menu()
                return

        if self.state == "dialogue":
            if key == "e":
                self.close_dialogue()
            return

        if self.state == "paused":
            if key == "t":
                if self.match_settings and self.match_settings.is_multiplayer:
                    self.ui_manager.show_toast("Skill tree disabled in multiplayer", duration=1.2)
                    return
                if self.ui_manager.is_skill_tree_open():
                    self.ui_manager.close_skill_tree_panel()
                else:
                    self.ui_manager.open_skill_tree_panel()
                if self.state == "playing":
                    self._set_game_mouse_mode()
                else:
                    self._set_menu_mouse_mode()
            return

        local_player = self.get_local_player()
        if self.state == "playing" and local_player:
            if key == "f5":
                if self.match_settings and self.match_settings.is_multiplayer:
                    self.ui_manager.show_toast("Checkpoints disabled in multiplayer", duration=1.2)
                    return
                self.save_checkpoint(silent=False)
                return
            if key == "f9":
                if self.match_settings and self.match_settings.is_multiplayer:
                    self.ui_manager.show_toast("Checkpoints disabled in multiplayer", duration=1.2)
                    return
                self.load_checkpoint()
                return
            if key == "t":
                if self.match_settings and self.match_settings.is_multiplayer:
                    self.ui_manager.show_toast("Skill tree disabled in multiplayer", duration=1.2)
                    return
                if self.ui_manager.is_skill_tree_open():
                    self.ui_manager.close_skill_tree_panel()
                    self._set_game_mouse_mode()
                else:
                    self.ui_manager.open_skill_tree_panel()
                    self._set_menu_mouse_mode()
                return
            if key == "i":
                self.ui_manager.toggle_inventory()
                if self.ui_manager.inventory_open:
                    self._set_menu_mouse_mode()
                else:
                    self._set_game_mouse_mode()
                return
            if self.ui_manager.map_open and key not in ("m", "escape"):
                return
            if key == "v" and self.camera_controller:
                self.camera_controller.toggle_mode()
            elif key == "m":
                self.ui_manager.toggle_tactical_map()
                if self.ui_manager.map_open:
                    self._set_game_mouse_mode()
            elif key == "e":
                self.try_interact()
            elif key == "u":
                self.toggle_pause()
            if key == "left mouse down" and self.ui_manager.is_mouse_over_skill_tree():
                return
            if key == "left mouse down" and self.ui_manager.is_mouse_over_inventory():
                return
            local_player.handle_input(key)

    # ----------
    # Networking
    # ----------
    def start_network_server(self, host: str = "127.0.0.1", port: int = 7777) -> bool:
        try:
            resolved_port = int(port)
        except (TypeError, ValueError):
            resolved_port = 7777
        self.multiplayer_host = str(host)
        self.multiplayer_port = resolved_port
        max_clients = 8
        if self.match_settings and self.match_settings.is_multiplayer:
            max_clients = max(2, min(128, int(self.match_settings.max_players)))
        started = self.network_bridge.start_server(host=host, port=resolved_port, max_clients=max_clients)
        self.network_last_error_displayed = ""
        if started:
            self.ui_manager.show_toast(f"Server listening on {host}:{resolved_port} ({max_clients} slots)")
        else:
            details = getattr(self.network_bridge, "last_error", "")
            self.ui_manager.show_toast(f"Server failed to start{': ' + details if details else ''}")
        return started

    def start_network_client(self, host: str = "127.0.0.1", port: int = 7777) -> bool:
        try:
            resolved_port = int(port)
        except (TypeError, ValueError):
            resolved_port = 7777
        self.multiplayer_host = str(host)
        self.multiplayer_port = resolved_port
        started = self.network_bridge.start_client(host=host, port=resolved_port)
        self.network_last_error_displayed = ""
        if started:
            self.ui_manager.show_toast(f"Connecting to {host}:{resolved_port}")
        else:
            details = getattr(self.network_bridge, "last_error", "")
            self.ui_manager.show_toast(f"Client connection failed{': ' + details if details else ''}")
        return started

    def stop_network(self) -> None:
        self.network_bridge.stop()
        self._clear_remote_players()
        self.remote_player_states = {}
        self.remote_last_sequence = {}
        self.remote_last_seen_time = {}
        self.server_team_assignments = {}
        self.network_match_config = {}
        self.network_match_config_received_at = -1.0
        self.network_config_broadcast_timer = 0.0
        self.network_last_error_displayed = ""

    def _pump_network(self) -> None:
        if not self.network_bridge.is_active:
            if self.remote_player_states or any(pid != self.local_player_id for pid in self.players.keys()):
                self._clear_remote_players()
                self.remote_player_states = {}
                self.remote_last_sequence = {}
                self.remote_last_seen_time = {}
            self.network_config_broadcast_timer = 0.0
            self._display_network_error_if_needed()
            return

        if (
            self.network_bridge.mode == self.network_bridge.MODE_SERVER
            and self.state == "playing"
            and self.match_settings
            and self.match_settings.is_multiplayer
        ):
            self.network_config_broadcast_timer -= self.frame_dt
            if self.network_config_broadcast_timer <= 0.0:
                self.network_config_broadcast_timer = self.network_config_broadcast_interval
                self._queue_match_config_packet()
        else:
            self.network_config_broadcast_timer = 0.0

        local_player = self.get_local_player()
        if self.state == "playing" and local_player and local_player.alive:
            if not self.network_bridge.connection_ready:
                incoming_packets = self.network_bridge.poll()
                for packet in incoming_packets:
                    self._handle_network_packet(packet)
                self._display_network_error_if_needed()
                return
            send_interval = 1.0 / max(1.0, float(self.network_send_rate))
            self.network_send_accumulator += self.frame_dt
            sent_this_frame = 0
            max_send_burst = 4
            while self.network_send_accumulator >= send_interval and sent_this_frame < max_send_burst:
                self.network_send_accumulator -= send_interval
                self.network_sequence += 1
                try:
                    player_state = local_player.build_network_state(
                        player_id=self.local_player_id,
                        sequence=self.network_sequence,
                        timestamp=self.network_clock,
                    )
                    self.network_bridge.queue_player_state(player_state)
                except Exception:
                    # Keep simulation stable even if state serialization fails.
                    break
                sent_this_frame += 1
            if self.network_send_accumulator > send_interval * max_send_burst:
                self.network_send_accumulator = send_interval * max_send_burst

        try:
            incoming_packets = self.network_bridge.poll()
        except Exception:
            incoming_packets = []
        for packet in incoming_packets:
            self._handle_network_packet(packet)
        self._prune_stale_remote_players()
        self._display_network_error_if_needed()

    def _handle_network_packet(self, packet: dict) -> None:
        if not isinstance(packet, dict):
            return
        packet_type = str(packet.get("type", ""))
        if packet_type == "net_connected":
            payload = packet.get("payload", {})
            if isinstance(payload, dict):
                host = payload.get("host", self.multiplayer_host)
                port = payload.get("port", self.multiplayer_port)
                self.ui_manager.show_toast(f"Connected to {host}:{port}", duration=1.4)
            return
        if packet_type == "peer_disconnected":
            payload = packet.get("payload", {})
            if isinstance(payload, dict):
                player_id = str(payload.get("player_id", "") or "")
                if player_id:
                    self._remove_remote_player_entity(player_id)
            return
        if packet_type == "match_config":
            self._handle_match_config_packet(packet.get("payload", {}))
            return
        if packet_type == "team_assignment":
            self._handle_team_assignment_packet(packet.get("payload", {}))
            return
        if packet_type != "player_state":
            return
        payload = packet.get("payload", {})
        remote_state = PlayerSyncState.from_dict(payload)
        remote_state = self._sanitize_remote_state(remote_state)
        if not remote_state:
            return
        remote_player_id = str(remote_state.player_id)
        if not remote_player_id:
            return
        if remote_player_id == self.local_player_id:
            return
        if remote_player_id not in self.remote_player_states and len(self.remote_player_states) >= 256:
            return
        last_sequence = int(self.remote_last_sequence.get(remote_player_id, -1))
        if int(remote_state.sequence) <= last_sequence:
            return

        if self.network_bridge.mode == self.network_bridge.MODE_SERVER:
            assigned_team = self._assign_server_team_for_player(remote_player_id)
            if assigned_team:
                remote_state.team_id = assigned_team
                current_team = str(self.player_teams.get(remote_player_id, ""))
                if current_team != assigned_team:
                    self.assign_player_team(remote_player_id, assigned_team)
                    self.network_bridge.queue_packet(
                        {
                            "type": "team_assignment",
                            "payload": {"player_id": remote_player_id, "team_id": assigned_team},
                        }
                    )
            self.network_bridge.queue_packet({"type": "player_state", "payload": remote_state.to_dict()})

        self.remote_last_sequence[remote_player_id] = int(remote_state.sequence)
        self.remote_player_states[remote_player_id] = remote_state
        self.remote_last_seen_time[remote_player_id] = float(self.network_clock)
        incoming_team = str(remote_state.team_id or "")
        if incoming_team:
            self.player_teams[remote_player_id] = incoming_team

        if remote_player_id not in self.players:
            self._spawn_remote_player_from_state(remote_state)

        remote_player_entity = self.players.get(remote_player_id)
        if remote_player_entity and hasattr(remote_player_entity, "apply_network_state"):
            try:
                remote_player_entity.apply_network_state(remote_state)
            except Exception:
                pass

    def _sanitize_remote_state(self, remote_state: Optional[PlayerSyncState]) -> Optional[PlayerSyncState]:
        if not remote_state:
            return None
        player_id = str(getattr(remote_state, "player_id", "") or "").strip()
        if not player_id:
            return None
        if len(player_id) > 48:
            player_id = player_id[:48]
        remote_state.player_id = player_id

        if not math.isfinite(float(remote_state.timestamp)):
            return None
        if not math.isfinite(float(remote_state.sequence)):
            return None
        remote_state.sequence = max(0, min(2_147_483_647, int(remote_state.sequence)))

        pos = remote_state.position
        vel = remote_state.velocity
        coords = [float(pos.x), float(pos.y), float(pos.z), float(vel.x), float(vel.y), float(vel.z)]
        if not all(math.isfinite(v) for v in coords):
            return None

        map_half_extent = 220.0
        if self.world and hasattr(self.world, "get_map_half_extent"):
            try:
                map_half_extent = max(80.0, float(self.world.get_map_half_extent()) * 1.8)
            except Exception:
                map_half_extent = 220.0
        max_height = 420.0
        min_height = -80.0
        if abs(float(pos.x)) > map_half_extent or abs(float(pos.z)) > map_half_extent:
            return None
        if float(pos.y) < min_height or float(pos.y) > max_height:
            return None

        vel_limit = 120.0
        vel.x = max(-vel_limit, min(vel_limit, float(vel.x)))
        vel.y = max(-vel_limit, min(vel_limit, float(vel.y)))
        vel.z = max(-vel_limit, min(vel_limit, float(vel.z)))

        remote_state.rotation_y = float(remote_state.rotation_y) % 360.0
        remote_state.pitch = max(-89.0, min(89.0, float(remote_state.pitch)))
        remote_state.health_max = max(1.0, min(10000.0, float(remote_state.health_max)))
        remote_state.health = max(0.0, min(remote_state.health_max, float(remote_state.health)))
        remote_state.active_weapon_index = max(0, min(8, int(remote_state.active_weapon_index)))
        remote_state.skin_id = str(getattr(remote_state, "skin_id", "striker") or "striker")
        remote_state.team_id = str(getattr(remote_state, "team_id", "") or "")
        remote_state.weapons = list(getattr(remote_state, "weapons", []))[:8]
        return remote_state

    # -------
    # Cleanup
    # -------
    def cleanup_gameplay(self) -> None:
        self.scheduler.clear()
        self.asset_loader.stop_loop("ambient")
        destroyed_players = set()
        players_to_destroy = list(self.players.values())
        if self.player and self.player not in players_to_destroy:
            players_to_destroy.append(self.player)
        for player in players_to_destroy:
            if not player:
                continue
            player_key = id(player)
            if player_key in destroyed_players:
                continue
            destroyed_players.add(player_key)
            if hasattr(player, "destroy"):
                player.destroy()
            else:
                destroy(player)
        self.player = None
        self.players = {}
        self.player_teams = {}
        self.remote_player_states = {}
        self.remote_last_sequence = {}
        self.remote_last_seen_time = {}
        self.server_team_assignments = {}
        self.network_sequence = 0
        self.network_send_accumulator = 0.0
        for enemy in list(self.enemies):
            if enemy:
                destroy(enemy)
        self.enemies = []

        for npc in list(self.npcs):
            if npc:
                destroy(npc)
        self.npcs = []

        for pickup in list(self.pickups):
            if pickup:
                destroy(pickup)
        self.pickups = []

        if self.world:
            self.world.destroy()
            self.world = None
        self._purge_stale_world_roots()

        self.camera_controller = None
        self.quest_system = None
        self.current_dialogue_npc = None
        self.focused_weapon_pickup = None
        self.current_boss = None
        self.ui_manager.hide_hud()
        self.ui_manager.hide_pause_menu()
        self.ui_manager.hide_game_over()
        self.ui_manager.close_dialogue()
        self.ui_manager.set_interact_prompt("")
        if self.ui_manager.map_open:
            self.ui_manager.toggle_tactical_map()
        camera.position = (0, 4, -14)
        camera.rotation = (10, 0, 0)

    def quit_game(self) -> None:
        self.shutdown()
        application.quit()

    def shutdown(self) -> None:
        if self._shutdown_in_progress:
            return
        self._shutdown_in_progress = True
        self.stop_network()
        self.settings_manager.flush_pending()
        self.progression_manager.flush_pending()

    def _set_menu_mouse_mode(self) -> None:
        mouse.locked = False
        mouse.visible = True

    def _set_game_mouse_mode(self) -> None:
        mouse.locked = True
        mouse.visible = False

    def _start_ambient_loop(self) -> None:
        biome = self.world.get_biome_theme() if self.world and hasattr(self.world, "get_biome_theme") else ""
        if self.game_mode == "mission":
            sound_name = f"ambient_mission_{biome}" if biome else "ambient_mission"
        else:
            sound_name = f"ambient_roam_{biome}" if biome else "ambient_roam"
        # Fall back to a generic ambient file if specific loop is missing.
        started = self.asset_loader.start_loop("ambient", sound_name, volume=0.18)
        if not started:
            started = self.asset_loader.start_loop("ambient", "ambient_mission" if self.game_mode == "mission" else "ambient_roam", volume=0.18)
        if not started:
            self.asset_loader.start_loop("ambient", "ambient", volume=0.18)
