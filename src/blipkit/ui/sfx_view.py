"""Procedural SFX design workspace."""

from __future__ import annotations

import copy
import random
import time
import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk
import numpy as np

from blipkit.core.models import SFXPatch
from blipkit.core.sfx_synth import (
    categories,
    get_preset,
    mutate_patch,
    preset_names,
    randomize_patch,
    synthesize,
    waveform_preview,
)

from . import tokens as T
from .widgets import LabeledSlider, action_button, ui_font


class SFXView(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        patch: SFXPatch,
        on_save: Callable[[SFXPatch], None],
        on_change: Callable[[], None],
        on_status: Callable[[str], None],
        on_seek: Callable[[], None],
        on_play: Callable[[], None],
    ):
        super().__init__(parent, fg_color=T.SURFACE)
        self.patch = patch
        self.on_save = on_save
        self.on_change = on_change
        self.on_status = on_status
        self.on_seek = on_seek
        self.on_play = on_play
        self._sliders: dict[str, LabeledSlider] = {}
        self._playhead_started = 0.0
        self._playhead_after: str | None = None
        self._regenerate_after: str | None = None
        self._history_reset_after: str | None = None
        self._history_open = False
        self._pending_preview = False
        self._undo_stack: list[SFXPatch] = []
        self._redo_stack: list[SFXPatch] = []
        self._baseline = copy.deepcopy(patch)
        self._samples = synthesize(self.patch)
        self.auto_preview_var = tk.BooleanVar(value=True)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build_toolbar()
        self._build_body()
        self._refresh_preset_list()
        self.after(80, self.redraw_waveform)

    def _build_toolbar(self) -> None:
        toolbar = ctk.CTkFrame(self, height=60, fg_color=T.SURFACE, corner_radius=0)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_propagate(False)
        toolbar.grid_rowconfigure(0, weight=1)
        toolbar.grid_columnconfigure(8, weight=1)

        self.name_var = tk.StringVar(value=self.patch.name)
        name = ctk.CTkEntry(
            toolbar,
            width=180,
            height=T.CONTROL_H,
            textvariable=self.name_var,
            corner_radius=T.RADIUS_CONTROL,
            border_color=T.BORDER,
            fg_color=T.SURFACE,
            text_color=T.TEXT,
            font=ui_font(T.TEXT_16, "bold"),
        )
        name.grid(row=0, column=0, padx=(20, 12))
        name.bind("<FocusOut>", lambda _event: self._name_changed())
        name.bind("<Return>", lambda _event: self._name_changed())

        self.waveform_var = tk.StringVar(value=self.patch.waveform)
        waveform = ctk.CTkOptionMenu(
            toolbar,
            variable=self.waveform_var,
            values=["Sine", "Square", "Sawtooth", "Triangle", "Noise"],
            command=self._waveform_changed,
            width=116,
            height=T.CONTROL_H,
            corner_radius=T.RADIUS_CONTROL,
            fg_color=T.NAV_BG,
            button_color=T.NAV_ACTIVE,
            button_hover_color=T.BORDER,
            text_color=T.TEXT,
            dropdown_fg_color=T.SURFACE,
            dropdown_hover_color=T.NAV_ACTIVE,
            dropdown_text_color=T.TEXT,
            font=ui_font(T.TEXT_13),
        )
        waveform.grid(row=0, column=1, padx=(0, 8))
        self.transport_button = action_button(
            toolbar,
            "▶  试听",
            self.on_play,
            primary=True,
            width=76,
        )
        self.transport_button.grid(row=0, column=2, padx=(0, 8))
        ctk.CTkSwitch(
            toolbar,
            text="自动试听",
            variable=self.auto_preview_var,
            width=88,
            height=22,
            switch_width=32,
            switch_height=18,
            fg_color=T.BORDER,
            progress_color=T.ACCENT,
            button_color=T.SURFACE,
            button_hover_color=T.SURFACE,
            text_color=T.TEXT_SECONDARY,
            font=ui_font(T.TEXT_12),
        ).grid(row=0, column=3, padx=(0, 8))
        action_button(toolbar, "轻微变体", self.mutate, width=78, quiet=True).grid(
            row=0, column=4, padx=(0, 2)
        )
        action_button(toolbar, "随机", self.randomize, width=58, quiet=True).grid(
            row=0, column=5, padx=(0, 2)
        )
        action_button(toolbar, "回退", self.revert, width=58, quiet=True).grid(
            row=0, column=6, padx=(0, 8)
        )
        action_button(toolbar, "保存音效", self.save, width=82).grid(row=0, column=7)

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self, fg_color=T.SURFACE, corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        browser = ctk.CTkFrame(
            body,
            width=200,
            fg_color=T.NAV_BG,
            corner_radius=T.RADIUS_PANEL,
        )
        browser.grid(row=0, column=0, sticky="nsew", padx=(12, 8), pady=(0, 12))
        browser.grid_propagate(False)
        ctk.CTkLabel(
            browser,
            text="预设",
            text_color=T.TEXT,
            font=ui_font(T.TEXT_14, "bold"),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(16, 10))

        self.category_var = tk.StringVar(value=categories()[0])
        self.category_menu = ctk.CTkOptionMenu(
            browser,
            variable=self.category_var,
            values=categories(),
            command=lambda _value: self._refresh_preset_list(),
            width=168,
            height=T.CONTROL_H,
            corner_radius=T.RADIUS_CONTROL,
            fg_color=T.SURFACE,
            button_color=T.NAV_ACTIVE,
            button_hover_color=T.BORDER,
            text_color=T.TEXT,
            dropdown_fg_color=T.SURFACE,
            dropdown_hover_color=T.NAV_ACTIVE,
            font=ui_font(T.TEXT_13),
        )
        self.category_menu.pack(padx=16, pady=(0, 10))
        self.preset_list = ctk.CTkScrollableFrame(
            browser,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=T.TEXT_DISABLED,
            scrollbar_button_hover_color=T.TEXT_MUTED,
        )
        self.preset_list.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        center = ctk.CTkFrame(
            body,
            fg_color=T.SURFACE_ALT,
            corner_radius=T.RADIUS_PANEL,
        )
        center.grid(row=0, column=1, sticky="nsew", padx=8, pady=(0, 12))
        center.grid_rowconfigure(1, weight=1)
        center.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            center,
            text="波形预览",
            text_color=T.TEXT,
            font=ui_font(T.TEXT_14, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        self.canvas = tk.Canvas(
            center,
            bg=T.SURFACE_ALT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.canvas.bind("<Configure>", lambda _event: self.redraw_waveform())

        controls = ctk.CTkScrollableFrame(
            body,
            width=300,
            fg_color=T.SURFACE_ALT,
            corner_radius=T.RADIUS_PANEL,
            scrollbar_button_color=T.TEXT_DISABLED,
            scrollbar_button_hover_color=T.TEXT_MUTED,
        )
        controls.grid(row=0, column=2, sticky="nsew", padx=(8, 12), pady=(0, 12))
        ctk.CTkLabel(
            controls,
            text="合成参数",
            text_color=T.TEXT,
            font=ui_font(T.TEXT_14, "bold"),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(16, 14))

        specs = (
            ("start_freq", "起始频率 Hz", 30.0, 2400.0, 0),
            ("end_freq", "结束频率 Hz", 20.0, 2400.0, 0),
            ("bend", "弯曲", 0.2, 3.0, 2),
            ("duration", "时长 s", 0.04, 2.0, 2),
            ("attack", "起音", 0.001, 0.5, 3),
            ("decay", "衰减", 0.005, 0.8, 3),
            ("sustain", "延音", 0.0, 1.0, 2),
            ("release", "释音", 0.005, 0.8, 3),
            ("noise", "噪声", 0.0, 1.0, 2),
            ("vibrato_depth", "颤音深度", 0.0, 2.0, 2),
            ("vibrato_rate", "颤音速度 Hz", 0.1, 24.0, 1),
            ("lowpass_cutoff", "低通", 0.05, 1.0, 2),
            ("crush", "位深压缩", 0.0, 1.0, 2),
            ("volume", "音量", 0.0, 1.0, 2),
        )
        for attr, label, start, end, digits in specs:
            slider = LabeledSlider(
                controls,
                label,
                start,
                end,
                float(getattr(self.patch, attr)),
                lambda value, key=attr: self._parameter_changed(key, value),
                digits=digits,
            )
            slider.pack(fill="x", padx=16, pady=(0, 16))
            self._sliders[attr] = slider

        seed_row = ctk.CTkFrame(controls, fg_color="transparent")
        seed_row.pack(fill="x", padx=16, pady=(2, 16))
        ctk.CTkLabel(
            seed_row,
            text="随机种子",
            text_color=T.TEXT_SECONDARY,
            font=ui_font(T.TEXT_12),
        ).pack(side="left")
        self.seed_var = tk.StringVar(value=str(self.patch.seed))
        seed = ctk.CTkEntry(
            seed_row,
            width=92,
            height=T.CONTROL_H,
            textvariable=self.seed_var,
            corner_radius=T.RADIUS_CONTROL,
            border_color=T.BORDER,
            fg_color=T.SURFACE,
            font=ui_font(T.TEXT_13, mono=True),
        )
        seed.pack(side="right")
        seed.bind("<Return>", lambda _event: self._seed_changed())
        seed.bind("<FocusOut>", lambda _event: self._seed_changed())

    def _refresh_preset_list(self) -> None:
        for child in self.preset_list.winfo_children():
            child.destroy()
        for name in preset_names(self.category_var.get()):
            active = name == self.patch.name
            button = ctk.CTkButton(
                self.preset_list,
                text=name,
                anchor="w",
                height=T.NAV_ITEM_H,
                corner_radius=T.RADIUS,
                fg_color=T.NAV_ACTIVE if active else "transparent",
                hover_color=T.NAV_ACTIVE,
                text_color=T.TEXT if active else T.TEXT_SECONDARY,
                font=ui_font(T.TEXT_13, "bold" if active else "normal"),
                command=lambda preset=name: self.select_preset(preset),
            )
            button.pack(fill="x", pady=1)

    def select_preset(self, name: str) -> None:
        self._begin_edit(force=True)
        self.set_patch(get_preset(name), mark_changed=True, preview=True)
        self.on_status(f"已载入 {name} 预设")

    def set_patch(
        self,
        patch: SFXPatch,
        mark_changed: bool = False,
        preview: bool = False,
    ) -> None:
        self.patch = patch
        self.name_var.set(patch.name)
        self.waveform_var.set(patch.waveform)
        self.category_var.set(patch.category)
        self.seed_var.set(str(patch.seed))
        for attr, slider in self._sliders.items():
            slider.set(float(getattr(patch, attr)))
        self._pending_preview = preview
        self._perform_regenerate()
        self._refresh_preset_list()
        if mark_changed:
            self.on_change()

    def _begin_edit(self, force: bool = False) -> None:
        if force or not self._history_open:
            self._undo_stack.append(copy.deepcopy(self.patch))
            self._undo_stack = self._undo_stack[-60:]
            self._redo_stack.clear()
        self._history_open = not force
        if self._history_reset_after is not None:
            self.after_cancel(self._history_reset_after)
        self._history_reset_after = self.after(450, self._close_history_group)

    def _close_history_group(self) -> None:
        self._history_reset_after = None
        self._history_open = False

    def _name_changed(self) -> None:
        previous = self.patch.name
        updated = self.name_var.get().strip() or self.patch.name
        if updated != previous:
            self._begin_edit(force=True)
            self.patch.name = updated
        self.name_var.set(self.patch.name)
        if self.patch.name != previous:
            self.on_change()

    def _waveform_changed(self, value: str) -> None:
        if value == self.patch.waveform:
            return
        self._begin_edit(force=True)
        self.patch.waveform = value
        self._schedule_regenerate()

    def _parameter_changed(self, attr: str, value: float) -> None:
        if abs(float(getattr(self.patch, attr)) - value) < 0.000001:
            return
        self._begin_edit()
        setattr(self.patch, attr, value)
        self._schedule_regenerate()

    def _seed_changed(self) -> None:
        try:
            seed = int(self.seed_var.get())
        except ValueError:
            self.seed_var.set(str(self.patch.seed))
            return
        if seed == self.patch.seed:
            return
        self._begin_edit(force=True)
        self.patch.seed = seed
        self._schedule_regenerate()

    def _schedule_regenerate(self) -> None:
        self.on_change()
        self._pending_preview = True
        if self._regenerate_after is not None:
            self.after_cancel(self._regenerate_after)
        self._regenerate_after = self.after(90, self._perform_regenerate)

    def _perform_regenerate(self) -> None:
        self._regenerate_after = None
        preview = self._pending_preview
        self._pending_preview = False
        self._samples = synthesize(self.patch)
        self.redraw_waveform()
        if preview and self.auto_preview_var.get():
            self.on_seek()
            self.on_play()

    def randomize(self) -> None:
        self._begin_edit(force=True)
        self.set_patch(
            randomize_patch(self.patch, random.randint(1, 2**31 - 1)),
            mark_changed=True,
            preview=True,
        )
        self.on_status("已生成新的随机变体")

    def mutate(self) -> None:
        self._begin_edit(force=True)
        self.set_patch(
            mutate_patch(self.patch, random.randint(1, 2**31 - 1)),
            mark_changed=True,
            preview=True,
        )
        self.on_status("已生成轻微变体")

    def revert(self) -> None:
        if self.patch.to_dict() == self._baseline.to_dict():
            self.on_status("当前已经是保存版本")
            return
        self._begin_edit(force=True)
        self.set_patch(copy.deepcopy(self._baseline), mark_changed=True, preview=True)
        self.on_status("已回到保存版本")

    def undo(self) -> None:
        if not self._undo_stack:
            self.on_status("没有可撤销的操作")
            return
        self._redo_stack.append(copy.deepcopy(self.patch))
        self._history_open = False
        self.set_patch(self._undo_stack.pop(), mark_changed=True, preview=True)
        self.on_status("已撤销")

    def redo(self) -> None:
        if not self._redo_stack:
            self.on_status("没有可重做的操作")
            return
        self._undo_stack.append(copy.deepcopy(self.patch))
        self._history_open = False
        self.set_patch(self._redo_stack.pop(), mark_changed=True, preview=True)
        self.on_status("已重做")

    def save(self) -> None:
        self._name_changed()
        self.on_save(self.patch)
        self._baseline = copy.deepcopy(self.patch)
        self.on_status("音效已保存")

    def render_audio(self, sample_rate: int = 44100):
        if self._regenerate_after is not None:
            self.after_cancel(self._regenerate_after)
        self._regenerate_after = None
        self._samples = synthesize(self.patch, sample_rate=sample_rate)
        self.redraw_waveform()
        return self._samples

    def duration(self) -> float:
        return self.patch.duration

    def set_playback_state(self, playing: bool) -> None:
        if hasattr(self, "transport_button"):
            self.transport_button.configure(text="■  停止" if playing else "▶  试听")

    def redraw_waveform(self) -> None:
        if not hasattr(self, "canvas"):
            return
        width = max(40, self.canvas.winfo_width())
        height = max(40, self.canvas.winfo_height())
        self.canvas.delete("all")
        mid = height / 2.0
        self.canvas.create_line(0, mid, width, mid, fill=T.BORDER, width=1)
        for step in range(1, 8):
            x = width * step / 8.0
            self.canvas.create_line(x, 0, x, height, fill=T.BORDER_LIGHT)
        points = waveform_preview(self._samples, max(80, min(500, width // 2)))
        coords = []
        for index, value in enumerate(points):
            x = index * width / max(1, len(points) - 1)
            y = mid - value * height * 0.38
            coords.extend((x, y))
        if len(coords) >= 4:
            self.canvas.create_line(*coords, fill=T.ACCENT, width=2, smooth=True)
        peak = float(np.max(np.abs(self._samples))) if len(self._samples) else 0.0
        peak_db = 20.0 * np.log10(max(peak, 0.000001))
        self.canvas.create_text(
            10,
            10,
            text=(
                f"{self.patch.duration:0.2f}s  ·  {self.patch.waveform}"
                f"  ·  峰值 {peak_db:0.1f} dB  ·  seed {self.patch.seed}"
            ),
            anchor="nw",
            fill=T.DANGER if peak >= 0.98 else T.TEXT_MUTED,
            font=("SF Mono", 10),
        )

    def start_playhead(self) -> None:
        self.stop_playhead()
        self._playhead_started = time.monotonic()
        self._animate_playhead()

    def _animate_playhead(self) -> None:
        elapsed = time.monotonic() - self._playhead_started
        ratio = min(1.0, elapsed / max(0.04, self.patch.duration))
        width = max(40, self.canvas.winfo_width())
        self.canvas.delete("playhead")
        self.canvas.create_line(
            width * ratio,
            0,
            width * ratio,
            self.canvas.winfo_height(),
            fill=T.TEXT,
            width=1,
            tags="playhead",
        )
        if ratio < 1.0:
            self._playhead_after = self.after(25, self._animate_playhead)
        else:
            self._playhead_after = None

    def stop_playhead(self) -> None:
        if self._playhead_after:
            try:
                self.after_cancel(self._playhead_after)
            except ValueError:
                pass
        self._playhead_after = None
        if hasattr(self, "canvas"):
            self.canvas.delete("playhead")

    def destroy(self) -> None:
        self.stop_playhead()
        if self._regenerate_after is not None:
            try:
                self.after_cancel(self._regenerate_after)
            except ValueError:
                pass
            self._regenerate_after = None
        if self._history_reset_after is not None:
            try:
                self.after_cancel(self._history_reset_after)
            except ValueError:
                pass
            self._history_reset_after = None
        super().destroy()
