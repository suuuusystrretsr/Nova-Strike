from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from typing import Callable

from .models import GameConfig
from .service import LoaderService


class RoundedActionButton(tk.Canvas):
    def __init__(
        self,
        parent,
        text: str,
        command: Callable[[], None] | None = None,
        *,
        bg: str,
        hover_bg: str,
        disabled_bg: str,
        text_color: str = "#ffffff",
        disabled_text_color: str = "#94a3b8",
        pressed_bg: str | None = None,
        radius: int = 12,
        height: int = 42,
        font=None,
    ) -> None:
        super().__init__(
            parent,
            height=height,
            highlightthickness=0,
            bd=0,
            relief="flat",
            cursor="hand2",
            bg=str(getattr(parent, "cget", lambda _k: "#000000")("bg")),
        )
        self._text = str(text or "")
        self._command = command
        self._bg = bg
        self._hover_bg = hover_bg
        self._disabled_bg = disabled_bg
        self._pressed_bg = pressed_bg if pressed_bg else hover_bg
        self._text_color = text_color
        self._disabled_text_color = disabled_text_color
        self._radius = max(2, int(radius))
        self._font = font
        self._enabled = True
        self._hovered = False
        self._pressed = False

        self.bind("<Configure>", self._on_resize)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._redraw()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        self.configure(cursor="hand2" if self._enabled else "arrow")
        self._redraw()

    def set_text(self, text: str) -> None:
        self._text = str(text or "")
        self._redraw()

    def _on_resize(self, _event=None) -> None:
        self._redraw()

    def _on_enter(self, _event=None) -> None:
        self._hovered = True
        self._redraw()

    def _on_leave(self, _event=None) -> None:
        self._hovered = False
        self._pressed = False
        self._redraw()

    def _on_press(self, _event=None) -> None:
        if not self._enabled:
            return
        self._pressed = True
        self._redraw()

    def _on_release(self, event=None) -> None:
        if not self._enabled:
            return
        was_pressed = self._pressed
        self._pressed = False
        self._redraw()
        if not was_pressed or not self._command:
            return
        if event is not None:
            x = int(getattr(event, "x", 0))
            y = int(getattr(event, "y", 0))
            if x < 0 or y < 0 or x > self.winfo_width() or y > self.winfo_height():
                return
        self._command()

    def _draw_rounded_rect(self, x1: int, y1: int, x2: int, y2: int, radius: int, fill: str) -> None:
        r = max(1, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
        self.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, outline=fill, fill=fill)
        self.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, outline=fill, fill=fill)
        self.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, outline=fill, fill=fill)
        self.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, outline=fill, fill=fill)
        self.create_rectangle(x1 + r, y1, x2 - r, y2, outline=fill, fill=fill)
        self.create_rectangle(x1, y1 + r, x2, y2 - r, outline=fill, fill=fill)

    def _current_fill(self) -> str:
        if not self._enabled:
            return self._disabled_bg
        if self._pressed:
            return self._pressed_bg
        if self._hovered:
            return self._hover_bg
        return self._bg

    def _current_text_color(self) -> str:
        return self._text_color if self._enabled else self._disabled_text_color

    def _redraw(self) -> None:
        self.delete("all")
        width = max(10, int(self.winfo_width()))
        height = max(10, int(self.winfo_height()))
        self._draw_rounded_rect(1, 1, width - 1, height - 1, self._radius, self._current_fill())
        self.create_text(
            width // 2,
            height // 2,
            text=self._text,
            fill=self._current_text_color(),
            font=self._font,
        )


