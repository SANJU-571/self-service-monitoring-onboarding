import random

from tools.emit_demo_metrics import build_series, generate_sample, main, submit


def test_normal_traffic_stays_under_thresholds():
    rng = random.Random(1)
    for _ in range(200):
        s = generate_sample(False, rng)
        assert s.errors <= s.requests
        assert s.latency_ms < 300
        assert s.cpu_pct < 50
        assert s.errors / s.requests * 100 < 2


def test_incident_breaches_thresholds():
    rng = random.Random(2)
    for _ in range(200):
        s = generate_sample(True, rng)
        assert s.latency_ms > 800
        assert s.cpu_pct > 85
        assert s.errors / s.requests * 100 > 5


def test_series_shape():
    s = generate_sample(False, random.Random(3))
    series = build_series(s, ["service:x", "env:dev"], 1_700_000_000, 10)
    names = [m.metric for m in series]
    assert names == ["app.requests", "app.errors", "app.latency_ms", "app.cpu_pct"]
    assert all(m.tags == ["service:x", "env:dev"] for m in series)
    assert series[0].interval == 10


def test_dry_run_needs_no_key(monkeypatch):
    monkeypatch.delenv("DD_API_KEY", raising=False)
    assert main(["--service", "x", "--dry-run", "--count", "2", "--interval", "0"]) == 0


def test_missing_key_fails(monkeypatch):
    monkeypatch.delenv("DD_API_KEY", raising=False)
    assert main(["--service", "x", "--count", "1"]) == 1


class FakeApi:
    """Stands in for MetricsApi: raises the given error, or records the call."""

    def __init__(self, error=None):
        self.error = error
        self.calls = 0

    def submit_metrics(self, body):
        self.calls += 1
        if self.error is not None:
            raise self.error


def test_submit_succeeds():
    api = FakeApi()
    assert submit(api, payload=None) is True
    assert api.calls == 1


def test_connection_reset_does_not_stop_the_emitter():
    # The WinError 10054 crash seen on Windows: the connection drops mid-request.
    assert submit(FakeApi(ConnectionResetError(10054, "connection reset")), None) is True


def test_urllib3_protocol_error_does_not_stop_the_emitter():
    from urllib3.exceptions import ProtocolError

    error = ProtocolError("Connection aborted.", ConnectionResetError(10054, "reset"))
    assert submit(FakeApi(error), None) is True


def test_server_error_is_retried():
    from datadog_api_client.exceptions import ApiException

    assert submit(FakeApi(ApiException(status=503, reason="Service Unavailable")), None) is True


def test_bad_api_key_stops_the_emitter():
    from datadog_api_client.exceptions import ApiException

    assert submit(FakeApi(ApiException(status=403, reason="Forbidden")), None) is False
