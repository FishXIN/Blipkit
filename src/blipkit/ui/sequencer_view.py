"""Interactive piano-roll workspace."""

from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from blipkit.core.models import Note, Song, Track
from blipkit.core.music_assistant import SCALES, chord_to_midi, is_in_scale
from blipkit.core.sequencer import render_song, song_duration
from blipkit.core.soundbank import BUILTIN_PRESETS

from . import tokens as T
from .widgets import action_button, ui_font


class SequencerView(ctk.CTkFrame):
    PITCH_LOW = 36
    PITCH_HIGH = 84
    ROW_H = 18
    CELL_W = 24
    SUBDIVISIONS = 4
    LABEL_W = 54
    RULER_H = 24

    def __init__(
        self,
        parent,
        song: Song,
        on_change: Callable[[], None],
        on_status: Callable[[str], None],
    ):
        super().__init__(parent, fg_color=T.SURFACE)
        self.song = song
        self.on_change = on_change
        self.on_status = on_status
        self.selected_track_index = 0
        self.selected_note_id: str | None = None
        self.insert_beat = 0.0
        self._note_items: dict[int, Note] = {}
        self._playhead_started = 0.0
        self._playhead_after: str | None = None
        self._playhead_duration = 0.0

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
            height=46,
            fg_color=T.SURFACE,
            corner_radius=0,
            border_width=0,
        )
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_propagate(False)
        toolbar.grid_columnconfigure(12, weight=1)

        self.song_title = ctk.CTkLabel(
            toolbar,
            text=self.song.name,
            text_color=T.TEXT,
            font=ui_font(14, "bold"),
        )
        self.song_title.grid(row=0, column=0, padx=(16, 14), pady=8)

        self.bpm_var = tk.StringVar(value=str(self.song.bpm))
        self._compact_label(toolbar, "BPM", 1)
        bpm = ctk.CTkEntry(
            toolbar,
            width=54,
            height=28,
            textvariable=self.bpm_var,
            corner_radius=T.RADIUS,
            border_color=T.BORDER,
            fg_color=T.SURFACE,
            text_color=T.TEXT,
            font=ui_font(12, mono=True),
        )
        bpm.grid(row=0, column=2, padx=(0, 12))
        bpm.bind("<Return>", self._apply_song_controls)
        bpm.bind("<FocusOut>", self._apply_song_controls)

        self.signature_var = tk.StringVar(value=self.song.time_signature)
        signature = self._option(toolbar, self.signature_var, ["4/4", "3/4", "6/8", "5/4"], 68)
        signature.grid(row=0, column=3, padx=(0, 8))

        self.key_var = tk.StringVar(value=self.song.key)
        key_menu = self._option(
            toolbar,
            self.key_var,
            ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"],
            58,
        )
        key_menu.grid(row=0, column=4, padx=(0, 8))

        self.scale_var = tk.StringVar(value=self.song.scale)
        scale = self._option(toolbar, self.scale_var, list(SCALES), 122)
        scale.grid(row=0, column=5, padx=(0, 8))

        self.instrument_var = tk.StringVar(value=self.selected_track.instrument)
        instrument = self._option(
            toolbar,
            self.instrument_var,
            [preset.name for preset in BUILTIN_PRESETS],
            148,
            command=self._instrument_changed,
        )
        instrument.grid(row=0, column=6, padx=(0, 12))

        self.chord_var = tk.StringVar(value="Cmaj")
        chord = ctk.CTkEntry(
            toolbar,
            width=72,
            height=28,
            textvariable=self.chord_var,
            corner_radius=T.RADIUS,
            border_color=T.BORDER,
            fg_color=T.SURFACE,
            font=ui_font(12, mono=True),
        )
        chord.grid(row=0, column=7, padx=(0, 6))
        chord.bind("<Return>", lambda _event: self.insert_chord())
        action_button(toolbar, "插入和弦", self.insert_chord, width=78).grid(
            row=0, column=8, padx=(0, 8)
        )

        self.scale_warning_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            toolbar,
            text="音阶提示",
            variable=self.scale_warning_var,
            command=self.redraw,
            width=76,
            checkbox_width=15,
            checkbox_height=15,
            corner_radius=2,
            border_color=T.BORDER,
            fg_color=T.ACCENT,
            hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_SECONDARY,
            font=ui_font(12),
        ).grid(row=0, column=9, padx=(4, 12))

    def _compact_label(self, parent, text: str, column: int) -> None:
        ctk.CTkLabel(
            parent,
            text=text,
            text_color=T.TEXT_MUTED,
            font=ui_font(10, mono=True),
        ).grid(row=0, column=column, padx=(0, 5))

    def _option(self, parent, variable, values, width, command=None):
        return ctk.CTkOptionMenu(
            parent,
            variable=variable,
            values=values,
            command=command or self._option_changed,
            width=width,
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
            dropdown_font=ui_font(12),
        )

    def _build_editor(self) -> None:
        body = ctk.CTkFrame(self, fg_color=T.SURFACE, corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        self.track_panel = ctk.CTkFrame(
            body,
            width=174,
            fg_color=T.SURFACE_ALT,
            corner_radius=0,
            border_width=1,
            border_color=T.BORDER,
        )
        self.track_panel.grid(row=0, column=0, sticky="nsw")
        self.track_panel.grid_propagate(False)

        grid_shell = ctk.CTkFrame(body, fg_color=T.SURFACE, corner_radius=0)
        grid_shell.grid(row=0, column=1, sticky="nsew")
        grid_shell.grid_rowconfigure(0, weight=1)
        grid_shell.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            grid_shell,
            background=T.SURFACE,
            highlightthickness=0,
            bd=0,
            cursor="crosshair",
        )
        x_scroll = ctk.CTkScrollbar(
            grid_shell,
            orientation="horizontal",
            command=self.canvas.xview,
            height=12,
            fg_color=T.SURFACE,
            button_color=T.TEXT_DISABLED,
            button_hover_color=T.TEXT_MUTED,
        )
        y_scroll = ctk.CTkScrollbar(
            grid_shell,
            orientation="vertical",
            command=self.canvas.yview,
            width=12,
            fg_color=T.SURFACE,
            button_color=T.TEXT_DISABLED,
            button_hover_color=T.TEXT_MUTED,
        )
        self.canvas.configure(
            xscrollcommand=x_scroll.set,
            yscrollcommand=y_scroll.set,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.canvas.bind("<Button-1>", self._canvas_click)
        self.canvas.bind("<Double-Button-1>", self._canvas_double_click)
        self.canvas.bind("<Button-2>", self._canvas_delete)
        self.canvas.bind("<Button-3>", self._canvas_delete)
        self.canvas.bind("<Shift-MouseWheel>", self._horizontal_wheel)
        self.canvas.bind("<MouseWheel>", self._vertical_wheel)
        self.after(80, lambda: self.canvas.yview_moveto(0.37))

        self._rebuild_tracks()

    def _rebuild_tracks(self) -> None:
        for child in self.track_panel.winfo_children():
            child.destroy()
        header = ctk.CTkFrame(self.track_panel, fg_color="transparent", height=42)
        header.pack(fill="x", padx=12, pady=(10, 6))
        ctk.CTkLabel(
            header,
            text="轨道",
            text_color=T.TEXT,
            font=ui_font(13, "bold"),
            anchor="w",
        ).pack(side="left")
        action_button(header, "+", self.add_track, width=30).pack(side="right")

        for index, track in enumerate(self.song.tracks):
            active = index == self.selected_track_index
            row = ctk.CTkFrame(
                self.track_panel,
                height=48,
                corner_radius=T.RADIUS,
                fg_color=T.ACCENT_SOFT if active else "transparent",
            )
            row.pack(fill="x", padx=8, pady=2)
            row.pack_propagate(False)
            color = ctk.CTkFrame(
                row,
                width=3,
                height=28,
                corner_radius=2,
                fg_color=track.color,
            )
            color.pack(side="left", padx=(8, 8))
            label = ctk.CTkLabel(
                row,
                text=track.name,
                text_color=T.TEXT if active else T.TEXT_SECONDARY,
                font=ui_font(12, "bold" if active else "normal"),
                anchor="w",
            )
            label.pack(side="left", fill="x", expand=True)
            count = ctk.CTkLabel(
                row,
                text=str(len(track.notes)),
                text_color=T.TEXT_MUTED,
                font=ui_font(10, mono=True),
                width=24,
            )
            count.pack(side="right", padx=(0, 5))
            for widget in (row, label, count, color):
                widget.bind(
                    "<Button-1>",
                    lambda _event, idx=index: self.select_track(idx),
                )

        action_button(
            self.track_panel,
            "删除轨道",
            self.delete_track,
            width=90,
            danger=True,
        ).pack(side="bottom", padx=12, pady=12)

    def _option_changed(self, _value=None) -> None:
        self._apply_song_controls()

    def _instrument_changed(self, value: str) -> None:
        self.selected_track.instrument = value
        self.on_change()
        self.on_status(f"轨道音色已切换为 {value}")

    def _apply_song_controls(self, _event=None) -> None:
        try:
            self.song.bpm = max(20, min(300, int(self.bpm_var.get())))
        except ValueError:
            self.bpm_var.set(str(self.song.bpm))
        self.song.time_signature = self.signature_var.get()
        self.song.key = self.key_var.get()
        self.song.scale = self.scale_var.get()
        self.on_change()
        self.redraw()

    def select_track(self, index: int) -> None:
        self.selected_track_index = max(0, min(index, len(self.song.tracks) - 1))
        self.instrument_var.set(self.selected_track.instrument)
        self.selected_note_id = None
        self._rebuild_tracks()
        self.redraw()

    def add_track(self) -> None:
        index = len(self.song.tracks) + 1
        colors = ("#5B8DEF", "#57A773", "#C58A3A", "#A56CC1", "#D46666")
        self.song.tracks.append(
            Track(name=f"轨道 {index}", color=colors[(index - 1) % len(colors)])
        )
        self.selected_track_index = len(self.song.tracks) - 1
        self.instrument_var.set(self.selected_track.instrument)
        self._rebuild_tracks()
        self.redraw()
        self.on_change()

    def delete_track(self) -> None:
        if len(self.song.tracks) <= 1:
            self.on_status("工程至少保留一条轨道")
            return
        removed = self.song.tracks.pop(self.selected_track_index)
        self.selected_track_index = max(0, self.selected_track_index - 1)
        self.instrument_var.set(self.selected_track.instrument)
        self._rebuild_tracks()
        self.redraw()
        self.on_change()
        self.on_status(f"已删除轨道 {removed.name}")

    def _canvas_position(self, event) -> tuple[float, int]:
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        subdivision = max(0, int((x - self.LABEL_W) // self.CELL_W))
        beat = subdivision / float(self.SUBDIVISIONS)
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

    def _canvas_click(self, event) -> None:
        existing = self._note_at_event(event)
        if existing:
            self.selected_note_id = existing.id
            self.insert_beat = existing.start
            self.redraw()
            return
        beat, pitch = self._canvas_position(event)
        if beat < 0 or beat >= self.song.bars * 4:
            return
        if pitch < self.PITCH_LOW or pitch > self.PITCH_HIGH:
            return
        self.selected_track.notes.append(Note(pitch=pitch, start=beat, duration=1.0))
        self.insert_beat = beat
        self.selected_note_id = self.selected_track.notes[-1].id
        self._rebuild_tracks()
        self.redraw()
        self.on_change()
        self.on_status(f"已写入 {self._pitch_name(pitch)}{pitch // 12 - 1}")

    def _canvas_double_click(self, event) -> None:
        self._remove_note(self._note_at_event(event))

    def _canvas_delete(self, event) -> None:
        self._remove_note(self._note_at_event(event))

    def _remove_note(self, note: Note | None) -> None:
        if not note:
            return
        self.selected_track.notes = [
            item for item in self.selected_track.notes if item.id != note.id
        ]
        self.selected_note_id = None
        self._rebuild_tracks()
        self.redraw()
        self.on_change()

    def delete_selected_note(self) -> None:
        note = next(
            (item for item in self.selected_track.notes if item.id == self.selected_note_id),
            None,
        )
        self._remove_note(note)

    def insert_chord(self) -> None:
        try:
            pitches = chord_to_midi(self.chord_var.get())
        except ValueError as exc:
            self.on_status(str(exc))
            return
        for pitch in pitches:
            self.selected_track.notes.append(
                Note(pitch=pitch, start=self.insert_beat, duration=2.0, velocity=86)
            )
        self._rebuild_tracks()
        self.redraw()
        self.on_change()
        self.on_status(f"已插入和弦 {self.chord_var.get()}")

    @staticmethod
    def _pitch_name(pitch: int) -> str:
        return ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")[pitch % 12]

    def redraw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        self._note_items.clear()
        rows = self.PITCH_HIGH - self.PITCH_LOW + 1
        columns = self.song.bars * 4 * self.SUBDIVISIONS
        width = self.LABEL_W + columns * self.CELL_W
        height = self.RULER_H + rows * self.ROW_H
        canvas.configure(scrollregion=(0, 0, width, height))

        canvas.create_rectangle(0, 0, width, self.RULER_H, fill=T.SURFACE_ALT, outline="")
        for beat in range(self.song.bars * 4 + 1):
            x = self.LABEL_W + beat * self.CELL_W * self.SUBDIVISIONS
            canvas.create_text(
                x + 5,
                self.RULER_H / 2,
                text=str(beat + 1),
                fill=T.TEXT_MUTED,
                font=("SF Mono", 9),
                anchor="w",
            )

        for row, pitch in enumerate(range(self.PITCH_HIGH, self.PITCH_LOW - 1, -1)):
            y = self.RULER_H + row * self.ROW_H
            black = pitch % 12 in (1, 3, 6, 8, 10)
            in_scale = is_in_scale(pitch, self.song.key, self.song.scale)
            fill = "#F3F4F6" if black else T.SURFACE
            if self.scale_warning_var.get() and not in_scale:
                fill = "#FFF8EF" if not black else "#F5EEE5"
            canvas.create_rectangle(
                self.LABEL_W,
                y,
                width,
                y + self.ROW_H,
                fill=fill,
                outline="",
            )
            key_fill = T.PIANO_BLACK if black else T.SURFACE
            canvas.create_rectangle(
                0,
                y,
                self.LABEL_W,
                y + self.ROW_H,
                fill=key_fill,
                outline=T.BORDER,
            )
            if pitch % 12 == 0:
                canvas.create_text(
                    self.LABEL_W - 6,
                    y + self.ROW_H / 2,
                    text=f"C{pitch // 12 - 1}",
                    fill="#FFFFFF" if black else T.TEXT_SECONDARY,
                    font=("SF Mono", 9),
                    anchor="e",
                )

        for subdivision in range(columns + 1):
            x = self.LABEL_W + subdivision * self.CELL_W
            if subdivision % (self.SUBDIVISIONS * 4) == 0:
                color, line_width = T.GRID_BAR, 1
            elif subdivision % self.SUBDIVISIONS == 0:
                color, line_width = T.GRID_BEAT, 1
            else:
                color, line_width = T.GRID_SUB, 1
            canvas.create_line(x, self.RULER_H, x, height, fill=color, width=line_width)

        for note in self.selected_track.notes:
            row = self.PITCH_HIGH - note.pitch
            if row < 0 or row >= rows:
                continue
            x1 = self.LABEL_W + note.start * self.SUBDIVISIONS * self.CELL_W + 1
            x2 = x1 + max(8, note.duration * self.SUBDIVISIONS * self.CELL_W - 2)
            y1 = self.RULER_H + row * self.ROW_H + 2
            y2 = y1 + self.ROW_H - 4
            selected = note.id == self.selected_note_id
            item = canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill=T.NOTE_SELECTED if selected else self.selected_track.color,
                outline="#FFFFFF" if selected else "",
                width=1,
            )
            self._note_items[item] = note

    def _horizontal_wheel(self, event) -> str:
        self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _vertical_wheel(self, event) -> str:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def render_audio(self):
        self._apply_song_controls()
        return render_song(self.song, loop_only=True, stereo=True)

    def duration(self) -> float:
        return song_duration(self.song, loop_only=True)

    def start_playhead(self) -> None:
        self.stop_playhead()
        self._playhead_started = time.monotonic()
        self._playhead_duration = max(0.05, self.duration())
        self._animate_playhead()

    def _animate_playhead(self) -> None:
        elapsed = time.monotonic() - self._playhead_started
        ratio = min(1.0, elapsed / self._playhead_duration)
        start_x = self.LABEL_W + self.song.loop_start * self.SUBDIVISIONS * self.CELL_W
        end_x = self.LABEL_W + self.song.loop_end * self.SUBDIVISIONS * self.CELL_W
        x = start_x + (end_x - start_x) * ratio
        self.canvas.delete("playhead")
        self.canvas.create_line(
            x,
            self.RULER_H,
            x,
            self.RULER_H + (self.PITCH_HIGH - self.PITCH_LOW + 1) * self.ROW_H,
            fill=T.ACCENT,
            width=2,
            tags="playhead",
        )
        if ratio < 1.0:
            self._playhead_after = self.after(33, self._animate_playhead)
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
