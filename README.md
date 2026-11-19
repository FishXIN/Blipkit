# Blipkit

[![CI](https://github.com/FishXIN/Blipkit/actions/workflows/ci.yml/badge.svg)](https://github.com/FishXIN/Blipkit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

面向独立游戏开发者的轻量桌面音频工作站，支持 macOS 与 Windows。音乐编排、程序化音效、乐理辅助、资产管理和游戏引擎导出集中在一个单窗口工作区内。

> 当前为 v0.2.0 预发布版本，文件格式与交互仍可能调整。

## 当前可用能力

- 多轨编排总览与 Piano Roll 双视图，支持框选、多选、轨道混音、和弦和循环试听
- MIDI 导入导出、可变小节数、吸附、缩放、量化、力度编辑和完整撤销/重做
- 80 个内置音色：62 个真实 SoundFont 采样音色和 18 个专用芯片音色
- 22 个游戏 SFX 预设，支持 ADSR、颤音、低通、位深压缩、自动试听和可撤销变体
- `.bkproj` 工程目录、自动保存、手动快照、SQLite 50 步操作历史和 ZIP 备份
- WAV / OGG / MP3 / FLAC 导出
- Unity、Godot 4、Unreal Engine 5、Web 和自定义目录输出
- Web 双格式导出与 `AudioManifest.js` 自动生成
- 无账号、无联网依赖、无 Electron

## 开发运行

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pip install --no-deps "tinysoundfont==0.3.7"
.venv/bin/python main.py
```

首次启动会在系统应用数据目录创建一个可直接试听和编辑的 `Starter.bkproj` 示例工程：

- macOS：`~/Library/Application Support/Blipkit`
- Windows：`%APPDATA%\Blipkit`

可通过 `BLIPKIT_DATA_DIR` 覆盖。

## 主要操作 · FL 风格

- `F5 / F7` 切换编排 / 钢琴卷帘；双击编排音符进入单轨编辑；`F1` 查看完整帮助。
- `P` 画笔（默认）、`B` 连画、`E` 选择、`D` 擦除、`C` 切片、`Y` 试听。
- 单击写入，拖动写入长度；记住上次音符长度。`B` 可连续填入音符。
- `Cmd/Ctrl + 拖动空白` 框选，追加 `Shift` 保留选择；选择工具中可直接框选。
- 拖动音符移动，`Shift + 拖动` 复制，拖动两端改变时长，`Alt/Option` 临时取消吸附。
- 右键按住擦除；中键拖动平移；拖到边缘自动滚动。`Esc` 取消本次拖拽。
- 编排中可直接选择当前轨的音符、框选、拖动换轨、Shift 拖动复制。
- 底部力度区拖动编辑；`Alt/Option + 滚轮` 改所选音符力度。
- 方向键或 `Shift + 方向键` 移动 / 半音移调；`Cmd/Ctrl + ↑↓` 八度移调。
- `Cmd/Ctrl + B` 向右重复；`Cmd/Ctrl + D` 取消选择；`Cmd/Ctrl + C/X/V/A` 剪贴板和全选。
- `Alt/Option + Q` 量化，`Cmd/Ctrl + L` 连奏；`Insert` 在播放头处分割，或用切片工具。
- `Delete` 删除（Mac 为 `Fn + Delete`）；`Backspace` 切换吸附。
- `Cmd/Ctrl + Z` 撤销，`Cmd/Ctrl + Shift + Z` 或 `Cmd/Ctrl + Y` 重做。一次拖拽只记一步。
- `Cmd/Ctrl + Enter` 循环所选；钢琴卷帘中 `Shift + 拖动标尺` 设置循环区域。
- `Space` 播放 / 停止并返回起播点；`Cmd/Ctrl + Space` 暂停 / 继续。
- 滚轮纵向浏览，`Shift + 滚轮` 横向浏览；`Cmd/Ctrl + 滚轮` 或捏合按指针位置缩放。
- `PageUp / PageDown` 缩放，`Shift + 4` 整曲适配，`Shift + 5` 选区适配。
- `Cmd/Ctrl + S` 保存，`Cmd/Ctrl + R` 导出。导出在后台进行，可继续编辑。

重复和粘贴会自动增加小节，最多 128 小节。切换资产或页面保留当前会话的撤销历史。
输入框保留系统文字编辑行为。编排仍基于音符，尚未加入 FL Studio 的 Pattern / 音频片段模型。

详细制作流程、兼容差异与验收记录见 [docs/WORKFLOW.md](docs/WORKFLOW.md)。

## CLI

```bash
python cli.py create ./MyGame.bkproj --template RPG
python cli.py info ./MyGame.bkproj
python cli.py list ./MyGame.bkproj
python cli.py export ./MyGame.bkproj ./build/audio --format wav
python cli.py export ./MyGame.bkproj ./web/public --engine Web
```

## 测试

```bash
.venv/bin/pytest
```

## 打包

macOS：

```bash
chmod +x build_app.sh
./build_app.sh
```

Windows PowerShell：

```powershell
.\build_windows.ps1
```

两端均使用 PyInstaller `onedir` 模式，避免单文件包每次启动时解压造成的等待。

## 工程结构

```text
Blipkit/
├── main.py
├── cli.py
├── src/blipkit/
│   ├── core/
│   │   ├── sequencer.py
│   │   ├── midi_io.py
│   │   ├── sfx_synth.py
│   │   ├── soundbank.py
│   │   ├── audio_io.py
│   │   ├── engine_bridge.py
│   │   ├── project.py
│   │   └── export.py
│   └── ui/
│       ├── app.py
│       ├── sequencer_view.py
│       ├── sfx_view.py
│       ├── library_view.py
│       └── settings_view.py
└── tests/
    └── test_core.py
```

真实乐器由内置 MuseScore General SoundFont 离线渲染，芯片分类保留程序化合成。
SoundFont 的 MIT 许可证与鸣谢见 `assets/soundfonts/MuseScore_General_License.md`。

产品边界见 [docs/PRODUCT.md](docs/PRODUCT.md)，开发顺序见 [ROADMAP.md](ROADMAP.md)，
版本记录见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

[MIT](LICENSE)
