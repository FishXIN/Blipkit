from __future__ import annotations

import sys
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
    view.selected_track.notes.append(
        Note(pitch=72, start=0.0, duration=1.0)
    )
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
