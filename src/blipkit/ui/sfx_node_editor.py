"""Canvas-based editor for procedural SFX graphs."""

from __future__ import annotations

import math
import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from blipkit.core.models import SFXNode, SFXPatch
from blipkit.core.sfx_graph import (
    connect_nodes,
    ensure_patch_graph,
    make_node,
    node_param,
    node_spec,
    remove_node,
    topological_order,
)

from . import tokens as T
from .widgets import ui_font

NODE_W = 172
NODE_H = 94
HEADER_H = 30
PORT_R = 6
GRID = 40

CHOICE_LABELS = {
    "Sine": "正弦",
    "Triangle": "三角",
    "Sawtooth": "锯齿",
    "Square": "方波",
    "White": "白噪声",
    "Dark": "暗噪声",
    "Bright": "亮噪声",
    "Drop": "水滴",
    "Flow": "水流",
    "Splash": "飞溅",
    "Metal": "金属",
    "Glass": "玻璃",
    "Wood": "木材",
    "Plate": "薄板",
    "Tube": "管体",
    "Cavity": "空腔",
    "Vessel": "容器",
    "Lowpass": "低通",
    "Highpass": "高通",
    "Bandpass": "带通",
    "Room": "房间",
    "Hall": "大厅",
    "Underwater": "水下",
}


def display_choice(value: str) -> str:
    return CHOICE_LABELS.get(value, value)


def stored_choice(display: str, choices: tuple[str, ...]) -> str:
    for value in choices:
        if display_choice(value) == display:
            return value
    return choices[0] if choices else display


