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
    note = Note(pitch=82, start=1.0, duration=1.0)
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
    )
    view.pack(fill="both", expand=True)
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


def test_plain_arrow_moves_playhead_without_editing_selected_note(editor) -> None:
    view = editor.view
    view._set_edit_cursor(2.0, seek=False)
    view._set_selection({editor.note.id}, editor.note.id)
    view.canvas.focus_force()

    view.canvas.event_generate("<Right>")
    editor.root.update()

    assert view.insert_beat == pytest.approx(2.25)
    assert editor.note.start == 1.0


def test_modified_arrow_moves_selected_note_only(editor) -> None:
    view = editor.view
    view._set_edit_cursor(3.0, seek=False)
    view._set_selection({editor.note.id}, editor.note.id)
    view.canvas.focus_force()
    modifier = "Command" if sys.platform == "darwin" else "Control"

    view.canvas.event_generate(f"<{modifier}-Right>")
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
def test_qw_trim_selected_note_at_playhead(
    editor,
    key: str,
    expected_start: float,
    expected_duration: float,
) -> None:
    view = editor.view
    view._set_selection({editor.note.id}, editor.note.id)
    view._set_edit_cursor(1.5, seek=False)
    view.canvas.focus_force()

    view.canvas.event_generate(f"<KeyPress-{key}>")
    editor.root.update()

    assert editor.note.start == expected_start
    assert editor.note.duration == expected_duration


def test_er_moves_selected_notes_between_tracks(editor) -> None:
    view = editor.view
    view._set_selection({editor.note.id}, editor.note.id)
    view.canvas.focus_force()

    view.canvas.event_generate("<KeyPress-r>")
    editor.root.update()

    assert view.selected_track_index == 1
    assert editor.note in view.song.tracks[1].notes

    view.canvas.event_generate("<KeyPress-e>")
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
    view.canvas.event_generate(
        "<ButtonRelease-1>",
        x=end_x,
        y=round(y2 + 2),
    )
    view.canvas.update()

    assert view.insert_beat == 5.0
    assert view.selected_note_ids == {editor.note.id}
