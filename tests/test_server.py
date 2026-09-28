from http.client import HTTPConnection
import json
from threading import Thread
import unittest

from app.runtime import Runner
from app.server import make_server
from scripts.verify_local import verify


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(0, Runner(revision="test-revision"))
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.server_close()

    def request(self, method, path, body=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_ui_and_assets_are_served_on_loopback(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        for path, expected in (("/", b"SIMULATED"), ("/assets/app.js", b"textContent"),
                               ("/assets/app.css", b"focus-visible")):
            with self.subTest(path=path):
                status, headers, body = self.request("GET", path)
                self.assertEqual(status, 200)
                self.assertIn(expected, body)
                self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_a04_healthy_diagnosis_over_http(self):
        report = verify(self.server.server_port)
        self.assertEqual(report["result"], "PASS", report)
        self.assertEqual(report["run"]["revision"], "test-revision")

    def test_failure_scenario_over_http(self):
        status, _, body = self.request("POST", "/api/runs", json.dumps({
            "question": "Explain errors", "scenario": "orders-errors",
        }), {"Content-Type": "application/json"})
        run = json.loads(body)
        self.assertEqual(status, 201)
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["outcome"], "degraded")
        self.assertEqual(run["steps"][0]["result"]["http_status"], 503)

    def test_invalid_json_and_unsupported_scenario(self):
        for body in ("not-json", '{"question": "x", "scenario": "production"}'):
            with self.subTest(body=body):
                status, _, _ = self.request("POST", "/api/runs", body,
                                             {"Content-Type": "application/json"})
                self.assertEqual(status, 400)

    def test_cross_origin_and_rebinding_requests_are_rejected(self):
        for headers in ({"Origin": "https://unrelated.example"}, {"Host": "unrelated.example"}):
            with self.subTest(headers=headers):
                status, _, _ = self.request("POST", "/api/runs", "{}",
                                             {"Content-Type": "application/json", **headers})
                self.assertEqual(status, 403)

    def test_content_type_and_body_limit(self):
        status, _, _ = self.request("POST", "/api/runs", "{}", {"Content-Type": "text/plain"})
        self.assertEqual(status, 415)
        status, _, _ = self.request("POST", "/api/runs", "x" * 8193,
                                     {"Content-Type": "application/json"})
        self.assertEqual(status, 413)

    def test_missing_run_and_path_traversal(self):
        for path in ("/api/runs/absent", "/assets/../../config/lab.json", "/restart"):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path)[0], 404)

    def test_api_info_is_explicit_about_mode_and_storage(self):
        status, _, body = self.request("GET", "/api/info")
        info = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(info["mode"], "SIMULATED")
        self.assertEqual(info["storage"], "memory")


if __name__ == "__main__":
    unittest.main()
