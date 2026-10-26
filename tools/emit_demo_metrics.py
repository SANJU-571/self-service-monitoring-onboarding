#!/usr/bin/env python3
"""Send simulated service metrics to Datadog so the monitors and dashboards have data.

Real services would report these through the Datadog agent or APM. For the demo,
this script plays the part of a service and sends:
    app.requests    (count)  requests in the interval
    app.errors      (count)  failed requests
    app.latency_ms  (gauge)  average latency
    app.cpu_pct     (gauge)  CPU usage

Use --incident to push latency and errors over the thresholds and watch the
monitors fire, then stop it and watch them recover.

Usage:
    export DD_API_KEY=...            # never commit keys
    export DD_SITE=datadoghq.com     # or us5.datadoghq.com, datadoghq.eu, ...
    python tools/emit_demo_metrics.py --service payments-api --env dev
    python tools/emit_demo_metrics.py --service payments-api --env dev --incident
"""
from __future__ import annotations

import argparse
import logging
import os
import random
import signal
import sys
import time
from dataclasses import dataclass

log = logging.getLogger("emit_demo_metrics")


@dataclass(frozen=True)
class Sample:
    requests: int
    errors: int
    latency_ms: float
    cpu_pct: float


def generate_sample(incident: bool, rng: random.Random) -> Sample:
    """One interval of simulated traffic. Incident mode is slow and error-prone."""
    requests = rng.randint(80, 120)
    if incident:
        error_ratio = rng.uniform(0.08, 0.15)
        latency = rng.uniform(900, 1400)
        cpu = rng.uniform(88, 97)
    else:
        error_ratio = rng.uniform(0.0, 0.01)
        latency = rng.uniform(120, 250)
        cpu = rng.uniform(25, 45)
    errors = min(requests, round(requests * error_ratio))
    return Sample(requests, errors, round(latency, 1), round(cpu, 1))


def build_series(sample: Sample, tags: list[str], timestamp: int, interval: int):
    from datadog_api_client.v2.model.metric_intake_type import MetricIntakeType
    from datadog_api_client.v2.model.metric_point import MetricPoint
    from datadog_api_client.v2.model.metric_series import MetricSeries

    def series(name: str, value: float, kind: MetricIntakeType, **extra) -> MetricSeries:
        return MetricSeries(
            metric=name,
            type=kind,
            points=[MetricPoint(timestamp=timestamp, value=float(value))],
            tags=tags,
            **extra,
        )

    return [
        series("app.requests", sample.requests, MetricIntakeType.COUNT, interval=interval),
        series("app.errors", sample.errors, MetricIntakeType.COUNT, interval=interval),
        series("app.latency_ms", sample.latency_ms, MetricIntakeType.GAUGE),
        series("app.cpu_pct", sample.cpu_pct, MetricIntakeType.GAUGE),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--service", required=True)
    parser.add_argument("--env", default="dev", choices=["dev", "qa", "prod"])
    parser.add_argument("--interval", type=int, default=10, help="seconds between submissions")
    parser.add_argument("--incident", action="store_true", help="simulate an outage")
    parser.add_argument("--count", type=int, default=0, help="stop after N submissions (0 = run until Ctrl+C)")
    parser.add_argument("--dry-run", action="store_true", help="print samples without sending")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    if not args.dry_run and not os.environ.get("DD_API_KEY"):
        log.error("DD_API_KEY is not set")
        return 1

    tags = [f"service:{args.service}", f"env:{args.env}", "source:demo-emitter"]
    rng = random.Random()
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    api = None
    if not args.dry_run:
        from datadog_api_client import ApiClient, Configuration
        from datadog_api_client.v2.api.metrics_api import MetricsApi

        config = Configuration()
        config.api_key["apiKeyAuth"] = os.environ["DD_API_KEY"]
        config.server_variables["site"] = os.environ.get("DD_SITE", "datadoghq.com")
        api = MetricsApi(ApiClient(config))

    log.info("Sending metrics for %s (%s)%s, every %ds", args.service, args.env,
             " in INCIDENT mode" if args.incident else "", args.interval)

    sent = 0
    while running and (args.count == 0 or sent < args.count):
        sample = generate_sample(args.incident, rng)
        log.info("requests=%d errors=%d latency=%.0fms cpu=%.0f%%",
                 sample.requests, sample.errors, sample.latency_ms, sample.cpu_pct)
        if api is not None:
            from datadog_api_client.exceptions import ApiException
            from datadog_api_client.v2.model.metric_payload import MetricPayload

            payload = MetricPayload(series=build_series(sample, tags, int(time.time()), args.interval))
            try:
                api.submit_metrics(body=payload)
            except ApiException as exc:
                log.error("Datadog rejected the submission (%s): %s", exc.status, exc.reason)
                if exc.status in (401, 403):
                    return 1
        sent += 1
        if running and (args.count == 0 or sent < args.count):
            time.sleep(args.interval)

    log.info("Stopped after %d submission(s)", sent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
