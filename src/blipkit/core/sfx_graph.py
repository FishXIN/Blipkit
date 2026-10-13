"""Editable procedural SFX graph and DSP evaluator."""

from __future__ import annotations

import math
import random
import zlib
from dataclasses import dataclass

import numpy as np

from .dsp import band_limited_wave, limit_peak, one_pole_lowpass
from .models import SFXConnection, SFXNode, SFXPatch


@dataclass(frozen=True)
class NodeParam:
    key: str
    label: str
    default: float | str
    minimum: float | None = None
    maximum: float | None = None
    digits: int = 2
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class NodeSpec:
    kind: str
    label: str
    group: str
    params: tuple[NodeParam, ...]
    has_input: bool = True
    has_output: bool = True


NODE_SPECS: dict[str, NodeSpec] = {
    "oscillator": NodeSpec(
        "oscillator",
        "振荡器",
        "声源",
        (
            NodeParam(
                "waveform",
                "波形",
                "Sine",
                choices=("Sine", "Triangle", "Sawtooth", "Square"),
            ),
            NodeParam("start_freq", "起始频率 Hz", 700.0, 20.0, 4000.0, 0),
            NodeParam("end_freq", "结束频率 Hz", 320.0, 20.0, 4000.0, 0),
            NodeParam("bend", "频率曲线", 1.0, 0.2, 3.0, 2),
            NodeParam("level", "电平", 0.8, 0.0, 1.0, 2),
        ),
        has_input=False,
    ),
    "noise": NodeSpec(
        "noise",
        "噪声",
        "声源",
        (
            NodeParam("color", "颜色", "White", choices=("White", "Dark", "Bright")),
            NodeParam("cutoff", "截止频率 Hz", 4200.0, 80.0, 16000.0, 0),
            NodeParam("level", "电平", 0.5, 0.0, 1.0, 2),
        ),
        has_input=False,
    ),
    "impact": NodeSpec(
        "impact",
        "敲击",
        "声源",
        (
            NodeParam("hardness", "硬度", 0.7, 0.0, 1.0, 2),
            NodeParam("size", "尺寸", 0.5, 0.0, 1.0, 2),
            NodeParam("level", "电平", 0.9, 0.0, 1.0, 2),
        ),
        has_input=False,
    ),
    "water": NodeSpec(
        "water",
        "水体",
        "声源",
        (
            NodeParam("mode", "形态", "Drop", choices=("Drop", "Flow", "Splash")),
            NodeParam("rate", "事件密度", 12.0, 1.0, 36.0, 1),
            NodeParam("size", "水滴尺寸", 0.5, 0.0, 1.0, 2),
            NodeParam("turbulence", "湍流", 0.5, 0.0, 1.0, 2),
            NodeParam("level", "电平", 0.8, 0.0, 1.0, 2),
        ),
        has_input=False,
    ),
    "mixer": NodeSpec(
        "mixer",
        "混合",
        "组合",
        (NodeParam("gain", "总增益", 0.8, 0.0, 1.5, 2),),
    ),
    "resonator": NodeSpec(
        "resonator",
        "共振器",
        "处理",
        (
            NodeParam("material", "材质", "Metal", choices=("Metal", "Glass", "Wood")),
            NodeParam("shape", "形体", "Plate", choices=("Plate", "Tube", "Cavity", "Vessel")),
            NodeParam("frequency", "基频 Hz", 360.0, 35.0, 2400.0, 0),
            NodeParam("size", "尺寸", 0.5, 0.0, 1.0, 2),
            NodeParam("decay", "衰减 s", 1.2, 0.03, 3.0, 2),
            NodeParam("brightness", "明亮度", 0.75, 0.0, 1.0, 2),
            NodeParam("mix", "干湿比", 0.9, 0.0, 1.0, 2),
        ),
    ),
    "filter": NodeSpec(
        "filter",
        "滤波器",
        "处理",
        (
            NodeParam("mode", "模式", "Lowpass", choices=("Lowpass", "Highpass", "Bandpass")),
            NodeParam("cutoff", "截止频率 Hz", 5200.0, 40.0, 18000.0, 0),
            NodeParam("resonance", "共振", 0.2, 0.0, 1.0, 2),
        ),
    ),
    "envelope": NodeSpec(
        "envelope",
        "包络",
        "处理",
        (
            NodeParam("attack", "起音 s", 0.005, 0.001, 1.0, 3),
            NodeParam("decay", "衰减 s", 0.08, 0.005, 2.0, 3),
            NodeParam("sustain", "延音", 0.35, 0.0, 1.0, 2),
            NodeParam("release", "释音 s", 0.12, 0.005, 2.0, 3),
        ),
    ),
    "distortion": NodeSpec(
        "distortion",
        "失真",
        "处理",
        (
            NodeParam("drive", "驱动", 3.0, 1.0, 20.0, 1),
            NodeParam("mix", "干湿比", 0.35, 0.0, 1.0, 2),
        ),
    ),
    "space": NodeSpec(
        "space",
        "空间",
        "处理",
        (
            NodeParam("type", "类型", "Room", choices=("Room", "Hall", "Underwater")),
            NodeParam("amount", "空间量", 0.2, 0.0, 1.0, 2),
            NodeParam("decay", "反射衰减", 0.5, 0.0, 1.0, 2),
        ),
    ),
    "output": NodeSpec(
        "output",
        "输出",
        "输出",
        (NodeParam("volume", "输出音量", 1.0, 0.0, 1.0, 2),),
        has_output=False,
    ),
}

