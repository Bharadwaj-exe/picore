import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from picore.engine import evaluate
from picore.engine.wolfram import WolframError, query

SAMPLE = {"queryresult": {"success": True, "pods": [
    {"title": "Input interpretation", "subpods": [{"plaintext": "Moon | distance from Earth"}]},
    {"title": "Result", "subpods": [{"plaintext": "379496 km"}, {"plaintext": "235808 miles"}]},
]}}


class FakeProxy(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        inp = q.get("input", [""])[0]
        assert "appid" not in q          # the app must never send a key to the proxy
        status, body = 200, SAMPLE
        if inp == "spam":
            status, body = 429, {"error": "slow down"}
        elif inp == "broken":
            status, body = 502, {"error": "Wolfram|Alpha returned 500"}
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def proxy_url():
    server = HTTPServer(("127.0.0.1", 0), FakeProxy)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_proxy_success_keeps_multiline(proxy_url):
    pods = query("distance to the moon", proxy_url=proxy_url)
    assert pods[1] == ("Result", "379496 km\n235808 miles")


def test_proxy_rate_limited(proxy_url):
    with pytest.raises(WolframError, match="Too many"):
        query("spam", proxy_url=proxy_url)


def test_proxy_error_message_passed_through(proxy_url):
    with pytest.raises(WolframError, match="returned 500"):
        query("broken", proxy_url=proxy_url)


def test_engine_falls_back_to_proxy_for_words(proxy_url):
    r = evaluate("distance to the moon", wolfram_proxy=proxy_url)
    assert r.source == "wolfram"
    assert evaluate("2+2", wolfram_proxy=proxy_url).source == "local"   # maths stays offline


def test_offline_no_internet():
    with pytest.raises(WolframError, match="No internet|took too long|failed"):
        query("x", proxy_url="http://127.0.0.1:9", timeout=2)
