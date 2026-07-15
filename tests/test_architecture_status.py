from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skills import architecture_status_skill


class ArchitectureStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        self.output_dir = (
            self.project_root / "runtime" / "graphify" / "graphify-out"
        )
        self.output_dir.mkdir(parents=True)
        self.graph_path = self.output_dir / "graph.json"
        self.project_root_patch = patch.object(
            architecture_status_skill,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.project_root_patch.start()

    def tearDown(self) -> None:
        self.project_root_patch.stop()
        self.temp_dir.cleanup()

    def _write_graph(self, graph: object) -> None:
        self.graph_path.write_text(json.dumps(graph), encoding="utf-8")

    def test_valid_graph_reports_node_and_edge_counts(self) -> None:
        self._write_graph(
            {
                "nodes": [{"id": "one"}, {"id": "two"}, {"id": "three"}],
                "links": [{"source": "one", "target": "two"}],
            }
        )

        status = architecture_status_skill.get_architecture_status()

        self.assertTrue(status["available"])
        self.assertTrue(status["ready"])
        self.assertEqual(status["status"], "READY")
        self.assertEqual(status["nodes"], 3)
        self.assertEqual(status["edges"], 1)
        self.assertIsNotNone(status["generated_at"])

    def test_missing_graph_returns_unavailable_state(self) -> None:
        status = architecture_status_skill.get_architecture_status()

        self.assertFalse(status["available"])
        self.assertFalse(status["ready"])
        self.assertEqual(status["status"], "NOT GENERATED")
        self.assertEqual(status["nodes"], 0)
        self.assertEqual(status["edges"], 0)
        self.assertIsNone(status["generated_at"])

    def test_malformed_graph_returns_error_state(self) -> None:
        self.graph_path.write_text("{not valid json", encoding="utf-8")

        status = architecture_status_skill.get_architecture_status()

        self.assertFalse(status["available"])
        self.assertFalse(status["ready"])
        self.assertEqual(status["status"], "ERROR")
        self.assertIn("could not be read", status["detail"])

    def test_artifact_availability_is_reported(self) -> None:
        self._write_graph({"nodes": [], "links": []})
        (self.output_dir / "JARVIS_TREE.html").touch()

        status = architecture_status_skill.get_architecture_status()

        self.assertTrue(status["tree_available"])
        self.assertFalse(status["callflow_available"])

        (self.output_dir / "graphify-callflow.html").touch()
        status = architecture_status_skill.get_architecture_status()
        self.assertTrue(status["callflow_available"])


if __name__ == "__main__":
    unittest.main()
