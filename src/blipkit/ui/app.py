"""Blipkit single-window CustomTkinter application."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from blipkit import __version__
from blipkit.core.config import AppSettings, data_dir
from blipkit.core.engine_bridge import validate_engine_path
from blipkit.core.export import export_project
from blipkit.core.midi_io import export_song_midi, import_song_midi
from blipkit.core.models import AssetInfo, Note, SFXPatch, Song, Track
from blipkit.core.playback import AudioPlayer
from blipkit.core.project import BlipkitProject
from blipkit.core.sequencer import render_note
from blipkit.core.sfx_synth import get_preset
from blipkit.core.soundbank import get_preset as get_instrument_preset

from . import tokens as T
from .library_view import LibraryView
from .sequencer_view import SequencerView
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
        self.current_song = self._first_song()
        self.current_sfx = self._first_sfx()
        self.current_view = None
        self.current_mode = "music"
        self.last_editor_mode = "music"
        self.dirty = False
        self._playing = False
        self._playback_after_id: str | None = None
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
        header = ctk.CTkFrame(
            self,
            height=T.HEADER_H,
            fg_color=T.NAV_BG,
            corner_radius=0,
        )
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_rowconfigure(0, weight=1)
        header.grid_columnconfigure(0, minsize=T.SIDEBAR_W)
        header.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(
            header,
            text="BLIPKIT",
            width=T.SIDEBAR_W,
            text_color=T.TEXT,
            font=ui_font(17, "bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=(20, 0), sticky="w")
        ctk.CTkFrame(header, width=1, fg_color=T.BORDER).grid(row=0, column=1, sticky="ns", pady=16)
        self.project_label = ctk.CTkLabel(
            header,
            text=self.project.metadata.name,
            text_color=T.TEXT,
            font=ui_font(16, "bold"),
            anchor="w",
        )
        self.project_label.grid(row=0, column=2, padx=20, sticky="w")

        controls = ctk.CTkFrame(header, fg_color="transparent")
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
        content = ctk.CTkFrame(self, fg_color=T.NAV_BG, corner_radius=0)
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, minsize=T.SIDEBAR_W)
        content.grid_columnconfigure(1, weight=1)

        self.sidebar = ctk.CTkFrame(
            content,
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

        workspace_shell = ctk.CTkFrame(content, fg_color=T.NAV_BG, corner_radius=0)
        workspace_shell.grid(row=0, column=1, sticky="nsew")
        self.workspace = ctk.CTkFrame(
            workspace_shell,
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
        status = ctk.CTkFrame(
            self,
            height=T.STATUS_H,
            fg_color=T.NAV_BG,
            corner_radius=0,
        )
        status.grid(row=2, column=0, sticky="ew")
        status.grid_propagate(False)
        status.grid_rowconfigure(0, weight=1)
        status.grid_columnconfigure(0, minsize=T.SIDEBAR_W)
        status.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(
            status,
            text=f"Blipkit {__version__}",
            text_color=T.TEXT_DISABLED,
            font=ui_font(10, mono=True),
            anchor="w",
        ).grid(row=0, column=0, padx=20, sticky="w")
        ctk.CTkFrame(status, width=1, fg_color=T.BORDER).grid(row=0, column=1, sticky="ns", pady=10)
        self.status_var = tk.StringVar(value="工程已就绪")
        ctk.CTkLabel(
            status,
            textvariable=self.status_var,
            text_color=T.TEXT_MUTED,
            font=ui_font(T.TEXT_12),
            anchor="w",
        ).grid(row=0, column=2, padx=(12, 0), sticky="w")
        self.transport_meta = ctk.CTkLabel(
            status,
            text="",
            text_color=T.TEXT_MUTED,
            font=ui_font(T.TEXT_12, mono=True),
            anchor="e",
        )
        self.transport_meta.grid(row=0, column=3, padx=(12, 18))
        self._update_status_meta()

    def _bind_shortcuts(self) -> None:
        modifier = "Command" if sys.platform == "darwin" else "Control"
        self.bind_all(f"<{modifier}-s>", self._shortcut_save)
        self.bind_all(f"<{modifier}-o>", self._shortcut_open)
        self.bind_all(f"<{modifier}-n>", self._shortcut_new)
        self.bind_all(f"<{modifier}-e>", self._shortcut_export)
        self.bind_all(f"<{modifier}-i>", self._shortcut_import)
        self.bind_all("<space>", self._shortcut_play)
        self.bind_all("<Delete>", self._shortcut_delete)
        self.bind_all("<BackSpace>", self._shortcut_delete)
        self.bind_all(f"<{modifier}-c>", self._shortcut_copy)
        self.bind_all(f"<{modifier}-x>", self._shortcut_cut)
        self.bind_all(f"<{modifier}-v>", self._shortcut_paste)
        self.bind_all(f"<{modifier}-b>", self._shortcut_split)
        self.bind_all(f"<{modifier}-d>", self._shortcut_duplicate)
        self.bind_all(f"<{modifier}-z>", self._shortcut_undo)
        self.bind_all(f"<{modifier}-a>", self._shortcut_select_all)
        self.bind_all(f"<{modifier}-Shift-z>", self._shortcut_redo)
        self.bind_all(f"<{modifier}-equal>", lambda event: self._shortcut_zoom(event, 4))
        self.bind_all(f"<{modifier}-plus>", lambda event: self._shortcut_zoom(event, 4))
        self.bind_all(f"<{modifier}-minus>", lambda event: self._shortcut_zoom(event, -4))
        self.bind_all("<Left>", lambda event: self._shortcut_seek(event, steps=-1))
        self.bind_all("<Right>", lambda event: self._shortcut_seek(event, steps=1))
        self.bind_all("<Up>", lambda event: self._shortcut_jump(event, direction=-1))
        self.bind_all("<Down>", lambda event: self._shortcut_jump(event, direction=1))
        self.bind_all("<Home>", lambda event: self._shortcut_edge(event, end=False))
        self.bind_all("<End>", lambda event: self._shortcut_edge(event, end=True))
        self.bind_all(
            "<KeyPress-q>",
            lambda event: self._shortcut_trim(event, side="left"),
        )
        self.bind_all(
            "<KeyPress-w>",
            lambda event: self._shortcut_trim(event, side="right"),
        )
        self.bind_all(
            "<KeyPress-e>",
            lambda event: self._shortcut_move_track(event, offset=-1),
        )
        self.bind_all(
            "<KeyPress-r>",
            lambda event: self._shortcut_move_track(event, offset=1),
        )
        self.bind_all(
            f"<{modifier}-Left>",
            lambda event: self._shortcut_nudge(event, beats=-1),
        )
        self.bind_all(
            f"<{modifier}-Right>",
            lambda event: self._shortcut_nudge(event, beats=1),
        )
        self.bind_all(
            f"<{modifier}-Up>",
            lambda event: self._shortcut_nudge(event, pitches=1),
        )
        self.bind_all(
            f"<{modifier}-Down>",
            lambda event: self._shortcut_nudge(event, pitches=-1),
        )
        self.bind_all(
            f"<{modifier}-Shift-Up>",
            lambda event: self._shortcut_nudge(event, pitches=12),
        )
        self.bind_all(
            f"<{modifier}-Shift-Down>",
            lambda event: self._shortcut_nudge(event, pitches=-12),
        )
        self.bind_all(
            f"<{modifier}-Alt-Up>",
            lambda event: self._shortcut_nudge(event, velocity=5),
        )
        self.bind_all(
            f"<{modifier}-Alt-Down>",
            lambda event: self._shortcut_nudge(event, velocity=-5),
        )

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
        self.refresh_assets()
        self._update_status_meta()

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

    def _commit_current_editor(self) -> None:
        if isinstance(self.current_view, SFXView):
            self.current_sfx = self.current_view.patch
            self.project.save_sfx(self.current_sfx)
        elif isinstance(self.current_view, SequencerView):
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

    def toggle_playback(self) -> None:
        if self._playing:
            self.stop_playback()
            return
        if not hasattr(self.current_view, "render_audio"):
            self.set_status("当前视图没有可预览的音频")
            return
        self.set_status("正在生成预览…")
        self.update_idletasks()
        try:
            samples = self.current_view.render_audio(self.project.metadata.sample_rate)
            if self.player.play(samples, self.project.metadata.sample_rate):
                self._playing = True
                if hasattr(self.current_view, "set_playback_state"):
                    self.current_view.set_playback_state(True)
                if hasattr(self.current_view, "start_playhead"):
                    self.current_view.start_playhead()
                duration = self.current_view.duration()
                self._playback_after_id = self.after(
                    int(duration * 1000) + 80,
                    self._playback_finished,
                )
                self.set_status("正在播放")
            else:
                self.set_status("系统未找到可用的音频播放器")
        except Exception as exc:
            self.set_status(f"预览失败：{exc}")

    def preview_note(self, pitch: int, instrument: str, velocity: int = 100) -> None:
        self.stop_playback()
        sample_rate = self.project.metadata.sample_rate
        note = Note(pitch=pitch, start=0, duration=0.45, velocity=velocity)
        samples = render_note(
            note,
            max(60, self.current_song.bpm),
            get_instrument_preset(instrument),
            sample_rate,
        )
        self.player.play(samples, sample_rate)

    def import_midi(self) -> None:
        selected = filedialog.askopenfilename(
            title="导入 MIDI",
            filetypes=[("MIDI 文件", "*.mid *.midi"), ("所有文件", "*.*")],
        )
        if not selected:
            return
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
        if self._playback_after_id is not None:
            try:
                self.after_cancel(self._playback_after_id)
            except ValueError:
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
        self.set_status("正在导出音频…")
        self.update_idletasks()
        result = export_project(
            self.project,
            destination=destination,
            engine=engine,
            selected_ids=selected_ids,
            progress=lambda current, total, name: self.set_status(
                f"正在导出 {current}/{total} · {name}"
            ),
        )
        self.refresh_assets()
        if result.failed:
            self.set_status(f"导出完成：{len(result.files)} 个文件，{len(result.failed)} 个失败")
        else:
            self.set_status(f"导出完成：{len(result.files)} 个文件")

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
        if self.dirty:
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
        try:
            if self.dirty:
                self.save_current()
            self.player.stop()
            self.project.close()
        finally:
            self.destroy()


def run() -> None:
    app = BlipkitApp()
    app.mainloop()
