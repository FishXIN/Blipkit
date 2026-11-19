"""Pointer-level interaction tests for the piano roll."""

from __future__ import annotations

import sys
import tkinter as tk
from types import SimpleNamespace

import customtkinter as ctk
import pytest

from blipkit.core.models import Note, Song, Track
from blipkit.ui.sequencer_view import SequencerView


@pytest.fixture(scope="module")
def tk_root():
    try:
        root = ctk.CTk()
    except tk.TclError as exc:
        pytest.skip(f"Tk display unavailable: {exc}")
    root.geometry("1360x840+0+0")
    root.update()
    yield root
    root.destroy()


@pytest.fixture
def editor(tk_root):
    note = Note(pitch=126, start=1.0, duration=1.0)
    song = Song(
        name="interaction",
        bars=4,
        loop_end=16.0,
        tracks=[
            Track(name="track", notes=[note]),
            Track(name="track 2"),
        ],
    )
    events: list[str] = []
    view = SequencerView(
        tk_root,
        song,
        on_change=lambda: events.append("change"),
        on_seek=lambda: events.append("seek"),
        on_status=events.append,
        on_play=lambda: events.append("play"),
        on_preview=lambda *_args: None,
        on_import_midi=lambda: None,
        on_export_midi=lambda: None,
        on_mix_change=lambda: events.append("mix"),
    )
    view.pack(fill="both", expand=True)
    view.set_editor_view("钢琴卷帘")
    view.set_tool("选择")
    tk_root.update()
    tk_root.after(5, tk_root.quit)
    tk_root.mainloop()
    view.canvas.yview_moveto(0)
    tk_root.update()
    yield SimpleNamespace(root=tk_root, view=view, note=note, events=events)
    view.destroy()
    tk_root.update()


def _x_at_beat(view: SequencerView, beat: float) -> int:
    return round(view.LABEL_W + beat * view.SUBDIVISIONS * view.cell_w)


def _note_center(view: SequencerView, note: Note) -> tuple[int, int]:
    x1, y1, x2, y2 = view._note_rectangle(note)
    return round((x1 + x2) / 2), round((y1 + y2) / 2)


def _click(canvas: tk.Canvas, x: int, y: int) -> None:
    canvas.event_generate("<Button-1>", x=x, y=y)
    canvas.event_generate("<ButtonRelease-1>", x=x, y=y)
    canvas.update()


def test_blank_click_clears_selection_without_moving_playhead(editor) -> None:
    view = editor.view
    view._set_edit_cursor(2.0, seek=False)
    view._set_selection({editor.note.id}, editor.note.id)
    view.redraw()

    _click(view.canvas, _x_at_beat(view, 4.0), view.RULER_H + 10)

    assert view.insert_beat == 2.0
    assert view.selected_note_ids == set()


def test_ruler_click_moves_playhead_without_clearing_selection(editor) -> None:
    view = editor.view
    view._set_selection({editor.note.id}, editor.note.id)
    view.redraw()

    _click(view.canvas, _x_at_beat(view, 2.5), 10)

    assert view.insert_beat == pytest.approx(2.5)
    assert view.selected_note_ids == {editor.note.id}
    assert editor.events.count("seek") == 1


def test_ruler_drag_scrubs_playhead_with_one_seek_stop(editor) -> None:
    view = editor.view
    start_x = _x_at_beat(view, 1.0)
    end_x = _x_at_beat(view, 3.5)

    view.canvas.event_generate("<Button-1>", x=start_x, y=10)
    view.canvas.event_generate("<B1-Motion>", x=end_x, y=10, state=0x0100)
    view.canvas.event_generate("<ButtonRelease-1>", x=end_x, y=10)
    view.canvas.update()

    assert view.insert_beat == pytest.approx(3.5)
    assert editor.events.count("seek") == 1
    assert not view._scrubbing_playhead


def test_ruler_remains_clickable_after_vertical_scroll(editor) -> None:
    view = editor.view
    view._yview("moveto", "0.37")
    editor.root.update()

    assert view.canvas.canvasy(0) > view.RULER_H
    _click(view.canvas, _x_at_beat(view, 2.0), 10)

    assert view.insert_beat == pytest.approx(2.0)
    ruler_bounds = view.canvas.bbox("ruler_overlay")
    assert ruler_bounds is not None
    assert ruler_bounds[1] <= view.canvas.canvasy(0) + 1


