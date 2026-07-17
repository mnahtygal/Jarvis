from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import api


class ArchitectureApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)
        self.output_dir_patch = patch.object(
            api,
            "GRAPHIFY_OUTPUT_DIR",
            self.output_dir,
        )
        self.output_dir_patch.start()
        self.client = api.app.test_client()

    def tearDown(self) -> None:
        self.output_dir_patch.stop()
        self.temp_dir.cleanup()

    def test_tree_route_serves_allowed_artifact(self) -> None:
        content = b"<html><body>Project tree</body></html>"
        (self.output_dir / "JARVIS_TREE.html").write_bytes(content)

        response = self.client.get("/api/architecture/tree")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, content)
        self.assertEqual(response.cache_control.max_age, 0)
        response.close()

    def test_callflow_route_serves_allowed_artifact(self) -> None:
        content = b"<html><body>Call flow</body></html>"
        (self.output_dir / "graphify-callflow.html").write_bytes(content)

        response = self.client.get("/api/architecture/callflow")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, content)
        self.assertEqual(response.cache_control.max_age, 0)
        response.close()

    def test_missing_tree_returns_not_found(self) -> None:
        response = self.client.get("/api/architecture/tree")

        self.assertEqual(response.status_code, 404)

    def test_missing_callflow_returns_not_found(self) -> None:
        response = self.client.get("/api/architecture/callflow")

        self.assertEqual(response.status_code, 404)

    def test_arbitrary_artifact_access_is_not_routed(self) -> None:
        (self.output_dir / "manifest.json").write_text("{}", encoding="utf-8")

        response = self.client.get("/api/architecture/manifest.json")

        self.assertEqual(response.status_code, 404)

    def test_architecture_status_endpoint_uses_existing_skill(self) -> None:
        expected = {
            "available": True,
            "ready": True,
            "status": "READY",
            "nodes": 3,
            "edges": 2,
        }
        with patch.object(api, "get_architecture_status", return_value=expected):
            response = self.client.get("/api/status/architecture")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), expected)


if __name__ == "__main__":
    unittest.main()
