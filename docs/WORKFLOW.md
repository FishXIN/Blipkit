# FL 风格制作流程与本地验收

版本：0.2.0 · 2026-11-19

## 开始制作

1. 双击 `dist/Blipkit.app`，或双击仓库根目录的 `启动 Blipkit.command`（使用本地虚拟环境）。
2. 在左侧音乐列表点 `+` 创建空白音乐；设置 BPM、拍号、音色。`+ 轨道` 在两个编辑视图都能使用。
3. 按 `F7` 进入钢琴卷帘。`P` 单击写音符，拖动改变长度；`B` 连续绘制重复音符。新音符沿用上一次长度。
4. 按住 `Cmd/Ctrl` 拖动空白框选。拖动选择移动；`Shift` 拖动复制；按住 `Alt/Option` 临时自由移动。左右边缘均可调整长度。
5. 在底部力度区拖动设置力度。已选音符时只改所选集合；未选择时可编辑当前轨所有音符。`Alt/Option + 滚轮` 批量调整力度。
6. `Cmd/Ctrl + B` 重复乐句，空间不足时自动增加小节（上限 128）。`Alt/Option + Q` 量化；`Cmd/Ctrl + L` 连奏。
7. `F5` 回到编排；直接拖动音符修改时间或换轨，支持当前轨框选和 Shift 拖拽复制。双击进入精修。
8. `Cmd/Ctrl + Enter` 循环选择；钢琴卷帘标尺上 `Shift + 拖动` 自定义循环范围。关闭循环开关后恢复整曲播放，保留原循环区域。
9. `Space` 播放 / 停止返回起播点；`Cmd/Ctrl + Space` 暂停 / 继续。输入框中的空格只输入文字。
10. `Cmd/Ctrl + S` 保存。`Cmd/Ctrl + R` 或顶部导出按钮在后台导出已保存的工程快照，导出期间可以继续编辑。完成后状态栏显示输出目录；引擎路径在工程设置中配置。

一次拖拽、连续画笔、连续擦除或力度笔画只占一步撤销。拖拽中按 Esc 还原本次操作，同时保留此前的重做记录。切换页面和资产时保留本次运行的撤销历史、工具、缩放、选择和播放位置。

## 快捷键约定

完整快捷键位于应用内 `F1` 帮助和 README。Mac 使用 Command / Option，Windows 使用 Ctrl / Alt。

采用 FL 的 `P/B/E/D/C/Y` 工具键、`Cmd/Ctrl+B` 重复、`Cmd/Ctrl+D` 取消选择、Shift 拖拽克隆、Alt 临时自由吸附、F5/F7、八度移调、量化与连奏等常用习惯。参考：

- [Image-Line：Keyboard & Mouse Shortcuts](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/basics_shortcuts.htm)
- [Image-Line：Piano roll](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/pianoroll.htm)

保留常见多步撤销行为：`Cmd/Ctrl+Z` 撤销，`Cmd/Ctrl+Shift+Z` / `Cmd/Ctrl+Y` 重做。方向键本身也支持移动音符。`Cmd/Ctrl+N` 仍为新建工程，`Cmd/Ctrl+I` 导入 MIDI。并非 FL 的全部快捷键与功能都已实现。

编排当前仍以音符为单位，未引入 Pattern、音频片段、自动化、录音或 VST。导出沿用工程的循环起止范围；若要导出整曲，可选择全部音符后设置范围，或将标尺循环区域设为整曲。

## 实现与验证

- `editor_shortcuts.py`：两个视图共用一个键盘路由，输入框保留原生文字编辑行为。
- `piano_interaction.py`：指针操作事务、增量 Canvas 更新、边缘滚动、取消、力度编辑。
- `arrangement_view.py`：编排中的音符选择、移动、复制和换轨。
- `audition.py`：后台试听队列，只播放最新请求，缓存 64 个已渲染音符。
- `ExportSnapshot`：后台导出使用操作开始时的独立数据快照和独立 SQLite 连接。
- 工程参数和循环范围纳入撤销；导入 MIDI 前提交修改；保存前提交速度与小节输入。

本机 Tk 测试覆盖快捷键路由、输入框保护、拖动与两端缩放、复制、取消、单步撤销、框选、画笔、擦除、跨轨移动、边缘滚动、力度、循环、扩展小节、页面切换历史、保存与后台任务隔离。

验证结果：84 项测试通过；Ruff 与 Python 编译检查通过；打包应用连续运行 8 秒无异常退出或 traceback，并成功创建示例工程。原生 AVFoundation 音频引擎成功播放 Grand Piano 采样音符，播放时钟正常前进。应用签名完整性检查通过；arm64 压缩包约 58 MB，应用约 97 MB。

本机拖拽基准（macOS 26.6.2 / Apple Silicon / Python 3.12.0）：256 个音符、同时移动 32 个音符、120 次 motion + idle drawing；中位数 0.51 ms，P95 0.53 ms，松手提交 12.85 ms，拖动期间整屏重绘 0 次。运行 `.venv/bin/python scripts/benchmark_editor.py` 可复测。此数据不含音频试听延迟，不代表其他设备或大型工程的端到端延迟。

尚未完成的验收：Windows 实机、触控板真实捏合、多小时制作与设备音频延迟测量。桌面截图检查工具在本轮中途断连；交互验证使用真实 Tk 事件测试与实际窗口尺寸检查。播放仍使用预渲染音频，循环边界和首次音色准备不保证实时 DAW 级延迟。

## 本地开发

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/python scripts/benchmark_editor.py
./build_app.sh
```

macOS 的 Tk 测试需要可用的桌面会话。macOS 包使用本地临时签名，尚未进行 Apple 公证。Windows 包不包含商业代码签名。发布包与平台可用性以 [GitHub Releases](https://github.com/FishXIN/Blipkit/releases/tag/v0.2.0) 为准。
