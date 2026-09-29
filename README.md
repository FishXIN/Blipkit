# Blipkit

[![CI](https://github.com/FishXIN/Blipkit/actions/workflows/ci.yml/badge.svg)](https://github.com/FishXIN/Blipkit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

面向独立游戏开发者的轻量桌面音频工作站，支持 macOS 与 Windows。音乐编排、程序化音效、乐理辅助、资产管理和游戏引擎导出集中在一个单窗口工作区内。

> 当前为 Pre-alpha 原型，文件格式与交互可能继续调整。

## 当前可用能力

- Piano Roll 多轨编排，支持点击写入、音阶提示、和弦插入与无缝 Loop 渲染
- 80 个轻量内置程序化音色，覆盖芯片、键盘、弦乐、木管、铜管和民族音色
- 22 个游戏 SFX 预设，支持波形、ADSR、音调曲线、噪声和随机种子调节
- `.bkproj` 工程目录、自动保存、手动快照、SQLite 50 步操作历史和 ZIP 备份
- WAV / OGG / MP3 / FLAC 导出
- Unity、Godot 4、Unreal Engine 5、Web 和自定义目录输出
- Web 双格式导出与 `AudioManifest.js` 自动生成
- 无账号、无联网依赖、无 Electron

## 开发运行

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python main.py
```

首次启动会在系统应用数据目录创建一个可直接试听和编辑的 `Starter.bkproj` 示例工程：

- macOS：`~/Library/Application Support/Blipkit`
- Windows：`%APPDATA%\Blipkit`

可通过 `BLIPKIT_DATA_DIR` 覆盖。

## 主要操作

- 点击 Piano Roll 空白格写入音符
- 单击音符选中，双击或右键删除
- `Space` 播放或停止，`Cmd/Ctrl + S` 保存
- 左侧切换音乐编排、音效生成、资产管理和工程设置
- 工程设置中绑定 Unity、Godot、Unreal 或 Web 输出目录

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

当前内置音色采用程序化合成以保持包体和启动速度；外部 SF2 导入及真实采样音色属于后续版本范围。

产品边界见 [docs/PRODUCT.md](docs/PRODUCT.md)，开发顺序见 [ROADMAP.md](ROADMAP.md)。

## 许可证

[MIT](LICENSE)