class LoaderUI:
    BG_DARK = "#0f172a"
    PANEL_BG = "#1e293b"
    PANEL_BG_ALT = "#233449"
    PANEL_BORDER = "#334155"
    OUTPUT_BG = "#0b1220"
    ACCENT_BLUE = "#3b82f6"
    ACCENT_BLUE_HOVER = "#2563eb"
    SUCCESS_GREEN = "#22c55e"
    SUCCESS_GREEN_HOVER = "#16a34a"
    SECONDARY = "#475569"
    SECONDARY_HOVER = "#64748b"
    TEXT_PRIMARY = "#e2e8f0"
    TEXT_SECONDARY = "#cbd5e1"
    TEXT_MUTED = "#94a3b8"
    TEXT_DIM = "#64748b"
    DISABLED_BG = "#334155"
    LIST_SELECT_BG = "#1d4ed8"

    def __init__(self, service: LoaderService) -> None:
        self.service = service
        self.root = tk.Tk()
        self.root.title("Update Studios")
        self.root.geometry("1160x740")
        self.root.minsize(1024, 650)

        self.games: list[GameConfig] = []
        self.selected_game_id = ""
        self.worker: threading.Thread | None = None
        self.event_queue: queue.Queue[tuple[str, tuple]] = queue.Queue()
        self._log_line_limit = 600
        self._busy = False

        self.var_game_name = tk.StringVar(value="No game selected")
        self.var_local_version = tk.StringVar(value="-")
        self.var_latest_version = tk.StringVar(value="-")
        self.var_update_source = tk.StringVar(value="-")
        self.var_status = tk.StringVar(value="Ready")
        self.var_auto_update = tk.BooleanVar(value=True)

        self.action_buttons: list[object] = []
        self.brand_font = tkfont.Font(family="Segoe UI Semibold", size=21)
        self.game_title_font = tkfont.Font(family="Segoe UI Semibold", size=24)
        self.header_font = tkfont.Font(family="Segoe UI Semibold", size=15)
        self.subheader_font = tkfont.Font(family="Segoe UI Semibold", size=12)
        self.body_font = tkfont.Font(family="Segoe UI", size=10)
        self.small_font = tkfont.Font(family="Segoe UI", size=9)
        self.mono_font = tkfont.Font(family="Consolas", size=10)

        self._build_layout()
        self._refresh_games()
        self.root.after(80, self._pump_events)

    def run(self) -> None:
        self.root.mainloop()

    def _build_layout(self) -> None:
        self._configure_ttk_styles()
        self.root.configure(bg=self.BG_DARK)

        main = tk.Frame(self.root, bg=self.BG_DARK, padx=18, pady=18)
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=5)
        main.rowconfigure(0, weight=1)

        left = tk.Frame(main, bg=self.PANEL_BG, highlightthickness=1, highlightbackground=self.PANEL_BORDER, padx=14, pady=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.rowconfigure(2, weight=1)
        left.columnconfigure(0, weight=1)
        tk.Label(left, text="Installed Games", bg=self.PANEL_BG, fg=self.TEXT_PRIMARY, font=self.header_font).grid(row=0, column=0, sticky="w")
        tk.Label(
            left,
            text="Detected from registry and trusted developer packages",
            bg=self.PANEL_BG,
            fg=self.TEXT_MUTED,
            font=self.small_font,
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))

        list_frame = tk.Frame(left, bg=self.OUTPUT_BG, highlightthickness=1, highlightbackground=self.PANEL_BORDER)
        list_frame.grid(row=2, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        self.games_listbox = tk.Listbox(
            list_frame,
            height=20,
            exportselection=False,
            activestyle="none",
            bg=self.OUTPUT_BG,
            fg=self.TEXT_SECONDARY,
            selectbackground=self.LIST_SELECT_BG,
            selectforeground="#ffffff",
            highlightthickness=0,
            bd=0,
            font=self.body_font,
        )
        self.games_listbox.grid(row=0, column=0, sticky="nsew")
        self.games_listbox.bind("<<ListboxSelect>>", self._on_game_selected)
        scrollbar = tk.Scrollbar(
            list_frame,
            orient=tk.VERTICAL,
            command=self.games_listbox.yview,
            bg=self.SECONDARY,
            activebackground=self.SECONDARY_HOVER,
            troughcolor=self.BG_DARK,
            relief="flat",
            bd=0,
            highlightthickness=0,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.games_listbox.configure(yscrollcommand=scrollbar.set)

        left_actions = tk.Frame(left, bg=self.PANEL_BG)
        left_actions.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        left_actions.columnconfigure(0, weight=1)
        left_actions.columnconfigure(1, weight=1)
        refresh_btn = self._create_button(
            left_actions,
            text="Refresh",
            kind="secondary",
            command=self._refresh_games,
        )
        refresh_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        drop_btn = self._create_button(
            left_actions,
            text="Open Drop Folder",
            kind="secondary",
            command=self._open_drop_folder,
        )
        drop_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.action_buttons.extend([refresh_btn, drop_btn])

        right = tk.Frame(main, bg=self.PANEL_BG, highlightthickness=1, highlightbackground=self.PANEL_BORDER, padx=16, pady=16)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)

        header = tk.Frame(right, bg=self.PANEL_BG)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        tk.Label(header, text="Update Studios", bg=self.PANEL_BG, fg=self.TEXT_PRIMARY, font=self.brand_font).grid(row=0, column=0, sticky="w")
        tk.Label(
            header,
            text="Launcher and update manager",
            bg=self.PANEL_BG,
            fg=self.TEXT_MUTED,
            font=self.small_font,
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        details = tk.Frame(
            right,
            bg=self.PANEL_BG_ALT,
            highlightthickness=1,
            highlightbackground=self.PANEL_BORDER,
            padx=14,
            pady=12,
        )
        details.grid(row=1, column=0, sticky="ew", pady=(12, 8))
        details.columnconfigure(1, weight=1)
        tk.Label(details, text="Selected Game", bg=self.PANEL_BG_ALT, fg=self.TEXT_MUTED, font=self.small_font).grid(row=0, column=0, sticky="w")
        tk.Label(details, textvariable=self.var_game_name, bg=self.PANEL_BG_ALT, fg=self.TEXT_PRIMARY, font=self.game_title_font).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(2, 10),
        )
        tk.Label(details, text="Local Version", bg=self.PANEL_BG_ALT, fg=self.TEXT_MUTED, font=self.small_font).grid(row=2, column=0, sticky="w")
        tk.Label(details, textvariable=self.var_local_version, bg=self.PANEL_BG_ALT, fg=self.TEXT_SECONDARY, font=self.subheader_font).grid(
            row=2,
            column=1,
            sticky="w",
        )
        tk.Label(details, text="Latest Version", bg=self.PANEL_BG_ALT, fg=self.TEXT_MUTED, font=self.small_font).grid(row=3, column=0, sticky="w", pady=(4, 0))
        tk.Label(details, textvariable=self.var_latest_version, bg=self.PANEL_BG_ALT, fg=self.TEXT_SECONDARY, font=self.subheader_font).grid(
            row=3,
            column=1,
            sticky="w",
            pady=(4, 0),
        )
        tk.Label(details, text="Update Source", bg=self.PANEL_BG_ALT, fg=self.TEXT_MUTED, font=self.small_font).grid(row=4, column=0, sticky="nw", pady=(6, 0))
        tk.Label(
            details,
            textvariable=self.var_update_source,
            bg=self.PANEL_BG_ALT,
            fg=self.TEXT_DIM,
            font=self.small_font,
            justify=tk.LEFT,
            wraplength=520,
        ).grid(row=4, column=1, sticky="w", pady=(6, 0))

        status_card = tk.Frame(right, bg=self.PANEL_BG)
        status_card.grid(row=2, column=0, sticky="ew", pady=(2, 8))
        status_card.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(status_card, orient=tk.HORIZONTAL, mode="determinate", maximum=100, style="Dark.Horizontal.TProgressbar")
        self.progress.grid(row=0, column=0, sticky="ew")
        tk.Label(status_card, textvariable=self.var_status, bg=self.PANEL_BG, fg=self.TEXT_MUTED, font=self.body_font).grid(
            row=1,
            column=0,
            sticky="w",
            pady=(6, 0),
        )

        self.output_tabs = ttk.Notebook(right, style="Dark.TNotebook")
        self.output_tabs.grid(row=3, column=0, sticky="nsew", pady=(2, 0))

        log_tab = tk.Frame(self.output_tabs, bg=self.OUTPUT_BG)
        notes_tab = tk.Frame(self.output_tabs, bg=self.OUTPUT_BG)
        log_tab.rowconfigure(0, weight=1)
        log_tab.columnconfigure(0, weight=1)
        notes_tab.rowconfigure(0, weight=1)
        notes_tab.columnconfigure(0, weight=1)
        self.output_tabs.add(log_tab, text="Activity Log")
        self.output_tabs.add(notes_tab, text="Patch Notes")

        self.log_text = tk.Text(
            log_tab,
            height=12,
            wrap=tk.WORD,
            bg=self.OUTPUT_BG,
            fg=self.TEXT_SECONDARY,
            insertbackground=self.TEXT_SECONDARY,
            relief="flat",
            bd=0,
            padx=10,
            pady=10,
            font=self.mono_font,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.configure(state=tk.DISABLED)

        self.notes_text = tk.Text(
            notes_tab,
            height=12,
            wrap=tk.WORD,
            bg=self.OUTPUT_BG,
            fg=self.TEXT_SECONDARY,
            insertbackground=self.TEXT_SECONDARY,
            relief="flat",
            bd=0,
            padx=12,
            pady=12,
            font=self.body_font,
        )
        self.notes_text.grid(row=0, column=0, sticky="nsew")
        self.notes_text.configure(state=tk.DISABLED)

        actions = tk.Frame(right, bg=self.PANEL_BG)
        actions.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        for index in range(4):
            actions.columnconfigure(index, weight=1)

        update_btn = self._create_button(actions, text="Check Update", kind="update", command=self._check_update_clicked)
        update_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        launch_btn = self._create_button(actions, text="Launch Game", kind="launch", command=self._launch_clicked)
        launch_btn.grid(row=0, column=1, sticky="ew", padx=6)
        open_install_btn = self._create_button(actions, text="Open Install Folder", kind="secondary", command=self._open_install_folder)
        open_install_btn.grid(row=0, column=2, sticky="ew", padx=6)
        open_loader_btn = self._create_button(actions, text="Open Loader Folder", kind="secondary", command=self._open_loader_folder)
        open_loader_btn.grid(row=0, column=3, sticky="ew", padx=(6, 0))
        self.action_buttons.extend([update_btn, launch_btn, open_install_btn, open_loader_btn])

        self.auto_update_check = ttk.Checkbutton(
            actions,
            text="Auto-update before launch",
            variable=self.var_auto_update,
            style="Dark.TCheckbutton",
        )
        self.auto_update_check.grid(row=1, column=0, columnspan=4, sticky="w", pady=(10, 0))
        self._bind_hover_cursor(self.auto_update_check)
        self._set_patch_notes(
            "Patch Notes\n\nSelect a game to view details.\n\nActivity and update results will appear here.",
            append=False,
        )

    def _configure_ttk_styles(self) -> None:
        style = ttk.Style(self.root)
        themes = style.theme_names()
        if "clam" in themes:
            style.theme_use("clam")
        elif "vista" in themes:
            style.theme_use("vista")

        style.configure(
            "Dark.Horizontal.TProgressbar",
            troughcolor=self.OUTPUT_BG,
            background=self.ACCENT_BLUE,
            bordercolor=self.PANEL_BG,
            lightcolor=self.ACCENT_BLUE,
            darkcolor=self.ACCENT_BLUE,
            thickness=10,
        )
        style.configure(
            "Dark.TCheckbutton",
            background=self.PANEL_BG,
            foreground=self.TEXT_SECONDARY,
            font=self.body_font,
        )
        style.map(
            "Dark.TCheckbutton",
            background=[("active", self.PANEL_BG)],
            foreground=[("disabled", self.TEXT_DIM), ("active", self.TEXT_PRIMARY)],
        )
        style.configure("Dark.TNotebook", background=self.PANEL_BG, borderwidth=0)
        style.configure(
            "Dark.TNotebook.Tab",
            background=self.SECONDARY,
            foreground=self.TEXT_MUTED,
            padding=(14, 8),
            font=self.small_font,
        )
        style.map(
            "Dark.TNotebook.Tab",
            background=[("selected", self.PANEL_BG_ALT), ("active", self.SECONDARY_HOVER)],
            foreground=[("selected", self.TEXT_PRIMARY), ("active", "#f8fafc")],
        )

    def _create_button(self, parent, text: str, kind: str, command: Callable[[], None]) -> RoundedActionButton:
        palette = {
            "launch": (self.ACCENT_BLUE, self.ACCENT_BLUE_HOVER),
            "update": (self.SUCCESS_GREEN, self.SUCCESS_GREEN_HOVER),
            "secondary": (self.SECONDARY, self.SECONDARY_HOVER),
        }
        normal_bg, hover_bg = palette.get(kind, palette["secondary"])
        button = RoundedActionButton(
            parent,
            text=text,
            command=command,
            bg=normal_bg,
            hover_bg=hover_bg,
            disabled_bg=self.DISABLED_BG,
            text_color="#ffffff",
            pressed_bg=hover_bg,
            font=self.body_font,
            radius=12,
            height=42,
        )
        self._bind_hover_cursor(button)
        return button

    def _refresh_games(self) -> None:
        games, report = self.service.refresh_games()
        self.games = games
        self.games_listbox.delete(0, tk.END)
        for game in games:
            self.games_listbox.insert(tk.END, game.display_name)
        if games:
            self.games_listbox.selection_set(0)
            self.games_listbox.activate(0)
            self._on_game_selected()
        else:
            self._update_details(None)

        for msg in report.messages:
            self._append_log(msg)
        if report.rejected:
            self._set_status(f"{report.rejected} package(s) rejected. Check studio_drop/rejected.", 1.0)
        elif report.imported:
            self._set_status(f"{report.imported} package(s) imported.", 1.0)
        else:
            self._set_status("Ready", 1.0)

    def _on_game_selected(self, _event=None) -> None:
        index = self._selected_index()
        if index is None or index >= len(self.games):
            self._update_details(None)
            return
        game = self.games[index]
        self.selected_game_id = game.game_id
        self._update_details(game)

    def _selected_index(self) -> int | None:
        selected = self.games_listbox.curselection()
        if not selected:
            return None
        return int(selected[0])

    def _selected_game(self) -> GameConfig | None:
        index = self._selected_index()
        if index is None or index >= len(self.games):
            return None
        return self.games[index]

    def _update_details(self, game: GameConfig | None) -> None:
        if not game:
            self.selected_game_id = ""
            self.var_game_name.set("No game selected")
            self.var_local_version.set("-")
            self.var_latest_version.set("-")
            self.var_update_source.set("-")
            self._set_patch_notes(
                "Patch Notes\n\nSelect a game to view details.\n\nActivity and update results will appear here.",
                append=False,
            )
            return
        self.var_game_name.set(game.display_name)
        self.var_local_version.set(game.local_version)
        self.var_latest_version.set("-")
        self.var_update_source.set(game.update_source)
        self._set_patch_notes(self._build_notes_for_game(game), append=False)

    def _build_notes_for_game(self, game: GameConfig) -> str:
        description = str(game.description or "").strip()
        if not description:
            description = "No published patch notes in metadata yet."
        return (
            f"{game.display_name}\n\n"
            f"Local Version: {game.local_version}\n"
            f"Latest Version: {self.var_latest_version.get()}\n\n"
            f"Update Source:\n{game.update_source}\n\n"
            f"Developer Notes:\n{description}\n\n"
            "Quick Update Steps:\n"
            "1. Click Check Update.\n"
            "2. If available, Launch Game with Auto-update enabled.\n"
            "3. Loader applies update first, then starts the game."
        )

    def _check_update_clicked(self) -> None:
        game = self._selected_game()
        if not game:
            messagebox.showinfo("Update Studios", "Select a game first.")
            return
        self._run_worker(lambda: self._task_check_update(game.game_id))

    def _launch_clicked(self) -> None:
        game = self._selected_game()
        if not game:
            messagebox.showinfo("Update Studios", "Select a game first.")
            return
        auto_update = bool(self.var_auto_update.get())
        self._run_worker(lambda: self._task_launch(game.game_id, auto_update))

    def _task_check_update(self, game_id: str) -> None:
        self._post_status("Checking for updates...", 0.05)
        result = self.service.check_for_update(game_id)
        self._post_latest_version(result.latest_version)
        self._post_log(result.message)
        self._post_notes(
            f"Update Check Result\n\n{result.message}\n\nLatest Available Version: {result.latest_version or '-'}",
            append=True,
        )
        self._post_status(result.message, 1.0)

    def _task_launch(self, game_id: str, auto_update: bool) -> None:
        def progress(message: str, pct: float) -> None:
            self._post_status(message, pct)
            self._post_log(message)

        message = self.service.launch_game(game_id, auto_update=auto_update, progress=progress)
        self._post_log(message)
        self._post_status(message, 1.0)
        self._post_refresh()

    def _run_worker(self, fn) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Update Studios", "Please wait for the current task to finish.")
            return

        def runner() -> None:
            try:
                fn()
            except Exception as exc:
                self.event_queue.put(("error", (str(exc),)))
            finally:
                self.event_queue.put(("task_done", tuple()))

        self._set_busy(True)
        self.worker = threading.Thread(target=runner, daemon=True)
        self.worker.start()

    def _pump_events(self) -> None:
        try:
            while True:
                event, payload = self.event_queue.get_nowait()
                if event == "status":
                    self._set_status(*payload)
                elif event == "log":
                    self._append_log(*payload)
                elif event == "notes":
                    self._set_patch_notes(*payload)
                elif event == "error":
                    self._append_log(f"Error: {payload[0]}")
                    self._set_status(f"Error: {payload[0]}", 1.0)
                    messagebox.showerror("Update Studios", payload[0])
                elif event == "latest":
                    self.var_latest_version.set(payload[0] or "-")
                    game = self._selected_game()
                    if game:
                        self._set_patch_notes(self._build_notes_for_game(game), append=False)
                elif event == "refresh":
                    self._refresh_games()
                elif event == "task_done":
                    self._set_busy(False)
        except queue.Empty:
            pass
        self.root.after(80, self._pump_events)

    def _set_status(self, message: str, pct: float) -> None:
        self.var_status.set(message)
        self.progress["value"] = int(max(0.0, min(1.0, float(pct))) * 100)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        try:
            total_lines = int(self.log_text.index("end-1c").split(".")[0])
        except Exception:
            total_lines = 0
        if total_lines > self._log_line_limit:
            trim_until = max(1, total_lines - self._log_line_limit)
            self.log_text.delete("1.0", f"{trim_until}.0")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _set_patch_notes(self, message: str, append: bool = False) -> None:
        self.notes_text.configure(state=tk.NORMAL)
        if append:
            self.notes_text.insert(tk.END, f"\n\n{message}")
        else:
            self.notes_text.delete("1.0", tk.END)
            self.notes_text.insert(tk.END, message)
        self.notes_text.see("1.0")
        self.notes_text.configure(state=tk.DISABLED)

    def _set_busy(self, busy: bool) -> None:
        self._busy = bool(busy)
        enabled = not self._busy
        for button in self.action_buttons:
            if hasattr(button, "set_enabled"):
                button.set_enabled(enabled)
            else:
                try:
                    button.configure(state=tk.NORMAL if enabled else tk.DISABLED)
                except Exception:
                    pass
        self.games_listbox.configure(state=tk.NORMAL if enabled else tk.DISABLED)
        self.auto_update_check.configure(state=tk.NORMAL if enabled else tk.DISABLED)
        try:
            self.root.configure(cursor="watch" if self._busy else "")
            self.root.update_idletasks()
        except Exception:
            pass

    def _bind_hover_cursor(self, widget) -> None:
        widget.bind("<Enter>", lambda _evt: self.root.configure(cursor="hand2" if not self._busy else "watch"), add="+")
        widget.bind("<Leave>", lambda _evt: self.root.configure(cursor="watch" if self._busy else ""), add="+")

    def _post_status(self, message: str, pct: float) -> None:
        self.event_queue.put(("status", (message, pct)))

    def _post_log(self, message: str) -> None:
        self.event_queue.put(("log", (message,)))

    def _post_notes(self, message: str, append: bool = False) -> None:
        self.event_queue.put(("notes", (message, append)))

    def _post_latest_version(self, version: str) -> None:
        self.event_queue.put(("latest", (version,)))

    def _post_refresh(self) -> None:
        self.event_queue.put(("refresh", tuple()))

    def _open_drop_folder(self) -> None:
        self._open_path(self.service.paths.incoming_drop_dir)

    def _open_install_folder(self) -> None:
        game = self._selected_game()
        if not game:
            return
        self._open_path(game.install_path())

    def _open_loader_folder(self) -> None:
        self._open_path(self.service.paths.root)

    def _open_path(self, path) -> None:
        target = str(path)
        try:
            os.startfile(target)  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror("Update Studios", f"Could not open folder:\n{target}\n\n{exc}")
