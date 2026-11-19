from __future__ import annotations

import gc
import sys
import threading
import tkinter as tk

import pytest

from blipkit.core.models import Note
from blipkit.ui.app import BlipkitApp
from blipkit.ui.sequencer_view import SequencerView


@pytest.fixture
def shortcut_app(tmp_path, monkeypatch):
    monkeypatch.setenv("BLIPKIT_DATA_DIR", str(tmp_path))
    try:
        app = BlipkitApp()
    except tk.TclError as exc:
        pytest.skip(f"Tk display unavailable: {exc}")
    app.withdraw()
    app.update()
    yield app
    app._close()


def test_standard_select_undo_and_redo_shortcuts(shortcut_app) -> None:
    app = shortcut_app
    view = app.current_view
    assert isinstance(view, SequencerView)
    view.set_editor_view("钢琴卷帘")
    view.select_track(0)
    app.deiconify()
    app.update()
    view.canvas.focus_force()
    app.update()

    view._clear_selection()
    view.canvas.event_generate("<Control-a>")
    app.update()
    assert len(view.selected_note_ids) == len(view.selected_track.notes)

    view.canvas.event_generate("<Control-Shift-A>")
    app.update()
    assert not view.selected_note_ids

    original_count = len(view.selected_track.notes)
    view._push_undo()
    view.selected_track.notes.append(Note(pitch=72, start=0.0, duration=1.0))
    view.redraw()

    view.canvas.event_generate("<Control-z>")
    app.update()
    assert len(view.selected_track.notes) == original_count

    view.canvas.event_generate("<Control-y>")
    app.update()
    assert len(view.selected_track.notes) == original_count + 1


def test_native_platform_shortcuts_remain_bound(shortcut_app) -> None:
    app = shortcut_app
    modifier = "Command" if sys.platform == "darwin" else "Control"
    for key in ("a", "c", "x", "v", "z", "s", "o", "n"):
        assert app.bind_all(f"<{modifier}-{key}>")
    assert app.bind_all(f"<{modifier}-Shift-Z>")
    assert app.bind_all(f"<{modifier}-y>")
    assert app.bind_all("<Escape>")


def test_ui_cycles_are_collected_on_ui_thread(shortcut_app):
    # A cycle created by the UI may otherwise be finalized by the next worker
    # allocation, deadlocking Tcl finalizers and the sampled-instrument lock.
    finalized_on = []

    class Cycle:
        def __init__(self):
            self.cycle = self

        def __del__(self):
            finalized_on.append(threading.get_ident())

    Cycle()
    assert not gc.isenabled()
    worker = threading.Thread(target=lambda: [Cycle() for _ in range(2000)])
    worker.start()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert not finalized_on
    shortcut_app.after_cancel(shortcut_app._garbage_after_id)
    shortcut_app._garbage_ticks = 59
    shortcut_app._collect_ui_garbage()
    assert len(finalized_on) == 2001
    assert set(finalized_on) == {threading.get_ident()}


def test_entry_typing_does_not_edit_or_play_music(shortcut_app, monkeypatch):
    app = shortcut_app
    view = app.current_view
    app.deiconify()
    view.set_editor_view("钢琴卷帘")
    view.select_all_notes()
    count = len(view.selected_track.notes)
    view.note_velocity_entry.focus_force()
    app.update()
    calls = []
    monkeypatch.setattr(app, "toggle_playback", lambda: calls.append("play"))
    view.note_velocity_entry._entry.event_generate("<KeyPress-p>")
    view.note_velocity_entry._entry.event_generate("<space>")
    view.note_velocity_entry._entry.event_generate("<Delete>")
    app.update()
    assert not calls
    assert len(view.selected_track.notes) == count


def test_editor_history_survives_page_switch(shortcut_app):
    app = shortcut_app
    view = app.current_view
    view.set_editor_view("钢琴卷帘")
    view.select_track(0)
    note = view.selected_track.notes[0]
    original_pitch = note.pitch
    view._set_selection({note.id}, note.id)
    view.nudge_selected(pitches=1)
    app.show_view("library")
    app.show_view("music")
    view = app.current_view
    assert view.view_var.get() == "钢琴卷帘"
    assert view.selected_track.notes[0].pitch == original_pitch + 1
    view.undo()
    assert view.selected_track.notes[0].pitch == original_pitch


def test_save_applies_pending_tempo(shortcut_app):
    app = shortcut_app
    view = app.current_view
    view.bpm_var.set("147")
    app.save_current()
    saved = next(song for _, song in app.project.load_songs() if song.id == view.song.id)
    assert saved.bpm == 147


def test_pause_shortcut_does_not_restart_playback(shortcut_app, monkeypatch):
    app = shortcut_app
    calls = []
    monkeypatch.setattr(app, "stop_playback", lambda: calls.append("pause"))
    monkeypatch.setattr(app, "toggle_playback", lambda: calls.append("toggle"))
    app._playing = True
    app.deiconify()
    view = app.current_view
    view.set_editor_view("钢琴卷帘")
    view.canvas.focus_force()
    app.update()
    modifier = "Command" if sys.platform == "darwin" else "Control"
    view.canvas.event_generate(f"<{modifier}-space>")
    app.update()
    assert calls == ["pause"]
    app._playing = False


def test_controls_fit_minimum_window(shortcut_app):
    app = shortcut_app
    app.geometry("1240x700")
    app.deiconify()
    app.update()
    view = app.current_view
    # Exercise each toolbar button at the actual supported minimum window size.
    toolbar = view.transport_button.master.master
    for row in toolbar.winfo_children():
        for widget in row.winfo_children():
            if widget.winfo_manager() == "pack" and hasattr(widget, "_text"):
                assert widget.winfo_ismapped(), getattr(widget, "_text", "")
                assert widget.winfo_x() + widget.winfo_width() <= row.winfo_width() + 2, (
                    getattr(widget, "_text", ""),
                    widget.winfo_x(),
                    widget.winfo_width(),
                    row.winfo_width(),
                )
