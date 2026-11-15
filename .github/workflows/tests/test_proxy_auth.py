"""Exercise the real HTTP checker against disposable loopback responses."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import threading
import unittest

SPEC = importlib.util.spec_from_file_location("check_proxy_auth", Path(__file__).with_name("check_proxy_auth.py"))
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)
KEY = "sk-synthetic-active-key"
AUTH_ERROR = {"error": {"type": "auth_error", "message": "Invalid key", "code": "401"}}
NO_DB_ERROR = {"error": {"type": "no_db_connection", "message": "No connected db.", "code": "400"}}
MODELS = {"data": [], "object": "list"}


@contextmanager
def proxy(responses):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.server.test_calls.append((self.path, self.headers.get("Authorization")))
            status, body = responses[len(self.server.test_calls) - 1]
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.test_calls = calls
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", calls
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


class ProxyAuthTests(unittest.TestCase):
    def test_wrong_key_denials_require_success_with_the_active_key(self):
        for wrong in ((401, AUTH_ERROR), (400, NO_DB_ERROR)):
            with self.subTest(wrong_status=wrong[0]), proxy([(401, AUTH_ERROR), wrong, (200, MODELS)]) as (url, calls):
                CHECKER.check_auth(KEY, url)
                self.assertEqual(calls, [("/v1/models", None), ("/v1/models", "Bearer sk-synthetic-wrong-key"),
                                         ("/v1/models", "Bearer " + KEY)])

    def test_unexpected_wrong_key_responses_fail(self):
        for wrong in ((200, MODELS), (400, AUTH_ERROR), (500, NO_DB_ERROR),
                      (400, {"error": {"type": "no_db_connection", "message": "Different error", "code": "400"}})):
            with self.subTest(wrong=wrong), proxy([(401, AUTH_ERROR), wrong]) as (url, calls):
                with self.assertRaises(AssertionError):
                    CHECKER.check_auth(KEY, url)
                self.assertEqual(len(calls), 2)

    def test_missing_and_active_key_failures_are_not_masked(self):
        cases = [[(200, MODELS)], [(500, AUTH_ERROR)],
                 [(401, AUTH_ERROR), (400, NO_DB_ERROR), (401, AUTH_ERROR)],
                 [(401, AUTH_ERROR), (400, NO_DB_ERROR), (200, {"error": "not a model list"})]]
        for responses in cases:
            with self.subTest(responses=responses), proxy(responses) as (url, calls):
                with self.assertRaises(AssertionError):
                    CHECKER.check_auth(KEY, url)


if __name__ == "__main__":
    unittest.main()