def test_track_selection_centers_its_note_range(editor) -> None:
    view = editor.view
    view.song.tracks[1].notes.append(Note(pitch=38, start=0, duration=1))

    view.select_track(1)
    editor.root.after(5, editor.root.quit)
    editor.root.mainloop()
    low_track_top = view.canvas.canvasy(0)

    view.select_track(0)
    editor.root.after(5, editor.root.quit)
    editor.root.mainloop()
    high_track_top = view.canvas.canvasy(0)

    assert low_track_top > high_track_top


def test_arrangement_renders_all_tracks_and_separates_selection_from_seek(editor) -> None:
    view = editor.view
    second_note = Note(pitch=38, start=0.5, duration=1)
    view.song.tracks[1].notes.append(second_note)
    view.set_editor_view("编排")
    editor.root.update()
    arrangement = view.arrangement_view

    assert len(arrangement._note_items) == 2
    view._set_edit_cursor(3.0, seek=False)
    arrangement._timeline_click(
        SimpleNamespace(
            x=30,
            y=arrangement.RULER_H + arrangement.ROW_H + 20,
        )
    )

    assert view.selected_track_index == 1
    assert view.insert_beat == 3.0

    arrangement._timeline_click(
        SimpleNamespace(
            x=2 * arrangement.SUBDIVISIONS * arrangement.cell_w,
            y=10,
        )
    )
    arrangement._timeline_release(None)

    assert view.insert_beat == pytest.approx(2.0)


def test_arrangement_double_click_opens_note_in_piano_roll(editor) -> None:
    view = editor.view
    second_note = Note(pitch=38, start=0.5, duration=1)
    view.song.tracks[1].notes.append(second_note)
    view.set_editor_view("编排")
    editor.root.update()
    arrangement = view.arrangement_view
    item = next(
        item
        for item, (_index, note) in arrangement._note_items.items()
        if note.id == second_note.id
    )
    x1, y1, x2, y2 = arrangement.timeline.bbox(item)

    arrangement._timeline_double_click(
        SimpleNamespace(
            x=round((x1 + x2) / 2),
            y=round((y1 + y2) / 2),
        )
    )
    editor.root.update()

    assert view.view_var.get() == "钢琴卷帘"
    assert view.selected_track_index == 1
    assert view.selected_note_ids == {second_note.id}
    assert view.insert_beat == second_note.start


def test_track_mute_notifies_live_playback_mix(editor) -> None:
    view = editor.view

    view.toggle_track_mute(0)

    assert view.song.tracks[0].muted
    assert "mix" in editor.events
    assert "change" in editor.events


def test_space_plays_without_scrolling_focused_canvas(editor) -> None:
    view = editor.view
    view._yview("moveto", "0.37")
    editor.root.update()
    start_y = view.canvas.canvasy(0)
    view.canvas.focus_force()

    view.canvas.event_generate("<space>")
    editor.root.update()

    assert "play" in editor.events
    assert view.canvas.canvasy(0) == pytest.approx(start_y)


def test_trackpad_small_deltas_scroll_both_scrollbars(editor) -> None:
    view = editor.view
    view._xview("moveto", "0.2")
    view._yview("moveto", "0.2")
    editor.root.update()
    start_x = view.canvas.canvasx(0)
    start_y = view.canvas.canvasy(0)

    view.x_scroll._canvas.event_generate("<MouseWheel>", delta=-1)
    view.y_scroll._canvas.event_generate("<MouseWheel>", delta=-1)
    editor.root.update()

    assert view.canvas.canvasx(0) > start_x
    assert view.canvas.canvasy(0) > start_y


