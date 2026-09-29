"""Procedural SFX design workspace."""

from __future__ import annotations

import random
import time
import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from blipkit.core.models import SFXPatch
from blipkit.core.sfx_synth import (
    categories,
    get_preset,
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
        on_status: Callable[[str], None],
    ):
        super().__init__(parent, fg_color=T.SURFACE)
        self.patch = patch
        self.on_save = on_save
        self.on_status = on_status
        self._sliders: dict[str, LabeledSlider] = {}
        self._playhead_started = 0.0
        self._playhead_after: str | None = None
        self._samples = synthesize(self.patch)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build_toolbar()
        self._build_body()
        self._refresh_preset_list()
        self.after(80, self.redraw_waveform)

    def _build_toolbar(self) -> None:
        toolbar = ctk.CTkFrame(self, height=46, fg_color=T.SURFACE, corner_radius=0)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_propagate(False)
        toolbar.grid_columnconfigure(5, weight=1)

        self.name_var = tk.StringVar(value=self.patch.name)
        name = ctk.CTkEntry(
            toolbar,
            width=180,
            height=28,
            textvariable=self.name_var,
            corner_radius=T.RADIUS,
            border_color=T.BORDER,
            fg_color=T.SURFACE,
            text_color=T.TEXT,
            font=ui_font(13, "bold"),
        )
        name.grid(row=0, column=0, padx=(16, 10), pady=8)
        name.bind("<FocusOut>", lambda _event: self._name_changed())
        name.bind("<Return>", lambda _event: self._name_changed())

        self.waveform_var = tk.StringVar(value=self.patch.waveform)
        waveform = ctk.CTkOptionMenu(
            toolbar,
            variable=self.waveform_var,
            values=["Sine", "Square", "Sawtooth", "Triangle", "Noise"],
            command=self._waveform_changed,
            width=110,
            height=28,
            corner_radius=T.RADIUS,
            fg_color=T.SURFACE_ALT,
            button_color=T.BORDER,
            button_hover_color=T.TEXT_DISABLED,
            text_color=T.TEXT,
            dropdown_fg_color=T.SURFACE,
            dropdown_hover_color=T.ACCENT_SOFT,
            dropdown_text_color=T.TEXT,
            font=ui_font(12),
        )
        waveform.grid(row=0, column=1, padx=(0, 8))
        action_button(toolbar, "随机变体", self.randomize, width=82).grid(
            row=0, column=2, padx=(0, 8)
        )
        action_button(toolbar, "保存音效", self.save, primary=True, width=82).grid(row=0, column=3)

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self, fg_color=T.SURFACE, corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        browser = ctk.CTkFrame(
            body,
            width=184,
            fg_color=T.SURFACE_ALT,
            corner_radius=0,
            border_width=1,
            border_color=T.BORDER,
        )
        browser.grid(row=0, column=0, sticky="nsew")
        browser.grid_propagate(False)
        ctk.CTkLabel(
            browser,
            text="预设",
            text_color=T.TEXT,
            font=ui_font(13, "bold"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(14, 8))

        self.category_var = tk.StringVar(value=categories()[0])
        self.category_menu = ctk.CTkOptionMenu(
            browser,
            variable=self.category_var,
            values=categories(),
            command=lambda _value: self._refresh_preset_list(),
            width=156,
            height=28,
            corner_radius=T.RADIUS,
            fg_color=T.SURFACE,
            button_color=T.BORDER,
            button_hover_color=T.TEXT_DISABLED,
            text_color=T.TEXT,
            dropdown_fg_color=T.SURFACE,
            dropdown_hover_color=T.ACCENT_SOFT,
            font=ui_font(12),
        )
        self.category_menu.pack(padx=14, pady=(0, 8))
        self.preset_list = ctk.CTkScrollableFrame(
            browser,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=T.TEXT_DISABLED,
            scrollbar_button_hover_color=T.TEXT_MUTED,
        )
        self.preset_list.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        center = ctk.CTkFrame(body, fg_color=T.SURFACE, corner_radius=0)
        center.grid(row=0, column=1, sticky="nsew")
        center.grid_rowconfigure(1, weight=1)
        center.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            center,
            text="波形预览",
            text_color=T.TEXT,
            font=ui_font(13, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))
        self.canvas = tk.Canvas(
            center,
            bg=T.SURFACE,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.canvas.bind("<Configure>", lambda _event: self.redraw_waveform())

        controls = ctk.CTkScrollableFrame(
            body,
            width=286,
            fg_color=T.SURFACE_ALT,
            corner_radius=0,
            border_width=1,
            border_color=T.BORDER,
            scrollbar_button_color=T.TEXT_DISABLED,
            scrollbar_button_hover_color=T.TEXT_MUTED,
        )
        controls.grid(row=0, column=2, sticky="nsew")
        ctk.CTkLabel(
            controls,
            text="合成参数",
            text_color=T.TEXT,
            font=ui_font(13, "bold"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(14, 10))

        specs = (
            ("start_freq", "起始频率 Hz", 30.0, 2400.0, 0),
            ("end_freq", "结束频率 Hz", 20.0, 2400.0, 0),
            ("bend", "弯曲", 0.2, 3.0, 2),
            ("duration", "时长 s", 0.04, 2.0, 2),
            ("attack", "Attack", 0.001, 0.5, 3),
            ("decay", "Decay", 0.005, 0.8, 3),
            ("sustain", "Sustain", 0.0, 1.0, 2),
            ("release", "Release", 0.005, 0.8, 3),
            ("noise", "噪声", 0.0, 1.0, 2),
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
            slider.pack(fill="x", padx=14, pady=(0, 13))
            self._sliders[attr] = slider

        seed_row = ctk.CTkFrame(controls, fg_color="transparent")
        seed_row.pack(fill="x", padx=14, pady=(2, 14))
        ctk.CTkLabel(
            seed_row,
            text="随机种子",
            text_color=T.TEXT_SECONDARY,
            font=ui_font(12),
        ).pack(side="left")
        self.seed_var = tk.StringVar(value=str(self.patch.seed))
        seed = ctk.CTkEntry(
            seed_row,
            width=92,
            height=28,
            textvariable=self.seed_var,
            corner_radius=T.RADIUS,
            border_color=T.BORDER,
            fg_color=T.SURFACE,
            font=ui_font(11, mono=True),
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
                height=30,
                corner_radius=T.RADIUS,
                fg_color=T.ACCENT_SOFT if active else "transparent",
                hover_color=T.ACCENT_SOFT,
                text_color=T.ACCENT if active else T.TEXT_SECONDARY,
                font=ui_font(12, "bold" if active else "normal"),
                command=lambda preset=name: self.select_preset(preset),
            )
            button.pack(fill="x", pady=1)

    def select_preset(self, name: str) -> None:
        self.set_patch(get_preset(name))
        self.on_status(f"已载入 {name} 预设")

    def set_patch(self, patch: SFXPatch) -> None:
        self.patch = patch
        self.name_var.set(patch.name)
        self.waveform_var.set(patch.waveform)
        self.category_var.set(patch.category)
        self.seed_var.set(str(patch.seed))
        for attr, slider in self._sliders.items():
            slider.set(float(getattr(patch, attr)))
        self._samples = synthesize(self.patch)
        self._refresh_preset_list()
        self.redraw_waveform()

    def _name_changed(self) -> None:
        self.patch.name = self.name_var.get().strip() or self.patch.name
        self.name_var.set(self.patch.name)

    def _waveform_changed(self, value: str) -> None:
        self.patch.waveform = value
        self._regenerate()

    def _parameter_changed(self, attr: str, value: float) -> None:
        setattr(self.patch, attr, value)
        self._regenerate()

    def _seed_changed(self) -> None:
        try:
            self.patch.seed = int(self.seed_var.get())
        except ValueError:
            self.seed_var.set(str(self.patch.seed))
        self._regenerate()

    def _regenerate(self) -> None:
        self._samples = synthesize(self.patch)
        self.redraw_waveform()

    def randomize(self) -> None:
        self.set_patch(randomize_patch(self.patch, random.randint(1, 2**31 - 1)))
        self.on_status("已生成新的随机变体")

    def save(self) -> None:
        self._name_changed()
        self.on_save(self.patch)

    def render_audio(self):
        self._regenerate()
        return self._samples

    def duration(self) -> float:
        return self.patch.duration

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
        self.canvas.create_text(
            10,
            10,
            text=(
                f"{self.patch.duration:0.2f}s  ·  {self.patch.waveform}  ·  seed {self.patch.seed}"
            ),
            anchor="nw",
            fill=T.TEXT_MUTED,
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
