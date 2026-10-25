"""NV-077: a hostile page must not stall capture or the batch semaphore."""

import asyncio
import functools
import http.server
import threading
import time
from pathlib import Path

import pytest

from src import capture as capture_mod
from src.cli import audit_batch

HTML_DIR = Path(__file__).parent / "fixtures" / "html"
DEADLINE_S = 8
OUTER_LIMIT_S = 45


@pytest.fixture
def local_server():
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(QuietHandler, directory=str(HTML_DIR))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def short_deadline(monkeypatch):
    monkeypatch.setattr(capture_mod, "CAPTURE_DEADLINE_S", DEADLINE_S, raising=False)


async def _run_batch(urls):
    try:
        return await asyncio.wait_for(audit_batch(urls, concurrency=1), OUTER_LIMIT_S)
    except TimeoutError:
        pytest.fail(f"batch did not finish within {OUTER_LIMIT_S}s (hostile page stalled it)")


async def test_promise_returning_scrollby_does_not_stall_batch(local_server, short_deadline):
    urls = [
        f"{local_server}/hostile_scrollby.html",
        f"{local_server}/benign.html",
    ]
    results = await _run_batch(urls)
    by_url = {r["url"]: r for r in results}
    assert by_url[urls[0]]["status"] in ("ok", "timeout")
    assert by_url[urls[1]]["status"] == "ok"


async def test_hung_page_maps_to_timeout_within_deadline(local_server, short_deadline):
    url = f"{local_server}/hostile_busy.html"
    start = time.monotonic()
    page = await asyncio.wait_for(capture_mod.capture(url), OUTER_LIMIT_S)
    elapsed = time.monotonic() - start
    assert page.status == "timeout"
    assert elapsed < DEADLINE_S + 10
