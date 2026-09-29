"""Flat local asset table."""

from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Callable, Iterable
from tkinter import ttk

import customtkinter as ctk

from blipkit.core.models import AssetInfo

from . import tokens as T
from .widgets import action_button, ui_font


class LibraryView(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        assets: Iterable[AssetInfo],
        on_open: Callable[[str, str], None],
        on_export: Callable[[list[str]], None],
    ):
        super().__init__(parent, fg_color=T.SURFACE)
        self.assets = list(assets)
        self.on_open = on_open
        self.on_export = on_export
        self._rows: dict[str, AssetInfo] = {}
        self.filter_var = tk.StringVar(value="全部")
        self.search_var = tk.StringVar()

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build_toolbar()
        self._build_table()
        self.refresh(self.assets)

    def _build_toolbar(self) -> None:
        toolbar = ctk.CTkFrame(self, height=48, fg_color=T.SURFACE, corner_radius=0)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_propagate(False)
        toolbar.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(
            toolbar,
            text="资产库",
            text_color=T.TEXT,
            font=ui_font(14, "bold"),
        ).grid(row=0, column=0, padx=(16, 14), pady=9)
        filter_control = ctk.CTkSegmentedButton(
            toolbar,
            values=["全部", "音乐", "音效"],
            variable=self.filter_var,
            command=lambda _value: self._populate(),
            height=28,
            corner_radius=T.RADIUS,
            fg_color=T.SURFACE_ALT,
            selected_color=T.ACCENT_SOFT,
            selected_hover_color=T.ACCENT_SOFT,
            unselected_color=T.SURFACE_ALT,
            unselected_hover_color=T.BORDER,
            text_color=T.TEXT,
            font=ui_font(11),
        )
        filter_control.grid(row=0, column=1, padx=(0, 10))
        search = ctk.CTkEntry(
            toolbar,
            width=180,
            height=28,
            textvariable=self.search_var,
            placeholder_text="搜索资产",
            corner_radius=T.RADIUS,
            border_color=T.BORDER,
            fg_color=T.SURFACE,
            font=ui_font(12),
        )
        search.grid(row=0, column=2)
        self.search_var.trace_add("write", lambda *_args: self._populate())
        action_button(
            toolbar,
            "导出所选",
            self._export_selected,
            primary=True,
            width=86,
        ).grid(row=0, column=4, padx=(8, 16))

    def _build_table(self) -> None:
        shell = ctk.CTkFrame(
            self,
            fg_color=T.SURFACE,
            corner_radius=0,
            border_width=1,
            border_color=T.BORDER,
        )
        shell.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        shell.grid_rowconfigure(0, weight=1)
        shell.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Blipkit.Treeview",
            background=T.SURFACE,
            fieldbackground=T.SURFACE,
            foreground=T.TEXT_SECONDARY,
            borderwidth=0,
            rowheight=34,
            font=("SF Pro Text", 12),
        )
        style.configure(
            "Blipkit.Treeview.Heading",
            background=T.SURFACE_ALT,
            foreground=T.TEXT_MUTED,
            borderwidth=0,
            relief="flat",
            font=("SF Pro Text", 11, "normal"),
        )
        style.map(
            "Blipkit.Treeview",
            background=[("selected", T.ACCENT_SOFT)],
            foreground=[("selected", T.TEXT)],
        )
        columns = ("name", "kind", "duration", "modified", "synced")
        self.tree = ttk.Treeview(
            shell,
            columns=columns,
            show="headings",
            selectmode="extended",
            style="Blipkit.Treeview",
        )
        labels = {
            "name": "名称",
            "kind": "类型",
            "duration": "时长",
            "modified": "最后修改",
            "synced": "引擎状态",
        }
        widths = {
            "name": 280,
            "kind": 90,
            "duration": 100,
            "modified": 180,
            "synced": 100,
        }
        for column in columns:
            self.tree.heading(column, text=labels[column], anchor="w")
            self.tree.column(
                column,
                width=widths[column],
                minwidth=70,
                stretch=column in ("name", "modified"),
                anchor="w",
            )
        scroll = ctk.CTkScrollbar(
            shell,
            orientation="vertical",
            command=self.tree.yview,
            width=12,
            fg_color=T.SURFACE,
            button_color=T.TEXT_DISABLED,
            button_hover_color=T.TEXT_MUTED,
        )
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", self._open_selected)

    def refresh(self, assets: Iterable[AssetInfo]) -> None:
        self.assets = list(assets)
        self._populate()

    def _populate(self) -> None:
        query = self.search_var.get().strip().lower()
        filter_name = self.filter_var.get()
        self.tree.delete(*self.tree.get_children())
        self._rows.clear()
        for asset in self.assets:
            if filter_name == "音乐" and asset.kind != "music":
                continue
            if filter_name == "音效" and asset.kind != "sfx":
                continue
            if query and query not in asset.name.lower():
                continue
            row_id = asset.id
            self._rows[row_id] = asset
            self.tree.insert(
                "",
                "end",
                iid=row_id,
                values=(
                    asset.name,
                    "音乐" if asset.kind == "music" else "音效",
                    f"{asset.duration:0.2f}s",
                    time.strftime("%Y-%m-%d %H:%M", time.localtime(asset.modified_at)),
                    "已同步" if asset.synced else "未导出",
                ),
            )

    def _selected_assets(self) -> list[AssetInfo]:
        return [self._rows[item] for item in self.tree.selection() if item in self._rows]

    def _open_selected(self, _event=None) -> None:
        selected = self._selected_assets()
        if selected:
            self.on_open(selected[0].kind, selected[0].id)

    def _export_selected(self) -> None:
        self.on_export([asset.id for asset in self._selected_assets()])
