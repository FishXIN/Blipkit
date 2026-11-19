"""Local Tk drag benchmark. Run with .venv/bin/python scripts/benchmark_editor.py."""

from __future__ import annotations

import json
import math
import platform
import statistics
import time
from types import SimpleNamespace

import customtkinter as ctk

from blipkit.core.models import Note, Song, Track
from blipkit.ui.sequencer_view import SequencerView

root = ctk.CTk()
root.geometry("1360x840")
notes = [Note(124 - i % 12, 1 + i / 4, 0.2) for i in range(256)]
song = Song("Benchmark", bars=32, loop_end=128, tracks=[Track("Lead", notes=notes)])
view = SequencerView(
    root,
    song,
    lambda: None,
    lambda: None,
    lambda _: None,
    lambda: None,
    lambda *_: None,
    lambda: None,
    lambda: None,
)
view.pack(fill="both", expand=True)
view.set_editor_view("钢琴卷帘")
view.set_tool("选择")
root.update()
view.canvas.yview_moveto(0)
view._set_selection({n.id for n in notes[:32]}, notes[0].id)
view.redraw()
root.update()
x1, y1, x2, y2 = view._note_rectangle(notes[0])
x, y = round((x1 + x2) / 2), round((y1 + y2) / 2)
view._canvas_click(SimpleNamespace(x=x, y=y, state=0))
redraws = []
original = view.redraw
view.redraw = lambda: redraws.append(True)
frames = []
for i in range(120):
    event = SimpleNamespace(x=x + round(100 + 80 * math.sin(i / 12)), y=y, state=0)
    started = time.perf_counter()
    view._canvas_drag(event)
    root.update_idletasks()
    frames.append((time.perf_counter() - started) * 1000)
view.redraw = original
started = time.perf_counter()
view._canvas_release(None)
release_ms = (time.perf_counter() - started) * 1000
result = {
    "platform": platform.platform(),
    "python": platform.python_version(),
    "notes": 256,
    "selected": 32,
    "motion_events": len(frames),
    "median_ms": round(statistics.median(frames), 2),
    "p95_ms": round(sorted(frames)[int(len(frames) * 0.95)], 2),
    "release_ms": round(release_ms, 2),
    "full_redraws_during_motion": len(redraws),
    "scope": "Tk motion + idle drawing, audition disabled; not audio latency",
}
root.destroy()
print(json.dumps(result, indent=2))
assert not redraws
