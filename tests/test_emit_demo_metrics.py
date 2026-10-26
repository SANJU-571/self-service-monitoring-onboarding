import random

from tools.emit_demo_metrics import build_series, generate_sample, main


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
