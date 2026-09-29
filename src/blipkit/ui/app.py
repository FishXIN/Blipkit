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
from blipkit.core.models import AssetInfo, SFXPatch, Song, Track
from blipkit.core.playback import AudioPlayer
from blipkit.core.project import BlipkitProject
from blipkit.core.sfx_synth import get_preset

from . import tokens as T
from .library_view import LibraryView
from .sequencer_view import SequencerView
from .settings_view import SettingsView
from .sfx_view import SFXView
from .widgets import action_button, ui_font


class BlipkitApp(ctk.CTk):
    def __init__(self) -> None:
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        super().__init__(fg_color=T.BG)
        self.title("Blipkit")
        self.geometry("1240x780")
        self.minsize(1040, 680)
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
        self.dirty = False
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
        if self.settings.last_project:
            path = Path(self.settings.last_project)
            if (path / "project.json").is_file():
                try:
                    return BlipkitProject.open(path)
                except (OSError, ValueError):
                    pass
        root = data_dir() / "Projects" / "Starter.bkproj"
        if (root / "project.json").is_file():
            project = BlipkitProject.open(root)
        else:
            project = BlipkitProject.create(root, "Starter", template="RPG")
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
            fg_color=T.SURFACE,
            corner_radius=0,
        )
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_rowconfigure(0, weight=1)
        header.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(
            header,
            text="BLIPKIT",
            width=T.NAV_W,
            text_color=T.TEXT,
            font=ui_font(15, "bold", mono=True),
            anchor="w",
        ).grid(row=0, column=0, padx=(18, 0), sticky="w")
        ctk.CTkFrame(header, width=1, fg_color=T.BORDER).grid(row=0, column=1, sticky="ns")
        self.project_label = ctk.CTkLabel(
            header,
            text=self.project.metadata.name,
            text_color=T.TEXT_SECONDARY,
            font=ui_font(12),
            anchor="w",
        )
        self.project_label.grid(row=0, column=2, padx=16, sticky="w")

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.grid(row=0, column=3, padx=12)
        action_button(controls, "打开", self.open_project, width=58).pack(side="left", padx=(0, 6))
        action_button(controls, "新建", self.new_project, width=58).pack(side="left", padx=(0, 6))
        action_button(controls, "快照", self.snapshot, width=58).pack(side="left", padx=(0, 6))
        action_button(controls, "导出", self.export_all, primary=True, width=66).pack(side="left")
        ctk.CTkFrame(self, height=1, fg_color=T.BORDER).place(
            x=0, rely=0, y=T.HEADER_H - 1, relwidth=1
        )

    def _build_content(self) -> None:
        content = ctk.CTkFrame(self, fg_color=T.BG, corner_radius=0)
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(2, weight=1)

        self.nav = ctk.CTkFrame(
            content,
            width=T.NAV_W,
            fg_color=T.SURFACE_ALT,
            corner_radius=0,
        )
        self.nav.grid(row=0, column=0, sticky="nsew")
        self.nav.grid_propagate(False)
        self._build_nav_buttons()

        self.asset_panel = ctk.CTkFrame(
            content,
            width=T.ASSET_W,
            fg_color=T.SURFACE,
            corner_radius=0,
            border_width=1,
            border_color=T.BORDER,
        )
        self.asset_panel.grid(row=0, column=1, sticky="nsew")
        self.asset_panel.grid_propagate(False)
        self.asset_panel.grid_rowconfigure(1, weight=1)
        self._build_asset_header()

        self.workspace = ctk.CTkFrame(
            content,
            fg_color=T.SURFACE,
            corner_radius=0,
        )
        self.workspace.grid(row=0, column=2, sticky="nsew")

    def _build_nav_buttons(self) -> None:
        ctk.CTkLabel(
            self.nav,
            text="工作区",
            text_color=T.TEXT_MUTED,
            font=ui_font(10, mono=True),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(16, 8))
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
                height=34,
                corner_radius=T.RADIUS,
                fg_color="transparent",
                hover_color=T.ACCENT_SOFT,
                text_color=T.TEXT_SECONDARY,
                font=ui_font(12),
            )
            button.pack(fill="x", padx=8, pady=2)
            self._nav_buttons[key] = button
        ctk.CTkLabel(
            self.nav,
            text=f"v{__version__}",
            text_color=T.TEXT_DISABLED,
            font=ui_font(10, mono=True),
            anchor="w",
        ).pack(side="bottom", fill="x", padx=14, pady=14)

    def _build_asset_header(self) -> None:
        header = ctk.CTkFrame(self.asset_panel, fg_color="transparent", height=48)
        header.grid(row=0, column=0, sticky="ew", padx=12)
        header.grid_propagate(False)
        ctk.CTkLabel(
            header,
            text="工程资产",
            text_color=T.TEXT,
            font=ui_font(13, "bold"),
            anchor="w",
        ).pack(side="left")
        action_button(header, "+", self.new_asset, width=30).pack(side="right")
        self.asset_list = ctk.CTkScrollableFrame(
            self.asset_panel,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=T.TEXT_DISABLED,
            scrollbar_button_hover_color=T.TEXT_MUTED,
        )
        self.asset_list.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 6))

    def _build_status(self) -> None:
        status = ctk.CTkFrame(
            self,
            height=T.STATUS_H,
            fg_color=T.SURFACE_ALT,
            corner_radius=0,
            border_width=1,
            border_color=T.BORDER,
        )
        status.grid(row=2, column=0, sticky="ew")
        status.grid_propagate(False)
        status.grid_columnconfigure(1, weight=1)
        self.play_button = action_button(status, "▶ 播放", self.toggle_playback, width=72)
        self.play_button.grid(row=0, column=0, padx=(10, 10), pady=2)
        self.status_var = tk.StringVar(value="工程已就绪")
        ctk.CTkLabel(
            status,
            textvariable=self.status_var,
            text_color=T.TEXT_MUTED,
            font=ui_font(11),
            anchor="w",
        ).grid(row=0, column=1, sticky="ew")
        self.transport_meta = ctk.CTkLabel(
            status,
            text="",
            text_color=T.TEXT_MUTED,
            font=ui_font(10, mono=True),
            anchor="e",
        )
        self.transport_meta.grid(row=0, column=2, padx=12)
        self._update_status_meta()

    def _bind_shortcuts(self) -> None:
        modifier = "Command" if sys.platform == "darwin" else "Control"
        self.bind_all(f"<{modifier}-s>", lambda _event: self.save_current())
        self.bind_all(f"<{modifier}-o>", lambda _event: self.open_project())
        self.bind_all("<space>", lambda _event: self.toggle_playback())
        self.bind_all("<Delete>", lambda _event: self._delete_note())
        self.bind_all("<BackSpace>", lambda _event: self._delete_note())

    def _delete_note(self) -> None:
        if isinstance(self.current_view, SequencerView):
            self.current_view.delete_selected_note()

    def show_view(self, mode: str) -> None:
        self.stop_playback()
        self.current_mode = mode
        for key, button in self._nav_buttons.items():
            active = key == mode
            button.configure(
                fg_color=T.ACCENT_SOFT if active else "transparent",
                text_color=T.ACCENT if active else T.TEXT_SECONDARY,
                font=ui_font(12, "bold" if active else "normal"),
            )
        if self.current_view is not None:
            self.current_view.destroy()
        if mode == "music":
            self.current_view = SequencerView(
                self.workspace,
                self.current_song,
                self.mark_dirty,
                self.set_status,
            )
        elif mode == "sfx":
            self.current_view = SFXView(
                self.workspace,
                self.current_sfx,
                self._save_sfx,
                self.set_status,
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
            font=ui_font(10, mono=True),
            anchor="w",
        ).pack(fill="x", padx=8, pady=(10, 4))
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
                height=30,
                corner_radius=T.RADIUS,
                fg_color=T.ACCENT_SOFT if active else "transparent",
                hover_color=T.ACCENT_SOFT,
                text_color=T.ACCENT if active else T.TEXT_SECONDARY,
                font=ui_font(12, "bold" if active else "normal"),
            )
            button.pack(fill="x", pady=1)
            self._asset_buttons.append(button)

    def open_asset(self, kind: str, asset_id: str) -> None:
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
        if self.current_mode == "sfx":
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

    def save_current(self) -> None:
        if isinstance(self.current_view, SFXView):
            self.current_sfx = self.current_view.patch
            self.project.save_sfx(self.current_sfx)
        elif isinstance(self.current_view, SequencerView):
            self.current_song = self.current_view.song
            self.project.save_song(self.current_song)
        else:
            self.project.save_metadata()
        self.dirty = False
        self.project_label.configure(text=self.project.metadata.name)
        self.refresh_assets()
        self.set_status("已保存")

    def _save_sfx(self, patch: SFXPatch) -> None:
        self.current_sfx = patch
        self.project.save_sfx(patch)
        self.dirty = False
        self.refresh_assets()
        self.set_status("音效已保存")

    def _save_settings(self) -> None:
        self.project.save_metadata()
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
        if self.play_button.cget("text").startswith("■"):
            self.stop_playback()
            return
        if not hasattr(self.current_view, "render_audio"):
            self.set_status("当前视图没有可预览的音频")
            return
        self.set_status("正在生成预览…")
        self.update_idletasks()
        try:
            samples = self.current_view.render_audio()
            if self.player.play(samples, self.project.metadata.sample_rate):
                self.play_button.configure(text="■ 停止")
                if hasattr(self.current_view, "start_playhead"):
                    self.current_view.start_playhead()
                duration = self.current_view.duration()
                self.after(int(duration * 1000) + 80, self._playback_finished)
                self.set_status("正在播放")
            else:
                self.set_status("系统未找到可用的音频播放器")
        except Exception as exc:
            self.set_status(f"预览失败：{exc}")

    def _playback_finished(self) -> None:
        if self.play_button.cget("text").startswith("■"):
            self.stop_playback(completed=True)

    def stop_playback(self, completed: bool = False) -> None:
        if hasattr(self, "player"):
            self.player.stop()
        if self.current_view is not None and hasattr(self.current_view, "stop_playhead"):
            self.current_view.stop_playhead()
        if hasattr(self, "play_button"):
            self.play_button.configure(text="▶ 播放")
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
