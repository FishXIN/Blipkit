"""Interactive piano-roll workspace."""

from __future__ import annotations

import copy
import time
import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk
import numpy as np

from blipkit.core.models import Note, Song, Track
from blipkit.core.music_assistant import chord_to_midi, is_in_scale
from blipkit.core.sequencer import render_song, song_duration
from blipkit.core.soundbank import BUILTIN_PRESETS

from . import tokens as T
from .widgets import LabeledSlider, action_button, icon_button, ui_font


class SequencerView(ctk.CTkFrame):
    PITCH_LOW = 36
    PITCH_HIGH = 84
    ROW_H = 20
    CELL_W = 26
    SUBDIVISIONS = 4
    LABEL_W = 58
    RULER_H = 28
    SNAP_BEATS = {
        "1/4": 1.0,
        "1/8": 0.5,
        "1/16": 0.25,
    }
    SCALE_LABELS = {
        "Major": "大调",
        "Natural Minor": "自然小调",
        "Harmonic Minor": "和声小调",
        "Melodic Minor": "旋律小调",
        "Major Pentatonic": "大调五声",
        "Minor Pentatonic": "小调五声",
        "Blues": "布鲁斯",
        "Whole Tone": "全音阶",
        "Diminished": "减音阶",
        "Lydian": "利底亚",
        "Mixolydian": "混合利底亚",
        "Dorian": "多利亚",
        "Phrygian": "弗里几亚",
        "Locrian": "洛克里亚",
        "In Sen": "日本阴旋法",
        "Gong": "宫调式",
    }

    def __init__(
        self,
        parent,
        song: Song,
        on_change: Callable[[], None],
        on_seek: Callable[[], None],
        on_status: Callable[[str], None],
        on_play: Callable[[], None],
        on_preview: Callable[[int, str, int], None],
        on_import_midi: Callable[[], None],
        on_export_midi: Callable[[], None],
    ):
        super().__init__(parent, fg_color=T.SURFACE)
        self.song = song
        self.on_change = on_change
        self.on_seek = on_seek
        self.on_status = on_status
        self.on_play = on_play
        self.on_preview = on_preview
        self.on_import_midi = on_import_midi
        self.on_export_midi = on_export_midi
        self.selected_track_index = 0
        self.selected_note_id: str | None = None
        self.selected_note_ids: set[str] = set()
        self.insert_beat = 0.0
        self.cell_w = self.CELL_W
        self.tool_var = tk.StringVar(value="选择")
        self.snap_var = tk.StringVar(value="1/16")
        self.preview_var = tk.BooleanVar(value=True)
        self.scale_warning_var = tk.BooleanVar(value=True)
        self.loop_var = tk.BooleanVar(value=False)
        self.metronome_var = tk.BooleanVar(value=False)
        self.position_var = tk.StringVar(value=self._format_position(0))
        self.note_summary_var = tk.StringVar(value="未选择音符")
        self.note_start_var = tk.StringVar(value="")
        self.note_duration_var = tk.StringVar(value="")
        self.note_velocity_var = tk.StringVar(value="")
        self._note_items: dict[int, Note] = {}
        self._drag_note: Note | None = None
        self._drag_mode = "move"
        self._drag_changed = False
        self._drag_offset_beat = 0.0
        self._drag_offset_pitch = 0
        self._drag_originals: dict[str, tuple[float, int, float]] = {}
        self._drawing_note: Note | None = None
        self._marquee_start: tuple[float, float] | None = None
        self._marquee_current: tuple[float, float] | None = None
        self._marquee_additive = False
        self._scrubbing_playhead = False
        self._hover_beat: float | None = None
        self._history_pushed = False
        self._delete_armed = False
        self._delete_reset_after: str | None = None
        self._playhead_started = 0.0
        self._playhead_after: str | None = None
        self._playhead_duration = 0.0
        self._playhead_start_beat = 0.0
        self._undo_stack: list[tuple[list[Track], int, float]] = []
        self._redo_stack: list[tuple[list[Track], int, float]] = []

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build_toolbar()
        self._build_editor()
        self.redraw()

    @property
    def selected_track(self) -> Track:
        if not self.song.tracks:
            self.song.tracks.append(Track(name="Track 1"))
        self.selected_track_index = min(self.selected_track_index, len(self.song.tracks) - 1)
        return self.song.tracks[self.selected_track_index]

    def _build_toolbar(self) -> None:
        toolbar = ctk.CTkFrame(
            self,
            height=158,
            fg_color=T.SURFACE,
            corner_radius=0,
            border_width=0,
        )
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_propagate(False)
        toolbar.grid_columnconfigure(0, weight=1)

        transport = ctk.CTkFrame(toolbar, fg_color="transparent", corner_radius=0)
        transport.grid(row=0, column=0, sticky="ew", padx=18, pady=(10, 6))

        self.song_title = ctk.CTkLabel(
            transport,
            text=self.song.name,
            text_color=T.TEXT,
            font=ui_font(T.TEXT_16, "bold"),
            width=106,
            anchor="w",
        )
        self.song_title.pack(side="left", padx=(0, 10))

        self.transport_button = action_button(
            transport,
            "▶  播放",
            self.on_play,
            primary=True,
            width=76,
        )
        self.transport_button.pack(side="left", padx=(0, 8))
        self._inline_label(transport, "位置")
        ctk.CTkLabel(
            transport,
            textvariable=self.position_var,
            width=64,
            anchor="w",
            text_color=T.TEXT_SECONDARY,
            font=ui_font(T.TEXT_13, mono=True),
        ).pack(side="left", padx=(5, 12))
        self._divider(transport).pack(side="left", padx=(0, 12), pady=5)

        self.bpm_var = tk.StringVar(value=str(self.song.bpm))
        self._inline_label(transport, "速度")
        bpm = ctk.CTkEntry(
            transport,
            width=54,
            height=T.CONTROL_H,
            textvariable=self.bpm_var,
            corner_radius=T.RADIUS_CONTROL,
            border_color=T.BORDER,
            fg_color=T.SURFACE,
            text_color=T.TEXT,
            font=ui_font(T.TEXT_13, mono=True),
        )
        bpm.pack(side="left", padx=(6, 4))
        bpm.bind("<Return>", self._apply_song_controls)
        bpm.bind("<FocusOut>", self._apply_song_controls)
        ctk.CTkLabel(
            transport,
            text="BPM",
            text_color=T.TEXT_MUTED,
            font=ui_font(T.TEXT_12),
        ).pack(side="left", padx=(0, 12))

        self.signature_var = tk.StringVar(value=self.song.time_signature)
        self._inline_label(transport, "拍号")
        signature = self._option(
            transport,
            self.signature_var,
            ["4/4", "3/4", "6/8", "5/4"],
            66,
        )
        signature.pack(side="left", padx=(6, 12))

        self.bars_var = tk.StringVar(value=str(self.song.bars))
        self._inline_label(transport, "小节")
        bars = ctk.CTkEntry(
            transport,
            width=42,
            height=T.CONTROL_H,
            textvariable=self.bars_var,
            corner_radius=T.RADIUS_CONTROL,
            border_color=T.BORDER,
            fg_color=T.SURFACE,
            text_color=T.TEXT,
            font=ui_font(T.TEXT_13, mono=True),
        )
        bars.pack(side="left", padx=(6, 12))
        bars.bind("<Return>", self._apply_song_controls)
        bars.bind("<FocusOut>", self._apply_song_controls)

        self._divider(transport).pack(side="left", padx=(0, 12), pady=5)
        self._inline_label(transport, "调式")

        self.key_var = tk.StringVar(value=self.song.key)
        key_menu = self._option(
            transport,
            self.key_var,
            ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"],
            58,
        )
        key_menu.pack(side="left", padx=(6, 4))

        self.scale_var = tk.StringVar(
            value=self.SCALE_LABELS.get(self.song.scale, self.song.scale)
        )
        scale = self._option(
            transport,
            self.scale_var,
            list(self.SCALE_LABELS.values()),
            112,
        )
        scale.pack(side="left", padx=(0, 12))
        self.instrument_var = tk.StringVar(value=self.selected_track.instrument)

        editor_bar = ctk.CTkFrame(
            toolbar,
            fg_color=T.SURFACE_ALT,
            corner_radius=T.RADIUS,
            height=46,
        )
        editor_bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        editor_bar.grid_propagate(False)

        ctk.CTkSegmentedButton(
            editor_bar,
            values=["选择", "画笔"],
            variable=self.tool_var,
            command=self._tool_changed,
            width=142,
            height=30,
            corner_radius=T.RADIUS,
            fg_color=T.SURFACE,
            selected_color=T.ACCENT_SOFT,
            selected_hover_color=T.ACCENT_SOFT,
            unselected_color=T.SURFACE,
            unselected_hover_color=T.NAV_ACTIVE,
            text_color=T.TEXT,
            font=ui_font(T.TEXT_12),
        ).pack(side="left", padx=(8, 10), pady=8)

        self._inline_label(editor_bar, "吸附")
        self._option(
            editor_bar,
            self.snap_var,
            list(self.SNAP_BEATS),
            66,
            command=self._snap_changed,
        ).pack(side="left", padx=(6, 10), pady=8)

        self._inline_label(editor_bar, "缩放")
        icon_button(editor_bar, "−", lambda: self.zoom_horizontal(-4)).pack(
            side="left", padx=(3, 0), pady=7
        )
        icon_button(editor_bar, "+", lambda: self.zoom_horizontal(4)).pack(
            side="left", padx=(0, 8), pady=7
        )

        ctk.CTkSwitch(
            editor_bar,
            text="试听",
            variable=self.preview_var,
            width=62,
            height=22,
            switch_width=32,
            switch_height=18,
            fg_color=T.BORDER,
            progress_color=T.ACCENT,
            button_color=T.SURFACE,
            button_hover_color=T.SURFACE,
            text_color=T.TEXT_SECONDARY,
            font=ui_font(T.TEXT_12),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkSwitch(
            editor_bar,
            text="音阶高亮",
            variable=self.scale_warning_var,
            command=self.redraw,
            width=92,
            height=22,
            switch_width=32,
            switch_height=18,
            fg_color=T.BORDER,
            progress_color=T.ACCENT,
            button_color=T.SURFACE,
            button_hover_color=T.SURFACE,
            text_color=T.TEXT_SECONDARY,
            font=ui_font(T.TEXT_12),
        ).pack(side="left", padx=(0, 10))

        ctk.CTkSwitch(
            editor_bar,
            text="循环",
            variable=self.loop_var,
            width=64,
            height=22,
            switch_width=32,
            switch_height=18,
            fg_color=T.BORDER,
            progress_color=T.ACCENT,
            button_color=T.SURFACE,
            button_hover_color=T.SURFACE,
            text_color=T.TEXT_SECONDARY,
            font=ui_font(T.TEXT_12),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkSwitch(
            editor_bar,
            text="节拍器",
            variable=self.metronome_var,
            width=76,
            height=22,
            switch_width=32,
            switch_height=18,
            fg_color=T.BORDER,
            progress_color=T.ACCENT,
            button_color=T.SURFACE,
            button_hover_color=T.SURFACE,
            text_color=T.TEXT_SECONDARY,
            font=ui_font(T.TEXT_12),
        ).pack(side="left", padx=(0, 8))

        self._divider(editor_bar, height=24).pack(side="left", padx=(0, 8), pady=10)
        self._inline_label(editor_bar, "音色")
        self._option(
            editor_bar,
            self.instrument_var,
            [preset.name for preset in BUILTIN_PRESETS],
            132,
            command=self._instrument_changed,
        ).pack(side="left", padx=(5, 6), pady=8)
        action_button(
            editor_bar,
            "导入 MIDI",
            self.on_import_midi,
            width=70,
            quiet=True,
        ).pack(side="left", pady=7)
        action_button(
            editor_bar,
            "导出 MIDI",
            self.on_export_midi,
            width=70,
            quiet=True,
        ).pack(side="left", padx=(0, 6), pady=7)

        self.chord_var = tk.StringVar(value="Cmaj")
        note_bar = ctk.CTkFrame(
            toolbar,
            fg_color="transparent",
            corner_radius=0,
            height=36,
        )
        note_bar.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 6))
        note_bar.grid_propagate(False)

        self.note_summary = ctk.CTkLabel(
            note_bar,
            textvariable=self.note_summary_var,
            width=104,
            text_color=T.TEXT_SECONDARY,
            font=ui_font(T.TEXT_12, "bold"),
            anchor="w",
        )
        self.note_summary.pack(side="left", padx=(0, 4))
        self.note_start_entry = self._note_entry(note_bar, self.note_start_var, 58)
        self._inline_label(note_bar, "位置")
        self.note_start_entry.pack(side="left", padx=(4, 8), pady=8)
        self.note_duration_entry = self._note_entry(note_bar, self.note_duration_var, 52)
        self._inline_label(note_bar, "时长")
        self.note_duration_entry.pack(side="left", padx=(4, 8), pady=8)
        self.note_velocity_entry = self._note_entry(note_bar, self.note_velocity_var, 48)
        self._inline_label(note_bar, "力度")
        self.note_velocity_entry.pack(side="left", padx=(4, 6), pady=8)
        self.quantize_button = action_button(
            note_bar,
            "量化",
            self.quantize_selected,
            width=54,
            quiet=True,
        )
        self.quantize_button.pack(side="left", pady=7)
        self.duplicate_button = action_button(
            note_bar,
            "复制",
            self.duplicate_selected_note,
            width=54,
            quiet=True,
        )
        self.duplicate_button.pack(side="left", pady=7)
        self.delete_note_button = action_button(
            note_bar,
            "删除",
            self.delete_selected_note,
            width=54,
            danger=True,
        )
        self.delete_note_button.pack(side="left", padx=(0, 6), pady=7)
        self._set_note_controls_enabled(False)

    @staticmethod
    def _divider(parent, height: int = 26):
        return ctk.CTkFrame(parent, width=1, height=height, fg_color=T.BORDER)

    def _inline_label(self, parent, text: str) -> ctk.CTkLabel:
        label = ctk.CTkLabel(
            parent,
            text=text,
            text_color=T.TEXT_MUTED,
            font=ui_font(T.TEXT_12),
        )
        label.pack(side="left")
        return label

    def _note_entry(self, parent, variable: tk.StringVar, width: int) -> ctk.CTkEntry:
        entry = ctk.CTkEntry(
            parent,
            width=width,
            height=28,
            textvariable=variable,
            corner_radius=T.RADIUS,
            border_color=T.BORDER,
            fg_color=T.SURFACE,
            text_color=T.TEXT,
            font=ui_font(T.TEXT_12, mono=True),
        )
        entry.bind("<Return>", self._apply_note_controls)
        entry.bind("<FocusOut>", self._apply_note_controls)
        return entry

    def _option(self, parent, variable, values, width, command=None):
        return ctk.CTkOptionMenu(
            parent,
            variable=variable,
            values=values,
            command=command or self._option_changed,
            width=width,
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
            dropdown_font=ui_font(T.TEXT_13),
        )

    def _build_editor(self) -> None:
        body = ctk.CTkFrame(self, fg_color=T.SURFACE, corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        self.track_panel = ctk.CTkFrame(
            body,
            width=188,
            fg_color=T.NAV_BG,
            corner_radius=T.RADIUS_PANEL,
        )
        self.track_panel.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(12, 8),
            pady=(0, 12),
        )
        self.track_panel.grid_propagate(False)

        grid_shell = ctk.CTkFrame(
            body,
            fg_color=T.SURFACE,
            corner_radius=T.RADIUS_PANEL,
            border_width=1,
            border_color=T.BORDER,
        )
        grid_shell.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(8, 12),
            pady=(0, 12),
        )
        grid_shell.grid_rowconfigure(0, weight=1)
        grid_shell.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            grid_shell,
            background=T.SURFACE,
            highlightthickness=0,
            bd=0,
            cursor="arrow",
        )
        self.x_scroll = ctk.CTkScrollbar(
            grid_shell,
            orientation="horizontal",
            command=self._xview,
            height=12,
            fg_color=T.SURFACE,
            button_color=T.TEXT_DISABLED,
            button_hover_color=T.TEXT_MUTED,
        )
        self.y_scroll = ctk.CTkScrollbar(
            grid_shell,
            orientation="vertical",
            command=self._yview,
            width=12,
            fg_color=T.SURFACE,
            button_color=T.TEXT_DISABLED,
            button_hover_color=T.TEXT_MUTED,
        )
        self.canvas.configure(
            xscrollcommand=self.x_scroll.set,
            yscrollcommand=self.y_scroll.set,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.y_scroll.grid(row=0, column=1, sticky="ns")
        self.x_scroll.grid(row=1, column=0, sticky="ew")
        self.canvas.bind("<Button-1>", self._canvas_click)
        self.canvas.bind("<B1-Motion>", self._canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._canvas_release)
        self.canvas.bind("<Double-Button-1>", self._canvas_double_click)
        self.canvas.bind("<Button-2>", self._canvas_delete)
        self.canvas.bind("<Button-3>", self._canvas_delete)
        self.canvas.bind("<Motion>", self._canvas_motion)
        self.canvas.bind("<Leave>", self._canvas_leave)
        self.canvas.bind("<Shift-MouseWheel>", self._horizontal_wheel)
        self.canvas.bind("<Command-MouseWheel>", self._zoom_wheel)
        self.canvas.bind("<Control-MouseWheel>", self._zoom_wheel)
        self.canvas.bind("<MouseWheel>", self._vertical_wheel)
        self.canvas.bind("<Button-4>", self._vertical_wheel)
        self.canvas.bind("<Button-5>", self._vertical_wheel)
        self.x_scroll.bind("<MouseWheel>", self._horizontal_wheel)
        self.x_scroll.bind("<Shift-MouseWheel>", self._horizontal_wheel)
        self.y_scroll.bind("<MouseWheel>", self._vertical_wheel)
        self.y_scroll.bind("<Shift-MouseWheel>", self._horizontal_wheel)
        self.canvas.bind("<space>", self._canvas_play)
        self.canvas.bind("<Left>", lambda event: self._canvas_nudge(event, beats=-1))
        self.canvas.bind("<Right>", lambda event: self._canvas_nudge(event, beats=1))
        self.canvas.bind("<Up>", lambda event: self._canvas_nudge(event, pitches=1))
        self.canvas.bind("<Down>", lambda event: self._canvas_nudge(event, pitches=-1))
        self.canvas.bind(
            "<Shift-Up>",
            lambda event: self._canvas_nudge(event, pitches=12),
        )
        self.canvas.bind(
            "<Shift-Down>",
            lambda event: self._canvas_nudge(event, pitches=-12),
        )
        self.canvas.bind(
            "<Alt-Up>",
            lambda event: self._canvas_nudge(event, velocity=5),
        )
        self.canvas.bind(
            "<Alt-Down>",
            lambda event: self._canvas_nudge(event, velocity=-5),
        )
        self.canvas.bind(
            "<Control-Left>",
            lambda event: self._canvas_nudge(event, durations=-1),
        )
        self.canvas.bind(
            "<Control-Right>",
            lambda event: self._canvas_nudge(event, durations=1),
        )
        self.after(80, lambda: self._yview("moveto", "0.37"))

        self._rebuild_tracks()

    def _rebuild_tracks(self) -> None:
        for child in self.track_panel.winfo_children():
            child.destroy()

        header = ctk.CTkFrame(self.track_panel, fg_color="transparent", height=44)
        header.pack(fill="x", padx=12, pady=(10, 6))
        ctk.CTkLabel(
            header,
            text="轨道",
            text_color=T.TEXT,
            font=ui_font(T.TEXT_14, "bold"),
            anchor="w",
        ).pack(side="left")
        self.delete_track_button = icon_button(
            header,
            "−",
            self.delete_track,
            danger=True,
        )
        self.delete_track_button.pack(side="right")
        icon_button(header, "+", self.add_track).pack(side="right", padx=(0, 2))
        icon_button(header, "↓", lambda: self.move_track(1)).pack(side="right")
        icon_button(header, "↑", lambda: self.move_track(-1)).pack(side="right")

        chord_panel = ctk.CTkFrame(
            self.track_panel,
            fg_color="transparent",
            corner_radius=0,
        )
        chord_panel.pack(side="bottom", fill="x", padx=12, pady=12)
        ctk.CTkLabel(
            chord_panel,
            text="和弦输入",
            text_color=T.TEXT_MUTED,
            font=ui_font(T.TEXT_12),
            anchor="w",
        ).pack(fill="x", pady=(0, 5))
        chord = ctk.CTkEntry(
            chord_panel,
            height=30,
            textvariable=self.chord_var,
            corner_radius=T.RADIUS,
            border_color=T.BORDER,
            fg_color=T.SURFACE,
            text_color=T.TEXT,
            font=ui_font(T.TEXT_13, mono=True),
        )
        chord.pack(fill="x")
        chord.bind("<Return>", lambda _event: self.insert_chord())
        action_button(
            chord_panel,
            "插入到播放头",
            self.insert_chord,
            width=120,
            quiet=True,
        ).pack(fill="x", pady=(4, 0))

        mixer_panel = ctk.CTkFrame(
            self.track_panel,
            fg_color="transparent",
            corner_radius=0,
        )
        mixer_panel.pack(side="bottom", fill="x", padx=12, pady=(0, 2))
        self.track_name_var = tk.StringVar(value=self.selected_track.name)
        track_name = ctk.CTkEntry(
            mixer_panel,
            height=28,
            textvariable=self.track_name_var,
            corner_radius=T.RADIUS,
            border_color=T.BORDER,
            fg_color=T.SURFACE,
            text_color=T.TEXT,
            font=ui_font(T.TEXT_12),
        )
        track_name.pack(fill="x", pady=(0, 8))
        track_name.bind("<Return>", lambda _event: self._track_name_changed())
        track_name.bind("<FocusOut>", lambda _event: self._track_name_changed())
        self.track_volume_slider = LabeledSlider(
            mixer_panel,
            "轨道音量",
            0.0,
            1.0,
            self.selected_track.volume,
            self._track_volume_changed,
            digits=2,
        )
        self.track_volume_slider.pack(fill="x")
        self.track_volume_slider.slider.bind(
            "<ButtonPress-1>",
            lambda _event: self._push_undo(),
            add="+",
        )

        track_list = ctk.CTkScrollableFrame(
            self.track_panel,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=T.TEXT_DISABLED,
            scrollbar_button_hover_color=T.TEXT_MUTED,
        )
        track_list.pack(fill="both", expand=True, padx=(6, 3), pady=(0, 4))

        for index, track in enumerate(self.song.tracks):
            active = index == self.selected_track_index
            row = ctk.CTkFrame(
                track_list,
                height=T.NAV_ITEM_H,
                corner_radius=T.RADIUS,
                fg_color=T.NAV_ACTIVE if active else "transparent",
            )
            row.pack(fill="x", padx=8, pady=2)
            row.pack_propagate(False)
            color = ctk.CTkFrame(
                row,
                width=3,
                height=24,
                corner_radius=2,
                fg_color=track.color,
            )
            color.pack(side="left", padx=(8, 8))
            label = ctk.CTkLabel(
                row,
                text=track.name,
                text_color=T.TEXT if active else T.TEXT_SECONDARY,
                font=ui_font(T.TEXT_13, "bold" if active else "normal"),
                anchor="w",
            )
            label.pack(side="left", fill="x", expand=True)
            count = ctk.CTkLabel(
                row,
                text=str(len(track.notes)),
                text_color=T.TEXT_MUTED,
                font=ui_font(T.TEXT_12, mono=True),
                width=24,
            )
            count.pack(side="right", padx=(0, 5))
            solo = ctk.CTkButton(
                row,
                text="S",
                command=lambda idx=index: self.toggle_track_solo(idx),
                width=26,
                height=26,
                corner_radius=T.RADIUS,
                border_width=0,
                fg_color=T.WARNING_SOFT if track.soloed else "transparent",
                hover_color=T.WARNING_SOFT,
                text_color=T.WARNING if track.soloed else T.TEXT_MUTED,
                font=ui_font(T.TEXT_12, "bold"),
            )
            solo.pack(side="right", padx=(0, 1))
            mute = ctk.CTkButton(
                row,
                text="M",
                command=lambda idx=index: self.toggle_track_mute(idx),
                width=26,
                height=26,
                corner_radius=T.RADIUS,
                border_width=0,
                fg_color=T.DANGER_SOFT if track.muted else "transparent",
                hover_color=T.DANGER_SOFT,
                text_color=T.DANGER if track.muted else T.TEXT_MUTED,
                font=ui_font(T.TEXT_12, "bold"),
            )
            mute.pack(side="right", padx=(0, 1))
            for widget in (row, label, count, color):
                widget.bind(
                    "<Button-1>",
                    lambda _event, idx=index: self.select_track(idx),
                )

    def toggle_track_mute(self, index: int) -> None:
        track = self.song.tracks[index]
        self._push_undo()
        track.muted = not track.muted
        self._rebuild_tracks()
        self.on_change()
        self.on_status(f"{track.name} {'已静音' if track.muted else '已取消静音'}")

    def toggle_track_solo(self, index: int) -> None:
        track = self.song.tracks[index]
        self._push_undo()
        track.soloed = not track.soloed
        self._rebuild_tracks()
        self.on_change()
        self.on_status(f"{track.name} {'独奏' if track.soloed else '取消独奏'}")

    def move_track(self, offset: int) -> None:
        target = self.selected_track_index + offset
        if target < 0 or target >= len(self.song.tracks):
            return
        self._push_undo()
        track = self.song.tracks.pop(self.selected_track_index)
        self.song.tracks.insert(target, track)
        self.selected_track_index = target
        self._rebuild_tracks()
        self.redraw()
        self.on_change()
        self.on_status(f"已移动轨道 {track.name}")

    def _track_name_changed(self) -> None:
        updated = self.track_name_var.get().strip()
        if not updated or updated == self.selected_track.name:
            self.track_name_var.set(self.selected_track.name)
            return
        self._push_undo()
        self.selected_track.name = updated
        self.on_change()
        self.on_status(f"轨道已重命名为 {updated}")
        self.after_idle(self._rebuild_tracks)

    def _track_volume_changed(self, value: float) -> None:
        value = max(0.0, min(1.0, value))
        if abs(value - self.selected_track.volume) < 0.001:
            return
        self.selected_track.volume = value
        self.on_change()

    def _tool_changed(self, value: str) -> None:
        self._update_canvas_cursor()
        self._clear_selection()
        self.redraw()
        self.on_status("画笔模式：拖拽空白处写入音符" if value == "画笔" else "选择模式")

    def set_tool(self, value: str) -> None:
        if value not in ("选择", "画笔"):
            return
        self.tool_var.set(value)
        self._tool_changed(value)

    def _snap_changed(self, value: str) -> None:
        self.snap_var.set(value)
        self.on_status(f"吸附精度 {value} 音符")

    def _snap_size(self) -> float:
        return self.SNAP_BEATS.get(self.snap_var.get(), 0.25)

    def _snap_beat(self, beat: float) -> float:
        size = self._snap_size()
        return round(beat / size) * size

    def _option_changed(self, _value=None) -> None:
        self._apply_song_controls()

    def _instrument_changed(self, value: str) -> None:
        if value == self.selected_track.instrument:
            return
        self._push_undo()
        self.selected_track.instrument = value
        self.on_change()
        self.on_status(f"轨道音色已切换为 {value}")

    def _apply_song_controls(self, _event=None) -> None:
        previous = (
            self.song.bpm,
            self.song.time_signature,
            self.song.key,
            self.song.scale,
            self.song.bars,
        )
        try:
            self.song.bpm = max(20, min(300, int(self.bpm_var.get())))
        except ValueError:
            self.bpm_var.set(str(self.song.bpm))
        max_note_end = max(
            (
                note.start + note.duration
                for track in self.song.tracks
                for note in track.notes
            ),
            default=0.0,
        )
        minimum_bars = max(1, int(np.ceil(max_note_end / 4.0)))
        try:
            self.song.bars = max(
                minimum_bars,
                min(128, int(self.bars_var.get())),
            )
        except ValueError:
            pass
        self.bars_var.set(str(self.song.bars))
        self.song.loop_end = self.song.bars * 4.0
        self.song.time_signature = self.signature_var.get()
        self.song.key = self.key_var.get()
        self.song.scale = next(
            (
                name
                for name, label in self.SCALE_LABELS.items()
                if label == self.scale_var.get()
            ),
            self.scale_var.get(),
        )
        current = (
            self.song.bpm,
            self.song.time_signature,
            self.song.key,
            self.song.scale,
            self.song.bars,
        )
        if current != previous:
            self.on_change()
            self.redraw()

    def _snapshot_state(self) -> tuple[list[Track], int, float]:
        return copy.deepcopy(self.song.tracks), self.selected_track_index, self.insert_beat

    def _push_undo(self) -> None:
        self._undo_stack.append(self._snapshot_state())
        self._undo_stack = self._undo_stack[-60:]
        self._redo_stack.clear()

    def _restore_state(self, state: tuple[list[Track], int, float]) -> None:
        tracks, track_index, insert_beat = state
        self.song.tracks = copy.deepcopy(tracks)
        self.selected_track_index = min(track_index, len(self.song.tracks) - 1)
        self.insert_beat = insert_beat
        self._clear_selection()
        self.instrument_var.set(self.selected_track.instrument)
        self.position_var.set(self._format_position(self.insert_beat))
        self._rebuild_tracks()
        self.redraw()
        self.on_change()

    def undo(self) -> None:
        if not self._undo_stack:
            self.on_status("没有可撤销的操作")
            return
        self._redo_stack.append(self._snapshot_state())
        self._restore_state(self._undo_stack.pop())
        self.on_status("已撤销")

    def redo(self) -> None:
        if not self._redo_stack:
            self.on_status("没有可重做的操作")
            return
        self._undo_stack.append(self._snapshot_state())
        self._restore_state(self._redo_stack.pop())
        self.on_status("已重做")

    def _selected_notes(self) -> list[Note]:
        return [
            note for note in self.selected_track.notes if note.id in self.selected_note_ids
        ]

    def _selected_note(self) -> Note | None:
        notes = self._selected_notes()
        if self.selected_note_id:
            primary = next(
                (note for note in notes if note.id == self.selected_note_id),
                None,
            )
            if primary is not None:
                return primary
        return notes[0] if notes else None

    def _set_selection(
        self,
        note_ids: set[str],
        primary_id: str | None = None,
    ) -> None:
        self.selected_note_ids = set(note_ids)
        self.selected_note_id = (
            primary_id
            if primary_id in self.selected_note_ids
            else next(iter(self.selected_note_ids), None)
        )
        self._sync_note_controls()

    def _clear_selection(self) -> None:
        self._set_selection(set())

    def select_all_notes(self) -> None:
        if not self.selected_track.notes:
            self.on_status("当前轨道没有音符")
            return
        ids = {note.id for note in self.selected_track.notes}
        self._set_selection(ids, self.selected_track.notes[0].id)
        self.redraw()
        self.on_status(f"已选择 {len(ids)} 个音符")

    def _set_note_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for entry in (
            self.note_start_entry,
            self.note_duration_entry,
            self.note_velocity_entry,
        ):
            entry.configure(state=state)
        for button in (
            self.quantize_button,
            self.duplicate_button,
            self.delete_note_button,
        ):
            button.configure(state=state)

    def _sync_note_controls(self) -> None:
        if not hasattr(self, "note_summary"):
            return
        notes = self._selected_notes()
        if not notes:
            self.note_summary_var.set("未选择音符")
            self.note_start_var.set("")
            self.note_duration_var.set("")
            self.note_velocity_var.set("")
            self._set_note_controls_enabled(False)
            return
        if len(notes) == 1:
            note = notes[0]
            self.note_summary_var.set(
                f"{self._pitch_name(note.pitch)}{note.pitch // 12 - 1}"
            )
        else:
            self.note_summary_var.set(f"{len(notes)} 个音符")
        self.note_start_var.set(f"{min(note.start for note in notes):g}")
        durations = {note.duration for note in notes}
        velocities = {note.velocity for note in notes}
        self.note_duration_var.set(f"{durations.pop():g}" if len(durations) == 1 else "")
        self.note_velocity_var.set(str(velocities.pop()) if len(velocities) == 1 else "")
        self._set_note_controls_enabled(True)

    def _apply_note_controls(self, _event=None) -> None:
        notes = self._selected_notes()
        if not notes:
            return
        try:
            start_text = self.note_start_var.get().strip()
            duration_text = self.note_duration_var.get().strip()
            velocity_text = self.note_velocity_var.get().strip()
            start = self._snap_beat(float(start_text)) if start_text else None
            duration = (
                max(self._snap_size(), self._snap_beat(float(duration_text)))
                if duration_text
                else None
            )
            velocity = (
                max(1, min(127, int(velocity_text)))
                if velocity_text
                else None
            )
        except ValueError:
            self._sync_note_controls()
            self.on_status("音符参数必须是数字")
            return
        earliest = min(note.start for note in notes)
        latest = max(note.start + (duration or note.duration) for note in notes)
        start_delta = (start - earliest) if start is not None else 0.0
        start_delta = max(-earliest, min(start_delta, self.song.bars * 4 - latest))
        changed = any(
            start_delta
            or (duration is not None and note.duration != duration)
            or (velocity is not None and note.velocity != velocity)
            for note in notes
        )
        if not changed:
            self._sync_note_controls()
            return
        self._push_undo()
        for note in notes:
            note.start += start_delta
            if duration is not None:
                note.duration = min(duration, self.song.bars * 4 - note.start)
            if velocity is not None:
                note.velocity = velocity
        self._sync_note_controls()
        self.redraw()
        self.on_change()
        self.on_status(f"已更新 {len(notes)} 个音符")

    def quantize_selected(self) -> None:
        notes = self._selected_notes()
        if not notes:
            self.on_status("请先选择音符")
            return
        updates = []
        for note in notes:
            duration = max(self._snap_size(), self._snap_beat(note.duration))
            start = min(
                self._snap_beat(note.start),
                self.song.bars * 4 - duration,
            )
            updates.append((note, start, duration))
        if all(
            (start, duration) == (note.start, note.duration)
            for note, start, duration in updates
        ):
            self.on_status("所选音符已在当前网格上")
            return
        self._push_undo()
        for note, start, duration in updates:
            note.start = start
            note.duration = duration
        self._sync_note_controls()
        self.redraw()
        self.on_change()
        self.on_status(f"已量化 {len(notes)} 个音符")

    def duplicate_selected_note(self) -> None:
        notes = self._selected_notes()
        if not notes:
            self.on_status("请先选择音符")
            return
        earliest = min(note.start for note in notes)
        latest = max(note.start + note.duration for note in notes)
        offset = max(self._snap_size(), self._snap_beat(latest - earliest))
        if latest + offset > self.song.bars * 4:
            self.on_status("右侧空间不足，无法复制")
            return
        self._push_undo()
        duplicates = [
            Note(
                pitch=note.pitch,
                start=note.start + offset,
                duration=note.duration,
                velocity=note.velocity,
            )
            for note in notes
        ]
        self.selected_track.notes.extend(duplicates)
        self._set_selection(
            {note.id for note in duplicates},
            duplicates[0].id,
        )
        self._rebuild_tracks()
        self.redraw()
        self.on_change()
        self._preview_note(duplicates[0])
        self.on_status(f"已复制 {len(duplicates)} 个音符")

    def nudge_selected(
        self,
        *,
        beats: float = 0.0,
        pitches: int = 0,
        durations: float = 0.0,
        velocity: int = 0,
    ) -> None:
        notes = self._selected_notes()
        if not notes:
            if beats:
                target = self._snap_beat(self.insert_beat + beats)
                self._set_edit_cursor(target, clear_selection=False)
            return
        earliest = min(note.start for note in notes)
        latest = max(note.start + note.duration for note in notes)
        lowest = min(note.pitch for note in notes)
        highest = max(note.pitch for note in notes)
        beats = max(-earliest, min(beats, self.song.bars * 4 - latest))
        pitches = max(self.PITCH_LOW - lowest, min(pitches, self.PITCH_HIGH - highest))
        updates = []
        for note in notes:
            duration = max(
                self._snap_size(),
                min(note.duration + durations, self.song.bars * 4 - note.start - beats),
            )
            note_velocity = max(1, min(127, note.velocity + velocity))
            updates.append(
                (
                    note,
                    note.start + beats,
                    note.pitch + pitches,
                    duration,
                    note_velocity,
                )
            )
        if all(
            (note.start, note.pitch, note.duration, note.velocity)
            == (start, pitch, duration, note_velocity)
            for note, start, pitch, duration, note_velocity in updates
        ):
            return
        self._push_undo()
        for note, start, pitch, duration, note_velocity in updates:
            note.start = start
            note.pitch = pitch
            note.duration = duration
            note.velocity = note_velocity
        self._sync_note_controls()
        self.redraw()
        self.on_change()
        self.on_status(f"已调整 {len(notes)} 个音符")

    def select_track(self, index: int) -> None:
        self._reset_delete_track()
        self.selected_track_index = max(0, min(index, len(self.song.tracks) - 1))
        self.instrument_var.set(self.selected_track.instrument)
        self._clear_selection()
        self._rebuild_tracks()
        self.redraw()

    def add_track(self) -> None:
        self._push_undo()
        index = len(self.song.tracks) + 1
        colors = ("#006CFF", "#18A57A", "#B66B18", "#8B5CF6", "#D84A4A")
        self.song.tracks.append(
            Track(name=f"轨道 {index}", color=colors[(index - 1) % len(colors)])
        )
        self.selected_track_index = len(self.song.tracks) - 1
        self.instrument_var.set(self.selected_track.instrument)
        self._clear_selection()
        self._rebuild_tracks()
        self.redraw()
        self.on_change()

    def delete_track(self) -> None:
        if len(self.song.tracks) <= 1:
            self.on_status("工程至少保留一条轨道")
            return
        if not self._delete_armed:
            self._delete_armed = True
            self.delete_track_button.configure(fg_color=T.DANGER_SOFT)
            self.on_status(f"再次点击 − 删除「{self.selected_track.name}」")
            self._delete_reset_after = self.after(2400, self._reset_delete_track)
            return
        self._reset_delete_track()
        self._push_undo()
        removed = self.song.tracks.pop(self.selected_track_index)
        self.selected_track_index = max(0, self.selected_track_index - 1)
        self.instrument_var.set(self.selected_track.instrument)
        self._clear_selection()
        self._rebuild_tracks()
        self.redraw()
        self.on_change()
        self.on_status(f"已删除轨道 {removed.name}")

    def _reset_delete_track(self) -> None:
        if self._delete_reset_after is not None:
            try:
                self.after_cancel(self._delete_reset_after)
            except ValueError:
                pass
        self._delete_reset_after = None
        self._delete_armed = False
        if hasattr(self, "delete_track_button"):
            self.delete_track_button.configure(fg_color="transparent")

    def _canvas_position(self, event, *, snap: bool = True) -> tuple[float, int]:
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        raw_beat = max(0.0, (x - self.LABEL_W) / (self.SUBDIVISIONS * self.cell_w))
        beat = self._snap_beat(raw_beat) if snap else raw_beat
        row = int((y - self.RULER_H) // self.ROW_H)
        pitch = self.PITCH_HIGH - row
        return beat, pitch

    def _note_at_event(self, event) -> Note | None:
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        for item in reversed(self.canvas.find_overlapping(x, y, x, y)):
            if item in self._note_items:
                return self._note_items[item]
        return None

    def _note_bounds(self, note: Note) -> tuple[float, float]:
        x1 = self.LABEL_W + note.start * self.SUBDIVISIONS * self.cell_w + 1
        x2 = x1 + max(8, note.duration * self.SUBDIVISIONS * self.cell_w - 2)
        return x1, x2

    def _note_rectangle(self, note: Note) -> tuple[float, float, float, float]:
        x1, x2 = self._note_bounds(note)
        row = self.PITCH_HIGH - note.pitch
        y1 = self.RULER_H + row * self.ROW_H + 2
        y2 = y1 + self.ROW_H - 4
        return x1, y1, x2, y2

    @staticmethod
    def _event_additive(event) -> bool:
        state = int(getattr(event, "state", 0) or 0)
        return bool(state & (0x0001 | 0x0004 | 0x0008 | 0x0010 | 0x100000))

    def _note_edge_at_event(self, event, note: Note) -> bool:
        x = self.canvas.canvasx(event.x)
        _x1, x2 = self._note_bounds(note)
        return abs(x - x2) <= 7

    def _playhead_x(self) -> float:
        return self.LABEL_W + self.insert_beat * self.SUBDIVISIONS * self.cell_w

    def _playhead_at_event(self, event) -> bool:
        x = self.canvas.canvasx(event.x)
        return event.y < self.RULER_H or abs(x - self._playhead_x()) <= 7

    def _timeline_height(self) -> int:
        rows = self.PITCH_HIGH - self.PITCH_LOW + 1
        return self.RULER_H + rows * self.ROW_H

    def _draw_hover_preview(self) -> None:
        self.canvas.delete("hover_preview")
        if self._hover_beat is None or self._scrubbing_playhead:
            return
        x = self.LABEL_W + self._hover_beat * self.SUBDIVISIONS * self.cell_w
        top = self.canvas.canvasy(0)
        self.canvas.create_line(
            x,
            top + self.RULER_H,
            x,
            self._timeline_height(),
            fill=T.TEXT_DISABLED,
            width=1,
            dash=(3, 3),
            tags="hover_preview",
        )
        self.canvas.create_line(
            x,
            top + self.RULER_H - 6,
            x,
            top + self.RULER_H,
            fill=T.TEXT_MUTED,
            width=1,
            tags="hover_preview",
        )

    def _update_canvas_cursor(self, cursor: str | None = None) -> None:
        if not hasattr(self, "canvas"):
            return
        default = "crosshair" if self.tool_var.get() == "画笔" else "arrow"
        self.canvas.configure(cursor=cursor or default)

    def _canvas_motion(self, event) -> None:
        if self._drag_note is not None or self._drawing_note is not None:
            return
        x = self.canvas.canvasx(event.x)
        timeline_left = self.canvas.canvasx(0) + self.LABEL_W
        if x >= timeline_left and 0 <= event.y <= self.canvas.winfo_height():
            raw_beat, _pitch = self._canvas_position(event, snap=False)
            self._hover_beat = min(raw_beat, self.song.bars * 4.0)
        else:
            self._hover_beat = None
        self._draw_hover_preview()
        note = self._note_at_event(event)
        if x >= timeline_left and self._playhead_at_event(event):
            self._update_canvas_cursor("sb_h_double_arrow")
        elif note is not None and self._note_edge_at_event(event, note):
            self._update_canvas_cursor("sb_h_double_arrow")
        elif note is not None:
            self._update_canvas_cursor("hand2")
        else:
            self._update_canvas_cursor()

    def _canvas_leave(self, _event=None) -> None:
        self._hover_beat = None
        self.canvas.delete("hover_preview")
        self._update_canvas_cursor()

    def _canvas_play(self, _event=None) -> str:
        self.on_play()
        return "break"

    def _canvas_nudge(
        self,
        _event=None,
        *,
        beats: int = 0,
        pitches: int = 0,
        durations: int = 0,
        velocity: int = 0,
    ) -> str:
        snap = self._snap_size()
        self.nudge_selected(
            beats=beats * snap,
            pitches=pitches,
            durations=durations * snap,
            velocity=velocity,
        )
        return "break"

    def _preview_note(self, note: Note) -> None:
        if self.preview_var.get():
            self.on_preview(note.pitch, self.selected_track.instrument, note.velocity)

    def _canvas_click(self, event) -> None:
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        additive = self._event_additive(event)
        self._marquee_start = None
        self._marquee_current = None
        if x < self.canvas.canvasx(0) + self.LABEL_W:
            if event.y >= self.RULER_H:
                _beat, pitch = self._canvas_position(event)
                if self.PITCH_LOW <= pitch <= self.PITCH_HIGH:
                    self.on_seek()
                    self.on_preview(pitch, self.selected_track.instrument, 96)
            return
        if self._playhead_at_event(event):
            raw_beat, _pitch = self._canvas_position(event, snap=False)
            if raw_beat > self.song.bars * 4:
                return
            self._scrubbing_playhead = True
            self._hover_beat = None
            self.canvas.delete("hover_preview")
            self.on_seek()
            self._set_edit_cursor(
                raw_beat,
                clear_selection=False,
                seek=False,
                announce=False,
            )
            return
        beat, pitch = self._canvas_position(event)
        if beat < 0 or beat >= self.song.bars * 4:
            return
        existing = self._note_at_event(event)
        if existing:
            if additive:
                selected = set(self.selected_note_ids)
                if existing.id in selected:
                    selected.remove(existing.id)
                else:
                    selected.add(existing.id)
                self._set_selection(selected, existing.id)
                self.redraw()
                if existing.id not in selected:
                    self.on_status(f"已选择 {len(selected)} 个音符")
                    return
            elif existing.id not in self.selected_note_ids:
                self._set_selection({existing.id}, existing.id)
            else:
                self._set_selection(set(self.selected_note_ids), existing.id)
            self._drag_note = existing
            self._drag_mode = "resize" if self._note_edge_at_event(event, existing) else "move"
            self._drag_changed = False
            raw_beat, _raw_pitch = self._canvas_position(event, snap=False)
            self._drag_offset_beat = raw_beat - existing.start
            self._drag_offset_pitch = pitch - existing.pitch
            self._drag_originals = {
                note.id: (note.start, note.pitch, note.duration)
                for note in self._selected_notes()
            }
            self._history_pushed = False
            self.redraw()
            self._preview_note(existing)
            return
        self._drag_note = None
        if pitch < self.PITCH_LOW or pitch > self.PITCH_HIGH:
            return
        if self.tool_var.get() == "画笔":
            self.on_seek()
            self._push_undo()
            self._history_pushed = True
            self._drawing_note = self._create_note(
                beat,
                pitch,
                duration=self._snap_size(),
            )
            self._set_selection(
                {self._drawing_note.id},
                self._drawing_note.id,
            )
            self.redraw()
            self._preview_note(self._drawing_note)
            return
        if not additive:
            self._clear_selection()
            self.redraw()
        self._marquee_start = (x, y)
        self._marquee_current = (x, y)
        self._marquee_additive = additive

    def _set_edit_cursor(
        self,
        beat: float,
        *,
        clear_selection: bool = False,
        seek: bool = True,
        announce: bool = True,
    ) -> None:
        if seek:
            self.on_seek()
        self.insert_beat = max(0.0, min(beat, self.song.bars * 4.0))
        self.position_var.set(self._format_position(self.insert_beat))
        if clear_selection:
            self._clear_selection()
        self.canvas.delete("edit_cursor")
        self._draw_edit_cursor(self._timeline_height())
        self.canvas.tag_raise("piano")
        if announce:
            self.on_status(f"播放位置 {self._format_position(self.insert_beat)}")

    def _create_note(
        self,
        beat: float,
        pitch: int,
        duration: float = 1.0,
    ) -> Note:
        note = Note(pitch=pitch, start=beat, duration=duration)
        self.selected_track.notes.append(note)
        return note

    def _canvas_drag(self, event) -> None:
        if self._scrubbing_playhead:
            raw_beat, _pitch = self._canvas_position(event, snap=False)
            self._set_edit_cursor(
                raw_beat,
                clear_selection=False,
                seek=False,
                announce=False,
            )
            return
        if self._drawing_note is not None:
            beat, _pitch = self._canvas_position(event)
            max_end = self.song.bars * 4
            end = max(
                self._drawing_note.start + self._snap_size(),
                min(max_end, beat + self._snap_size()),
            )
            self._drawing_note.duration = end - self._drawing_note.start
            self._sync_note_controls()
            self.redraw()
            return
        if self._marquee_start is not None:
            x = self.canvas.canvasx(event.x)
            y = self.canvas.canvasy(event.y)
            self._marquee_current = (x, y)
            x1, y1 = self._marquee_start
            if abs(x - x1) + abs(y - y1) < 5:
                return
            self.canvas.delete("marquee")
            self.canvas.create_rectangle(
                x1,
                y1,
                x,
                y,
                fill=T.ACCENT_SOFT,
                outline=T.ACCENT,
                width=1,
                stipple="gray25",
                tags="marquee",
            )
            return
        if self._drag_note is None:
            return
        raw_beat, pitch = self._canvas_position(event, snap=False)
        originals = self._drag_originals
        if self._drag_mode == "resize":
            end = self._snap_beat(raw_beat)
            primary_start, _primary_pitch, primary_duration = originals[self._drag_note.id]
            duration = max(
                self._snap_size(),
                min(self.song.bars * 4, end) - primary_start,
            )
            duration_delta = duration - primary_duration
            updates = []
            for note in self._selected_notes():
                start, note_pitch, note_duration = originals[note.id]
                updated_duration = max(
                    self._snap_size(),
                    min(note_duration + duration_delta, self.song.bars * 4 - start),
                )
                updates.append((note, start, note_pitch, updated_duration))
            if all(note.duration == updated for note, _start, _pitch, updated in updates):
                return
            if not self._history_pushed:
                self._push_undo()
                self._history_pushed = True
            for note, start, note_pitch, updated_duration in updates:
                note.start = start
                note.pitch = note_pitch
                note.duration = updated_duration
            self._drag_changed = True
            self._sync_note_controls()
            self.redraw()
            return
        primary_start, primary_pitch, _primary_duration = originals[self._drag_note.id]
        target_start = self._snap_beat(raw_beat - self._drag_offset_beat)
        target_pitch = pitch - self._drag_offset_pitch
        beat_delta = target_start - primary_start
        pitch_delta = target_pitch - primary_pitch
        earliest = min(start for start, _pitch, _duration in originals.values())
        latest = max(
            start + duration for start, _pitch, duration in originals.values()
        )
        lowest = min(note_pitch for _start, note_pitch, _duration in originals.values())
        highest = max(note_pitch for _start, note_pitch, _duration in originals.values())
        beat_delta = max(
            -earliest,
            min(beat_delta, self.song.bars * 4 - latest),
        )
        pitch_delta = max(
            self.PITCH_LOW - lowest,
            min(pitch_delta, self.PITCH_HIGH - highest),
        )
        if beat_delta == 0 and pitch_delta == 0:
            return
        if not self._history_pushed:
            self._push_undo()
            self._history_pushed = True
        for note in self._selected_notes():
            start, note_pitch, duration = originals[note.id]
            note.start = start + beat_delta
            note.pitch = note_pitch + pitch_delta
            note.duration = duration
        self._drag_changed = True
        self._sync_note_controls()
        self.redraw()
        if pitch_delta:
            self._preview_note(self._drag_note)

    def _canvas_release(self, _event) -> None:
        if self._scrubbing_playhead:
            self._scrubbing_playhead = False
            self.on_status(f"播放位置 {self._format_position(self.insert_beat)}")
            return
        if self._drawing_note is not None:
            note = self._drawing_note
            self._drawing_note = None
            self._rebuild_tracks()
            self._sync_note_controls()
            self.on_change()
            self.on_status(
                f"已写入 {self._pitch_name(note.pitch)}{note.pitch // 12 - 1}"
                f" · {note.duration:g} 拍"
            )
        if self._marquee_start is not None:
            start = self._marquee_start
            current = self._marquee_current or start
            moved = abs(current[0] - start[0]) + abs(current[1] - start[1]) >= 5
            self._marquee_start = None
            self._marquee_current = None
            self.canvas.delete("marquee")
            if moved:
                x1, x2 = sorted((start[0], current[0]))
                y1, y2 = sorted((start[1], current[1]))
                selected = set(self.selected_note_ids) if self._marquee_additive else set()
                for note in self.selected_track.notes:
                    nx1, ny1, nx2, ny2 = self._note_rectangle(note)
                    if nx2 >= x1 and nx1 <= x2 and ny2 >= y1 and ny1 <= y2:
                        selected.add(note.id)
                self._set_selection(selected)
                self.redraw()
                self.on_status(f"已选择 {len(selected)} 个音符")
            return
        if self._drag_note is not None and self._drag_changed:
            self.on_change()
            count = len(self.selected_note_ids)
            if self._drag_mode == "resize":
                self.on_status(f"已调整 {count} 个音符的时长")
            else:
                self.on_status(f"已移动 {count} 个音符")
        self._drag_note = None
        self._drag_originals = {}
        self._drag_changed = False
        self._history_pushed = False
        self._update_canvas_cursor()

    def _canvas_double_click(self, event) -> None:
        self._drag_note = None
        if self._note_at_event(event) is not None:
            return
        x = self.canvas.canvasx(event.x)
        if x < self.canvas.canvasx(0) + self.LABEL_W or event.y < self.RULER_H:
            return
        beat, pitch = self._canvas_position(event)
        if not (0 <= beat < self.song.bars * 4):
            return
        if not (self.PITCH_LOW <= pitch <= self.PITCH_HIGH):
            return
        self.on_seek()
        self._push_undo()
        note = self._create_note(beat, pitch)
        self._set_selection({note.id}, note.id)
        self._rebuild_tracks()
        self.redraw()
        self.on_change()
        self._preview_note(note)
        self.on_status(f"已写入 {self._pitch_name(note.pitch)}{note.pitch // 12 - 1}")

    def _canvas_delete(self, event) -> None:
        self._drag_note = None
        note = self._note_at_event(event)
        if note is None:
            return
        note_ids = (
            set(self.selected_note_ids)
            if note.id in self.selected_note_ids
            else {note.id}
        )
        self._remove_notes(note_ids)

    def _remove_notes(self, note_ids: set[str]) -> None:
        if not note_ids:
            return
        self._push_undo()
        self.selected_track.notes = [
            note for note in self.selected_track.notes if note.id not in note_ids
        ]
        self._clear_selection()
        self._rebuild_tracks()
        self.redraw()
        self.on_change()
        self.on_status(f"已删除 {len(note_ids)} 个音符")

    def delete_selected_note(self) -> None:
        self._remove_notes(set(self.selected_note_ids))

    def insert_chord(self) -> None:
        try:
            pitches = chord_to_midi(self.chord_var.get())
        except ValueError:
            self.on_status("无法识别这个和弦，请输入 Cmaj、Am 或 G7")
            return
        self._push_undo()
        inserted = []
        for pitch in pitches:
            inserted.append(
                Note(
                    pitch=pitch,
                    start=self.insert_beat,
                    duration=2.0,
                    velocity=86,
                )
            )
        self.selected_track.notes.extend(inserted)
        self._set_selection({note.id for note in inserted}, inserted[0].id)
        self._rebuild_tracks()
        self.redraw()
        self.on_change()
        self.on_status(f"已插入和弦 {self.chord_var.get()}")

    @staticmethod
    def _pitch_name(pitch: int) -> str:
        return ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")[pitch % 12]

    @staticmethod
    def _format_position(beat: float) -> str:
        sixteenth = max(0, int(beat * 4))
        bar = sixteenth // 16 + 1
        beat_in_bar = (sixteenth % 16) // 4 + 1
        subdivision = sixteenth % 4 + 1
        return f"{bar:02d}:{beat_in_bar:02d}:{subdivision:02d}"

    def redraw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        self._note_items.clear()
        rows = self.PITCH_HIGH - self.PITCH_LOW + 1
        columns = self.song.bars * 4 * self.SUBDIVISIONS
        width = self.LABEL_W + columns * self.cell_w
        height = self.RULER_H + rows * self.ROW_H
        canvas.configure(scrollregion=(0, 0, width, height))

        canvas.create_rectangle(
            0,
            0,
            width,
            self.RULER_H,
            fill=T.NAV_BG,
            outline="",
        )

        for row, pitch in enumerate(range(self.PITCH_HIGH, self.PITCH_LOW - 1, -1)):
            y = self.RULER_H + row * self.ROW_H
            black = pitch % 12 in (1, 3, 6, 8, 10)
            in_scale = is_in_scale(pitch, self.song.key, self.song.scale)
            fill = "#FAFAFC" if black else T.SURFACE
            if self.scale_warning_var.get() and not in_scale:
                fill = T.OUT_OF_SCALE
            canvas.create_rectangle(
                self.LABEL_W,
                y,
                width,
                y + self.ROW_H,
                fill=fill,
                outline="",
            )

        for subdivision in range(columns + 1):
            x = self.LABEL_W + subdivision * self.cell_w
            if subdivision % (self.SUBDIVISIONS * 4) == 0:
                color, line_width = T.GRID_BAR, 2
            elif subdivision % self.SUBDIVISIONS == 0:
                color, line_width = T.GRID_BEAT, 1
            else:
                color, line_width = T.GRID_SUB, 1
            canvas.create_line(x, self.RULER_H, x, height, fill=color, width=line_width)

        for note in self.selected_track.notes:
            row = self.PITCH_HIGH - note.pitch
            if row < 0 or row >= rows:
                continue
            x1, y1, x2, y2 = self._note_rectangle(note)
            selected = note.id in self.selected_note_ids
            primary = note.id == self.selected_note_id
            item = canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill=T.NOTE_SELECTED if selected else self.selected_track.color,
                outline=T.ACCENT if selected else "",
                width=2 if selected else 1,
            )
            self._note_items[item] = note
            velocity_x = x1 + max(2, (x2 - x1 - 4) * note.velocity / 127)
            velocity_line = canvas.create_line(
                x1 + 3,
                y2 - 3,
                velocity_x,
                y2 - 3,
                fill="#FFFFFF",
                width=1,
            )
            self._note_items[velocity_line] = note
            if primary:
                handle = canvas.create_line(
                    x2 - 2,
                    y1 + 3,
                    x2 - 2,
                    y2 - 3,
                    fill="#FFFFFF",
                    width=2,
                )
                self._note_items[handle] = note

        self._draw_timeline_overlay()
        self._draw_edit_cursor(height)
        self._draw_piano_overlay()
        self.after_idle(self._refresh_canvas_overlays)

    def _draw_timeline_overlay(self) -> None:
        canvas = self.canvas
        canvas.delete("ruler_overlay")
        top = canvas.canvasy(0)
        left = canvas.canvasx(0)
        right = canvas.canvasx(canvas.winfo_width())
        canvas.create_rectangle(
            left,
            top,
            right,
            top + self.RULER_H,
            fill=T.NAV_BG,
            outline="",
            tags="ruler_overlay",
        )
        for bar in range(self.song.bars + 1):
            x = self.LABEL_W + bar * 4 * self.cell_w * self.SUBDIVISIONS
            if left + self.LABEL_W <= x <= right:
                canvas.create_text(
                    x + 5,
                    top + self.RULER_H / 2,
                    text=str(bar + 1),
                    fill=T.TEXT_MUTED,
                    font=("SF Mono", 9),
                    anchor="w",
                    tags="ruler_overlay",
                )

    def _draw_piano_overlay(self) -> None:
        if not hasattr(self, "canvas"):
            return
        canvas = self.canvas
        canvas.delete("piano")
        left = canvas.canvasx(0)
        top = canvas.canvasy(0)
        canvas.create_rectangle(
            left,
            top,
            left + self.LABEL_W,
            top + self.RULER_H,
            fill=T.NAV_BG,
            outline="",
            tags="piano",
        )
        for row, pitch in enumerate(range(self.PITCH_HIGH, self.PITCH_LOW - 1, -1)):
            y = self.RULER_H + row * self.ROW_H
            black = pitch % 12 in (1, 3, 6, 8, 10)
            canvas.create_rectangle(
                left,
                y,
                left + self.LABEL_W,
                y + self.ROW_H,
                fill=T.PIANO_BLACK if black else T.SURFACE,
                outline=T.BORDER,
                tags="piano",
            )
            if pitch % 12 == 0:
                canvas.create_text(
                    left + self.LABEL_W - 6,
                    y + self.ROW_H / 2,
                    text=f"C{pitch // 12 - 1}",
                    fill="#FFFFFF" if black else T.TEXT_SECONDARY,
                    font=("SF Mono", 9),
                    anchor="e",
                    tags="piano",
                )
        canvas.tag_raise("piano")

    def _draw_edit_cursor(self, height: int) -> None:
        x = self._playhead_x()
        top = self.canvas.canvasy(0)
        self.canvas.create_line(
            x,
            top,
            x,
            height,
            fill=T.ACCENT,
            width=2,
            tags="edit_cursor",
        )
        self.canvas.create_polygon(
            x - 7,
            top,
            x + 7,
            top,
            x,
            top + 9,
            fill=T.ACCENT,
            outline="",
            tags="edit_cursor",
        )

    def _xview(self, *args) -> None:
        self.canvas.xview(*args)
        self._hover_beat = None
        self.canvas.delete("hover_preview")
        self._refresh_canvas_overlays()

    def _yview(self, *args) -> None:
        self.canvas.yview(*args)
        self._hover_beat = None
        self.canvas.delete("hover_preview")
        self._refresh_canvas_overlays()

    def _refresh_canvas_overlays(self) -> None:
        self._draw_timeline_overlay()
        self.canvas.delete("edit_cursor")
        self._draw_edit_cursor(self._timeline_height())
        self._draw_piano_overlay()

    def _horizontal_wheel(self, event) -> str:
        delta = self._normalized_wheel_delta(event)
        self._scroll_canvas_pixels(horizontal=-delta * 32)
        return "break"

    def _zoom_wheel(self, event) -> str:
        self.zoom_horizontal(4 if event.delta > 0 else -4)
        return "break"

    def zoom_horizontal(self, amount: int) -> None:
        previous_width = self.LABEL_W + self.song.bars * 4 * self.SUBDIVISIONS * self.cell_w
        center_x = self.canvas.canvasx(self.canvas.winfo_width() / 2)
        center_ratio = center_x / max(1, previous_width)
        updated = max(14, min(46, self.cell_w + amount))
        if updated == self.cell_w:
            return
        self.cell_w = updated
        self.redraw()
        new_width = self.LABEL_W + self.song.bars * 4 * self.SUBDIVISIONS * self.cell_w
        viewport = max(1, self.canvas.winfo_width())
        target = (center_ratio * new_width - viewport / 2) / max(1, new_width)
        self.canvas.xview_moveto(max(0.0, min(1.0, target)))
        self._refresh_canvas_overlays()
        self.on_status(f"时间轴缩放 {self.cell_w / self.CELL_W:.1f}×")

    def _vertical_wheel(self, event) -> str:
        if getattr(event, "num", None) == 4:
            delta = 1.0
        elif getattr(event, "num", None) == 5:
            delta = -1.0
        else:
            delta = self._normalized_wheel_delta(event)
        self._scroll_canvas_pixels(vertical=-delta * 24)
        return "break"

    @staticmethod
    def _normalized_wheel_delta(event) -> float:
        delta = float(getattr(event, "delta", 0) or 0)
        if abs(delta) >= 120:
            delta /= 120.0
        return max(-6.0, min(6.0, delta))

    def _scroll_canvas_pixels(
        self,
        *,
        horizontal: float = 0.0,
        vertical: float = 0.0,
    ) -> None:
        if horizontal:
            total = self.LABEL_W + self.song.bars * 4 * self.SUBDIVISIONS * self.cell_w
            viewport = self.canvas.winfo_width()
            offset = self.canvas.xview()[0] * total + horizontal
            offset = max(0.0, min(offset, max(0.0, total - viewport)))
            self._xview("moveto", offset / max(1.0, total))
        if vertical:
            total = self._timeline_height()
            viewport = self.canvas.winfo_height()
            offset = self.canvas.yview()[0] * total + vertical
            offset = max(0.0, min(offset, max(0.0, total - viewport)))
            self._yview("moveto", offset / max(1.0, total))

    def _playback_start(self) -> float:
        if self.insert_beat >= self.song.loop_end:
            return self.song.loop_start
        return max(self.song.loop_start, self.insert_beat)

    def render_audio(self, sample_rate: int = 44100):
        self._apply_song_controls()
        rendered = render_song(
            self.song,
            sample_rate=sample_rate,
            loop_only=False,
            stereo=True,
        )
        start_beat = self._playback_start()
        start = int(start_beat * 60.0 / self.song.bpm * sample_rate)
        end = int(self.song.loop_end * 60.0 / self.song.bpm * sample_rate)
        output = rendered[start:end]
        if self.metronome_var.get():
            output = self._add_metronome(output, start_beat, sample_rate)
        return output

    def _add_metronome(
        self,
        rendered: np.ndarray,
        start_beat: float,
        sample_rate: int,
    ) -> np.ndarray:
        output = np.asarray(rendered, dtype=np.float32).copy()
        if not len(output):
            return output
        seconds_per_beat = 60.0 / max(20, self.song.bpm)
        click_frames = max(1, int(0.035 * sample_rate))
        click_time = np.arange(click_frames, dtype=np.float32) / float(sample_rate)
        first_beat = int(np.ceil(start_beat))
        for beat in range(first_beat, int(np.ceil(self.song.loop_end))):
            start = int((beat - start_beat) * seconds_per_beat * sample_rate)
            if start >= len(output):
                break
            frequency = 1320.0 if beat % 4 == 0 else 880.0
            click = np.sin(2.0 * np.pi * frequency * click_time)
            click *= np.exp(-click_time * 70.0) * 0.24
            end = min(len(output), start + click_frames)
            if output.ndim == 2:
                output[start:end, :] += click[: end - start, None]
            else:
                output[start:end] += click[: end - start]
        return np.tanh(output).astype(np.float32)

    def should_loop(self) -> bool:
        return self.loop_var.get()

    def jump_to_loop_start(self) -> None:
        self.insert_beat = self.song.loop_start
        self.position_var.set(self._format_position(self.insert_beat))
        self.redraw()

    def duration(self) -> float:
        full_loop = song_duration(self.song, loop_only=True)
        elapsed = (self._playback_start() - self.song.loop_start) * 60.0 / self.song.bpm
        return max(0.05, full_loop - elapsed)

    def start_playhead(self) -> None:
        self.stop_playhead()
        self._playhead_start_beat = self._playback_start()
        self.insert_beat = self._playhead_start_beat
        self._playhead_started = time.monotonic()
        self._playhead_duration = max(0.05, self.duration())
        self._animate_playhead()

    def _animate_playhead(self) -> None:
        elapsed = time.monotonic() - self._playhead_started
        ratio = min(1.0, elapsed / self._playhead_duration)
        start_x = self.LABEL_W + self._playhead_start_beat * self.SUBDIVISIONS * self.cell_w
        end_x = self.LABEL_W + self.song.loop_end * self.SUBDIVISIONS * self.cell_w
        x = start_x + (end_x - start_x) * ratio
        self.insert_beat = (
            self._playhead_start_beat + (self.song.loop_end - self._playhead_start_beat) * ratio
        )
        self.position_var.set(self._format_position(self.insert_beat))
        self.canvas.delete("playhead")
        self.canvas.create_line(
            x,
            self.canvas.canvasy(0) + self.RULER_H,
            x,
            self.RULER_H + (self.PITCH_HIGH - self.PITCH_LOW + 1) * self.ROW_H,
            fill=T.ACCENT,
            width=2,
            tags="playhead",
        )
        left = self.canvas.canvasx(0)
        right = self.canvas.canvasx(self.canvas.winfo_width())
        if x > right - 40 or x < left:
            total_width = self.LABEL_W + self.song.bars * 4 * self.SUBDIVISIONS * self.cell_w
            target = (x - self.canvas.winfo_width() * 0.25) / max(1, total_width)
            self.canvas.xview_moveto(max(0.0, min(1.0, target)))
            self._refresh_canvas_overlays()
        self.canvas.tag_raise("piano")
        if ratio < 1.0:
            self._playhead_after = self.after(33, self._animate_playhead)
        else:
            self._playhead_after = None
            self.redraw()

    def set_playback_state(self, playing: bool) -> None:
        if hasattr(self, "transport_button"):
            self.transport_button.configure(text="■  停止" if playing else "▶  播放")

    def stop_playhead(self) -> None:
        if self._playhead_after:
            try:
                self.after_cancel(self._playhead_after)
            except ValueError:
                pass
        self._playhead_after = None
        if hasattr(self, "canvas"):
            self.canvas.delete("playhead")
            self.redraw()

    def destroy(self) -> None:
        self.stop_playhead()
        self._reset_delete_track()
        super().destroy()