def test_trackpad_pinch_zooms_around_pointer_anchor(editor) -> None:
    view = editor.view
    view._xview("moveto", "0.2")
    editor.root.update()
    anchor_x = 320
    before_width = view.cell_w
    before_beat = (view.canvas.canvasx(anchor_x) - view.LABEL_W) / (view.SUBDIVISIONS * view.cell_w)

    view._apply_trackpad_magnification(0.09, anchor_x)
    editor.root.update()

    after_beat = (view.canvas.canvasx(anchor_x) - view.LABEL_W) / (view.SUBDIVISIONS * view.cell_w)
    assert view.cell_w > before_width
    assert view.cell_w < before_width * 1.5
    assert after_beat == pytest.approx(before_beat, abs=0.05)


def test_piano_roll_zoom_out_fits_entire_song(editor) -> None:
    view = editor.view
    editor.root.update()
    viewport = view.canvas.winfo_width()
    columns = view.song.total_beats * view.SUBDIVISIONS

    view.zoom_horizontal(-400)
    editor.root.update()

    expected = (viewport - view.LABEL_W - 2) / columns
    assert view.cell_w == pytest.approx(expected)
    assert view.canvas.xview() == pytest.approx((0.0, 1.0))
    assert editor.events[-1] == "时间轴缩放：整首适配"


def test_piano_roll_allows_deep_zoom_in(editor) -> None:
    view = editor.view

    view.zoom_horizontal(400)
    editor.root.update()

    assert view.cell_w == pytest.approx(4096.0)
    assert view.cell_w > 46


def test_arrangement_zoom_out_fits_entire_song(editor) -> None:
    view = editor.view
    view.set_editor_view("编排")
    editor.root.update()
    viewport = view.arrangement_view.timeline.winfo_width()
    columns = view.song.total_beats * view.SUBDIVISIONS

    view.zoom_horizontal(-400)
    editor.root.update()

    expected = (viewport - 2) / columns
    assert view.arrangement_cell_w == pytest.approx(expected)
    assert view.arrangement_view.timeline.xview() == pytest.approx((0.0, 1.0))


def test_piano_zoom_coalesces_full_redraws(editor, monkeypatch) -> None:
    view = editor.view
    piano_redraws = 0
    arrangement_redraws = 0
    original_piano_redraw = view._redraw_piano_roll
    original_arrangement_redraw = view._redraw_arrangement

    def counted_piano_redraw() -> None:
        nonlocal piano_redraws
        piano_redraws += 1
        original_piano_redraw()

    def counted_arrangement_redraw() -> None:
        nonlocal arrangement_redraws
        arrangement_redraws += 1
        original_arrangement_redraw()

    monkeypatch.setattr(view, "_redraw_piano_roll", counted_piano_redraw)
    monkeypatch.setattr(view, "_redraw_arrangement", counted_arrangement_redraw)
    note_item = view._note_rect_items[editor.note.id]

    for _step in range(12):
        view.zoom_horizontal(4, anchor_x=320)

    assert piano_redraws == 0
    assert arrangement_redraws == 0
    assert view._note_rect_items[editor.note.id] == note_item

    editor.root.after(150, editor.root.quit)
    editor.root.mainloop()

    assert piano_redraws == 1
    assert arrangement_redraws == 0


def test_arrangement_zoom_coalesces_full_redraws(editor, monkeypatch) -> None:
    view = editor.view
    view.set_editor_view("编排")
    piano_redraws = 0
    arrangement_redraws = 0
    original_piano_redraw = view._redraw_piano_roll
    original_arrangement_redraw = view._redraw_arrangement

    def counted_piano_redraw() -> None:
        nonlocal piano_redraws
        piano_redraws += 1
        original_piano_redraw()

    def counted_arrangement_redraw() -> None:
        nonlocal arrangement_redraws
        arrangement_redraws += 1
        original_arrangement_redraw()

    monkeypatch.setattr(view, "_redraw_piano_roll", counted_piano_redraw)
    monkeypatch.setattr(view, "_redraw_arrangement", counted_arrangement_redraw)

    for _step in range(12):
        view.zoom_horizontal(4, anchor_x=320)

    assert piano_redraws == 0
    assert arrangement_redraws == 0

    editor.root.after(150, editor.root.quit)
    editor.root.mainloop()

    assert piano_redraws == 0
    assert arrangement_redraws == 1


