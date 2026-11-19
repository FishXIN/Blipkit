"""One FL-style keymap shared by both music editors and the application."""

import sys

PRIMARY_MASK = 0x0008 if sys.platform == "darwin" else 0x0004
ALT_MASK = 0x0010 if sys.platform == "darwin" else 0x0008


def primary(event):
    return bool(event.state & (PRIMARY_MASK | 0x0004))


def alt(event):
    return bool(event.state & ALT_MASK)


def handle_editor_key(view, event):
    key = event.keysym.lower()
    command = primary(event)
    shift = bool(event.state & 1)
    option = alt(event)
    action = None
    if key == "escape":
        action = view.cancel_gesture
    elif view.gesture_active:
        # Do not interleave history, tools or transport with a pointer transaction.
        return "break"
    elif command:
        actions = {
            "a": view.clear_note_selection if shift else view.select_all_notes,
            "b": view.duplicate_selected_note,
            "d": view.clear_note_selection,
            "c": view.copy_selected_notes,
            "x": view.cut_selected_notes,
            "v": view.paste_notes_at_playhead,
            "z": view.redo if shift else view.undo,
            "y": view.redo,
            "q": view.quantize_selected,
            "l": view.legato_selected,
            "1": lambda: view.set_editor_view("编排"),
            "2": lambda: view.set_editor_view("钢琴卷帘"),
            "equal": lambda: view.zoom_horizontal(4),
            "plus": lambda: view.zoom_horizontal(4),
            "minus": lambda: view.zoom_horizontal(-4),
            "return": view.loop_selection,
            "up": lambda: view.nudge_selected(pitches=12),
            "down": lambda: view.nudge_selected(pitches=-12),
            "left": lambda: view.jump_to_adjacent_edit(-1),
            "right": lambda: view.jump_to_adjacent_edit(1),
        }
        action = actions.get(key)
    elif key in ("left", "right", "up", "down"):
        step = 1 / 96 if option else view._snap_size()
        action = {
            "left": lambda: view.nudge_selected(beats=-step),
            "right": lambda: view.nudge_selected(beats=step),
            "up": lambda: view.nudge_selected(pitches=1),
            "down": lambda: view.nudge_selected(pitches=-1),
        }[key]
    elif option and key == "q":
        action = view.quantize_selected
    elif not option:
        actions = {
            "space": view.on_play,
            "p": lambda: view.set_tool("画笔"),
            "b": lambda: view.set_tool("连画"),
            "e": lambda: view.set_tool("选择"),
            "d": lambda: view.set_tool("擦除"),
            "c": lambda: view.set_tool("切片"),
            "y": lambda: view.set_tool("试听"),
            "g": lambda: view.select_track(view.selected_track_index - 1),
            "k": lambda: view.select_track(view.selected_track_index + 1),
            "delete": view.delete_selected_note,
            "backspace": view.toggle_snap,
            "insert": view.split_selected_at_playhead,
            "home": lambda: view.jump_to_timeline_edge(False),
            "end": lambda: view.jump_to_timeline_edge(True),
            "prior": lambda: view.zoom_horizontal(4),
            "next": lambda: view.zoom_horizontal(-4),
            "f5": lambda: view.set_editor_view("编排"),
            "f7": lambda: view.set_editor_view("钢琴卷帘"),
            "f1": view.show_shortcut_help,
            "4": view.fit_song if shift else None,
            "5": view.zoom_selection if shift else None,
        }
        action = actions.get(key)
    if action is not None:
        action()
        return "break"
    return None


SHORTCUT_HELP = """FL 风格操作

P 画笔 · B 连画 · E 选择 · D 擦除 · C 切片 · Y 试听
F5 编排 · F7 钢琴卷帘 · F1 操作帮助

单击空白写音符；拖动控制长度，记住上次时长
Ctrl / Cmd + 拖动空白框选；加 Shift 追加选择
Shift + 拖动音符复制；Alt / Option 拖动临时自由吸附
拖动音符两端调整时长；右键按住滑动连续擦除
中键拖动画布；拖到边缘自动滚动；Esc 取消本次拖拽

方向键 / Shift + 方向键：移动、半音移调
Ctrl / Cmd + ↑↓：八度移调；Alt / Option + ←→：精细移动
Ctrl / Cmd + B：向右重复；Ctrl / Cmd + D：取消选择
Ctrl / Cmd + A / C / X / V：全选 / 复制 / 剪切 / 粘贴
Ctrl / Cmd + Z：撤销；Shift + Z 或 Y：重做
Alt / Option + Q：量化；Ctrl / Cmd + L：连奏
Delete：删除（Mac 为 Fn + Delete）；Backspace：切换吸附
Ctrl / Cmd + Enter：循环所选；Shift + 拖动标尺：设置循环

Space：播放 / 停止并回到起播点；Ctrl / Cmd + Space：暂停 / 继续
Home / End：播放头到首尾；Ctrl / Cmd + ←→：相邻音符边界
滚轮：纵向滚动；Shift + 滚轮：横向滚动
Ctrl / Cmd + 滚轮、触控板捏合：以指针为中心缩放
PageUp / PageDown：缩放；Shift + 4：整曲适配；Shift + 5：选区适配
Alt / Option + 滚轮：调整所选音符力度

编排视图可直接选取、框选当前轨音符，拖动换轨与 Shift 复制。
双击轨道进入钢琴卷帘。当前编排单位是音符，尚不提供 FL Pattern。
输入框使用系统文字编辑快捷键。"""
