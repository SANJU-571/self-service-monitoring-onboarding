from pathlib import Path

import pytest
import yaml

from tools.validate_teams import check_request, load_schema, main, validate_dir

REPO_TEAMS = Path(__file__).resolve().parent.parent / "teams"


@pytest.fixture(scope="module")
def validator():
    return load_schema()


def valid_request(**overrides):
    data = {
        "team": "payments",
        "service": "payments-api",
        "env": "dev",
        "owner": "payments-team@example.com",
        "notify": ["@payments-team@example.com"],
        "monitors": {
            "latency_ms": {"warning": 400, "critical": 800},
            "error_rate_pct": {"warning": 2, "critical": 5},
            "no_traffic": {"enabled": True},
        },
    }
    data.update(overrides)
    return data


def messages(problems):
    return " | ".join(p.message for p in problems)


def test_repo_team_files_are_valid():
    assert validate_dir(REPO_TEAMS) == []


def test_valid_request_passes(validator):
    assert check_request("payments-api.yaml", valid_request(), validator) == []


def test_env_suffixed_file_name_is_allowed(validator):
    assert check_request("payments-api-dev.yaml", valid_request(), validator) == []


def test_missing_required_field(validator):
    data = valid_request()
    del data["owner"]
    assert "'owner' is a required property" in messages(check_request("payments-api.yaml", data, validator))


def test_unknown_monitor_rejected(validator):
    data = valid_request(monitors={"disk_pct": {"warning": 1, "critical": 2}})
    assert "disk_pct" in messages(check_request("payments-api.yaml", data, validator))


def test_notify_handle_needs_at_sign(validator):
    data = valid_request(notify=["payments-team@example.com"])
    assert "notify/0" in messages(check_request("payments-api.yaml", data, validator))


def test_bad_env_rejected(validator):
    data = valid_request(env="staging")
    assert "env" in messages(check_request("payments-api.yaml", data, validator))


def test_warning_must_be_below_critical(validator):
    data = valid_request(monitors={"latency_ms": {"warning": 800, "critical": 800}})
    assert "must be below critical" in messages(check_request("payments-api.yaml", data, validator))


def test_percentage_over_100_rejected(validator):
    data = valid_request(monitors={"cpu_pct": {"warning": 90, "critical": 120}})
    assert "cannot exceed 100" in messages(check_request("payments-api.yaml", data, validator))


def test_file_name_must_match_service(validator):
    assert "file name should be" in messages(check_request("wrong-name.yaml", valid_request(), validator))


def test_prod_requires_runbook(validator):
    data = valid_request(env="prod")
    assert "runbook_url" in messages(check_request("payments-api.yaml", data, validator))


def test_prod_with_runbook_passes(validator):
    data = valid_request(env="prod", runbook_url="https://example.com/runbook")
    assert check_request("payments-api-prod.yaml", data, validator) == []


def test_non_mapping_file(validator):
    assert "YAML mapping" in messages(check_request("x.yaml", ["a", "b"], validator))


def write(tmp_path, name, data):
    (tmp_path / name).write_text(yaml.safe_dump(data), encoding="utf-8")


def test_duplicate_service_env_detected(tmp_path):
    write(tmp_path, "payments-api.yaml", valid_request())
    write(tmp_path, "payments-api-dev.yaml", valid_request())
    assert "already onboarded" in messages(validate_dir(tmp_path))


def test_same_service_different_env_is_fine(tmp_path):
    write(tmp_path, "payments-api-dev.yaml", valid_request())
    write(tmp_path, "payments-api-prod.yaml", valid_request(env="prod", runbook_url="https://example.com/rb"))
    assert validate_dir(tmp_path) == []


def test_yml_extension_rejected(tmp_path):
    write(tmp_path, "payments-api.yml", valid_request())
    assert ".yaml extension" in messages(validate_dir(tmp_path))


def test_invalid_yaml_reported(tmp_path):
    (tmp_path / "broken.yaml").write_text("team: [unclosed", encoding="utf-8")
    assert "invalid YAML" in messages(validate_dir(tmp_path))


def test_empty_dir_fails(tmp_path):
    assert "no onboarding files" in messages(validate_dir(tmp_path))


def test_cli_exit_codes(tmp_path):
    assert main([str(REPO_TEAMS)]) == 0
    write(tmp_path, "wrong.yaml", valid_request())
    assert main([str(tmp_path)]) == 1
