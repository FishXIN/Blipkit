"""Compact all-track arrangement timeline."""

from __future__ import annotations

import math
import sys
import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from blipkit.core.models import Note, Song

from . import tokens as T

FONT_UI = T.FONT_UI_MAC if sys.platform == "darwin" else T.FONT_UI_WIN
FONT_MONO = T.FONT_MONO_MAC if sys.platform == "darwin" else T.FONT_MONO_WIN


class ArrangementView(ctk.CTkFrame):
    RULER_H = 28
    ROW_H = 48
    SUBDIVISIONS = 4
    HEADER_W = 220

    def __init__(
        self,
        parent,
        on_select_track: Callable[[int], None],
        on_open_track: Callable[[int, Note | None], None],
        on_seek: Callable[[float], None],
        on_play: Callable[[], None],
        on_toggle_mute: Callable[[int], None],
        on_toggle_solo: Callable[[int], None],
        on_zoom: Callable[[int], None],
    ):
        super().__init__(
            parent,
            fg_color=T.SURFACE,
            corner_radius=T.RADIUS_PANEL,
            border_width=1,
            border_color=T.BORDER,
        )
        self.on_select_track = on_select_track
        self.on_open_track = on_open_track
        self.on_seek = on_seek
        self.on_play = on_play
        self.on_toggle_mute = on_toggle_mute
        self.on_toggle_solo = on_toggle_solo
        self.on_zoom = on_zoom
        self.song: Song | None = None
        self.selected_track_index = 0
        self.insert_beat = 0.0
        self.cell_w = 26
        self._note_items: dict[int, tuple[int, Note]] = {}
        self._scrubbing = False

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.headers = tk.Canvas(
            self,
            width=self.HEADER_W,
            background=T.NAV_BG,
            highlightthickness=0,
            bd=0,
        )
        self.timeline = tk.Canvas(
            self,
            background=T.SURFACE,
            highlightthickness=0,
            bd=0,
            cursor="arrow",
        )
        self.v_scroll = ctk.CTkScrollbar(
            self,
            orientation="vertical",
            command=self._yview,
            width=12,
            fg_color=T.SURFACE,
            button_color=T.TEXT_DISABLED,
            button_hover_color=T.TEXT_MUTED,
        )
        self.x_scroll = ctk.CTkScrollbar(
            self,
            orientation="horizontal",
            command=self._xview,
            height=12,
            fg_color=T.SURFACE,
            button_color=T.TEXT_DISABLED,
            button_hover_color=T.TEXT_MUTED,
        )
        self.timeline.configure(
            xscrollcommand=self.x_scroll.set,
            yscrollcommand=self._timeline_yset,
        )
        self.headers.grid(row=0, column=0, sticky="ns")
        self.timeline.grid(row=0, column=1, sticky="nsew")
        self.v_scroll.grid(row=0, column=2, sticky="ns")
        self.x_scroll.grid(row=1, column=1, sticky="ew")
        ctk.CTkFrame(self, fg_color=T.NAV_BG, corner_radius=0).grid(
            row=1,
            column=0,
            sticky="nsew",
        )

        self.headers.bind("<Button-1>", self._header_click)
        self.headers.bind("<Double-Button-1>", self._header_double_click)
        self.timeline.bind("<Button-1>", self._timeline_click)
        self.timeline.bind("<B1-Motion>", self._timeline_drag)
        self.timeline.bind("<ButtonRelease-1>", self._timeline_release)
        self.timeline.bind("<Double-Button-1>", self._timeline_double_click)
        self.timeline.bind("<Motion>", self._timeline_motion)
        self.timeline.bind("<Leave>", self._timeline_leave)
        self.timeline.bind("<space>", lambda _event: self._play())
        for widget in (self.headers, self.timeline, self.v_scroll):
            widget.bind("<MouseWheel>", self._vertical_wheel)
        self.timeline.bind("<Shift-MouseWheel>", self._horizontal_wheel)
        self.x_scroll.bind("<MouseWheel>", self._horizontal_wheel)
        modifier = "Command" if sys.platform == "darwin" else "Control"
        self.timeline.bind(
            f"<{modifier}-MouseWheel>",
            lambda event: self._zoom_wheel(event),
        )

    def redraw(
        self,
        song: Song,
        selected_track_index: int,
        insert_beat: float,
        cell_w: float,
    ) -> None:
        self.song = song
        self.selected_track_index = selected_track_index
        self.insert_beat = insert_beat
        self.cell_w = cell_w
        x_fraction = self.timeline.xview()[0]
        y_fraction = self.timeline.yview()[0]
        self.timeline.delete("all")
        self.headers.delete("all")
        self._note_items.clear()

        width = max(1, song.total_beats * self.SUBDIVISIONS * cell_w)
        height = self.RULER_H + max(1, len(song.tracks)) * self.ROW_H
        self.timeline.configure(scrollregion=(0, 0, width, height))
        self.headers.configure(scrollregion=(0, 0, self.HEADER_W, height))

        for index, track in enumerate(song.tracks):
            top = self.RULER_H + index * self.ROW_H
            active = index == selected_track_index
            fill = T.ACCENT_SOFT if active else T.SURFACE_ALT if index % 2 else T.SURFACE
            self.timeline.create_rectangle(
                0,
                top,
                width,
                top + self.ROW_H,
                fill=fill,
                outline="",
            )
            self.headers.create_rectangle(
                0,
                top,
                self.HEADER_W,
                top + self.ROW_H,
                fill=T.NAV_ACTIVE if active else T.NAV_BG,
                outline="",
            )
            self.headers.create_rectangle(
                10,
                top + 8,
                13,
                top + self.ROW_H - 8,
                fill=track.color,
                outline="",
            )
            self.headers.create_text(
                24,
                top + 16,
                text=track.name,
                fill=T.TEXT if active else T.TEXT_SECONDARY,
                font=(FONT_UI, 11, "bold" if active else "normal"),
                anchor="w",
            )
            self.headers.create_text(
                24,
                top + 34,
                text=track.instrument,
                fill=T.TEXT_MUTED,
                font=(FONT_UI, 9),
                anchor="w",
            )
            self.headers.create_text(
                self.HEADER_W - 52,
                top + self.ROW_H / 2,
                text="M",
                fill=T.DANGER if track.muted else T.TEXT_MUTED,
                font=(FONT_MONO, 11, "bold"),
            )
            self.headers.create_text(
                self.HEADER_W - 22,
                top + self.ROW_H / 2,
                text="S",
                fill=T.WARNING if track.soloed else T.TEXT_MUTED,
                font=(FONT_MONO, 11, "bold"),
            )
            self._draw_track_notes(index, track.notes, track.color, top)

        columns = round(song.total_beats * self.SUBDIVISIONS)
        bar_columns = max(1, round(song.beats_per_bar * self.SUBDIVISIONS))
        for subdivision in range(columns + 1):
            x = subdivision * cell_w
            if subdivision % bar_columns == 0:
                color, line_width = T.GRID_BAR, 2
            elif subdivision % self.SUBDIVISIONS == 0:
                color, line_width = T.GRID_BEAT, 1
            elif cell_w < 5:
                continue
            else:
                color, line_width = T.GRID_SUB, 1
            self.timeline.create_line(
                x,
                self.RULER_H,
                x,
                height,
                fill=color,
                width=line_width,
            )
        self.timeline.tag_raise("arrange_note")

        self.timeline.xview_moveto(x_fraction)
        self._yview("moveto", y_fraction)
        self._refresh_overlays()
        self.set_playhead(insert_beat)

    def preview_horizontal_zoom(self, cell_w: float) -> None:
        if self.song is None or cell_w <= 0 or self.cell_w <= 0:
            return
        factor = cell_w / self.cell_w
        if abs(factor - 1.0) < 0.0001:
            return
        self.timeline.scale("all", 0, 0, factor, 1)
        self.cell_w = cell_w
        width = max(1.0, self.song.total_beats * self.SUBDIVISIONS * cell_w)
        height = self.RULER_H + max(1, len(self.song.tracks)) * self.ROW_H
        self.timeline.configure(scrollregion=(0, 0, width, height))
        self.timeline.delete("arrange_hover")
        self._refresh_overlays()

    def _draw_track_notes(
        self,
        track_index: int,
        notes: list[Note],
        color: str,
        top: float,
    ) -> None:
        if not notes:
            return
        lowest = min(note.pitch for note in notes)
        highest = max(note.pitch for note in notes)
        span = max(1, highest - lowest)
        inner_height = self.ROW_H - 16
        for note in notes:
            x1 = note.start * self.SUBDIVISIONS * self.cell_w
            x2 = (note.start + note.duration) * self.SUBDIVISIONS * self.cell_w
            ratio = (note.pitch - lowest) / span
            y = top + 8 + (1.0 - ratio) * (inner_height - 7)
            item = self.timeline.create_rectangle(
                x1,
                y,
                max(x1 + 2, x2),
                y + 6,
                fill=color,
                outline="",
                tags="arrange_note",
            )
            self._note_items[item] = (track_index, note)

    def _draw_ruler_overlay(self) -> None:
        if self.song is None:
            return
        self.timeline.delete("arrange_ruler")
        top = self.timeline.canvasy(0)
        left = self.timeline.canvasx(0)
        right = self.timeline.canvasx(self.timeline.winfo_width())
        self.timeline.create_rectangle(
            left,
            top,
            right,
            top + self.RULER_H,
            fill=T.NAV_BG,
            outline="",
            tags="arrange_ruler",
        )
        bar_width = (
            self.song.beats_per_bar * self.SUBDIVISIONS * self.cell_w
        )
        label_step = max(1, math.ceil(42 / max(1.0, bar_width)))
        for bar in range(0, self.song.bars + 1, label_step):
            x = bar * self.song.beats_per_bar * self.SUBDIVISIONS * self.cell_w
            if left <= x <= right:
                self.timeline.create_text(
                    x + 5,
                    top + self.RULER_H / 2,
                    text=str(bar + 1),
                    fill=T.TEXT_MUTED,
                    font=(FONT_MONO, 9),
                    anchor="w",
                    tags="arrange_ruler",
                )
        self.timeline.tag_raise("arrange_ruler")

    def _draw_header_overlay(self) -> None:
        self.headers.delete("header_overlay")
        top = self.headers.canvasy(0)
        self.headers.create_rectangle(
            0,
            top,
            self.HEADER_W,
            top + self.RULER_H,
            fill=T.NAV_BG,
            outline="",
            tags="header_overlay",
        )
        self.headers.create_text(
            14,
            top + self.RULER_H / 2,
            text="全部轨道",
            fill=T.TEXT_MUTED,
            font=(FONT_UI, 11, "bold"),
            anchor="w",
            tags="header_overlay",
        )
        self.headers.tag_raise("header_overlay")

    def _refresh_overlays(self) -> None:
        self._draw_ruler_overlay()
        self._draw_header_overlay()
        self.set_playhead(self.insert_beat)

    def set_playhead(self, beat: float, auto_scroll: bool = False) -> None:
        if self.song is None:
            return
        self.insert_beat = max(0.0, min(beat, self.song.total_beats))
        x = self.insert_beat * self.SUBDIVISIONS * self.cell_w
        top = self.timeline.canvasy(0)
        height = self.RULER_H + max(1, len(self.song.tracks)) * self.ROW_H
        self.timeline.delete("arrange_playhead")
        self.timeline.create_line(
            x,
            top,
            x,
            height,
            fill=T.ACCENT,
            width=2,
            tags="arrange_playhead",
        )
        self.timeline.create_polygon(
            x - 6,
            top,
            x + 6,
            top,
            x,
            top + 8,
            fill=T.ACCENT,
            outline="",
            tags="arrange_playhead",
        )
        self.timeline.tag_raise("arrange_playhead")
        if auto_scroll:
            left = self.timeline.canvasx(0)
            right = self.timeline.canvasx(self.timeline.winfo_width())
            if x > right - 40 or x < left:
                total = self.song.total_beats * self.SUBDIVISIONS * self.cell_w
                target = (x - self.timeline.winfo_width() * 0.25) / max(1, total)
                self._xview("moveto", max(0.0, min(1.0, target)))

    def xview_fraction(self) -> float:
        return self.timeline.xview()[0]

    def set_xview_fraction(self, fraction: float) -> None:
        self._xview("moveto", max(0.0, min(1.0, fraction)))

    def _track_index_at(self, event) -> int | None:
        if self.song is None or event.y < self.RULER_H:
            return None
        y = self.timeline.canvasy(event.y)
        index = int((y - self.RULER_H) // self.ROW_H)
        return index if 0 <= index < len(self.song.tracks) else None

    def _note_at(self, event) -> tuple[int, Note] | None:
        x = self.timeline.canvasx(event.x)
        y = self.timeline.canvasy(event.y)
        for item in reversed(self.timeline.find_overlapping(x - 2, y - 2, x + 2, y + 2)):
            if item in self._note_items:
                return self._note_items[item]
        return None

    def _header_click(self, event) -> None:
        if self.song is None or event.y < self.RULER_H:
            return
        y = self.headers.canvasy(event.y)
        index = int((y - self.RULER_H) // self.ROW_H)
        if not 0 <= index < len(self.song.tracks):
            return
        if event.x >= self.HEADER_W - 38:
            self.on_toggle_solo(index)
        elif event.x >= self.HEADER_W - 68:
            self.on_toggle_mute(index)
        else:
            self.on_select_track(index)

    def _header_double_click(self, event) -> None:
        if self.song is None or event.y < self.RULER_H:
            return
        y = self.headers.canvasy(event.y)
        index = int((y - self.RULER_H) // self.ROW_H)
        if 0 <= index < len(self.song.tracks):
            self.on_open_track(index, None)

    def _timeline_click(self, event) -> None:
        if self.song is None:
            return
        if event.y < self.RULER_H:
            self._scrubbing = True
            self._seek_from_event(event)
            return
        note = self._note_at(event)
        index = note[0] if note else self._track_index_at(event)
        if index is not None:
            self.on_select_track(index)

    def _timeline_double_click(self, event) -> None:
        note = self._note_at(event)
        index = note[0] if note else self._track_index_at(event)
        if index is not None:
            self.on_open_track(index, note[1] if note else None)

    def _timeline_drag(self, event) -> None:
        if self._scrubbing:
            self._seek_from_event(event)

    def _timeline_release(self, _event) -> None:
        self._scrubbing = False

    def _seek_from_event(self, event) -> None:
        if self.song is None:
            return
        beat = self.timeline.canvasx(event.x) / (self.SUBDIVISIONS * self.cell_w)
        self.on_seek(max(0.0, min(beat, self.song.total_beats)))

    def _timeline_motion(self, event) -> None:
        if self.song is None or event.y < self.RULER_H:
            self.timeline.delete("arrange_hover")
            return
        x = self.timeline.canvasx(event.x)
        top = self.timeline.canvasy(0) + self.RULER_H
        height = self.RULER_H + max(1, len(self.song.tracks)) * self.ROW_H
        self.timeline.delete("arrange_hover")
        self.timeline.create_line(
            x,
            top,
            x,
            height,
            fill=T.TEXT_DISABLED,
            dash=(3, 3),
            tags="arrange_hover",
        )
        self.timeline.configure(cursor="hand2" if self._note_at(event) else "arrow")

    def _timeline_leave(self, _event=None) -> None:
        self.timeline.delete("arrange_hover")
        self.timeline.configure(cursor="arrow")

    def _play(self) -> str:
        self.on_play()
        return "break"

    def _timeline_yset(self, first: str, last: str) -> None:
        self.v_scroll.set(first, last)
        self.headers.yview_moveto(float(first))
        self._refresh_overlays()

    def _xview(self, *args) -> None:
        self.timeline.xview(*args)
        self._refresh_overlays()

    def _yview(self, *args) -> None:
        self.timeline.yview(*args)
        self.headers.yview(*args)
        self._refresh_overlays()

    def _vertical_wheel(self, event) -> str:
        delta = self._normalized_wheel_delta(event)
        self._scroll_pixels(vertical=-delta * 32)
        return "break"

    def _horizontal_wheel(self, event) -> str:
        delta = self._normalized_wheel_delta(event)
        self._scroll_pixels(horizontal=-delta * 40)
        return "break"

    def _zoom_wheel(self, event) -> str:
        self.on_zoom(4 if event.delta > 0 else -4)
        return "break"

    @staticmethod
    def _normalized_wheel_delta(event) -> float:
        delta = float(getattr(event, "delta", 0) or 0)
        if abs(delta) >= 120:
            delta /= 120.0
        return max(-6.0, min(6.0, delta))

    def _scroll_pixels(self, *, horizontal: float = 0.0, vertical: float = 0.0) -> None:
        if self.song is None:
            return
        if horizontal:
            total = self.song.total_beats * self.SUBDIVISIONS * self.cell_w
            viewport = self.timeline.winfo_width()
            offset = self.timeline.xview()[0] * total + horizontal
            offset = max(0.0, min(offset, max(0.0, total - viewport)))
            self._xview("moveto", offset / max(1.0, total))
        if vertical:
            total = self.RULER_H + max(1, len(self.song.tracks)) * self.ROW_H
            viewport = self.timeline.winfo_height()
            offset = self.timeline.yview()[0] * total + vertical
            offset = max(0.0, min(offset, max(0.0, total - viewport)))
            self._yview("moveto", offset / max(1.0, total))