NODE_GROUPS = ("声源", "组合", "处理", "输出")


def node_spec(kind: str) -> NodeSpec:
    return NODE_SPECS.get(kind, NODE_SPECS["oscillator"])


def make_node(kind: str, x: float, y: float, **overrides) -> SFXNode:
    spec = node_spec(kind)
    params = {item.key: item.default for item in spec.params}
    params.update(overrides)
    return SFXNode(kind=spec.kind, x=x, y=y, params=params)


def node_param(node: SFXNode, key: str) -> float | str:
    for param in node_spec(node.kind).params:
        if param.key == key:
            return node.params.get(key, param.default)
    return node.params.get(key, 0.0)


def _connections_for_ids(
    node_ids: set[str],
    connections: list[SFXConnection],
) -> list[SFXConnection]:
    return [
        item
        for item in connections
        if item.source in node_ids and item.target in node_ids and item.source != item.target
    ]


def topological_order(
    nodes: list[SFXNode],
    connections: list[SFXConnection],
) -> list[str]:
    node_ids = {node.id for node in nodes}
    valid = _connections_for_ids(node_ids, connections)
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for item in valid:
        incoming[item.target] += 1
        outgoing[item.source].append(item.target)
    ready = sorted(node_id for node_id, count in incoming.items() if count == 0)
    order = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for target in outgoing[node_id]:
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
                ready.sort()
    if len(order) != len(node_ids):
        raise ValueError("音效节点图不能包含环路")
    return order


def connect_nodes(
    nodes: list[SFXNode],
    connections: list[SFXConnection],
    source: str,
    target: str,
) -> list[SFXConnection]:
    by_id = {node.id: node for node in nodes}
    if source not in by_id or target not in by_id or source == target:
        raise ValueError("无效的节点连接")
    if not node_spec(by_id[source].kind).has_output:
        raise ValueError("输出节点不能连接到其他节点")
    if not node_spec(by_id[target].kind).has_input:
        raise ValueError("声源节点不能接收输入")

    result = [
        item
        for item in connections
        if not (item.source == source and item.target == target)
    ]
    if by_id[target].kind != "mixer":
        result = [item for item in result if item.target != target]
    result.append(SFXConnection(source=source, target=target))
    topological_order(nodes, result)
    return result


def remove_node(
    nodes: list[SFXNode],
    connections: list[SFXConnection],
    node_id: str,
) -> tuple[list[SFXNode], list[SFXConnection]]:
    return (
        [node for node in nodes if node.id != node_id],
        [
            item
            for item in connections
            if item.source != node_id and item.target != node_id
        ],
    )


def _wire(nodes: list[SFXNode], *pairs: tuple[int, int]) -> list[SFXConnection]:
    return [
        SFXConnection(source=nodes[source].id, target=nodes[target].id)
        for source, target in pairs
    ]


