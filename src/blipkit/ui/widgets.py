"""Reusable compact controls for the Blipkit desktop surface."""

from __future__ import annotations

import sys
from collections.abc import Callable

import customtkinter as ctk

from . import tokens as T


def ui_font(size: int = 13, weight: str = "normal", mono: bool = False):
    if mono:
        family = T.FONT_MONO_WIN if sys.platform.startswith("win") else T.FONT_MONO_MAC
    else:
        family = "Segoe UI" if sys.platform.startswith("win") else T.FONT_UI
    return ctk.CTkFont(family=family, size=size, weight=weight)


def action_button(
    parent,
    text: str,
    command: Callable | None = None,
    primary: bool = False,
    width: int = 86,
    danger: bool = False,
):
    if primary:
        fg = T.ACCENT
        hover = T.ACCENT_HOVER
        text_color = "#FFFFFF"
        border = T.ACCENT
    elif danger:
        fg = T.SURFACE
        hover = T.DANGER_SOFT
        text_color = T.DANGER
        border = T.BORDER
    else:
        fg = T.SURFACE
        hover = T.SURFACE_ALT
        text_color = T.TEXT
        border = T.BORDER
    return ctk.CTkButton(
        parent,
        text=text,
        command=command,
        width=width,
        height=30,
        corner_radius=T.RADIUS,
        border_width=1,
        border_color=border,
        fg_color=fg,
        hover_color=hover,
        text_color=text_color,
        font=ui_font(13, "bold" if primary else "normal"),
    )


class LabeledSlider(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        label: str,
        from_: float,
        to: float,
        value: float,
        command: Callable[[float], None],
        digits: int = 2,
    ):
        super().__init__(parent, fg_color="transparent")
        self._digits = digits
        self._command = command
        self.grid_columnconfigure(0, weight=1)
        self.label = ctk.CTkLabel(
            self,
            text=label,
            text_color=T.TEXT_SECONDARY,
            font=ui_font(12),
            anchor="w",
        )
        self.label.grid(row=0, column=0, sticky="w")
        self.value_label = ctk.CTkLabel(
            self,
            text=self._format(value),
            text_color=T.TEXT_MUTED,
            font=ui_font(11, mono=True),
            width=54,
            anchor="e",
        )
        self.value_label.grid(row=0, column=1, sticky="e")
        self.slider = ctk.CTkSlider(
            self,
            from_=from_,
            to=to,
            number_of_steps=200,
            height=16,
            button_length=14,
            button_color=T.ACCENT,
            button_hover_color=T.ACCENT_HOVER,
            progress_color=T.ACCENT,
            fg_color=T.BORDER,
            command=self._changed,
        )
        self.slider.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.slider.set(value)

    def _format(self, value: float) -> str:
        return ("%." + str(self._digits) + "f") % value

    def _changed(self, value: float) -> None:
        self.value_label.configure(text=self._format(value))
        self._command(float(value))

    def set(self, value: float) -> None:
        self.slider.set(value)
        self.value_label.configure(text=self._format(value))
