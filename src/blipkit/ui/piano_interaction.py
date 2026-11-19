"""Transactional pointer editing. Motion updates only affected Canvas items."""

import math
import tkinter as tk
from types import SimpleNamespace

from blipkit.core.models import Note

from . import tokens as T
from .editor_shortcuts import alt, primary


class PianoInteraction:
    def _init_interaction(self):
        self._gesture_before = None
        self._pointer_origin = (0, 0)
        self._pointer_event = None
        self._auto_scroll_id = None
        self._clone_pending = False
        self._erasing = False
        self._painting = False
        self._paint_last = None
        self._loop_anchor = None
        self._last_note_duration = 1.0
        self._pan_origin = None
        self._velocity_active = False

    @property
    def gesture_active(self):
        return bool(
            self._gesture_before is not None
            or self._marquee_start is not None
            or self._scrubbing_playhead
            or self._pan_origin is not None
            or getattr(self.arrangement_view, "drag_active", False)
        )

    def _begin_gesture(self, event):
        self._gesture_before = self._snapshot_state()
        self._pointer_origin = (event.x, event.y)
        self._pointer_event = event
        self._drag_changed = False

    def _commit_gesture(self):
        before = self._gesture_before
        self._gesture_before = None
        if before is not None and before[0] != self.song.to_dict():
            self._undo_stack.append(before)
            self._undo_stack = self._undo_stack[-60:]
            self._redo_stack.clear()
            self.on_change()
            self.on_mix_change()
            return True
        return False

    def cancel_gesture(self):
        if getattr(self.arrangement_view, "drag_active", False):
            self.arrangement_view.cancel_drag()
        before = self._gesture_before
        self._gesture_before = None
        self._reset_pointer()
        if before is not None:
            self._restore_state(before, notify=False)
            self.on_status("已取消拖拽")
        else:
            self.clear_note_selection()

    def _reset_pointer(self):
        if self._auto_scroll_id is not None:
            self.after_cancel(self._auto_scroll_id)
        self._auto_scroll_id = None
        self._pointer_event = None
        self._drag_note = None
        self._drawing_note = None
        self._drag_originals = {}
        self._drag_changed = False
        self._clone_pending = False
        self._erasing = self._painting = False
        self._paint_last = None
        self._scrubbing_playhead = False
        self._loop_anchor = None
        self._marquee_start = self._marquee_current = None
        self._pan_origin = None
        self._velocity_active = False
        self.canvas.delete("marquee")
        self._marquee_item = None
        self._update_canvas_cursor()

    def _pointer_snap(self, beat, event):
        return beat if alt(event) else self._snap_beat(beat)

    def _note_edge(self, event, note):
        x = self.canvas.canvasx(event.x)
        left, right = self._note_bounds(note)
        zone = min(7, (right - left) / 3)
        if abs(x - right) <= zone:
            return "resize"
        if abs(x - left) <= zone:
            return "resize_left"
        return "move"

    def _canvas_click(self, event):
        self.canvas.focus_set()
        if self.gesture_active:
            self.cancel_gesture()
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if event.x < self.LABEL_W:
            if event.y >= self.RULER_H:
                _, pitch = self._canvas_position(event, snap=False)
                if self.PITCH_LOW <= pitch <= self.PITCH_HIGH:
                    self.on_preview(pitch, self.selected_track.instrument, 96)
            return
        if event.y < self.RULER_H:
            beat, _ = self._canvas_position(event, snap=False)
            if event.state & 1:
                self._begin_gesture(event)
                self._loop_anchor = self._pointer_snap(beat, event)
            else:
                self._scrubbing_playhead = True
                self.on_seek()
                self._set_edit_cursor(beat, seek=False, announce=False)
            return
        raw, pitch = self._canvas_position(event, snap=False)
        beat = self._pointer_snap(raw, event)
        if not (0 <= beat < self.song.total_beats and self.PITCH_LOW <= pitch <= self.PITCH_HIGH):
            return
        existing = self._note_at_event(event)
        additive = bool(event.state & 1)
        if primary(event):
            if existing:
                ids = set(self.selected_note_ids) if additive else set()
                if existing.id in ids:
                    ids.remove(existing.id)
                else:
                    ids.add(existing.id)
                self._set_selection(ids, existing.id)
                self._refresh_note_items()
                return
            self._start_marquee(x, y, additive)
            return
        tool = self.tool_var.get()
        if tool == "擦除":
            self._erase_press(event)
            return
        if tool == "切片":
            if existing:
                self._slice_note(existing, beat)
            return
        if tool == "试听":
            if existing:
                self._preview_note(existing)
            return
        if existing:
            if existing.id not in self.selected_note_ids:
                ids = self.selected_note_ids | {existing.id} if additive else {existing.id}
                self._set_selection(ids, existing.id)
            else:
                self._set_selection(set(self.selected_note_ids), existing.id)
            self._begin_gesture(event)
            self._drag_note = existing
            self._drag_mode = self._note_edge(event, existing)
            self._clone_pending = additive and self._drag_mode == "move"
            self._drag_offset_beat = raw - existing.start
            self._drag_offset_pitch = pitch - existing.pitch
            self._drag_originals = {
                n.id: (n.start, n.pitch, n.duration) for n in self._selected_notes()
            }
            self._last_note_duration = existing.duration
            self._refresh_note_items()
            self._preview_note(existing)
            return
        if tool in ("画笔", "连画"):
            self._begin_gesture(event)
            self._painting = tool == "连画"
            duration = min(self._last_note_duration, self.song.total_beats - beat)
            self._drawing_note = self._create_note(beat, pitch, duration)
            self._set_selection({self._drawing_note.id}, self._drawing_note.id)
            self._paint_last = (beat, pitch)
            self._refresh_note_items()
            self._preview_note(self._drawing_note)
        else:
            self._start_marquee(x, y, additive)

    def _start_marquee(self, x, y, additive):
        if not additive:
            self._clear_selection()
            self._refresh_note_items()
        self._marquee_start = self._marquee_current = (x, y)
        self._marquee_additive = additive

    def _refresh_note_items(self):
        for note in self.selected_track.notes:
            self._update_note_canvas_item(note)
        self.canvas.tag_raise("piano")
        self.canvas.tag_raise("ruler_overlay")
        self._sync_note_controls()

    def _canvas_drag(self, event):
        self._pointer_event = SimpleNamespace(x=event.x, y=event.y, state=event.state)
        self._apply_pointer_drag(event)
        if self._auto_scroll_id is None and (
            self._drag_note or self._drawing_note or self._marquee_start or self._erasing
        ):
            self._auto_scroll_id = self.after(16, self._auto_scroll)

    def _auto_scroll(self):
        self._auto_scroll_id = None
        event = self._pointer_event
        if event is None:
            return
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        dx = min(24, max(0, event.x - w + 28)) - min(24, max(0, self.LABEL_W + 28 - event.x))
        dy = min(20, max(0, event.y - h + 28)) - min(20, max(0, self.RULER_H + 28 - event.y))
        if dx or dy:
            self._scroll_canvas_pixels(horizontal=dx, vertical=dy)
            self._apply_pointer_drag(event)
        self._auto_scroll_id = self.after(16, self._auto_scroll)

    def _apply_pointer_drag(self, event):
        raw, pitch = self._canvas_position(event, snap=False)
        beat = self._pointer_snap(raw, event)
        if self._loop_anchor is not None:
            start, end = sorted((self._loop_anchor, beat))
            self.song.loop_start = max(0, min(start, self.song.total_beats - self._snap_size()))
            self.song.loop_end = min(self.song.total_beats, max(end, start + self._snap_size()))
            self.loop_var.set(True)
            self._draw_timeline_overlay()
            return
        if self._scrubbing_playhead:
            self._set_edit_cursor(raw, seek=False, announce=False)
            return
        if self._erasing:
            self._erase_at(event)
            return
        if self._drawing_note is not None:
            if self._painting:
                self._paint_to(beat, pitch)
                return
            # A click retains the remembered length; a deliberate drag resizes it.
            if abs(event.x - self._pointer_origin[0]) < 3:
                return
            end = min(
                self.song.total_beats,
                max(beat + self._snap_size(), self._drawing_note.start + self._minimum_note(event)),
            )
            self._drawing_note.duration = end - self._drawing_note.start
            self._update_note_canvas_item(self._drawing_note)
            self._sync_note_controls()
            return
        if self._marquee_start is not None:
            x = max(self.LABEL_W, self.canvas.canvasx(event.x))
            y = max(self.RULER_H, self.canvas.canvasy(event.y))
            self._marquee_current = (x, y)
            x1, y1 = self._marquee_start
            if abs(x - x1) + abs(y - y1) < 4:
                return
            if self._marquee_item is None:
                self._marquee_item = self.canvas.create_rectangle(
                    x1,
                    y1,
                    x,
                    y,
                    fill=T.ACCENT_SOFT,
                    outline=T.ACCENT,
                    stipple="gray25",
                    tags="marquee",
                )
                if self._note_rect_items:
                    self.canvas.tag_lower(
                        self._marquee_item, next(iter(self._note_rect_items.values()))
                    )
            else:
                self.canvas.coords(self._marquee_item, x1, y1, x, y)
            return
        if self._drag_note is None:
            return
        if max(abs(event.x - self._pointer_origin[0]), abs(event.y - self._pointer_origin[1])) < 3:
            if not self._drag_changed:
                return
        if self._clone_pending:
            original_id = self._drag_note.id
            copies = []
            for note in self._selected_notes():
                cloned = Note(note.pitch, note.start, note.duration, note.velocity)
                copies.append(cloned)
                if note.id == original_id:
                    self._drag_note = cloned
            self.selected_track.notes.extend(copies)
            self._set_selection({n.id for n in copies}, self._drag_note.id)
            self._drag_originals = {n.id: (n.start, n.pitch, n.duration) for n in copies}
            self._clone_pending = False
            self._refresh_note_items()
        originals = self._drag_originals
        start, original_pitch, duration = originals[self._drag_note.id]
        minimum = self._minimum_note(event)
        notes = self._selected_notes()
        previous_pitch = self._drag_note.pitch
        if self._drag_mode in ("resize", "resize_left"):
            left = self._drag_mode == "resize_left"
            delta = beat - (start if left else start + duration)
            if left:
                delta = max(
                    -min(v[0] for v in originals.values()),
                    min(delta, min(v[2] - minimum for v in originals.values())),
                )
            else:
                delta = max(
                    max(minimum - v[2] for v in originals.values()),
                    min(
                        delta, min(self.song.total_beats - v[0] - v[2] for v in originals.values())
                    ),
                )
            for note in notes:
                ns, np, nd = originals[note.id]
                note.start = ns + delta if left else ns
                note.duration = nd - delta if left else nd + delta
                note.pitch = np
        else:
            delta = self._pointer_snap(raw - self._drag_offset_beat, event) - start
            delta = max(
                -min(v[0] for v in originals.values()),
                min(delta, self.song.total_beats - max(v[0] + v[2] for v in originals.values())),
            )
            transpose = pitch - self._drag_offset_pitch - original_pitch
            transpose = max(
                self.PITCH_LOW - min(v[1] for v in originals.values()),
                min(transpose, self.PITCH_HIGH - max(v[1] for v in originals.values())),
            )
            for note in notes:
                ns, np, nd = originals[note.id]
                note.start, note.pitch, note.duration = ns + delta, np + transpose, nd
        for note in notes:
            self._update_note_canvas_item(note)
        self._drag_changed = True
        self._sync_note_controls()
        if self._drag_note.pitch != previous_pitch:
            self._preview_note(self._drag_note)

    def _minimum_note(self, event):
        return 1 / 96 if alt(event) or self.snap_var.get() == "自由" else self._snap_size()

    def _paint_to(self, beat, pitch):
        last, _ = self._paint_last
        step = max(self._snap_size(), self._last_note_duration)
        direction = 1 if beat >= last else -1
        for index in range(1, int(abs(beat - last) / step + 1e-6) + 1):
            start = last + direction * index * step
            if not (
                0 <= start < self.song.total_beats and self.PITCH_LOW <= pitch <= self.PITCH_HIGH
            ):
                continue
            if any(
                n.pitch == pitch and abs(n.start - start) < 1e-6 for n in self.selected_track.notes
            ):
                continue
            note = self._create_note(start, pitch, min(step, self.song.total_beats - start))
            self.selected_note_ids.add(note.id)
            self._update_note_canvas_item(note)
            self._paint_last = (start, pitch)

    def _canvas_release(self, _event=None):
        if self._marquee_start is not None:
            a, b = self._marquee_start, self._marquee_current or self._marquee_start
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) >= 4:
                x1, x2 = sorted((a[0], b[0]))
                y1, y2 = sorted((a[1], b[1]))
                ids = set(self.selected_note_ids) if self._marquee_additive else set()
                for note in self.selected_track.notes:
                    nx1, ny1, nx2, ny2 = self._note_rectangle(note)
                    if nx2 >= x1 and nx1 <= x2 and ny2 >= y1 and ny1 <= y2:
                        ids.add(note.id)
                self._set_selection(ids)
        note = self._drawing_note or self._drag_note
        if note is not None:
            self._last_note_duration = note.duration
        changed = self._commit_gesture()
        self._reset_pointer()
        if changed:
            self._rebuild_tracks()
            self.on_status(f"已编辑 · {len(self.selected_note_ids)} 个音符 · 可撤销")
        self._sync_note_controls()
        self.redraw()

    def _canvas_double_click(self, event):
        note = self._note_at_event(event)
        if note is not None:
            self._canvas_release(event)
            self.note_velocity_entry.focus_set()
            self.note_velocity_entry.select_range(0, "end")
            return
        if self.tool_var.get() == "选择":
            previous = self.tool_var.get()
            self.tool_var.set("画笔")
            self._canvas_click(event)
            self._canvas_release(event)
            self.tool_var.set(previous)

    def _erase_press(self, event):
        self.canvas.focus_set()
        self._begin_gesture(event)
        self._erasing = True
        self._erase_at(event)

    def _erase_at(self, event):
        if event.x < self.LABEL_W or event.y < self.RULER_H:
            return
        note = self._note_at_event(event)
        if note is None:
            return
        ids = set(self.selected_note_ids) if note.id in self.selected_note_ids else {note.id}
        self.selected_track.notes[:] = [n for n in self.selected_track.notes if n.id not in ids]
        for item, candidate in list(self._note_items.items()):
            if candidate.id in ids:
                self.canvas.delete(item)
                del self._note_items[item]
        for note_id in ids:
            for mapping in (
                self._note_rect_items,
                self._note_velocity_items,
                self._note_handle_items,
            ):
                mapping.pop(note_id, None)
        self._set_selection(self.selected_note_ids - ids)

    def _canvas_delete(self, event):
        self._erase_press(event)
        self._canvas_release(event)

    def _slice_note(self, note, beat):
        if not note.start + 1 / 96 <= beat <= note.start + note.duration - 1 / 96:
            return
        self._push_undo()
        end = note.start + note.duration
        note.duration = beat - note.start
        right = Note(note.pitch, beat, end - beat, note.velocity)
        self.selected_track.notes.append(right)
        self._set_selection({note.id, right.id}, right.id)
        self.redraw()
        self.on_change()
        self.on_mix_change()

    def _pan_press(self, event):
        self.canvas.focus_set()
        self._pan_origin = (event.x, event.y)
        self.canvas.scan_mark(event.x, event.y)
        self.canvas.configure(cursor="fleur")

    def _pan_drag(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self._refresh_canvas_overlays()

    def _velocity_wheel(self, event):
        self.nudge_selected(velocity=4 if event.delta > 0 else -4)
        return "break"

    def _velocity_press(self, event):
        self.velocity_canvas.focus_set()
        self._begin_gesture(event)
        self._velocity_active = True
        self._velocity_drag(event)

    def _velocity_drag(self, event):
        if not self._velocity_active:
            return
        x = self.canvas.canvasx(event.x)
        velocity = max(1, min(127, round((70 - event.y) / 54 * 127)))
        notes = self._selected_notes() or self.selected_track.notes
        for note in notes:
            nx = self.LABEL_W + note.start * self.SUBDIVISIONS * self.cell_w
            if abs(nx - x) <= 7:
                note.velocity = velocity
                self._update_note_canvas_item(note)
                self._update_velocity_item(note)
        self._sync_note_controls()

    def _update_velocity_item(self, note):
        if not hasattr(self, "velocity_canvas"):
            return
        x = self.LABEL_W + note.start * self.SUBDIVISIONS * self.cell_w - self.canvas.canvasx(0)
        y = 70 - note.velocity / 127 * 54
        item = self._velocity_lane_items.get(note.id)
        color = T.NOTE_SELECTED if note.id in self.selected_note_ids else self.selected_track.color
        if item is None:
            item = self.velocity_canvas.create_line(x, 70, x, y, fill=color, width=4)
            self._velocity_lane_items[note.id] = item
        else:
            self.velocity_canvas.coords(item, x, 70, x, y)
            self.velocity_canvas.itemconfigure(item, fill=color)

    def _redraw_velocity_lane(self):
        if not hasattr(self, "velocity_canvas"):
            return
        self.velocity_canvas.delete("all")
        self._velocity_lane_items = {}
        for note in self.selected_track.notes:
            self._update_velocity_item(note)
        self.velocity_canvas.create_rectangle(0, 0, self.LABEL_W, 78, fill=T.NAV_BG, outline="")
        self.velocity_canvas.create_text(8, 20, text="力度", anchor="w", fill=T.TEXT_MUTED)

    def toggle_snap(self):
        if self.snap_var.get() == "自由":
            self.snap_var.set(getattr(self, "_previous_snap", "1/16"))
        else:
            self._previous_snap = self.snap_var.get()
            self.snap_var.set("自由")
        self._snap_changed(self.snap_var.get())

    def loop_selection(self):
        notes = self._selected_notes()
        if not notes:
            self.on_status("先选择需要循环的音符")
            return
        self._push_undo()
        self.song.loop_start = min(n.start for n in notes)
        self.song.loop_end = max(n.start + n.duration for n in notes)
        self.loop_var.set(True)
        self._set_edit_cursor(self.song.loop_start)
        self.redraw()
        self.on_change()
        self.on_status("循环范围已设为所选音符")

    def legato_selected(self):
        notes = sorted(self._selected_notes(), key=lambda n: n.start)
        updates = []
        for note in notes:
            following = next((n.start for n in notes if n.start > note.start + 1e-6), None)
            if following is not None and abs(note.duration - (following - note.start)) > 1e-6:
                updates.append((note, following - note.start))
        if not updates:
            return
        self._push_undo()
        for note, duration in updates:
            note.duration = duration
        self.redraw()
        self.on_change()
        self.on_mix_change()
        self.on_status("已将音符连接至下一组起音")

    def fit_song(self):
        self.zoom_horizontal(-400)

    def zoom_selection(self):
        notes = self._selected_notes()
        if not notes:
            return
        start = min(n.start for n in notes)
        end = max(n.start + n.duration for n in notes)
        canvas = self._active_timeline_canvas()
        label = self.LABEL_W if self.view_var.get() == "钢琴卷帘" else 0
        current = self.cell_w if label else self.arrangement_cell_w
        target = (canvas.winfo_width() - label - 60) / (max(1, end - start) * self.SUBDIVISIONS)
        self.zoom_horizontal(math.log(max(0.01, target / current)) / math.log(1.18) * 4)
        self._finalize_horizontal_zoom()
        total = (
            self.song.total_beats
            * self.SUBDIVISIONS
            * (self.cell_w if label else self.arrangement_cell_w)
        )
        canvas.xview_moveto(
            max(
                0,
                (
                    start * self.SUBDIVISIONS * (self.cell_w if label else self.arrangement_cell_w)
                    - 20
                )
                / (total + label),
            )
        )
        self._refresh_canvas_overlays()

    def show_shortcut_help(self):
        from .editor_shortcuts import SHORTCUT_HELP

        window = tk.Toplevel(self)
        window.title("Blipkit · FL 风格操作")
        window.geometry("690x650")
        text = tk.Text(window, wrap="word", padx=24, pady=20, font=("Helvetica", 13))
        text.pack(fill="both", expand=True)
        text.insert("1.0", SHORTCUT_HELP)
        text.configure(state="disabled")
        window.bind("<Escape>", lambda _event: window.destroy())