def build_template_graph(
    template: str,
    patch: SFXPatch,
) -> tuple[list[SFXNode], list[SFXConnection]]:
    if template in {"metal_plate", "metal_tube", "glass_hit", "wood_knock"}:
        material = {
            "metal_plate": ("Metal", "Plate", 360.0, 1.35, 0.82, 0.58),
            "metal_tube": ("Metal", "Tube", 280.0, 1.2, 0.72, 0.72),
            "glass_hit": ("Glass", "Vessel", 620.0, 1.05, 0.9, 0.42),
            "wood_knock": ("Wood", "Cavity", 210.0, 0.32, 0.42, 0.64),
        }[template]
        name, shape, frequency, decay, hardness, size = material
        nodes = [
            make_node("impact", 40, 150, hardness=hardness, size=size, level=0.92),
            make_node(
                "resonator",
                250,
                150,
                material=name,
                shape=shape,
                frequency=frequency,
                size=size,
                decay=decay,
                brightness=hardness,
                mix=0.92,
            ),
            make_node(
                "envelope",
                460,
                150,
                attack=0.001,
                decay=0.09,
                sustain=0.55 if name == "Metal" else 0.35,
                release=min(1.2, decay * 0.65),
            ),
            make_node(
                "space",
                670,
                150,
                type="Room",
                amount=0.16 if name != "Wood" else 0.05,
                decay=0.45,
            ),
            make_node("output", 880, 150, volume=1.0),
        ]
        return nodes, _wire(nodes, (0, 1), (1, 2), (2, 3), (3, 4))

    if template in {"water_drop", "water_flow", "water_splash"}:
        mode = {
            "water_drop": "Drop",
            "water_flow": "Flow",
            "water_splash": "Splash",
        }[template]
        nodes = [
            make_node(
                "water",
                40,
                150,
                mode=mode,
                rate=3.0 if mode == "Drop" else 18.0,
                size=0.38 if mode == "Drop" else 0.62,
                turbulence=0.28 if mode == "Drop" else 0.76,
                level=0.86,
            ),
            make_node(
                "filter",
                250,
                150,
                mode="Bandpass",
                cutoff=2400.0 if mode == "Drop" else 3200.0,
                resonance=0.34,
            ),
            make_node(
                "envelope",
                460,
                150,
                attack=0.002 if mode == "Drop" else 0.08,
                decay=0.12,
                sustain=0.72 if mode == "Flow" else 0.28,
                release=0.18 if mode == "Drop" else 0.3,
            ),
            make_node("space", 670, 150, type="Room", amount=0.12, decay=0.35),
            make_node("output", 880, 150, volume=1.0),
        ]
        return nodes, _wire(nodes, (0, 1), (1, 2), (2, 3), (3, 4))

    source_kind = "noise" if patch.waveform.lower() == "noise" else "oscillator"
    if source_kind == "noise":
        source = make_node(
            "noise",
            40,
            150,
            color="Dark",
            cutoff=max(500.0, patch.start_freq * 5.0),
            level=1.0,
        )
    else:
        source = make_node(
            "oscillator",
            40,
            150,
            waveform=patch.waveform,
            start_freq=patch.start_freq,
            end_freq=patch.end_freq,
            bend=patch.bend,
            level=max(0.1, 1.0 - patch.noise * 0.65),
        )
    nodes = [
        source,
        make_node(
            "envelope",
            250,
            150,
            attack=patch.attack,
            decay=patch.decay,
            sustain=patch.sustain,
            release=patch.release,
        ),
        make_node(
            "filter",
            460,
            150,
            mode="Lowpass",
            cutoff=180.0 + patch.lowpass_cutoff**2 * 16000.0,
            resonance=0.08,
        ),
        make_node("output", 670, 150, volume=1.0),
    ]
    connections = _wire(nodes, (0, 1), (1, 2), (2, 3))
    if patch.noise > 0.01 and source_kind != "noise":
        noise = make_node(
            "noise",
            40,
            300,
            color="White",
            cutoff=max(500.0, patch.start_freq * 5.0),
            level=patch.noise,
        )
        mixer = make_node("mixer", 250, 235, gain=0.8)
        nodes.extend((noise, mixer))
        connections = _wire(nodes, (0, 5), (4, 5), (5, 1), (1, 2), (2, 3))
    return nodes, connections


