from __future__ import annotations

import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SITE_TEMPLATE = REPOSITORY_ROOT / "deploy/nginx/jarvis-handheld.conf.example"
LOG_TEMPLATE = (
    REPOSITORY_ROOT / "deploy/nginx/jarvis-handheld-log-format.conf.example"
)
DOCUMENTATION = (
    REPOSITORY_ROOT / "docs/API.md",
    REPOSITORY_ROOT / "docs/HANDHELD_DEPLOYMENT.md",
    REPOSITORY_ROOT / "docs/ARCHITECTURE.md",
    REPOSITORY_ROOT / "docs/CHANGELOG.md",
)


def _location_blocks(configuration: str) -> dict[tuple[str, str], str]:
    blocks: dict[tuple[str, str], str] = {}
    lines = configuration.splitlines()
    index = 0
    while index < len(lines):
        match = re.match(r"\s*location\s+(?:(=)\s+)?(\S+)\s*\{", lines[index])
        if match is None:
            index += 1
            continue
        depth = lines[index].count("{") - lines[index].count("}")
        block_lines = [lines[index]]
        index += 1
        while index < len(lines) and depth:
            block_lines.append(lines[index])
            depth += lines[index].count("{") - lines[index].count("}")
            index += 1
        blocks[(match.group(1) or "", match.group(2))] = "\n".join(block_lines)
    return blocks


class HandheldDeploymentTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.site = SITE_TEMPLATE.read_text(encoding="utf-8")
        cls.log_format = LOG_TEMPLATE.read_text(encoding="utf-8")
        cls.locations = _location_blocks(cls.site)
        cls.docs = "\n".join(
            path.read_text(encoding="utf-8") for path in DOCUMENTATION
        )

    def test_only_tls_port_443_is_declared(self) -> None:
        listeners = re.findall(r"^\s*listen\s+([^;]+);", self.site, re.MULTILINE)

        self.assertEqual(listeners, ["443 ssl default_server"])
        self.assertIn("ssl_protocols TLSv1.2 TLSv1.3;", self.site)
        self.assertNotRegex(self.site, r"(?m)^\s*listen\s+80(?:\s|;)")

    def test_only_three_exact_locations_are_proxied(self) -> None:
        proxied = {
            location
            for location, block in self.locations.items()
            if "proxy_pass" in block
        }

        self.assertEqual(proxied, {
            ("=", "/health"),
            ("=", "/handheld/v1/chat"),
            ("=", "/handheld/v2/chat"),
        })
        self.assertEqual(self.site.count("proxy_pass http://127.0.0.1:5000;"), 3)

    def test_exact_routes_reject_wrong_methods(self) -> None:
        health = self.locations[("=", "/health")]
        v1 = self.locations[("=", "/handheld/v1/chat")]
        v2 = self.locations[("=", "/handheld/v2/chat")]

        self.assertIn("if ($request_method != GET) { return 405; }", health)
        self.assertIn("if ($request_method != POST) { return 405; }", v1)
        self.assertIn("if ($request_method != POST) { return 405; }", v2)

    def test_unknown_routes_are_rejected(self) -> None:
        fallback = self.locations[("", "/")]

        self.assertIn("return 404;", fallback)
        self.assertNotIn("proxy_pass", fallback)

    def test_proxy_limits_timeouts_and_forwarding_are_hardened(self) -> None:
        self.assertIn("client_max_body_size 768;", self.site)
        self.assertIn("proxy_redirect off;", self.site)
        for route in ("/handheld/v1/chat", "/handheld/v2/chat"):
            block = self.locations[("=", route)]
            self.assertIn("proxy_connect_timeout 5s;", block)
            self.assertIn("proxy_read_timeout 65s;", block)
            self.assertIn("proxy_send_timeout 5s;", block)
            self.assertIn("proxy_set_header X-Forwarded-For $remote_addr;", block)
            self.assertIn("proxy_set_header X-Forwarded-Proto https;", block)
            self.assertIn("proxy_set_header X-Forwarded-Port 443;", block)
            self.assertIn('proxy_set_header Connection "";', block)

    def test_named_sanitized_access_log_is_used(self) -> None:
        access_logs = re.findall(r"^\s*access_log\s+([^;]+);", self.site, re.MULTILINE)

        self.assertEqual(
            access_logs,
            ["/var/log/nginx/jarvis-handheld-access.log jarvis_handheld"],
        )
        self.assertNotIn("log_format", self.site)
        self.assertRegex(self.log_format, r"(?m)^log_format\s+jarvis_handheld\b")

    def test_log_format_contains_only_approved_variables(self) -> None:
        variables = set(re.findall(r"\$[A-Za-z0-9_]+", self.log_format))

        self.assertEqual(variables, {
            "$remote_addr",
            "$request_method",
            "$uri",
            "$status",
            "$body_bytes_sent",
            "$request_time",
        })
        for forbidden in (
            "$request",
            "$request_uri",
            "$args",
            "$request_body",
            "$http_authorization",
            "$http_cookie",
            "$http_referer",
            "$http_user_agent",
        ):
            self.assertNotIn(forbidden, variables)

    def test_templates_contain_no_secret_or_certificate_material(self) -> None:
        combined = self.site + self.log_format

        for forbidden in (
            "-----BEGIN",
            "JARVIS_HANDHELD_TOKEN",
            "Authorization:",
            "Bearer ",
        ):
            self.assertNotIn(forbidden, combined)
        self.assertIn(
            "ssl_certificate     /etc/jarvis/pki/certs/jarvis-handheld-server.crt;",
            self.site,
        )
        self.assertIn(
            "ssl_certificate_key /etc/jarvis/pki/private/jarvis-handheld-server.key;",
            self.site,
        )

    def test_documentation_names_both_nginx_install_targets(self) -> None:
        for required in (
            "deploy/nginx/jarvis-handheld.conf.example",
            "deploy/nginx/jarvis-handheld-log-format.conf.example",
            "/etc/nginx/sites-available/jarvis-handheld",
            "/etc/nginx/conf.d/jarvis-handheld-log-format.conf",
            "root:root",
            "0644",
            "sudo nginx -t",
        ):
            self.assertIn(required, self.docs)


if __name__ == "__main__":
    unittest.main()