class SFXNodeEditor(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        patch: SFXPatch,
        on_select: Callable[[str | None], None],
        on_begin_edit: Callable[[], None],
        on_change: Callable[[bool], None],
        on_status: Callable[[str], None],
    ):
        super().__init__(parent, fg_color=T.SURFACE_ALT, corner_radius=T.RADIUS_PANEL)
        self.patch = patch
        self.on_select = on_select
        self.on_begin_edit = on_begin_edit
        self.on_change = on_change
        self.on_status = on_status
        self.selected_id: str | None = None
        self._drag_node: str | None = None
        self._drag_offset = (0.0, 0.0)
        self._drag_changed = False
        self._connecting_from: str | None = None
        self.zoom = 0.7
        self._fit_pending = True

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build_toolbar()
        self._build_canvas()
        had_graph = bool(self.patch.graph_nodes)
        ensure_patch_graph(self.patch)
        if had_graph:
            self.redraw()
        else:
            self.auto_layout(record=False)
        self._select_initial()
        self.after_idle(self.fit_view)

    def _build_toolbar(self) -> None:
        toolbar = ctk.CTkFrame(self, height=42, fg_color="transparent", corner_radius=0)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        toolbar.grid_propagate(False)
        toolbar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            toolbar,
            text="节点画布",
            text_color=T.TEXT,
            font=ui_font(T.TEXT_14, "bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=(16, 8), pady=(12, 8))
        self.zoom_label = ctk.CTkLabel(
            toolbar,
            text="70%",
            text_color=T.TEXT_MUTED,
            font=ui_font(T.TEXT_12),
            anchor="e",
        )
        self.zoom_label.grid(row=0, column=1, sticky="e", padx=(0, 4), pady=(12, 8))
        for column, text, command, width in (
            (2, "−", self.zoom_out, 30),
            (3, "+", self.zoom_in, 30),
            (4, "适配", self.fit_view, 46),
            (5, "整理", self.auto_layout, 46),
        ):
            ctk.CTkButton(
                toolbar,
                text=text,
                width=width,
                height=28,
                corner_radius=T.RADIUS,
                border_width=0,
                fg_color="transparent",
                hover_color=T.NAV_ACTIVE,
                text_color=T.TEXT_SECONDARY,
                font=ui_font(T.TEXT_12),
                command=command,
            ).grid(row=0, column=column, padx=(0, 2), pady=(8, 6))

    def _build_canvas(self) -> None:
        self.canvas = tk.Canvas(
            self,
            bg=T.SURFACE_ALT,
            highlightthickness=0,
            bd=0,
            scrollregion=(0, 0, 1400, 720),
        )
        self.canvas.grid(row=1, column=0, sticky="nsew")
        vertical = ctk.CTkScrollbar(
            self,
            orientation="vertical",
            command=self.canvas.yview,
            fg_color="transparent",
            button_color=T.TEXT_DISABLED,
            button_hover_color=T.TEXT_MUTED,
            width=12,
        )
        vertical.grid(row=1, column=1, sticky="ns")
        horizontal = ctk.CTkScrollbar(
            self,
            orientation="horizontal",
            command=self.canvas.xview,
            fg_color="transparent",
            button_color=T.TEXT_DISABLED,
            button_hover_color=T.TEXT_MUTED,
            height=12,
        )
        horizontal.grid(row=2, column=0, sticky="ew")
        self.canvas.configure(
            xscrollcommand=horizontal.set,
            yscrollcommand=vertical.set,
        )
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<ButtonPress-2>", self._pan_start)
        self.canvas.bind("<B2-Motion>", self._pan_move)
        self.canvas.bind("<MouseWheel>", self._mouse_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self._shift_mouse_wheel)
        self.canvas.bind("<Configure>", self._canvas_configured)

    def _select_initial(self) -> None:
        output = next(
            (node for node in self.patch.graph_nodes if node.kind == "output"),
            None,
        )
        self.select(output.id if output else self.patch.graph_nodes[0].id)

    def set_patch(self, patch: SFXPatch) -> None:
        self.patch = patch
        had_graph = bool(self.patch.graph_nodes)
        ensure_patch_graph(self.patch)
        self.selected_id = None
        self._fit_pending = True
        if had_graph:
            self.redraw()
        else:
            self.auto_layout(record=False)
        self._select_initial()
        self.after_idle(self.fit_view)

    def selected_node(self) -> SFXNode | None:
        return next(
            (node for node in self.patch.graph_nodes if node.id == self.selected_id),
            None,
        )

    def select(self, node_id: str | None) -> None:
        self.selected_id = node_id
        self.on_select(node_id)
        self.redraw()

    def add_node(self, kind: str) -> None:
        self.on_begin_edit()
        visible_x, visible_y = self._world_point(
            max(80, self.canvas.winfo_width() // 2),
            max(80, self.canvas.winfo_height() // 2),
        )
        offset = (len(self.patch.graph_nodes) % 4) * 24
        node = make_node(kind, visible_x - NODE_W / 2 + offset, visible_y - 40 + offset)
        self.patch.graph_nodes.append(node)
        self.patch.graph_enabled = True
        self.selected_id = node.id
        self.on_change(True)
        self.on_select(node.id)
        self.on_status(f"已添加{node_spec(kind).label}节点")
        self.redraw()

    def delete_selected(self) -> None:
        node = self.selected_node()
        if node is None:
            return
        self.on_begin_edit()
        self.patch.graph_nodes, self.patch.graph_connections = remove_node(
            self.patch.graph_nodes,
            self.patch.graph_connections,
            node.id,
        )
        self.selected_id = None
        self.on_change(True)
        self.on_select(None)
        self.on_status(f"已删除{node_spec(node.kind).label}节点")
        self.redraw()

    def disconnect_selected_input(self) -> None:
        node = self.selected_node()
        if node is None:
            return
        remaining = [
            item
            for item in self.patch.graph_connections
            if item.target != node.id
        ]
        if len(remaining) == len(self.patch.graph_connections):
            self.on_status("当前节点没有输入连线")
            return
        self.on_begin_edit()
        self.patch.graph_connections = remaining
        self.patch.graph_enabled = True
        self.on_change(True)
        self.on_status("已断开节点输入")
        self.redraw()

    def auto_layout(self, record: bool = True) -> None:
        if not self.patch.graph_nodes:
            return
        try:
            order = topological_order(
                self.patch.graph_nodes,
                self.patch.graph_connections,
            )
        except ValueError:
            order = [node.id for node in self.patch.graph_nodes]
        if record:
            self.on_begin_edit()
        incoming: dict[str, list[str]] = {node.id: [] for node in self.patch.graph_nodes}
        for item in self.patch.graph_connections:
            if item.target in incoming:
                incoming[item.target].append(item.source)
        depth: dict[str, int] = {}
        for node_id in order:
            parents = incoming.get(node_id, [])
            depth[node_id] = max((depth.get(parent, 0) + 1 for parent in parents), default=0)
        rows: dict[int, int] = {}
        for node_id in order:
            node = self._node(node_id)
            if node is None:
                continue
            column = depth.get(node_id, 0)
            row = rows.get(column, 0)
            node.x = 48 + column * 220
            node.y = 70 + row * 130
            rows[column] = row + 1
        if record:
            self.on_change(False)
            self.on_status("已整理节点")
        self.redraw()

    def zoom_in(self) -> None:
        self.zoom = min(1.2, self.zoom + 0.1)
        self._fit_pending = False
        self.redraw()

    def zoom_out(self) -> None:
        self.zoom = max(0.4, self.zoom - 0.1)
        self._fit_pending = False
        self.redraw()

    def fit_view(self) -> None:
        if not self.patch.graph_nodes or not hasattr(self, "canvas"):
            return
        viewport_w = max(240, self.canvas.winfo_width())
        viewport_h = max(180, self.canvas.winfo_height())
        fitted = 0.4
        for step in range(100, 39, -1):
            candidate = step / 100.0
            content_w = max(
                node.x * candidate + max(80.0, NODE_W * candidate)
                for node in self.patch.graph_nodes
            )
            content_h = max(
                node.y * candidate + max(44.0, NODE_H * candidate)
                for node in self.patch.graph_nodes
            )
            if content_w + 20 <= viewport_w and content_h + 20 <= viewport_h:
                fitted = candidate
                break
        self.zoom = fitted
        self._fit_pending = False
        self.canvas.xview_moveto(0.0)
        self.canvas.yview_moveto(0.0)
        self.redraw()

    def _canvas_configured(self, _event) -> None:
        if self._fit_pending:
            self.after_idle(self.fit_view)
        else:
            self.redraw()

    def redraw(self) -> None:
        if not hasattr(self, "canvas"):
            return
        self.canvas.delete("all")
        max_x = max(
            (
                self._node_bounds(node)[0]
                + self._node_bounds(node)[2]
                + 48
                for node in self.patch.graph_nodes
            ),
            default=self.canvas.winfo_width(),
        )
        max_y = max(
            (
                self._node_bounds(node)[1]
                + self._node_bounds(node)[3]
                + 48
                for node in self.patch.graph_nodes
            ),
            default=self.canvas.winfo_height(),
        )
        width = max(self.canvas.winfo_width(), int(max_x))
        height = max(self.canvas.winfo_height(), int(max_y))
        self.canvas.configure(scrollregion=(0, 0, width, height))
        self._draw_grid(width, height)
        for connection in self.patch.graph_connections:
            source = self._node(connection.source)
            target = self._node(connection.target)
            if source is not None and target is not None:
                self._draw_connection(source, target)
        for node in self.patch.graph_nodes:
            self._draw_node(node)
        self.zoom_label.configure(text=f"{int(round(self.zoom * 100))}%")

    def _draw_grid(self, width: int, height: int) -> None:
        step = max(20, int(round(GRID * self.zoom)))
        for x in range(0, width + step, step):
            self.canvas.create_line(x, 0, x, height, fill=T.BORDER_LIGHT)
        for y in range(0, height + step, step):
            self.canvas.create_line(0, y, width, y, fill=T.BORDER_LIGHT)

    def _draw_connection(self, source: SFXNode, target: SFXNode) -> None:
        start_x, start_y = self._output_position(source)
        end_x, end_y = self._input_position(target)
        bend = max(36.0, abs(end_x - start_x) * 0.42)
        self.canvas.create_line(
            start_x,
            start_y,
            start_x + bend,
            start_y,
            end_x - bend,
            end_y,
            end_x,
            end_y,
            fill=T.ACCENT,
            width=2,
            smooth=True,
            splinesteps=24,
        )

    def _draw_node(self, node: SFXNode) -> None:
        selected = node.id == self.selected_id
        spec = node_spec(node.kind)
        outline = T.ACCENT if selected else T.BORDER
        x, y, width, height = self._node_bounds(node)
        compact = self.zoom < 0.7
        header_height = height if compact else max(24, HEADER_H * self.zoom)
        self.canvas.create_rectangle(
            x,
            y,
            x + width,
            y + height,
            fill=T.SURFACE,
            outline=outline,
            width=2 if selected else 1,
        )
        self.canvas.create_rectangle(
            x + 1,
            y + 1,
            x + width - 1,
            y + header_height,
            fill=T.NAV_ACTIVE if selected else T.SURFACE_HOVER,
            outline="",
        )
        self.canvas.create_text(
            x + 10,
            y + header_height / 2 + 1,
            text=spec.label,
            anchor="w",
            fill=T.TEXT,
            font=ui_font(T.TEXT_13, "bold"),
        )
        if self.zoom >= 0.85:
            self.canvas.create_text(
                x + width - 8,
                y + header_height / 2 + 1,
                text=spec.group,
                anchor="e",
                fill=T.TEXT_MUTED,
                font=ui_font(T.TEXT_12),
            )
        if not compact:
            summaries = []
            for param in spec.params[:2]:
                value = node_param(node, param.key)
                if isinstance(value, str):
                    formatted = display_choice(value)
                elif param.digits == 0:
                    formatted = str(int(round(float(value))))
                else:
                    formatted = f"{float(value):.{param.digits}f}"
                summaries.append(f"{param.label}  {formatted}")
            for index, summary in enumerate(summaries):
                self.canvas.create_text(
                    x + 10,
                    y + header_height + 15 + index * 19,
                    text=summary,
                    anchor="w",
                    fill=T.TEXT_SECONDARY if index == 0 else T.TEXT_MUTED,
                    font=ui_font(T.TEXT_12),
                )
        if spec.has_input:
            port_x, port_y = self._input_position(node)
            self.canvas.create_oval(
                port_x - PORT_R,
                port_y - PORT_R,
                port_x + PORT_R,
                port_y + PORT_R,
                fill=T.SURFACE,
                outline=T.TEXT_MUTED,
                width=2,
            )
        if spec.has_output:
            port_x, port_y = self._output_position(node)
            self.canvas.create_oval(
                port_x - PORT_R,
                port_y - PORT_R,
                port_x + PORT_R,
                port_y + PORT_R,
                fill=T.ACCENT,
                outline=T.ACCENT,
            )

    def _node(self, node_id: str) -> SFXNode | None:
        return next(
            (node for node in self.patch.graph_nodes if node.id == node_id),
            None,
        )

    def _node_bounds(self, node: SFXNode) -> tuple[float, float, float, float]:
        x = node.x * self.zoom
        y = node.y * self.zoom
        width = max(80.0, NODE_W * self.zoom)
        height = max(44.0, NODE_H * self.zoom)
        return x, y, width, height

    def _input_position(self, node: SFXNode) -> tuple[float, float]:
        x, y, _width, height = self._node_bounds(node)
        return x, y + height / 2

    def _output_position(self, node: SFXNode) -> tuple[float, float]:
        x, y, width, height = self._node_bounds(node)
        return x + width, y + height / 2

    def _canvas_point(self, event) -> tuple[float, float]:
        return self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def _world_point(self, x: float, y: float) -> tuple[float, float]:
        return self.canvas.canvasx(x) / self.zoom, self.canvas.canvasy(y) / self.zoom

    def _hit_node(self, x: float, y: float) -> SFXNode | None:
        for node in reversed(self.patch.graph_nodes):
            left, top, width, height = self._node_bounds(node)
            if left <= x <= left + width and top <= y <= top + height:
                return node
        return None

    def _hit_port(self, x: float, y: float, output: bool) -> SFXNode | None:
        for node in self.patch.graph_nodes:
            spec = node_spec(node.kind)
            if output and not spec.has_output:
                continue
            if not output and not spec.has_input:
                continue
            port_x, port_y = (
                self._output_position(node) if output else self._input_position(node)
            )
            if math.hypot(x - port_x, y - port_y) <= PORT_R + 6:
                return node
        return None

    def _press(self, event) -> None:
        x, y = self._canvas_point(event)
        output = self._hit_port(x, y, output=True)
        if output is not None:
            self._connecting_from = output.id
            self.select(output.id)
            return
        node = self._hit_node(x, y)
        if node is None:
            self.select(None)
            return
        self.select(node.id)
        self._drag_node = node.id
        world_x, world_y = self._world_point(event.x, event.y)
        self._drag_offset = (world_x - node.x, world_y - node.y)
        self._drag_changed = False

    def _motion(self, event) -> None:
        x, y = self._canvas_point(event)
        if self._connecting_from is not None:
            source = self._node(self._connecting_from)
            if source is None:
                return
            start_x, start_y = self._output_position(source)
            bend = max(54.0, abs(x - start_x) * 0.42)
            self.canvas.delete("preview")
            self.canvas.create_line(
                start_x,
                start_y,
                start_x + bend,
                start_y,
                x - bend,
                y,
                x,
                y,
                fill=T.TEXT_MUTED,
                width=2,
                dash=(5, 4),
                smooth=True,
                splinesteps=24,
                tags="preview",
            )
            return
        node = self._node(self._drag_node or "")
        if node is None:
            return
        world_x, world_y = self._world_point(event.x, event.y)
        new_x = max(8.0, world_x - self._drag_offset[0])
        new_y = max(8.0, world_y - self._drag_offset[1])
        if abs(new_x - node.x) > 1.0 or abs(new_y - node.y) > 1.0:
            if not self._drag_changed:
                self.on_begin_edit()
            self._drag_changed = True
            node.x = new_x
            node.y = new_y
            self.redraw()

    def _release(self, event) -> None:
        x, y = self._canvas_point(event)
        if self._connecting_from is not None:
            source = self._connecting_from
            target = self._hit_port(x, y, output=False)
            self._connecting_from = None
            self.canvas.delete("preview")
            if target is not None:
                try:
                    updated = connect_nodes(
                        self.patch.graph_nodes,
                        self.patch.graph_connections,
                        source,
                        target.id,
                    )
                except ValueError as error:
                    self.on_status(str(error))
                else:
                    self.on_begin_edit()
                    self.patch.graph_connections = updated
                    self.patch.graph_enabled = True
                    self.on_change(True)
                    self.select(target.id)
                    self.on_status("节点已连接")
            self.redraw()
            return
        if self._drag_changed:
            self.on_change(False)
        self._drag_node = None
        self._drag_changed = False

    def _pan_start(self, event) -> None:
        self.canvas.scan_mark(event.x, event.y)

    def _pan_move(self, event) -> None:
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _mouse_wheel(self, event) -> str:
        direction = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(direction, "units")
        return "break"

    def _shift_mouse_wheel(self, event) -> str:
        direction = -1 if event.delta > 0 else 1
        self.canvas.xview_scroll(direction, "units")
        return "break"