def ensure_patch_graph(patch: SFXPatch) -> None:
    if patch.graph_nodes:
        return
    if patch.material == "Water":
        template = "water_flow" if patch.exciter == "Flow" else "water_drop"
    elif patch.material == "Metal":
        template = "metal_tube" if patch.body == "Tube" else "metal_plate"
    elif patch.material == "Glass":
        template = "glass_hit"
    elif patch.material == "Wood":
        template = "wood_knock"
    else:
        template = "legacy"
    patch.graph_nodes, patch.graph_connections = build_template_graph(template, patch)


def apply_graph_template(patch: SFXPatch, template: str) -> SFXPatch:
    patch.graph_nodes, patch.graph_connections = build_template_graph(template, patch)
    patch.graph_enabled = True
    return patch


def vary_graph_nodes(
    nodes: list[SFXNode],
    rng: random.Random,
    amount: float,
) -> list[SFXNode]:
    result = []
    spread = min(0.35, max(0.01, amount))
    for node in nodes:
        params = dict(node.params)
        for spec in node_spec(node.kind).params:
            if spec.minimum is None or spec.maximum is None:
                continue
            value = float(params.get(spec.key, spec.default))
            span = spec.maximum - spec.minimum
            changed = value + rng.uniform(-span * spread, span * spread)
            params[spec.key] = min(spec.maximum, max(spec.minimum, changed))
        result.append(SFXNode(node.kind, node.x, node.y, params, node.id))
    return result


def _node_rng(patch: SFXPatch, node: SFXNode) -> np.random.Generator:
    node_seed = zlib.crc32(node.id.encode("utf-8"))
    return np.random.default_rng((int(patch.seed) ^ node_seed) & 0xFFFFFFFF)


def _source_oscillator(
    node: SFXNode,
    frames: int,
    sample_rate: int,
) -> np.ndarray:
    start = float(node_param(node, "start_freq"))
    end = float(node_param(node, "end_freq"))
    bend = max(0.08, float(node_param(node, "bend")))
    t = np.linspace(0.0, 1.0, frames, endpoint=False, dtype=np.float64)
    frequency = start + (end - start) * np.power(t, bend)
    phase_step = frequency / sample_rate
    cycle = np.cumsum(phase_step)
    waveform = str(node_param(node, "waveform")).lower()
    signal = band_limited_wave(cycle, phase_step, waveform)
    return signal * float(node_param(node, "level"))


def _source_noise(
    patch: SFXPatch,
    node: SFXNode,
    frames: int,
    sample_rate: int,
) -> np.ndarray:
    rng = _node_rng(patch, node)
    white = rng.uniform(-1.0, 1.0, frames)
    cutoff = min(sample_rate * 0.45, float(node_param(node, "cutoff")))
    color = str(node_param(node, "color"))
    if color == "Dark":
        signal = one_pole_lowpass(white, cutoff, sample_rate)
    elif color == "Bright":
        signal = white - one_pole_lowpass(white, cutoff, sample_rate)
    else:
        signal = white
    return signal * float(node_param(node, "level"))


def _source_impact(
    patch: SFXPatch,
    node: SFXNode,
    frames: int,
    sample_rate: int,
) -> np.ndarray:
    rng = _node_rng(patch, node)
    seconds = np.arange(frames, dtype=np.float64) / sample_rate
    hardness = float(node_param(node, "hardness"))
    size = float(node_param(node, "size"))
    level = float(node_param(node, "level"))
    noise = rng.uniform(-1.0, 1.0, frames)
    burst = np.exp(-seconds / (0.003 + (1.0 - hardness) * 0.026))
    thump_frequency = 42.0 + (1.0 - size) * 150.0
    thump = np.sin(2.0 * np.pi * thump_frequency * seconds)
    thump *= np.exp(-seconds / (0.035 + size * 0.09))
    return (noise * burst * (0.55 + hardness * 0.45) + thump * 0.38) * level


