#!/usr/bin/env python3
"""Turn a Terraform plan into a short, per-service summary for reviewers.

The pipeline runs:
    terraform show -json tfplan > plan.json
    python tools/plan_summary.py plan.json

and publishes the Markdown output to the run's Summary tab, so a reviewer
sees "payments-api-dev: +3 monitors, +1 dashboard" instead of raw plan text.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ACTION_SYMBOLS = {"create": "+", "update": "~", "delete": "-", "replace": "±"}
RESOURCE_LABELS = {"datadog_monitor": "monitor", "datadog_dashboard_json": "dashboard"}
MODULE_KEY = re.compile(r'module\.team_monitoring\["([^"]+)"\]')


def classify(actions: list[str]) -> str | None:
    if actions in (["no-op"], ["read"]):
        return None
    if "create" in actions and "delete" in actions:
        return "replace"
    return actions[0]


def summarize(plan: dict) -> dict[str, dict[tuple[str, str], int]]:
    """Return {service_key: {(action, label): count}}."""
    summary: dict[str, dict[tuple[str, str], int]] = defaultdict(lambda: defaultdict(int))
    for change in plan.get("resource_changes", []):
        action = classify(change["change"]["actions"])
        if action is None:
            continue
        match = MODULE_KEY.search(change.get("module_address", "") or change["address"])
        service = match.group(1) if match else "(root)"
        label = RESOURCE_LABELS.get(change["type"], change["type"])
        summary[service][(action, label)] += 1
    return summary


def to_markdown(summary: dict[str, dict[tuple[str, str], int]]) -> str:
    if not summary:
        return "## Monitoring plan\n\nNo changes. Datadog already matches the onboarding files.\n"

    lines = ["## Monitoring plan", "", "| Service | Changes |", "| --- | --- |"]
    for service in sorted(summary):
        parts = []
        for (action, label), count in sorted(summary[service].items()):
            plural = label if count == 1 else f"{label}s"
            parts.append(f"{ACTION_SYMBOLS.get(action, action)}{count} {plural}")
        lines.append(f"| {service} | {', '.join(parts)} |")

    deletes = sum(c for s in summary.values() for (a, _), c in s.items() if a in ("delete", "replace"))
    if deletes:
        lines += ["", f"**Warning:** this plan deletes or replaces {deletes} resource(s). Check that a team file wasn't removed by mistake."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan_json", type=Path, help="output of: terraform show -json tfplan")
    parser.add_argument("-o", "--output", type=Path, help="write Markdown here instead of stdout")
    args = parser.parse_args(argv)

    plan = json.loads(args.plan_json.read_text(encoding="utf-8"))
    markdown = to_markdown(summarize(plan))

    if args.output:
        args.output.write_text(markdown, encoding="utf-8")
    else:
        sys.stdout.write(markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
