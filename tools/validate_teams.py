#!/usr/bin/env python3
"""Validate monitoring onboarding requests before Terraform runs.

Checks every teams/*.yaml file for:
  * schema errors (required fields, allowed monitors, handle format)
  * warning thresholds that are not below critical
  * duplicate service/env pairs
  * file names that don't match the service
  * prod services without a runbook

Exit code 0 means every file is valid; 1 means at least one problem was found.

Usage:
    python tools/validate_teams.py teams
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

log = logging.getLogger("validate_teams")

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "team.schema.json"
THRESHOLD_MONITORS = ("latency_ms", "error_rate_pct", "cpu_pct")


@dataclass(frozen=True)
class Problem:
    file: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}: {self.message}"


def load_schema(path: Path = SCHEMA_PATH) -> Draft202012Validator:
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def check_request(name: str, data: object, validator: Draft202012Validator) -> list[Problem]:
    """Return every problem found in one onboarding request."""
    if not isinstance(data, dict):
        return [Problem(name, "file must contain a YAML mapping")]

    problems = [
        Problem(name, f"{'/'.join(map(str, e.path)) or '(root)'}: {e.message}")
        for e in sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    ]
    if problems:
        # Semantic checks assume the shape is right, so stop here.
        return problems

    for monitor in THRESHOLD_MONITORS:
        limits = data["monitors"].get(monitor)
        if limits and limits["warning"] >= limits["critical"]:
            problems.append(
                Problem(name, f"monitors/{monitor}: warning ({limits['warning']}) must be below critical ({limits['critical']})")
            )

    for monitor in ("error_rate_pct", "cpu_pct"):
        limits = data["monitors"].get(monitor)
        if limits and limits["critical"] > 100:
            problems.append(Problem(name, f"monitors/{monitor}: critical is a percentage and cannot exceed 100"))

    stem = Path(name).stem
    allowed = {data["service"], f"{data['service']}-{data['env']}"}
    if stem not in allowed:
        problems.append(Problem(name, f"file name should be '{data['service']}.yaml' or '{data['service']}-{data['env']}.yaml'"))

    if data["env"] == "prod" and not data.get("runbook_url"):
        problems.append(Problem(name, "prod services must include a runbook_url"))

    return problems


def validate_dir(teams_dir: Path, validator: Draft202012Validator | None = None) -> list[Problem]:
    validator = validator or load_schema()
    files = sorted(teams_dir.glob("*.yaml")) + sorted(teams_dir.glob("*.yml"))
    if not files:
        return [Problem(str(teams_dir), "no onboarding files found")]

    problems: list[Problem] = []
    seen: dict[tuple[str, str], str] = {}

    for path in files:
        if path.suffix == ".yml":
            problems.append(Problem(path.name, "use the .yaml extension; Terraform only reads *.yaml"))
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            problems.append(Problem(path.name, f"invalid YAML: {exc}"))
            continue

        file_problems = check_request(path.name, data, validator)
        problems.extend(file_problems)
        if file_problems:
            continue

        key = (data["service"], data["env"])
        if key in seen:
            problems.append(Problem(path.name, f"{key[0]} ({key[1]}) is already onboarded in {seen[key]}"))
        else:
            seen[key] = path.name

    log.info("Checked %d file(s), %d valid service(s)", len(files), len(seen))
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("teams_dir", type=Path, nargs="?", default=Path("teams"))
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")

    if not args.teams_dir.is_dir():
        log.error("Not a directory: %s", args.teams_dir)
        return 1

    problems = validate_dir(args.teams_dir)
    for p in problems:
        # Azure DevOps turns this prefix into an error annotation on the run.
        print(f"##vso[task.logissue type=error]{p}")
        log.error("FAIL %s", p)

    if problems:
        log.error("%d problem(s) found", len(problems))
        return 1
    log.info("All onboarding files are valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
