"""Tests for the polite HTTP client's robots.txt handling (Prompt B.1)."""
import httpx
import pytest

from pipeline import http_client


class _Resp:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=None, response=None
            )
        return None


@pytest.fixture(autouse=True)
def _clean_robots_cache():
    http_client._robots.clear()
    yield
    http_client._robots.clear()


def _patch_robots(monkeypatch, resp):
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("headers", {})
        if isinstance(resp, Exception):
            raise resp
        return resp

    monkeypatch.setattr(http_client.httpx, "get", fake_get)
    return captured


def test_allow_all_robots_permits_fetch(monkeypatch):
    captured = _patch_robots(monkeypatch, _Resp(200, "User-agent: *\nAllow: /\n"))
    assert http_client._robots_allowed("https://example.com/racing") is True
    assert captured["url"] == "https://example.com/robots.txt"
    # we identify ourselves with our own User-Agent, not Python-urllib
    assert captured["headers"]["User-Agent"] == http_client.settings.scrape_user_agent


def test_disallow_rule_blocks_matching_path(monkeypatch):
    _patch_robots(monkeypatch, _Resp(200, "User-agent: *\nDisallow: /private\n"))
    assert http_client._robots_allowed("https://example.com/private/card") is False
    assert http_client._robots_allowed("https://example.com/public/card") is True


def test_robots_403_means_fully_disallowed(monkeypatch):
    """Cloudflare-protected hosts answer robots.txt with 403 — RFC 9309: stay out."""
    _patch_robots(monkeypatch, _Resp(403, "<html>Just a moment...</html>"))
    assert http_client._robots_allowed("https://blocked.example/form-guide/fixtures") is False


def test_robots_network_error_allows_with_rate_limiting(monkeypatch):
    _patch_robots(monkeypatch, httpx.ConnectTimeout("boom"))
    assert http_client._robots_allowed("https://flaky.example/x") is True


def test_robots_404_treated_as_no_rules(monkeypatch):
    _patch_robots(monkeypatch, _Resp(404, ""))
    assert http_client._robots_allowed("https://nofile.example/x") is True


def test_fetch_html_refuses_when_disallowed(monkeypatch, tmp_path):
    _patch_robots(monkeypatch, _Resp(403, ""))
    monkeypatch.setattr(http_client.settings, "raw_html_cache_dir", str(tmp_path / "raw"))
    assert http_client.fetch_html("https://blocked.example/form-guide/fixtures") is None


def test_disk_cache_avoids_second_request(monkeypatch, tmp_path):
    _patch_robots(monkeypatch, _Resp(200, "User-agent: *\nAllow: /\n"))
    calls = {"n": 0}

    def fake_get(url, **kwargs):  # page fetch
        calls["n"] += 1
        return _Resp(200, "<html>race card</html>")

    monkeypatch.setattr(http_client.httpx, "get", fake_get)
    monkeypatch.setattr(http_client.settings, "raw_html_cache_dir", str(tmp_path / "raw"))
    monkeypatch.setattr(http_client.settings, "scrape_min_interval_seconds", 0.0)
    first = http_client.fetch_html("https://example.com/form-guide/fixtures", max_age_seconds=3600)
    calls_after_first = calls["n"]
    second = http_client.fetch_html("https://example.com/form-guide/fixtures", max_age_seconds=3600)
    assert first == second == "<html>race card</html>"
    assert calls["n"] == calls_after_first  # second call served from the on-disk cache