def _water_event(
    signal: np.ndarray,
    seconds: np.ndarray,
    start: float,
    frequency: float,
    lifetime: float,
    amplitude: float,
    sample_rate: int,
) -> None:
    start_frame = min(len(signal) - 1, max(0, int(start * sample_rate)))
    local = seconds[start_frame:] - start
    sweep_time = max(0.012, lifetime * 0.45)
    phase = 2.0 * np.pi * frequency * sweep_time * (
        1.0 - np.exp(-local / sweep_time)
    )
    envelope = (1.0 - np.exp(-local * 260.0)) * np.exp(-local / lifetime)
    signal[start_frame:] += np.sin(phase) * envelope * amplitude


def _source_water(
    patch: SFXPatch,
    node: SFXNode,
    frames: int,
    sample_rate: int,
) -> np.ndarray:
    rng = _node_rng(patch, node)
    seconds = np.arange(frames, dtype=np.float64) / sample_rate
    mode = str(node_param(node, "mode"))
    rate = float(node_param(node, "rate"))
    size = float(node_param(node, "size"))
    turbulence = float(node_param(node, "turbulence"))
    level = float(node_param(node, "level"))
    duration = frames / sample_rate
    signal = np.zeros(frames, dtype=np.float64)
    if mode == "Drop":
        count = max(1, int(round(rate)))
        starts = [0.0]
        if count > 1:
            starts.extend(sorted(rng.uniform(0.04, duration * 0.82, count - 1)))
    else:
        count = max(2, int(round(rate * duration)))
        starts = sorted(rng.uniform(0.0, duration * 0.94, count))
    for index, start in enumerate(starts):
        frequency = (520.0 + (1.0 - size) * 1450.0) * rng.uniform(0.72, 1.32)
        lifetime = 0.035 + size * 0.12 + rng.uniform(0.015, 0.08)
        amplitude = rng.uniform(0.25, 0.7) / (1.0 + index * 0.025)
        _water_event(
            signal,
            seconds,
            float(start),
            frequency,
            lifetime,
            amplitude,
            sample_rate,
        )
    white = rng.uniform(-1.0, 1.0, frames)
    if mode == "Flow":
        flow = one_pole_lowpass(white, 900.0 + turbulence * 5200.0, sample_rate)
        motion = (
            0.72
            + 0.17 * np.sin(2.0 * np.pi * 1.3 * seconds)
            + 0.11 * np.sin(2.0 * np.pi * 4.7 * seconds + 0.8)
        )
        signal += flow * motion * (0.28 + turbulence * 0.32)
    elif mode == "Splash":
        burst = np.exp(-seconds / (0.045 + size * 0.11))
        signal += white * burst * (0.42 + turbulence * 0.45)
    return signal * level


def _sum_inputs(inputs: list[np.ndarray], frames: int) -> np.ndarray:
    if not inputs:
        return np.zeros(frames, dtype=np.float64)
    signal = np.sum(np.stack(inputs, axis=0), axis=0)
    if len(inputs) > 1:
        signal /= math.sqrt(len(inputs))
    return signal


def _fft_convolve(signal: np.ndarray, impulse: np.ndarray, frames: int) -> np.ndarray:
    total = len(signal) + len(impulse) - 1
    fft_size = 1 << max(1, total - 1).bit_length()
    spectrum = np.fft.rfft(signal, fft_size) * np.fft.rfft(impulse, fft_size)
    return np.fft.irfft(spectrum, fft_size)[:frames]


