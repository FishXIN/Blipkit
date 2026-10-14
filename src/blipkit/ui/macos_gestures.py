from __future__ import annotations

import sys
import tkinter as tk
from collections import deque
from collections.abc import Callable

try:
    if sys.platform != "darwin":
        raise ImportError
    from AppKit import NSApplication, NSMagnificationGestureRecognizer
    from Foundation import NSObject
except ImportError:
    NSApplication = None
    NSMagnificationGestureRecognizer = None
    NSObject = object


class _MagnifyTarget(NSObject):
    def handleMagnify_(self, sender) -> None:
        magnification = float(sender.magnification())
        sender.setMagnification_(0.0)
        if magnification:
            self.callback(magnification)


class MacMagnifyGesture:
    def __init__(
        self,
        widget: tk.Misc,
        callback: Callable[[float], None],
    ) -> None:
        self.widget = widget
        self.callback = callback
        self.target = None
        self.recognizer = None
        self.native_view = None
        self._closed = False
        self._install_attempts = 0
        self._pending: deque[float] = deque()
        self._poll_after_id: str | None = None
        widget.bind("<Destroy>", self._on_destroy, add="+")
        self._poll_after_id = widget.after(16, self._poll)
        if NSApplication is not None:
            widget.after_idle(self._install)

    @property
    def installed(self) -> bool:
        return self.recognizer is not None

    def _install(self) -> None:
        if self._closed or self.recognizer is not None:
            return
        try:
            title = self.widget.winfo_toplevel().title()
            app = NSApplication.sharedApplication()
            windows = list(app.windows())
            window = next(
                (candidate for candidate in windows if candidate.title() == title),
                app.keyWindow() or app.mainWindow(),
            )
            if window is None:
                raise RuntimeError("Tk window is not ready")
            self.native_view = window.contentView()
            self.target = _MagnifyTarget.alloc().init()
            self.target.callback = self._enqueue
            self.recognizer = (
                NSMagnificationGestureRecognizer.alloc().initWithTarget_action_(
                    self.target,
                    "handleMagnify:",
                )
            )
            self.native_view.addGestureRecognizer_(self.recognizer)
        except Exception:
            self.target = None
            self.recognizer = None
            self.native_view = None
            self._install_attempts += 1
            if self._install_attempts < 20 and not self._closed:
                self.widget.after(100, self._install)

    def _enqueue(self, magnification: float) -> None:
        self._pending.append(magnification)

    def _poll(self) -> None:
        self._poll_after_id = None
        if self._closed:
            return
        magnification = 0.0
        while self._pending:
            magnification += self._pending.popleft()
        if magnification:
            self.callback(magnification)
        try:
            self._poll_after_id = self.widget.after(16, self._poll)
        except tk.TclError:
            self._closed = True

    def _on_destroy(self, event) -> None:
        if event.widget is self.widget:
            self.close()

    def close(self) -> None:
        self._closed = True
        if self._poll_after_id is not None:
            try:
                self.widget.after_cancel(self._poll_after_id)
            except (tk.TclError, ValueError):
                pass
        self._poll_after_id = None
        self._pending.clear()
        if self.native_view is not None and self.recognizer is not None:
            try:
                self.native_view.removeGestureRecognizer_(self.recognizer)
            except Exception:
                pass
        self.target = None
        self.recognizer = None
        self.native_view = None
