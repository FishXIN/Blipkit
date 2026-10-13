"""Regression tests for the editable procedural SFX graph."""

from __future__ import annotations

import unittest

import numpy as np

from blipkit.core.models import SFXPatch
from blipkit.core.sfx_graph import (
    connect_nodes,
    make_node,
    synthesize_graph,
    topological_order,
)
from blipkit.core.sfx_synth import get_preset, synthesize


class SFXGraphTests(unittest.TestCase):
    def test_material_graph_round_trip_preserves_nodes_and_connections(self):
        source = get_preset("Metal Plate")
        restored = SFXPatch.from_dict(source.to_dict())

        self.assertTrue(restored.graph_enabled)
        self.assertEqual(restored.to_dict(), source.to_dict())
        self.assertEqual(len(restored.graph_nodes), 5)
        self.assertEqual(len(restored.graph_connections), 4)

    def test_cycle_is_rejected(self):
        first = make_node("filter", 0, 0)
        second = make_node("filter", 200, 0)
        nodes = [first, second]
        connections = connect_nodes(nodes, [], first.id, second.id)

        with self.assertRaisesRegex(ValueError, "环路"):
            connect_nodes(nodes, connections, second.id, first.id)

    def test_connection_order_is_topological(self):
        source = make_node("noise", 0, 0)
        processor = make_node("filter", 200, 0)
        output = make_node("output", 400, 0)
        nodes = [output, processor, source]
        connections = connect_nodes(nodes, [], source.id, processor.id)
        connections = connect_nodes(nodes, connections, processor.id, output.id)

        order = topological_order(nodes, connections)

        self.assertLess(order.index(source.id), order.index(processor.id))
        self.assertLess(order.index(processor.id), order.index(output.id))

    def test_rewiring_changes_rendered_audio(self):
        source = make_node(
            "oscillator",
            0,
            0,
            waveform="Sawtooth",
            start_freq=620.0,
            end_freq=180.0,
        )
        distortion = make_node("distortion", 200, 0, drive=8.0, mix=0.8)
        output = make_node("output", 400, 0)
        patch = SFXPatch(
            name="graph",
            duration=0.4,
            volume=0.8,
            graph_enabled=True,
            graph_nodes=[source, distortion, output],
        )
        patch.graph_connections = connect_nodes(
            patch.graph_nodes,
            [],
            source.id,
            output.id,
        )
        dry = synthesize_graph(patch, sample_rate=8000)
        patch.graph_connections = connect_nodes(
            patch.graph_nodes,
            [],
            source.id,
            distortion.id,
        )
        patch.graph_connections = connect_nodes(
            patch.graph_nodes,
            patch.graph_connections,
            distortion.id,
            output.id,
        )
        driven = synthesize_graph(patch, sample_rate=8000)

        self.assertFalse(np.array_equal(dry, driven))
        self.assertGreater(float(np.mean(np.abs(dry - driven))), 0.01)

    def test_material_templates_are_deterministic_and_audible(self):
        for name in (
            "Metal Plate",
            "Metal Tube",
            "Glass Hit",
            "Wood Knock",
            "Water Drop",
            "Water Flow",
        ):
            patch = get_preset(name)
            first = synthesize(patch, sample_rate=8000)
            second = synthesize(patch, sample_rate=8000)
            self.assertTrue(np.array_equal(first, second), name)
            self.assertGreater(float(np.sqrt(np.mean(first**2))), 0.02, name)
            self.assertLessEqual(float(np.max(np.abs(first))), 0.921, name)


if __name__ == "__main__":
    unittest.main()
