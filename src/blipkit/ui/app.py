"""Blipkit single-window CustomTkinter application."""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
import numpy as np

from blipkit import __version__
from blipkit.core.audition import NoteAuditioner
from blipkit.core.config import AppSettings, data_dir
from blipkit.core.engine_bridge import validate_engine_path
from blipkit.core.export import ExportSnapshot, export_project
from blipkit.core.midi_io import export_song_midi, import_song_midi
from blipkit.core.models import AssetInfo, SFXPatch, Song, Track
from blipkit.core.playback import AudioPlayer
from blipkit.core.project import BlipkitProject
from blipkit.core.sfx_synth import get_preset

from . import tokens as T
from .editor_shortcuts import handle_editor_key
from .library_view import LibraryView
from .sequencer_view import SequencerPlaybackPlan, SequencerView
from .settings_view import SettingsView
from .sfx_view import SFXView
from .widgets import action_button, icon_button, ui_font


class BlipkitApp(ctk.CTk):
    def __init__(self) -> None:
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        super().__init__(fg_color=T.BG)
        self.title("Blipkit")
        self.geometry("1360x840")
        self.minsize(1240, 700)
        self._apply_window_icon()
        if sys.platform == "darwin":
            self.createcommand("tk::mac::Quit", self._close)

        self.settings = AppSettings.load()
        self.project = self._initial_project()
        self.player = AudioPlayer()
        self.audition_player = AudioPlayer()
        self.note_auditioner = NoteAuditioner()
        self.current_song = self._first_song()
        self.current_sfx = self._first_sfx()
        self.current_view = None
        self.current_mode = "music"
        self.last_editor_mode = "music"
        self.dirty = False
        self._sidebar_collapsed = False
        self._playing = False
        self._playback_loading = False
        self._playback_request_id = 0
        self._playback_after_id: str | None = None
        self._music_preview_cache = OrderedDict()
        self._music_stem_cache = OrderedDict()
        self._music_render_results = queue.SimpleQueue()
        self._music_render_active_key: str | None = None
        self._music_render_pending_plan: SequencerPlaybackPlan | None = None
        self._music_render_warm_after_id: str | None = None
        self._music_render_poll_after_id: str | None = None
        self._playback_request = None
        self._mix_update_id = 0
        self._mix_update_request = None
        self._mix_update_results = queue.SimpleQueue()
        self._closing = False
        self._editor_sessions = {}
        self._shared_note_clipboard = []
        self._transport_origin = 0.0
        self._export_running = False
        self._export_events = queue.SimpleQueue()
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._asset_buttons: list[ctk.CTkButton] = []

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build_header()
        self._build_content()
        self._build_status()
        self._bind_shortcuts()
        self.refresh_assets()
        self.show_view("music")
        self._music_render_poll_after_id = self.after(16, self._poll_music_render_results)
        threading.Thread(
            target=self.player.prepare,
            args=(self.project.metadata.sample_rate,),
            name="blipkit-audio-prepare",
            daemon=True,
        ).start()
        threading.Thread(
            target=self.audition_player.prepare,
            args=(self.project.metadata.sample_rate,),
            name="blipkit-audition-prepare",
            daemon=True,
        ).start()
        self.after(self.settings.autosave_seconds * 1000, self._autosave)

    def _apply_window_icon(self) -> None:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
        path = base / "assets" / "icon.png"
        if not path.is_file():
            return
        try:
            self._window_icon = tk.PhotoImage(file=str(path))
            self.iconphoto(True, self._window_icon)
        except tk.TclError:
            self._window_icon = None

    def _initial_project(self) -> BlipkitProject:
        project = None
        if self.settings.last_project:
            path = Path(self.settings.last_project)
            if (path / "project.json").is_file():
                try:
                    project = BlipkitProject.open(path)
                except (OSError, ValueError):
                    pass
        if project is None:
            root = data_dir() / "Projects" / "Starter.bkproj"
            if (root / "project.json").is_file():
                project = BlipkitProject.open(root)
            else:
                project = BlipkitProject.create(root, "Starter", template="RPG")
        project.ensure_showcase_songs()
        self.settings.remember_project(project.path)
        return project

    def _first_song(self) -> Song:
        songs = self.project.load_songs()
        if songs:
            return songs[0][1]
        song = Song(name="bgm_main", tracks=[Track(name="主旋律")])
        self.project.save_song(song)
        return song

    def _first_sfx(self) -> SFXPatch:
        patches = self.project.load_sfx()
        if patches:
            return patches[0][1]
        patch = get_preset("Click")
        self.project.save_sfx(patch)
        return patch

    def _build_header(self) -> None:
        self.header = ctk.CTkFrame(
            self,
            height=T.HEADER_H,
            fg_color=T.NAV_BG,
            corner_radius=0,
        )
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_propagate(False)
        self.header.grid_rowconfigure(0, weight=1)
        self.header.grid_columnconfigure(0, minsize=T.SIDEBAR_W)
        self.header.grid_columnconfigure(2, weight=1)
        self.header_sidebar = ctk.CTkFrame(
            self.header,
            width=T.SIDEBAR_W,
            fg_color="transparent",
            corner_radius=0,
        )
        self.header_sidebar.grid(row=0, column=0, sticky="nsew")
        self.header_sidebar.grid_propagate(False)
        self.header_sidebar.grid_rowconfigure(0, weight=1)
        self.header_sidebar.grid_columnconfigure(0, weight=1)
        self.brand_label = ctk.CTkLabel(
            self.header_sidebar,
            text="BLIPKIT",
            text_color=T.TEXT,
            font=ui_font(17, "bold"),
            anchor="w",
        )
        self.brand_label.grid(row=0, column=0, padx=(20, 0), sticky="w")
        self.sidebar_toggle = icon_button(
            self.header_sidebar,
            "‹",
            self.toggle_sidebar,
        )
        self.sidebar_toggle.grid(row=0, column=1, padx=(0, 8))
        self.header_divider = ctk.CTkFrame(
            self.header,
            width=1,
            fg_color=T.BORDER,
        )
        self.header_divider.grid(row=0, column=1, sticky="ns", pady=16)
        self.project_label = ctk.CTkLabel(
            self.header,
            text=self.project.metadata.name,
            text_color=T.TEXT,
            font=ui_font(16, "bold"),
            anchor="w",
        )
        self.project_label.grid(row=0, column=2, padx=20, sticky="w")

        controls = ctk.CTkFrame(self.header, fg_color="transparent")
        controls.grid(row=0, column=3, padx=(12, 16))
        action_button(controls, "打开", self.open_project, width=64, quiet=True).pack(
            side="left", padx=(0, 4)
        )
        action_button(controls, "新建", self.new_project, width=64, quiet=True).pack(
            side="left", padx=(0, 4)
        )
        action_button(controls, "快照", self.snapshot, width=64, quiet=True).pack(
            side="left", padx=(0, 8)
        )
        action_button(controls, "导出", self.export_all, primary=True, width=72).pack(side="left")
        ctk.CTkFrame(self, height=1, fg_color=T.BORDER_LIGHT).place(
            x=0, rely=0, y=T.HEADER_H - 1, relwidth=1
        )

    def _build_content(self) -> None:
        self.content = ctk.CTkFrame(self, fg_color=T.NAV_BG, corner_radius=0)
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, minsize=T.SIDEBAR_W)
        self.content.grid_columnconfigure(1, weight=1)

        self.sidebar = ctk.CTkFrame(
            self.content,
            width=T.SIDEBAR_W,
            fg_color=T.NAV_BG,
            corner_radius=0,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(3, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)

        self.nav = ctk.CTkFrame(self.sidebar, fg_color="transparent", corner_radius=0)
        self.nav.grid(row=0, column=0, sticky="ew")
        self._build_nav_buttons()

        ctk.CTkFrame(self.sidebar, height=1, fg_color=T.BORDER).grid(
            row=1, column=0, sticky="ew", padx=16, pady=(16, 10)
        )
        self.asset_header = ctk.CTkFrame(
            self.sidebar,
            height=36,
            fg_color="transparent",
            corner_radius=0,
        )
        self.asset_header.grid(row=2, column=0, sticky="ew", padx=16)
        self.asset_header.grid_propagate(False)
        self._build_asset_header()
        self.asset_list = ctk.CTkScrollableFrame(
            self.sidebar,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=T.TEXT_DISABLED,
            scrollbar_button_hover_color=T.TEXT_MUTED,
        )
        self.asset_list.grid(row=3, column=0, sticky="nsew", padx=(10, 7), pady=(0, 6))

        self.workspace_shell = ctk.CTkFrame(
            self.content,
            fg_color=T.NAV_BG,
            corner_radius=0,
        )
        self.workspace_shell.grid(row=0, column=1, sticky="nsew")
        self.workspace = ctk.CTkFrame(
            self.workspace_shell,
            fg_color=T.SURFACE,
            corner_radius=T.RADIUS_PANEL,
            border_width=1,
            border_color=T.BORDER_LIGHT,
        )
        self.workspace.pack(fill="both", expand=True, padx=(0, 8), pady=(0, 8))

    def _build_nav_buttons(self) -> None:
        ctk.CTkLabel(
            self.nav,
            text="工作区",
            text_color=T.TEXT_MUTED,
            font=ui_font(T.TEXT_12),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(16, 8))
        items = (
            ("music", "音乐编排"),
            ("sfx", "音效生成"),
            ("library", "资产管理"),
            ("settings", "工程设置"),
        )
        for key, label in items:
            button = ctk.CTkButton(
                self.nav,
                text=label,
                command=lambda name=key: self.show_view(name),
                anchor="w",
                height=T.NAV_ITEM_H,
                corner_radius=T.RADIUS,
                fg_color="transparent",
                hover_color=T.NAV_ACTIVE,
                text_color=T.TEXT_SECONDARY,
                font=ui_font(T.TEXT_14),
            )
            button.pack(fill="x", padx=16, pady=1)
            self._nav_buttons[key] = button

    def _build_asset_header(self) -> None:
        ctk.CTkLabel(
            self.asset_header,
            text="工程资产",
            text_color=T.TEXT_MUTED,
            font=ui_font(T.TEXT_12),
            anchor="w",
        ).pack(side="left")
        icon_button(self.asset_header, "+", self.new_asset).pack(side="right")

    def _build_status(self) -> None:
        self.status = ctk.CTkFrame(
            self,
            height=T.STATUS_H,
            fg_color=T.NAV_BG,
            corner_radius=0,
        )
        self.status.grid(row=2, column=0, sticky="ew")
        self.status.grid_propagate(False)
        self.status.grid_rowconfigure(0, weight=1)
        self.status.grid_columnconfigure(0, minsize=T.SIDEBAR_W)
        self.status.grid_columnconfigure(2, weight=1)
        self.version_label = ctk.CTkLabel(
            self.status,
            text=f"Blipkit {__version__}",
            text_color=T.TEXT_DISABLED,
            font=ui_font(10, mono=True),
            anchor="w",
        )
        self.version_label.grid(row=0, column=0, padx=20, sticky="w")
        self.status_divider = ctk.CTkFrame(
            self.status,
            width=1,
            fg_color=T.BORDER,
        )
        self.status_divider.grid(row=0, column=1, sticky="ns", pady=10)
        self.status_var = tk.StringVar(value="工程已就绪")
        ctk.CTkLabel(
            self.status,
            textvariable=self.status_var,
            text_color=T.TEXT_MUTED,
            font=ui_font(T.TEXT_12),
            anchor="w",
        ).grid(row=0, column=2, padx=(12, 0), sticky="w")
        self.transport_meta = ctk.CTkLabel(
            self.status,
            text="",
            text_color=T.TEXT_MUTED,
            font=ui_font(T.TEXT_12, mono=True),
            anchor="e",
        )
        self.transport_meta.grid(row=0, column=3, padx=(12, 18))
        self._update_status_meta()

    def toggle_sidebar(self) -> None:
        self._set_sidebar_collapsed(not self._sidebar_collapsed)

    def _set_sidebar_collapsed(self, collapsed: bool) -> None:
        if collapsed == self._sidebar_collapsed:
            return
        self._sidebar_collapsed = collapsed
        if collapsed:
            self.sidebar.grid_remove()
            self.content.grid_columnconfigure(0, minsize=0)
            self.header.grid_columnconfigure(0, minsize=44)
            self.header_sidebar.configure(width=44)
            self.brand_label.grid_remove()
            self.sidebar_toggle.configure(text="☰")
            self.project_label.grid_configure(padx=(16, 20))
            self.workspace.pack_configure(padx=(8, 8))
            self.status.grid_columnconfigure(0, minsize=44)
            self.version_label.grid_remove()
            self.set_status("侧栏已收起")
        else:
            self.sidebar.grid()
            self.content.grid_columnconfigure(0, minsize=T.SIDEBAR_W)
            self.header.grid_columnconfigure(0, minsize=T.SIDEBAR_W)
            self.header_sidebar.configure(width=T.SIDEBAR_W)
            self.brand_label.grid()
            self.sidebar_toggle.configure(text="‹")
            self.project_label.grid_configure(padx=20)
            self.workspace.pack_configure(padx=(0, 8))
            self.status.grid_columnconfigure(0, minsize=T.SIDEBAR_W)
            self.version_label.grid()
            self.set_status("侧栏已展开")
        self.after_idle(self._refresh_workspace_layout)

    def _refresh_workspace_layout(self) -> None:
        if isinstance(self.current_view, SequencerView):
            self.current_view.redraw()
        elif isinstance(self.current_view, SFXView):
            self.current_view.redraw_waveform()

    def _bind_shortcuts(self) -> None:
        modifier = "Command" if sys.platform == "darwin" else "Control"
        self.bind_all("<KeyPress>", self._shortcut_editor)
        for mod in {modifier, "Control"}:
            for key in (
                "a",
                "b",
                "c",
                "d",
                "x",
                "v",
                "z",
                "y",
                "Shift-Z",
                "Shift-z",
                "Shift-A",
                "Shift-a",
            ):
                self.bind_all(f"<{mod}-{key}>", self._shortcut_editor)
            for key, callback in {
                "s": self._shortcut_save,
                "o": self._shortcut_open,
                "n": self._shortcut_new,
                "r": self._shortcut_export,
                "e": self._shortcut_export,
                "i": self._shortcut_import,
                "backslash": self._shortcut_toggle_sidebar,
                "space": self._shortcut_pause,
            }.items():
                self.bind_all(f"<{mod}-{key}>", callback)
        self.bind_all("<space>", self._shortcut_play)
        self.bind_all("<Escape>", self._shortcut_editor)

    def _shortcut_editor(self, event):
        if self._is_text_input(event):
            return None
        if isinstance(self.current_view, SequencerView):
            return handle_editor_key(self.current_view, event)
        # Keep SFX history accessible through the same system shortcuts.
        if event.state & (0x0004 | (0x0008 if sys.platform == "darwin" else 0)):
            key = event.keysym.lower()
            if key == "z":
                return self._shortcut_redo(event) if event.state & 1 else self._shortcut_undo(event)
            if key == "y":
                return self._shortcut_redo(event)
        return None

    def _shortcut_pause(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        if self._playing or self._playback_loading:
            self.stop_playback()
            self.set_status("已暂停 · Ctrl/Cmd + Space 继续")
        else:
            self.toggle_playback()
        return "break"

    @staticmethod
    def _is_text_input(event) -> bool:
        widget = getattr(event, "widget", None)
        if widget is None:
            return False
        try:
            return widget.winfo_class() in {
                "Entry",
                "TEntry",
                "Text",
                "Spinbox",
            }
        except tk.TclError:
            return False

    def _shortcut_save(self, _event=None) -> str:
        self.save_current()
        return "break"

    def _shortcut_toggle_sidebar(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        self.toggle_sidebar()
        return "break"

    def _shortcut_open(self, _event=None) -> str:
        self.open_project()
        return "break"

    def _shortcut_new(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        self.new_project()
        return "break"

    def _shortcut_export(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        self.export_all()
        return "break"

    def _shortcut_import(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        self.import_midi()
        return "break"

    def _shortcut_play(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        self.toggle_playback()
        return "break"

    def _shortcut_delete(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        if hasattr(self.current_view, "delete_selected_note"):
            self.current_view.delete_selected_note()
        return "break"

    def _shortcut_duplicate(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        if hasattr(self.current_view, "duplicate_selected_note"):
            self.current_view.duplicate_selected_note()
        return "break"

    def _shortcut_copy(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        if hasattr(self.current_view, "copy_selected_notes"):
            self.current_view.copy_selected_notes()
        return "break"

    def _shortcut_cut(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        if hasattr(self.current_view, "cut_selected_notes"):
            self.current_view.cut_selected_notes()
        return "break"

    def _shortcut_paste(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        if hasattr(self.current_view, "paste_notes_at_playhead"):
            self.current_view.paste_notes_at_playhead()
        return "break"

    def _shortcut_split(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        if hasattr(self.current_view, "split_selected_at_playhead"):
            self.current_view.split_selected_at_playhead()
        return "break"

    def _shortcut_undo(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        if hasattr(self.current_view, "undo"):
            self.current_view.undo()
        return "break"

    def _shortcut_redo(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        if hasattr(self.current_view, "redo"):
            self.current_view.redo()
        return "break"

    def _shortcut_select_all(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        if hasattr(self.current_view, "select_all_notes"):
            self.current_view.select_all_notes()
            return "break"
        return None

    def _shortcut_deselect_all(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        if hasattr(self.current_view, "clear_note_selection"):
            self.current_view.clear_note_selection()
            return "break"
        return None

    def _shortcut_seek(self, event, *, steps: int):
        if self._is_text_input(event):
            return None
        if isinstance(self.current_view, SequencerView):
            self.current_view.move_playhead(steps)
            return "break"
        return None

    def _shortcut_jump(self, event, *, direction: int):
        if self._is_text_input(event):
            return None
        if isinstance(self.current_view, SequencerView):
            self.current_view.jump_to_adjacent_edit(direction)
            return "break"
        return None

    def _shortcut_edge(self, event, *, end: bool):
        if self._is_text_input(event):
            return None
        if isinstance(self.current_view, SequencerView):
            self.current_view.jump_to_timeline_edge(end)
            return "break"
        return None

    def _shortcut_trim(self, event, *, side: str):
        if self._is_text_input(event):
            return None
        if isinstance(self.current_view, SequencerView):
            self.current_view.trim_selected_to_playhead(side)
            return "break"
        return None

    def _shortcut_move_track(self, event, *, offset: int):
        if self._is_text_input(event):
            return None
        if isinstance(self.current_view, SequencerView):
            self.current_view.move_selected_to_track(offset)
            return "break"
        return None

    def _shortcut_zoom(self, event, amount: int):
        if self._is_text_input(event):
            return None
        if isinstance(self.current_view, SequencerView):
            self.current_view.zoom_horizontal(amount)
            return "break"
        return None

    def _shortcut_editor_view(self, event, value: str):
        if self._is_text_input(event):
            return None
        if isinstance(self.current_view, SequencerView):
            self.current_view.set_editor_view(value)
            return "break"
        return None

    def _shortcut_nudge(
        self,
        event,
        *,
        beats: int = 0,
        pitches: int = 0,
        durations: int = 0,
        velocity: int = 0,
    ):
        if self._is_text_input(event):
            return None
        if isinstance(self.current_view, SequencerView):
            snap = self.current_view._snap_size()
            self.current_view.nudge_selected(
                beats=beats * snap,
                pitches=pitches,
                durations=durations * snap,
                velocity=velocity,
            )
            return "break"
        return None

    def show_view(self, mode: str) -> None:
        if self.current_view is not None and self.dirty:
            self._commit_current_editor()
        self.stop_playback()
        self.note_auditioner.cancel()
        self.audition_player.stop()
        self.current_mode = mode
        if mode in ("music", "sfx"):
            self.last_editor_mode = mode
        for key, button in self._nav_buttons.items():
            active = key == mode
            button.configure(
                fg_color=T.NAV_ACTIVE if active else "transparent",
                text_color=T.TEXT if active else T.TEXT_SECONDARY,
                font=ui_font(T.TEXT_14, "bold" if active else "normal"),
            )
        if isinstance(self.current_view, SequencerView):
            view = self.current_view
            if view.gesture_active:
                view.cancel_gesture()
            self._shared_note_clipboard = view._note_clipboard
            self._editor_sessions[view._session_key] = {
                "undo": view._undo_stack,
                "redo": view._redo_stack,
                "track": view.selected_track_index,
                "selection": set(view.selected_note_ids),
                "primary": view.selected_note_id,
                "cursor": view.insert_beat,
                "view": view.view_var.get(),
                "tool": view.tool_var.get(),
                "snap": view.snap_var.get(),
                "loop": view.loop_var.get(),
                "cell": view.cell_w,
                "arrangement_cell": view.arrangement_cell_w,
            }
        if self.current_view is not None:
            self.current_view.destroy()
        if mode == "music":
            self.current_view = SequencerView(
                self.workspace,
                self.current_song,
                self.mark_dirty,
                self.stop_playback,
                self.set_status,
                self.toggle_playback,
                self.preview_note,
                self.import_midi,
                self.export_midi,
                on_mix_change=self._on_track_mix_change,
            )
        elif mode == "sfx":
            self.current_view = SFXView(
                self.workspace,
                self.current_sfx,
                self._save_sfx,
                self.mark_dirty,
                self.set_status,
                self.stop_playback,
                self.toggle_playback,
            )
        elif mode == "library":
            self.current_view = LibraryView(
                self.workspace,
                self.project.assets(),
                self.open_asset,
                self.export_selected,
            )
        else:
            self.current_view = SettingsView(
                self.workspace,
                self.project.metadata,
                self.project.path,
                self._save_settings,
                self.mark_dirty,
                self.set_status,
            )
        self.current_view.pack(fill="both", expand=True)
        if isinstance(self.current_view, SequencerView):
            view = self.current_view
            view._session_key = (str(self.project.path), view.song.id)
            view._note_clipboard = self._shared_note_clipboard
            session = self._editor_sessions.get(view._session_key)
            if session:
                view._undo_stack, view._redo_stack = session["undo"], session["redo"]
                view.select_track(session["track"])
                view._set_selection(session["selection"], session["primary"])
                view.insert_beat = session["cursor"]
                view.tool_var.set(session["tool"])
                view.snap_var.set(session["snap"])
                view.loop_var.set(session["loop"])
                view.cell_w, view.arrangement_cell_w = session["cell"], session["arrangement_cell"]
                view.set_editor_view(session["view"])
        self.refresh_assets()
        self._update_status_meta()
        self._schedule_music_preview(40)

    def refresh_assets(self) -> None:
        for child in self.asset_list.winfo_children():
            child.destroy()
        self._asset_buttons.clear()
        assets = self.project.assets()
        music = [asset for asset in assets if asset.kind == "music"]
        sfx = [asset for asset in assets if asset.kind == "sfx"]
        self._asset_group("音乐", music)
        self._asset_group("音效", sfx)
        if isinstance(self.current_view, LibraryView):
            self.current_view.refresh(assets)

    def _asset_group(self, title: str, assets: list[AssetInfo]) -> None:
        ctk.CTkLabel(
            self.asset_list,
            text=f"{title}  {len(assets)}",
            text_color=T.TEXT_MUTED,
            font=ui_font(T.TEXT_12),
            anchor="w",
        ).pack(fill="x", padx=10, pady=(12, 4))
        for asset in assets:
            active_id = self.current_song.id if asset.kind == "music" else self.current_sfx.id
            active = asset.id == active_id and (
                (asset.kind == "music" and self.current_mode == "music")
                or (asset.kind == "sfx" and self.current_mode == "sfx")
            )
            button = ctk.CTkButton(
                self.asset_list,
                text=asset.name,
                command=lambda kind=asset.kind, asset_id=asset.id: self.open_asset(kind, asset_id),
                anchor="w",
                height=36,
                corner_radius=T.RADIUS,
                fg_color=T.NAV_ACTIVE if active else "transparent",
                hover_color=T.NAV_ACTIVE,
                text_color=T.TEXT if active else T.TEXT_SECONDARY,
                font=ui_font(T.TEXT_13, "bold" if active else "normal"),
            )
            button.pack(fill="x", pady=1)
            self._asset_buttons.append(button)

    def open_asset(self, kind: str, asset_id: str) -> None:
        if self.dirty:
            self._commit_current_editor()
        if kind == "music":
            for _, song in self.project.load_songs():
                if song.id == asset_id:
                    self.current_song = song
                    self.show_view("music")
                    break
        else:
            for _, patch in self.project.load_sfx():
                if patch.id == asset_id:
                    self.current_sfx = patch
                    self.show_view("sfx")
                    break
        self.refresh_assets()

    def new_asset(self) -> None:
        if self.dirty:
            self._commit_current_editor()
        if self.last_editor_mode == "sfx":
            names = {patch.name for _, patch in self.project.load_sfx()}
            index = 1
            while f"新音效 {index}" in names:
                index += 1
            self.current_sfx = get_preset("Click")
            self.current_sfx.name = f"新音效 {index}"
            self.project.save_sfx(self.current_sfx)
            self.show_view("sfx")
        else:
            names = {song.name for _, song in self.project.load_songs()}
            index = 1
            while f"新音乐 {index}" in names:
                index += 1
            self.current_song = Song(
                name=f"新音乐 {index}",
                tracks=[Track(name="主旋律")],
            )
            self.project.save_song(self.current_song)
            self.show_view("music")
        self.refresh_assets()
        self.set_status("已创建新资产")

    def mark_dirty(self) -> None:
        self.dirty = True
        self.project_label.configure(text=self.project.metadata.name + "  •")
        self._schedule_music_preview(500)

    def _commit_current_editor(self) -> None:
        if isinstance(self.current_view, SFXView):
            self.current_sfx = self.current_view.patch
            self.project.save_sfx(self.current_sfx)
        elif isinstance(self.current_view, SequencerView):
            self.current_view._apply_song_controls()
            self.current_song = self.current_view.song
            self.project.save_song(self.current_song)
        elif isinstance(self.current_view, SettingsView):
            self.current_view.apply()
            self.project.save_metadata()
        else:
            self.project.save_metadata()
        self.dirty = False
        self.project_label.configure(text=self.project.metadata.name)

    def save_current(self) -> None:
        self._commit_current_editor()
        self.refresh_assets()
        self.set_status("已保存")

    def _save_sfx(self, patch: SFXPatch) -> None:
        self.current_sfx = patch
        self.project.save_sfx(patch)
        self.dirty = False
        self.project_label.configure(text=self.project.metadata.name)
        self.refresh_assets()
        self.set_status("音效已保存")

    def _save_settings(self) -> None:
        self.project.save_metadata()
        self.dirty = False
        self.project_label.configure(text=self.project.metadata.name)
        self._update_status_meta()

    def snapshot(self) -> None:
        if isinstance(self.current_view, SequencerView):
            self.project.snapshot_song(
                self.current_view.song,
                "snapshot",
            )
            self.set_status("已保存音乐快照")
        else:
            self.save_current()
            self.set_status("当前资产已保存")

    def _schedule_music_preview(self, delay_ms: int) -> None:
        if self._closing:
            return
        if self._music_render_warm_after_id is not None:
            try:
                self.after_cancel(self._music_render_warm_after_id)
            except (ValueError, tk.TclError):
                pass
        self._music_render_warm_after_id = self.after(
            delay_ms,
            self._warm_current_music,
        )

    def _warm_current_music(self) -> None:
        self._music_render_warm_after_id = None
        if (
            self._playing
            or self._playback_loading
            or not isinstance(self.current_view, SequencerView)
        ):
            return
        try:
            plan = self.current_view.create_playback_plan(self.project.metadata.sample_rate)
        except Exception:
            return
        rendered = self._cached_music_preview(plan)
        stems = self._cached_music_stems(plan)
        if stems is None:
            self._request_music_render(plan)
        elif rendered is None:
            self._remember_music_preview(plan.cache_key, plan.mix_stems(stems))

    @staticmethod
    def _music_preview_cache_path(plan: SequencerPlaybackPlan) -> Path:
        safe_key = plan.cache_key.replace(":", "_")
        return data_dir() / "cache" / f"music_preview_{safe_key}.npy"

    def _remember_music_preview(self, cache_key: str, samples):
        self._music_preview_cache[cache_key] = samples
        self._music_preview_cache.move_to_end(cache_key)
        while len(self._music_preview_cache) > 2:
            self._music_preview_cache.popitem(last=False)
        return samples

    def _remember_music_stems(
        self,
        cache_key: str,
        stems: tuple[np.ndarray, ...],
    ) -> tuple[np.ndarray, ...]:
        self._music_stem_cache[cache_key] = stems
        self._music_stem_cache.move_to_end(cache_key)
        while len(self._music_stem_cache) > 1:
            self._music_stem_cache.popitem(last=False)
        return stems

    def _cached_music_stems(
        self,
        plan: SequencerPlaybackPlan,
    ) -> tuple[np.ndarray, ...] | None:
        stems = self._music_stem_cache.get(plan.stem_cache_key)
        if stems is not None:
            self._music_stem_cache.move_to_end(plan.stem_cache_key)
        return stems

    def _cached_music_preview(self, plan: SequencerPlaybackPlan):
        cached = self._music_preview_cache.get(plan.cache_key)
        if cached is not None:
            self._music_preview_cache.move_to_end(plan.cache_key)
            return cached
        path = self._music_preview_cache_path(plan)
        if not path.is_file():
            return None
        try:
            samples = np.load(path, mmap_mode="r", allow_pickle=False)
        except (OSError, ValueError):
            path.unlink(missing_ok=True)
            return None
        if samples.dtype != np.float32 or samples.ndim not in (1, 2) or not len(samples):
            path.unlink(missing_ok=True)
            return None
        return self._remember_music_preview(plan.cache_key, samples)

    def _write_music_preview_cache(
        self,
        plan: SequencerPlaybackPlan,
        samples,
    ) -> None:
        path = self._music_preview_cache_path(plan)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        try:
            with temp.open("wb") as output:
                np.save(output, np.asarray(samples, dtype=np.float32), allow_pickle=False)
            temp.replace(path)
            cached = sorted(
                path.parent.glob("music_preview_*.npy"),
                key=lambda item: item.stat().st_mtime,
            )
            for stale in cached[:-6]:
                stale.unlink(missing_ok=True)
        finally:
            temp.unlink(missing_ok=True)

    def _request_music_render(self, plan: SequencerPlaybackPlan) -> None:
        rendered = self._cached_music_preview(plan)
        stems = self._cached_music_stems(plan)
        if stems is not None:
            if rendered is None:
                self._remember_music_preview(plan.cache_key, plan.mix_stems(stems))
            return
        if self._music_render_active_key is not None:
            if self._music_render_active_key != plan.stem_cache_key:
                self._music_render_pending_plan = plan
            return
        self._music_render_active_key = plan.stem_cache_key
        threading.Thread(
            target=self._render_music_plan,
            args=(plan,),
            name="blipkit-preview-render",
            daemon=True,
        ).start()

    def _render_music_plan(self, plan: SequencerPlaybackPlan) -> None:
        try:
            samples, stems = plan.render_bundle()
            self._write_music_preview_cache(plan, samples)
            error = None
        except Exception as exc:
            samples = None
            stems = None
            error = exc
        self._music_render_results.put((plan, samples, stems, error))

    def _poll_music_render_results(self) -> None:
        if self._closing:
            return
        audition = self.note_auditioner.take_latest()
        if audition is not None:
            samples, sample_rate, error = audition
            if error:
                self.set_status(f"试听失败：{error}")
            else:
                try:
                    self.audition_player.play(samples, sample_rate)
                except Exception as exc:
                    self.set_status(f"试听失败：{exc}")
        self._poll_export_events()
        while True:
            try:
                plan, samples, stems, error = self._music_render_results.get_nowait()
            except queue.Empty:
                break
            if self._music_render_active_key == plan.stem_cache_key:
                self._music_render_active_key = None
            if error is None and samples is not None:
                self._remember_music_preview(plan.cache_key, samples)
            if error is None and stems is not None:
                self._remember_music_stems(plan.stem_cache_key, stems)
            request = self._playback_request
            if request is not None and request[1].stem_cache_key == plan.stem_cache_key:
                request_id, request_plan, request_view = request
                if error is not None:
                    self._cancel_pending_playback(f"预览失败：{error}")
                elif stems is not None:
                    request_samples = request_plan.mix_stems(stems)
                    self._remember_music_preview(
                        request_plan.cache_key,
                        request_samples,
                    )
                    self._start_music_playback(
                        request_id,
                        request_plan,
                        request_view,
                        request_samples,
                    )
            mix_request = self._mix_update_request
            if mix_request is not None and mix_request[1].stem_cache_key == plan.stem_cache_key:
                mix_id, mix_plan, mix_view = mix_request
                self._mix_update_request = None
                if error is not None:
                    self.set_status(f"混音更新失败：{error}")
                elif samples is not None and mix_plan.cache_key == plan.cache_key:
                    self._queue_mix_preparation(
                        mix_id,
                        mix_plan,
                        mix_view,
                        rendered=samples,
                    )
                elif stems is not None:
                    self._queue_mix_preparation(
                        mix_id,
                        mix_plan,
                        mix_view,
                        stems=stems,
                    )

        self._poll_prepared_mix_updates()
        if self._music_render_active_key is None and self._music_render_pending_plan is not None:
            pending = self._music_render_pending_plan
            self._music_render_pending_plan = None
            if self._cached_music_stems(pending) is None:
                self._request_music_render(pending)
        self._music_render_poll_after_id = self.after(
            16,
            self._poll_music_render_results,
        )

    def _cancel_pending_playback(self, status: str | None = None) -> None:
        self._playback_request_id += 1
        self._playback_request = None
        self._playback_loading = False
        if self.current_view is not None and hasattr(
            self.current_view,
            "set_playback_state",
        ):
            self.current_view.set_playback_state(False)
        if status:
            self.set_status(status)

    def _start_music_playback(
        self,
        request_id: int,
        plan: SequencerPlaybackPlan,
        view: SequencerView,
        rendered,
    ) -> None:
        if (
            request_id != self._playback_request_id
            or self.current_view is not view
            or not self._playback_loading
        ):
            return
        try:
            samples = plan.output_from(rendered)
        except Exception as exc:
            self._cancel_pending_playback(f"预览失败：{exc}")
            return
        self._playback_request = None
        self._begin_audio_playback(samples, plan.sample_rate, view)

    def _begin_audio_playback(self, samples, sample_rate: int, view) -> None:
        try:
            started = self.player.play(samples, sample_rate)
        except Exception as exc:
            self._cancel_pending_playback(f"预览失败：{exc}")
            return
        if not started:
            self._cancel_pending_playback("系统未找到可用的音频播放器")
            return
        self._playback_loading = False
        self._playing = True
        if hasattr(view, "set_playback_state"):
            view.set_playback_state(True)
        if hasattr(view, "start_playhead"):
            view.start_playhead(self.player.current_time)
        duration = max(0.05, len(samples) / float(sample_rate))
        self._playback_after_id = self.after(
            int(duration * 1000) + 80,
            self._playback_finished,
        )
        self.set_status("正在播放")

    def _on_track_mix_change(self) -> None:
        if not self._playing or not isinstance(self.current_view, SequencerView):
            return
        view = self.current_view
        self._mix_update_id += 1
        mix_id = self._mix_update_id
        elapsed = self.player.current_time()
        current_beat = min(
            view.playback_end,
            view._playhead_start_beat + elapsed * view.song.bpm / 60.0,
        )
        view.insert_beat = current_beat
        plan = view.create_playback_plan(self.project.metadata.sample_rate)
        rendered = self._cached_music_preview(plan)
        stems = None if rendered is not None else self._cached_music_stems(plan)
        if rendered is None and stems is None:
            self._mix_update_request = (mix_id, plan, view)
            self._request_music_render(plan)
            return
        self._mix_update_request = None
        self._queue_mix_preparation(
            mix_id,
            plan,
            view,
            rendered=rendered,
            stems=stems,
        )

    def _queue_mix_preparation(
        self,
        mix_id: int,
        plan: SequencerPlaybackPlan,
        view: SequencerView,
        *,
        rendered=None,
        stems: tuple[np.ndarray, ...] | None = None,
    ) -> None:
        if mix_id != self._mix_update_id or not self._playing or self.current_view is not view:
            return
        audio_time = self.player.current_time()
        current_beat = min(
            view.playback_end,
            view._playhead_start_beat + audio_time * view.song.bpm / 60.0,
        )
        prepared_plan = replace(plan, start_beat=current_beat)
        threading.Thread(
            target=self._prepare_mix_update,
            args=(
                mix_id,
                prepared_plan,
                view,
                rendered,
                stems,
                audio_time,
            ),
            name="blipkit-live-mix",
            daemon=True,
        ).start()

    def _prepare_mix_update(
        self,
        mix_id: int,
        plan: SequencerPlaybackPlan,
        view: SequencerView,
        rendered,
        stems: tuple[np.ndarray, ...] | None,
        audio_time: float,
    ) -> None:
        try:
            if rendered is None:
                if stems is None:
                    raise RuntimeError("No cached stems are available")
                rendered = plan.mix_stems(stems)
            samples = plan.output_from(rendered)
            error = None
        except Exception as exc:
            samples = None
            error = exc
        self._mix_update_results.put((mix_id, plan, view, samples, rendered, audio_time, error))

    def _poll_prepared_mix_updates(self) -> None:
        while True:
            try:
                (
                    mix_id,
                    plan,
                    view,
                    samples,
                    rendered,
                    audio_time,
                    error,
                ) = self._mix_update_results.get_nowait()
            except queue.Empty:
                return
            if mix_id != self._mix_update_id or not self._playing or self.current_view is not view:
                continue
            if error is not None or samples is None:
                self.set_status(f"混音更新失败：{error}")
                continue
            self._remember_music_preview(plan.cache_key, rendered)
            elapsed = self.player.current_time()
            lag_seconds = max(0.0, elapsed - audio_time)
            lag_frames = min(
                len(samples),
                round(lag_seconds * plan.sample_rate),
            )
            if lag_frames >= len(samples):
                continue
            current_beat = min(
                view.playback_end,
                plan.start_beat + lag_seconds * view.song.bpm / 60.0,
            )
            self._commit_mix_update(
                plan,
                view,
                samples[lag_frames:],
                current_beat,
            )

    def _commit_mix_update(
        self,
        plan: SequencerPlaybackPlan,
        view: SequencerView,
        samples,
        current_beat: float,
    ) -> None:
        try:
            started = self.player.replace(samples, plan.sample_rate)
        except Exception as exc:
            self.set_status(f"混音更新失败：{exc}")
            return
        if not started:
            self.set_status("混音更新失败：系统音频不可用")
            return
        view.insert_beat = current_beat
        if self._playback_after_id is not None:
            try:
                self.after_cancel(self._playback_after_id)
            except (ValueError, tk.TclError):
                pass
        view.start_playhead(self.player.current_time)
        duration = max(0.05, len(samples) / float(plan.sample_rate))
        self._playback_after_id = self.after(
            int(duration * 1000) + 80,
            self._playback_finished,
        )

    def toggle_playback(self) -> None:
        if self._playing or self._playback_loading:
            self.stop_playback()
            if isinstance(self.current_view, SequencerView):
                self.current_view._set_edit_cursor(self._transport_origin, seek=False)
            return
        if not hasattr(self.current_view, "render_audio"):
            self.set_status("当前视图没有可预览的音频")
            return
        view = self.current_view
        if isinstance(view, SequencerView):
            self._transport_origin = view.insert_beat
        sample_rate = self.project.metadata.sample_rate
        self._playback_request_id += 1
        request_id = self._playback_request_id
        self._playback_loading = True
        if hasattr(view, "set_playback_state"):
            view.set_playback_state(True)
        if isinstance(view, SequencerView):
            try:
                plan = view.create_playback_plan(sample_rate)
            except Exception as exc:
                self._cancel_pending_playback(f"预览失败：{exc}")
                return
            self._playback_request = (request_id, plan, view)
            cached = self._cached_music_preview(plan)
            if cached is None:
                stems = self._cached_music_stems(plan)
                if stems is not None:
                    cached = plan.mix_stems(stems)
                    self._remember_music_preview(plan.cache_key, cached)
            if cached is not None:
                self._start_music_playback(request_id, plan, view, cached)
            else:
                self.set_status("正在准备播放…")
                self._request_music_render(plan)
            return
        self.set_status("正在准备播放…")
        self.update_idletasks()
        try:
            samples = view.render_audio(sample_rate)
            self._begin_audio_playback(samples, sample_rate, view)
        except Exception as exc:
            self._cancel_pending_playback(f"预览失败：{exc}")

    def preview_note(self, pitch: int, instrument: str, velocity: int = 100) -> None:
        self.note_auditioner.request(
            pitch,
            instrument,
            velocity,
            max(60, self.current_song.bpm),
            self.project.metadata.sample_rate,
        )

    def import_midi(self) -> None:
        selected = filedialog.askopenfilename(
            title="导入 MIDI",
            filetypes=[("MIDI 文件", "*.mid *.midi"), ("所有文件", "*.*")],
        )
        if not selected:
            return
        if self.dirty:
            self._commit_current_editor()
        try:
            song = import_song_midi(Path(selected))
            existing = {item.name for _, item in self.project.load_songs()}
            original = song.name
            index = 2
            while song.name in existing:
                song.name = f"{original} {index}"
                index += 1
            self.project.save_song(song)
            self.current_song = song
            self.dirty = False
            self.show_view("music")
            self.set_status(f"已导入 MIDI：{song.name}")
        except Exception as exc:
            self.set_status(f"MIDI 导入失败：{exc}")

    def export_midi(self) -> None:
        if not isinstance(self.current_view, SequencerView):
            return
        self.current_view._apply_song_controls()
        selected = filedialog.asksaveasfilename(
            title="导出 MIDI",
            defaultextension=".mid",
            initialfile=f"{self.current_view.song.name}.mid",
            filetypes=[("MIDI 文件", "*.mid"), ("所有文件", "*.*")],
        )
        if not selected:
            return
        try:
            path = export_song_midi(self.current_view.song, Path(selected))
            self.set_status(f"已导出 MIDI：{path.name}")
        except Exception as exc:
            self.set_status(f"MIDI 导出失败：{exc}")

    def _playback_finished(self) -> None:
        self._playback_after_id = None
        if self._playing:
            if (
                self.current_view is not None
                and hasattr(self.current_view, "should_loop")
                and self.current_view.should_loop()
            ):
                self.stop_playback()
                self.current_view.jump_to_loop_start()
                self.after_idle(self.toggle_playback)
                return
            self.stop_playback(completed=True)

    def stop_playback(self, completed: bool = False) -> None:
        self._playback_request_id += 1
        self._mix_update_id += 1
        self._playback_request = None
        self._mix_update_request = None
        self._playback_loading = False
        if self._playback_after_id is not None:
            try:
                self.after_cancel(self._playback_after_id)
            except (ValueError, tk.TclError):
                pass
            self._playback_after_id = None
        if hasattr(self, "player"):
            self.player.stop()
        if self.current_view is not None and hasattr(self.current_view, "stop_playhead"):
            self.current_view.stop_playhead()
        self._playing = False
        if self.current_view is not None and hasattr(self.current_view, "set_playback_state"):
            self.current_view.set_playback_state(False)
        if completed:
            self.set_status("播放完成")

    def export_all(self) -> None:
        self._export(None)

    def export_selected(self, selected_ids: list[str]) -> None:
        if not selected_ids:
            self.set_status("请先选择需要导出的资产")
            return
        self._export(selected_ids)

    def _export(self, selected_ids: list[str] | None) -> None:
        self.save_current()
        engine = self.project.metadata.engine
        if engine == "None":
            destination = self.project.path / "exports"
        else:
            path = self.project.metadata.engine_path
            if not path or not validate_engine_path(engine, Path(path)):
                self.show_view("settings")
                self.set_status("请先设置有效的引擎输出路径")
                return
            destination = Path(path)
        if self._export_running:
            self.set_status("已有导出正在进行")
            return
        snapshot = ExportSnapshot(self.project)
        self._export_running = True
        self.set_status("正在导出音频… 可继续编辑")

        def export_worker():
            try:
                result = export_project(
                    snapshot,
                    destination=destination,
                    engine=engine,
                    selected_ids=selected_ids,
                    progress=lambda current, total, name: self._export_events.put(
                        ("progress", f"正在导出 {current}/{total} · {name}")
                    ),
                )
                self._export_events.put(("done", (result, destination)))
            except Exception as exc:
                self._export_events.put(("error", str(exc)))

        threading.Thread(target=export_worker, daemon=True, name="blipkit-export").start()

    def _poll_export_events(self):
        while not self._export_events.empty():
            kind, payload = self._export_events.get()
            if kind == "progress":
                self.set_status(payload)
            elif kind == "error":
                self._export_running = False
                self.set_status(f"导出失败：{payload}")
            else:
                self._export_running = False
                result, destination = payload
                suffix = f" · {len(result.failed)} 个失败" if result.failed else ""
                self.set_status(f"已导出 {len(result.files)} 个文件{suffix} → {destination}")

    def new_project(self) -> None:
        parent = filedialog.askdirectory(
            parent=self,
            title="选择新工程保存位置",
            initialdir=str(data_dir() / "Projects"),
        )
        if not parent:
            return
        base = Path(parent)
        index = 1
        path = base / "New Game.bkproj"
        while path.exists():
            index += 1
            path = base / f"New Game {index}.bkproj"
        self._switch_project(BlipkitProject.create(path, path.stem, template="RPG"))
        self.set_status("新工程已创建")

    def open_project(self) -> None:
        selected = filedialog.askdirectory(
            parent=self,
            title="打开 .bkproj 工程目录",
            initialdir=str(Path(self.settings.last_project).parent)
            if self.settings.last_project
            else str(Path.home()),
        )
        if not selected:
            return
        try:
            project = BlipkitProject.open(Path(selected))
        except (OSError, ValueError) as exc:
            self.set_status(f"打开失败：{exc}")
            return
        self._switch_project(project)
        self.set_status("工程已打开")

    def _switch_project(self, project: BlipkitProject) -> None:
        self.stop_playback()
        if self.dirty:
            self.save_current()
        self.project.close()
        self.project = project
        self.settings.remember_project(project.path)
        self.current_song = self._first_song()
        self.current_sfx = self._first_sfx()
        self.project_label.configure(text=project.metadata.name)
        self.dirty = False
        self.refresh_assets()
        self.show_view("music")

    def _autosave(self) -> None:
        editing = isinstance(self.current_view, SequencerView) and self.current_view.gesture_active
        if self.dirty and not editing:
            self.save_current()
            self.set_status("已自动保存")
        self.after(self.settings.autosave_seconds * 1000, self._autosave)

    def _update_status_meta(self) -> None:
        if not hasattr(self, "transport_meta"):
            return
        bpm = self.current_song.bpm if self.current_song else 120
        engine = self.project.metadata.engine
        engine_text = "本地" if engine == "None" else engine
        self.transport_meta.configure(
            text=(f"BPM {bpm}   |   {engine_text}   |   .{self.project.metadata.export_format}")
        )

    def set_status(self, message: str) -> None:
        if hasattr(self, "status_var"):
            self.status_var.set(message)

    def _close(self) -> None:
        if self._export_running:
            self.set_status("正在导出，完成后可关闭窗口")
            return
        if isinstance(self.current_view, SequencerView) and self.current_view.gesture_active:
            self.current_view.cancel_gesture()
        self._closing = True
        self.note_auditioner.close()
        try:
            for after_id in (
                self._music_render_warm_after_id,
                self._music_render_poll_after_id,
            ):
                if after_id is not None:
                    try:
                        self.after_cancel(after_id)
                    except (ValueError, tk.TclError):
                        pass
            if self.dirty:
                self.save_current()
            self.player.close()
            self.audition_player.close()
            self.project.close()
        finally:
            self.destroy()


def run() -> None:
    app = BlipkitApp()
    app.mainloop()