def _resonator(
    signal: np.ndarray,
    node: SFXNode,
    frames: int,
    sample_rate: int,
) -> np.ndarray:
    material = str(node_param(node, "material")).lower()
    shape = str(node_param(node, "shape")).lower()
    frequency = float(node_param(node, "frequency"))
    size = float(node_param(node, "size"))
    decay = float(node_param(node, "decay"))
    brightness = float(node_param(node, "brightness"))
    mix = float(node_param(node, "mix"))
    ratios = {
        "metal": (1.0, 2.71, 5.18, 8.43, 12.1, 16.8),
        "glass": (1.0, 2.32, 4.25, 6.63, 9.38),
        "wood": (1.0, 1.47, 2.09, 2.93, 3.74),
    }.get(material, (1.0, 2.0, 3.0, 4.0))
    if shape == "tube":
        ratios = (1.0, 2.02, 3.01, 4.03, 5.05, 6.08)
    elif shape == "cavity":
        ratios = (0.54, *ratios[:4])
    elif shape == "vessel":
        ratios = (0.78, 1.0, 2.32, 4.25, 6.63)
    elif shape == "plate":
        ratios = tuple(
            ratio * factor
            for ratio, factor in zip(
                ratios,
                (1.0, 1.06, 0.94, 1.11, 0.91, 1.04),
                strict=False,
            )
        )
    base = frequency * (2.0 ** ((0.5 - size) * 2.0))
    impulse_frames = min(frames, max(32, int(decay * sample_rate * 3.0)))
    t = np.arange(impulse_frames, dtype=np.float64) / sample_rate
    impulse = np.zeros(impulse_frames, dtype=np.float64)
    weight_sum = 0.0
    for index, ratio in enumerate(ratios):
        mode_frequency = base * ratio
        if mode_frequency >= sample_rate * 0.46:
            continue
        weight = 1.0 / (1.0 + index * (0.75 - brightness * 0.42))
        mode_decay = max(0.012, decay / (1.0 + index * 0.16))
        impulse += (
            np.sin(2.0 * np.pi * mode_frequency * t)
            * np.exp(-t / mode_decay)
            * weight
        )
        weight_sum += weight
    if weight_sum:
        impulse /= weight_sum
    energy = float(np.sqrt(np.sum(impulse**2)))
    if energy > 1e-9:
        impulse /= energy
    wet = _fft_convolve(signal, impulse, frames)
    wet_peak = float(np.max(np.abs(wet))) if wet.size else 0.0
    dry_peak = float(np.max(np.abs(signal))) if signal.size else 0.0
    if wet_peak > 1e-9 and dry_peak > 1e-9:
        wet *= min(12.0, dry_peak * 1.15 / wet_peak)
    return signal * (1.0 - mix) + wet * mix


def _biquad(
    signal: np.ndarray,
    mode: str,
    cutoff: float,
    resonance: float,
    sample_rate: int,
) -> np.ndarray:
    cutoff = min(sample_rate * 0.45, max(20.0, cutoff))
    q = 0.55 + max(0.0, min(1.0, resonance)) * 10.0
    omega = 2.0 * np.pi * cutoff / sample_rate
    alpha = math.sin(omega) / (2.0 * q)
    cos_omega = math.cos(omega)
    if mode == "Highpass":
        b0 = (1.0 + cos_omega) / 2.0
        b1 = -(1.0 + cos_omega)
        b2 = b0
    elif mode == "Bandpass":
        b0 = alpha
        b1 = 0.0
        b2 = -alpha
    else:
        b0 = (1.0 - cos_omega) / 2.0
        b1 = 1.0 - cos_omega
        b2 = b0
    a0 = 1.0 + alpha
    a1 = -2.0 * cos_omega
    a2 = 1.0 - alpha
    b0, b1, b2 = b0 / a0, b1 / a0, b2 / a0
    a1, a2 = a1 / a0, a2 / a0
    output = np.zeros_like(signal, dtype=np.float64)
    x1 = x2 = y1 = y2 = 0.0
    for index, sample in enumerate(signal):
        value = b0 * sample + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        output[index] = value
        x2, x1 = x1, sample
        y2, y1 = y1, value
    return output


def _envelope(
    signal: np.ndarray,
    node: SFXNode,
    frames: int,
    sample_rate: int,
) -> np.ndarray:
    attack = min(frames, max(1, int(float(node_param(node, "attack")) * sample_rate)))
    decay = min(
        max(0, frames - attack),
        max(1, int(float(node_param(node, "decay")) * sample_rate)),
    )
    release = min(
        max(1, frames - attack - decay),
        max(1, int(float(node_param(node, "release")) * sample_rate)),
    )
    sustain = float(node_param(node, "sustain"))
    sustain_start = min(frames, attack + decay)
    release_start = max(sustain_start, frames - release)
    env = np.full(frames, sustain, dtype=np.float64)
    env[:attack] = np.linspace(0.0, 1.0, attack)
    if decay:
        env[attack:sustain_start] = np.linspace(1.0, sustain, decay)
    env[release_start:] = np.linspace(sustain, 0.0, frames - release_start)
    return signal * env


