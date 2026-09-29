"""Project and export settings view."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from blipkit.core.engine_bridge import ENGINES, validate_engine_path
from blipkit.core.models import ProjectMetadata

from . import tokens as T
from .widgets import action_button, ui_font


class SettingsView(ctk.CTkScrollableFrame):
    def __init__(
        self,
        parent,
        metadata: ProjectMetadata,
        project_path: Path,
        on_save: Callable[[], None],
        on_status: Callable[[str], None],
    ):
        super().__init__(
            parent,
            fg_color=T.SURFACE,
            corner_radius=0,
            scrollbar_button_color=T.TEXT_DISABLED,
            scrollbar_button_hover_color=T.TEXT_MUTED,
        )
        self.metadata = metadata
        self.project_path = Path(project_path)
        self.on_save = on_save
        self.on_status = on_status
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self) -> None:
        content = ctk.CTkFrame(self, fg_color="transparent", width=720)
        content.grid(row=0, column=0, sticky="nw", padx=28, pady=24)
        content.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            content,
            text="工程设置",
            text_color=T.TEXT,
            font=ui_font(20, "bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=3, sticky="ew")
        ctk.CTkLabel(
            content,
            text="音频规格与游戏引擎输出路径",
            text_color=T.TEXT_MUTED,
            font=ui_font(12),
            anchor="w",
        ).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 22))

        row = 2
        row = self._section(content, row, "工程")
        self.name_var = tk.StringVar(value=self.metadata.name)
        self._entry_row(content, row, "工程名称", self.name_var)
        row += 1
        self._static_row(content, row, "工程目录", str(self.project_path))
        row += 1

        row = self._section(content, row, "音频输出")
        self.rate_var = tk.StringVar(value=str(self.metadata.sample_rate))
        self._option_row(content, row, "采样率", self.rate_var, ["22050", "44100", "48000"])
        row += 1
        self.depth_var = tk.StringVar(value=str(self.metadata.bit_depth))
        self._option_row(content, row, "位深", self.depth_var, ["16", "24"])
        row += 1
        self.channels_var = tk.StringVar(value=self.metadata.channels)
        self._option_row(content, row, "声道", self.channels_var, ["Mono", "Stereo"])
        row += 1
        self.format_var = tk.StringVar(value=self.metadata.export_format)
        self._option_row(content, row, "默认格式", self.format_var, ["wav", "ogg", "mp3", "flac"])
        row += 1
        self.normalize_var = tk.BooleanVar(value=self.metadata.normalize)
        self._switch_row(content, row, "音量标准化", self.normalize_var)
        row += 1

        row = self._section(content, row, "引擎联动")
        self.engine_var = tk.StringVar(value=self.metadata.engine)
        self._option_row(
            content, row, "目标引擎", self.engine_var, list(ENGINES), self._engine_changed
        )
        row += 1
        self.path_var = tk.StringVar(value=self.metadata.engine_path)
        self._path_row(content, row)
        row += 1
        self.engine_status = ctk.CTkLabel(
            content,
            text="",
            text_color=T.TEXT_MUTED,
            font=ui_font(11),
            anchor="w",
        )
        self.engine_status.grid(row=row, column=1, columnspan=2, sticky="ew", pady=(0, 18))
        self._update_engine_status()
        row += 1

        ctk.CTkFrame(content, height=1, fg_color=T.BORDER).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(8, 16)
        )
        row += 1
        action_button(
            content,
            "保存设置",
            self.save,
            primary=True,
            width=100,
        ).grid(row=row, column=1, sticky="w")

    def _section(self, parent, row: int, text: str) -> int:
        if row > 2:
            ctk.CTkFrame(parent, height=1, fg_color=T.BORDER).grid(
                row=row, column=0, columnspan=3, sticky="ew", pady=(20, 18)
            )
            row += 1
        ctk.CTkLabel(
            parent,
            text=text,
            text_color=T.TEXT,
            font=ui_font(13, "bold"),
            anchor="w",
        ).grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        return row + 1

    def _form_label(self, parent, row: int, text: str) -> None:
        ctk.CTkLabel(
            parent,
            text=text,
            text_color=T.TEXT_SECONDARY,
            font=ui_font(12),
            width=120,
            anchor="w",
        ).grid(row=row, column=0, sticky="w", pady=6)

    def _entry_row(self, parent, row: int, label: str, variable) -> None:
        self._form_label(parent, row, label)
        ctk.CTkEntry(
            parent,
            textvariable=variable,
            width=260,
            height=30,
            corner_radius=T.RADIUS,
            border_color=T.BORDER,
            fg_color=T.SURFACE,
            text_color=T.TEXT,
            font=ui_font(12),
        ).grid(row=row, column=1, sticky="w", pady=6)

    def _static_row(self, parent, row: int, label: str, value: str) -> None:
        self._form_label(parent, row, label)
        ctk.CTkLabel(
            parent,
            text=value,
            text_color=T.TEXT_MUTED,
            font=ui_font(11, mono=True),
            anchor="w",
        ).grid(row=row, column=1, columnspan=2, sticky="w", pady=6)

    def _option_row(self, parent, row, label, variable, values, command=None) -> None:
        self._form_label(parent, row, label)
        ctk.CTkOptionMenu(
            parent,
            variable=variable,
            values=values,
            command=command,
            width=180,
            height=30,
            corner_radius=T.RADIUS,
            fg_color=T.SURFACE_ALT,
            button_color=T.BORDER,
            button_hover_color=T.TEXT_DISABLED,
            text_color=T.TEXT,
            dropdown_fg_color=T.SURFACE,
            dropdown_hover_color=T.ACCENT_SOFT,
            dropdown_text_color=T.TEXT,
            font=ui_font(12),
        ).grid(row=row, column=1, sticky="w", pady=6)

    def _switch_row(self, parent, row, label, variable) -> None:
        self._form_label(parent, row, label)
        ctk.CTkSwitch(
            parent,
            text="",
            variable=variable,
            width=44,
            height=22,
            switch_width=36,
            switch_height=18,
            fg_color=T.BORDER,
            progress_color=T.ACCENT,
            button_color=T.SURFACE,
            button_hover_color=T.SURFACE,
        ).grid(row=row, column=1, sticky="w", pady=6)

    def _path_row(self, parent, row: int) -> None:
        self._form_label(parent, row, "输出路径")
        entry = ctk.CTkEntry(
            parent,
            textvariable=self.path_var,
            width=390,
            height=30,
            corner_radius=T.RADIUS,
            border_color=T.BORDER,
            fg_color=T.SURFACE,
            text_color=T.TEXT,
            font=ui_font(11, mono=True),
        )
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        entry.bind("<FocusOut>", lambda _event: self._update_engine_status())
        action_button(parent, "选择", self._choose_path, width=58).grid(
            row=row, column=2, padx=(8, 0), pady=6
        )

    def _engine_changed(self, _value: str) -> None:
        self._update_engine_status()

    def _choose_path(self) -> None:
        selected = filedialog.askdirectory(
            parent=self.winfo_toplevel(),
            title="选择引擎项目或输出目录",
            initialdir=self.path_var.get() or str(Path.home()),
        )
        if selected:
            self.path_var.set(selected)
            self._update_engine_status()

    def _update_engine_status(self) -> None:
        if not hasattr(self, "engine_status"):
            return
        engine = self.engine_var.get()
        path = self.path_var.get().strip()
        if engine == "None":
            text, color = "未启用引擎联动，将导出到工程 exports 目录", T.TEXT_MUTED
        elif not path:
            text, color = "请选择目标目录", T.WARNING
        elif validate_engine_path(engine, Path(path)):
            text, color = "路径有效", T.SUCCESS
        else:
            text, color = "路径与所选引擎不匹配", T.DANGER
        self.engine_status.configure(text=text, text_color=color)

    def save(self) -> None:
        self.metadata.name = self.name_var.get().strip() or self.metadata.name
        self.metadata.sample_rate = int(self.rate_var.get())
        self.metadata.bit_depth = int(self.depth_var.get())
        self.metadata.channels = self.channels_var.get()
        self.metadata.export_format = self.format_var.get()
        self.metadata.normalize = bool(self.normalize_var.get())
        self.metadata.engine = self.engine_var.get()
        self.metadata.engine_path = self.path_var.get().strip()
        self._update_engine_status()
        self.on_save()
        self.on_status("工程设置已保存")