def test_draw_tool_opens_piano_roll_from_arrangement(editor) -> None:
    view = editor.view
    view.set_editor_view("编排")

    view.set_tool("画笔")
    editor.root.update()

    assert view.view_var.get() == "钢琴卷帘"
    assert view.tool_var.get() == "画笔"
    assert "画笔模式" in editor.events[-1]


def test_brush_drag_updates_only_active_note_until_release(editor) -> None:
    view = editor.view
    view.set_tool("画笔")
    editor.events.clear()
    pitch = 120
    y = round(view.RULER_H + (view.PITCH_HIGH - pitch + 0.5) * view.ROW_H)
    start_x = _x_at_beat(view, 2.0)
    view.canvas.event_generate("<Button-1>", x=start_x, y=y)
    editor.root.update()
    assert view._drawing_note is not None

    redraws = 0
    original_redraw = view.redraw

    def counted_redraw() -> None:
        nonlocal redraws
        redraws += 1
        original_redraw()

    view.redraw = counted_redraw
    for step in range(1, 25):
        view.canvas.event_generate(
            "<B1-Motion>",
            x=_x_at_beat(view, 2.0 + step * 0.125),
            y=y,
            state=0x0100,
        )
        editor.root.update()

    assert redraws == 0
    assert "seek" not in editor.events
    view.canvas.event_generate(
        "<ButtonRelease-1>",
        x=_x_at_beat(view, 5.0),
        y=y,
    )
    editor.root.update()
    assert redraws == 1
    assert "mix" in editor.events


def test_toolbar_switches_report_state_and_refresh_playback(editor) -> None:
    view = editor.view
    editor.events.clear()

    view.preview_var.set(False)
    view._preview_changed()
    view.scale_warning_var.set(False)
    view._scale_warning_changed()
    view.loop_var.set(True)
    view._loop_changed()
    view.metronome_var.set(True)
    view._metronome_changed()

    assert "音符试听已关闭" in editor.events
    assert "音阶高亮已关闭" in editor.events
    assert "循环播放已开启" in editor.events
    assert "节拍器已开启" in editor.events
    assert "mix" in editor.events


def test_time_signature_changes_real_timeline_geometry(editor) -> None:
    view = editor.view
    editor.events.clear()
    view.signature_var.set("3/4")

    view._option_changed()
    editor.root.update()

    assert view.song.beats_per_bar == 3
    assert view.song.total_beats == 12
    assert view.song.loop_end == 12
    assert view._format_position(3) == "02:01:01"
    assert "change" in editor.events
    assert "mix" in editor.events
    assert any("3/4" in event for event in editor.events)


def test_plain_arrow_moves_selected_note_without_seeking(editor) -> None:
    view = editor.view
    view._set_edit_cursor(2.0, seek=False)
    view._set_selection({editor.note.id}, editor.note.id)
    view.canvas.focus_force()

    view.canvas.event_generate("<Right>")
    editor.root.update()

    assert view.insert_beat == 2.0
    assert editor.note.start == pytest.approx(1.25)


def test_modified_arrow_moves_selected_note_only(editor) -> None:
    view = editor.view
    view._set_edit_cursor(3.0, seek=False)
    view._set_selection({editor.note.id}, editor.note.id)
    view.canvas.focus_force()
    view.canvas.event_generate("<Shift-Right>")
    editor.root.update()

    assert view.insert_beat == 3.0
    assert editor.note.start == pytest.approx(1.25)


def test_copy_and_paste_places_notes_at_playhead(editor) -> None:
    view = editor.view
    view._set_selection({editor.note.id}, editor.note.id)
    assert view.copy_selected_notes()
    view._set_edit_cursor(4.0, seek=False)

    view.paste_notes_at_playhead()

    assert len(view.selected_track.notes) == 2
    pasted = next(note for note in view.selected_track.notes if note.id != editor.note.id)
    assert pasted.start == 4.0
    assert pasted.pitch == editor.note.pitch
    assert view.selected_note_ids == {pasted.id}


def test_split_uses_playhead_and_keeps_both_halves_selected(editor) -> None:
    view = editor.view
    view._set_selection({editor.note.id}, editor.note.id)
    view._set_edit_cursor(1.5, seek=False)

    view.split_selected_at_playhead()

    assert len(view.selected_track.notes) == 2
    assert sorted(note.duration for note in view.selected_track.notes) == [0.5, 0.5]
    assert len(view.selected_note_ids) == 2