def _space(signal: np.ndarray, node: SFXNode, sample_rate: int) -> np.ndarray:
    amount = float(node_param(node, "amount"))
    decay = float(node_param(node, "decay"))
    space_type = str(node_param(node, "type"))
    if amount <= 0.001:
        return signal
    source = signal
    if space_type == "Underwater":
        source = one_pole_lowpass(source, 420.0 + (1.0 - amount) * 1200.0, sample_rate)
        taps = ((0.028, 0.44), (0.061, 0.3), (0.097, 0.2))
    elif space_type == "Hall":
        taps = ((0.043, 0.52), (0.071, 0.4), (0.109, 0.3), (0.157, 0.22))
    else:
        taps = ((0.017, 0.46), (0.031, 0.31), (0.047, 0.2))
    wet = np.zeros_like(source, dtype=np.float64)
    for index, (delay_seconds, gain) in enumerate(taps):
        delay = max(1, int(delay_seconds * sample_rate))
        if delay < len(source):
            wet[delay:] += source[:-delay] * gain * (decay ** (index * 0.65))
    return source * (1.0 - amount * 0.22) + wet * amount


def _render_node(
    patch: SFXPatch,
    node: SFXNode,
    inputs: list[np.ndarray],
    frames: int,
    sample_rate: int,
) -> np.ndarray:
    if node.kind == "oscillator":
        return _source_oscillator(node, frames, sample_rate)
    if node.kind == "noise":
        return _source_noise(patch, node, frames, sample_rate)
    if node.kind == "impact":
        return _source_impact(patch, node, frames, sample_rate)
    if node.kind == "water":
        return _source_water(patch, node, frames, sample_rate)

    signal = _sum_inputs(inputs, frames)
    if node.kind == "mixer":
        return signal * float(node_param(node, "gain"))
    if node.kind == "resonator":
        return _resonator(signal, node, frames, sample_rate)
    if node.kind == "filter":
        filtered = _biquad(
            signal,
            str(node_param(node, "mode")),
            float(node_param(node, "cutoff")),
            float(node_param(node, "resonance")),
            sample_rate,
        )
        input_peak = float(np.max(np.abs(signal))) if signal.size else 0.0
        output_peak = float(np.max(np.abs(filtered))) if filtered.size else 0.0
        if input_peak > 1e-9 and output_peak > 1e-9:
            filtered *= min(6.0, input_peak * 0.92 / output_peak)
        return filtered
    if node.kind == "envelope":
        return _envelope(signal, node, frames, sample_rate)
    if node.kind == "distortion":
        drive = float(node_param(node, "drive"))
        mix = float(node_param(node, "mix"))
        wet = np.tanh(signal * drive) / max(1.0, math.tanh(drive))
        return signal * (1.0 - mix) + wet * mix
    if node.kind == "space":
        return _space(signal, node, sample_rate)
    if node.kind == "output":
        return signal * float(node_param(node, "volume"))
    return signal


def synthesize_graph(patch: SFXPatch, sample_rate: int = 44100) -> np.ndarray:
    if not patch.graph_nodes:
        raise ValueError("音效节点图为空")
    frames = max(16, int(max(0.03, patch.duration) * sample_rate))
    nodes = {node.id: node for node in patch.graph_nodes}
    connections = _connections_for_ids(set(nodes), patch.graph_connections)
    order = topological_order(patch.graph_nodes, connections)
    incoming: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for item in connections:
        incoming[item.target].append(item.source)

    signals: dict[str, np.ndarray] = {}
    for node_id in order:
        node = nodes[node_id]
        inputs = [signals[source] for source in incoming[node_id] if source in signals]
        signals[node_id] = _render_node(patch, node, inputs, frames, sample_rate)

    output_nodes = [node for node in patch.graph_nodes if node.kind == "output"]
    if output_nodes:
        signal = signals[output_nodes[-1].id]
    else:
        sources = {item.source for item in connections}
        sinks = [signals[node_id] for node_id in order if node_id not in sources]
        signal = _sum_inputs(sinks, frames)
    signal = limit_peak(signal * max(0.0, min(1.0, patch.volume)), ceiling=0.92)
    if not np.all(np.isfinite(signal)):
        raise ValueError("音效节点图产生了无效采样")
    return signal.astype(np.float32)