@pytest.mark.parametrize(
    ("key", "expected_start", "expected_duration"),
    [
        ("q", 1.5, 0.5),
        ("w", 1.0, 0.5),
    ],
)
def test_trim_selected_note_at_playhead(
    editor,
    key: str,
    expected_start: float,
    expected_duration: float,
) -> None:
    view = editor.view
    view._set_selection({editor.note.id}, editor.note.id)
    view._set_edit_cursor(1.5, seek=False)
    view.canvas.focus_force()

    view.trim_selected_to_playhead("left" if key == "q" else "right")
    editor.root.update()

    assert editor.note.start == expected_start
    assert editor.note.duration == expected_duration


def test_move_selected_notes_between_tracks(editor) -> None:
    view = editor.view
    view._set_selection({editor.note.id}, editor.note.id)
    view.canvas.focus_force()

    view.move_selected_to_track(1)
    editor.root.update()

    assert view.selected_track_index == 1
    assert editor.note in view.song.tracks[1].notes

    view.move_selected_to_track(-1)
    editor.root.update()

    assert view.selected_track_index == 0
    assert editor.note in view.song.tracks[0].notes


def test_note_click_selects_without_moving_playhead(editor) -> None:
    view = editor.view
    view._set_edit_cursor(3.0, seek=False)

    _click(view.canvas, *_note_center(view, editor.note))

    assert view.insert_beat == 3.0
    assert view.selected_note_ids == {editor.note.id}


def test_blank_drag_marquee_selects_without_moving_playhead(editor) -> None:
    view = editor.view
    view._set_edit_cursor(5.0, seek=False)
    x1, y1, _x2, y2 = view._note_rectangle(editor.note)
    start_x = round(x1 - view.cell_w)
    end_x = _x_at_beat(view, 2.2)

    view.canvas.event_generate("<Button-1>", x=start_x, y=round(y1 - 2))
    view.canvas.event_generate(
        "<B1-Motion>",
        x=end_x,
        y=round(y2 + 2),
        state=0x0100,
    )
    view.canvas.update()
    marquee = view.canvas.find_withtag("marquee")
    assert len(marquee) == 1
    marquee_item = marquee[0]
    assert view.canvas.itemcget(marquee_item, "fill") == "#EAF2FF"
    assert view.canvas.itemcget(marquee_item, "stipple") == "gray25"
    stacking_order = view.canvas.find_all()
    note_item = view._note_rect_items[editor.note.id]
    assert stacking_order.index(marquee_item) < stacking_order.index(note_item)

    view.canvas.event_generate(
        "<B1-Motion>",
        x=end_x + 2,
        y=round(y2 + 4),
        state=0x0100,
    )
    view.canvas.update()
    assert view.canvas.find_withtag("marquee") == (marquee_item,)
    view.canvas.event_generate(
        "<ButtonRelease-1>",
        x=end_x + 2,
        y=round(y2 + 4),
    )
    view.canvas.update()

    assert view.insert_beat == 5.0
    assert view.selected_note_ids == {editor.note.id}


def _pointer(x, y, state=0):
    return SimpleNamespace(x=round(x), y=round(y), state=state)


def _drag_note(view, note, dx, dy=0, state=0):
    x, y = _note_center(view, note)
    view._canvas_click(_pointer(x, y, state))
    view._canvas_drag(_pointer(x + dx, y + dy, state))
    return x, y


def test_move_and_resize_do_not_rebuild_the_canvas(editor, monkeypatch):
    view = editor.view
    item = view._note_rect_items[editor.note.id]
    redraws = []
    original = view.redraw
    monkeypatch.setattr(view, "redraw", lambda: redraws.append(True))
    x, y = _drag_note(view, editor.note, view.cell_w * 2)
    for step in range(3, 25):
        view._canvas_drag(_pointer(x + step * view.cell_w, y))
    assert not redraws
    assert view._note_rect_items[editor.note.id] == item
    monkeypatch.setattr(view, "redraw", original)
    view._canvas_release(None)
    assert len(view._undo_stack) == 1
    view.undo()
    assert view.selected_track.notes[0].start == 1
    assert "mix" in editor.events


def test_returning_drag_to_origin_is_not_an_edit(editor):
    view = editor.view
    x, y = _drag_note(view, editor.note, view.cell_w * 2)
    view._canvas_drag(_pointer(x, y))
    view._canvas_release(None)
    assert editor.note.start == 1
    assert not view._undo_stack


def test_shift_drag_clones_and_escape_restores_redo(editor):
    view = editor.view
    view._set_selection({editor.note.id}, editor.note.id)
    view.nudge_selected(beats=1)
    view.undo()
    note = view.selected_track.notes[0]
    _drag_note(view, note, view.cell_w * 4, state=1)
    assert len(view.selected_track.notes) == 2
    view.cancel_gesture()
    assert len(view.selected_track.notes) == 1
    assert len(view._redo_stack) == 1
    view.redo()
    assert view.selected_track.notes[0].start == 2


def test_shift_drag_copy_commits_as_one_undo(editor):
    view = editor.view
    _drag_note(view, editor.note, view.cell_w * 4, state=1)
    view._canvas_release(None)
    assert sorted(n.start for n in view.selected_track.notes) == [1, 2]
    assert len(view._undo_stack) == 1
    view.undo()
    assert len(view.selected_track.notes) == 1


def test_alt_drag_bypasses_grid_without_changing_selection(editor):
    from blipkit.ui.editor_shortcuts import ALT_MASK

    view = editor.view
    _drag_note(view, editor.note, 11, state=ALT_MASK)
    view._canvas_release(None)
    assert editor.note.start == pytest.approx(1 + 11 / (view.cell_w * 4))
    assert view.selected_note_ids == {editor.note.id}


def test_left_resize_keeps_right_edge_and_restores_on_undo(editor):
    view = editor.view
    left, y1, _, y2 = view._note_rectangle(editor.note)
    view._canvas_click(_pointer(left + 1, (y1 + y2) / 2))
    view._canvas_drag(_pointer(left + view.cell_w, (y1 + y2) / 2))
    view._canvas_release(None)
    assert editor.note.start == 1.25
    assert editor.note.duration == 0.75
    view.undo()
    assert view.selected_track.notes[0].start == 1
    assert view.selected_track.notes[0].duration == 1


def test_brush_remembers_length_and_paint_fills_skipped_cells(editor):
    view = editor.view
    view.set_tool("连画")
    view._last_note_duration = 0.25
    x = _x_at_beat(view, 3)
    y = view.RULER_H + view.ROW_H * 4 + 10
    view._canvas_click(_pointer(x, y))
    view._canvas_drag(_pointer(x + view.cell_w * 8, y))
    view._canvas_release(None)
    notes = [n for n in view.selected_track.notes if n.id != editor.note.id]
    assert len(notes) == 9
    assert [n.start for n in notes] == pytest.approx([3 + i / 4 for i in range(9)])
    assert len(view._undo_stack) == 1
    view.undo()
    assert len(view.selected_track.notes) == 1


def test_control_marquee_works_in_draw_tool(editor):
    from blipkit.ui.editor_shortcuts import PRIMARY_MASK

    view = editor.view
    view.set_tool("画笔")
    x1, y1, x2, y2 = view._note_rectangle(editor.note)
    view._canvas_click(_pointer(x1 - 8, y1 - 1, PRIMARY_MASK))
    view._canvas_drag(_pointer(x2 + 8, y2 + 1, PRIMARY_MASK))
    view._canvas_release(None)
    assert len(view.selected_track.notes) == 1
    assert view.selected_note_ids == {editor.note.id}
    assert not view._undo_stack


def test_erase_sweep_is_one_undo(editor):
    view = editor.view
    second = Note(124, 3, 1)
    view.selected_track.notes.append(second)
    view.redraw()
    view._erase_press(_pointer(*_note_center(view, editor.note)))
    view._canvas_drag(_pointer(*_note_center(view, second)))
    view._canvas_release(None)
    assert not view.selected_track.notes
    assert len(view._undo_stack) == 1
    view.undo()
    assert len(view.selected_track.notes) == 2


def test_fl_tool_keys_and_duplicate_deselect(editor):
    view = editor.view
    view.canvas.focus_force()
    for key, tool in (
        ("p", "画笔"),
        ("b", "连画"),
        ("e", "选择"),
        ("d", "擦除"),
        ("c", "切片"),
        ("y", "试听"),
    ):
        view.canvas.event_generate(f"<KeyPress-{key}>")
        editor.root.update()
        assert view.tool_var.get() == tool
    view._set_selection({editor.note.id}, editor.note.id)
    modifier = "Command" if sys.platform == "darwin" else "Control"
    view.canvas.event_generate(f"<{modifier}-b>")
    editor.root.update()
    assert len(view.selected_track.notes) == 2
    view.canvas.event_generate(f"<{modifier}-d>")
    editor.root.update()
    assert not view.selected_note_ids


def test_duplicate_extends_song_and_undo_restores_length(editor):
    view = editor.view
    editor.note.start = 15
    view._set_selection({editor.note.id}, editor.note.id)
    view.duplicate_selected_note()
    assert view.song.bars == 5
    assert view.song.loop_end == 20
    view.undo()
    assert view.song.bars == 4
    assert view.song.loop_end == 16
    assert len(view.selected_track.notes) == 1


def test_song_controls_and_loop_selection_are_undoable(editor):
    view = editor.view
    view.bpm_var.set("150")
    view._apply_song_controls()
    view._set_selection({editor.note.id}, editor.note.id)
    view.loop_selection()
    view.create_playback_plan(8000)
    assert (view.song.loop_start, view.song.loop_end) == (1, 2)
    view.undo()
    assert (view.song.loop_start, view.song.loop_end) == (0, 16)
    view.undo()
    assert view.song.bpm == 120
    assert view.bpm_var.get() == "120"


def test_velocity_lane_drag_is_undoable(editor):
    view = editor.view
    x = _x_at_beat(view, editor.note.start)
    view._velocity_press(_pointer(x, 50))
    view._velocity_drag(_pointer(x, 40))
    view._canvas_release(None)
    assert editor.note.velocity == round(30 / 54 * 127)
    assert len(view._undo_stack) == 1
    view.undo()
    assert view.selected_track.notes[0].velocity == 100


def test_arrangement_drag_moves_note_to_another_track(editor):
    view = editor.view
    view.set_editor_view("编排")
    editor.root.update()
    arrangement = view.arrangement_view
    item = next(
        item for item, (_, note) in arrangement._note_items.items() if note.id == editor.note.id
    )
    x1, y1, x2, y2 = arrangement.timeline.coords(item)
    start = _pointer((x1 + x2) / 2, (y1 + y2) / 2)
    arrangement._timeline_click(start)
    end = _pointer(start.x + arrangement.cell_w * 4, start.y + arrangement.ROW_H)
    arrangement._timeline_drag(end)
    arrangement._timeline_release(end)
    assert not view.song.tracks[0].notes
    assert view.song.tracks[1].notes[0].start == 2
    view.undo()
    assert len(view.song.tracks[0].notes) == 1
    assert not view.song.tracks[1].notes


def test_edge_drag_scrolls_and_stops_after_release(editor):
    view = editor.view
    _drag_note(view, editor.note, view.canvas.winfo_width())
    before = view.canvas.canvasx(0)
    view._auto_scroll()
    assert view.canvas.canvasx(0) > before
    view._canvas_release(None)
    assert view._auto_scroll_id is None


def test_imported_short_notes_keep_duration_when_transposed(editor):
    view = editor.view
    editor.note.duration = 0.07
    view._set_selection({editor.note.id}, editor.note.id)
    view.nudge_selected(pitches=-1)
    assert editor.note.duration == 0.07


def test_disabling_loop_plays_full_song_without_losing_region(editor):
    view = editor.view
    view._set_selection({editor.note.id}, editor.note.id)
    view.loop_selection()
    view.loop_var.set(False)
    view.insert_beat = 0
    plan = view.create_playback_plan(8000)
    assert plan.start_beat == 0
    assert plan.song.loop_end == 16
    assert (view.song.loop_start, view.song.loop_end) == (1, 2)
    assert view.duration() == 8
