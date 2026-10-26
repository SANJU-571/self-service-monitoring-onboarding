from tools.plan_summary import summarize, to_markdown


def change(address, rtype, actions, module=None):
    item = {"address": address, "type": rtype, "change": {"actions": actions}}
    if module:
        item["module_address"] = module
    return item


PLAN = {
    "resource_changes": [
        change('module.team_monitoring["payments-api-dev"].datadog_monitor.threshold["latency_ms"]',
               "datadog_monitor", ["create"], 'module.team_monitoring["payments-api-dev"]'),
        change('module.team_monitoring["payments-api-dev"].datadog_monitor.threshold["cpu_pct"]',
               "datadog_monitor", ["create"], 'module.team_monitoring["payments-api-dev"]'),
        change('module.team_monitoring["payments-api-dev"].datadog_dashboard_json.service',
               "datadog_dashboard_json", ["create"], 'module.team_monitoring["payments-api-dev"]'),
        change('module.team_monitoring["orders-service-dev"].datadog_monitor.threshold["latency_ms"]',
               "datadog_monitor", ["update"], 'module.team_monitoring["orders-service-dev"]'),
        change('module.team_monitoring["orders-service-dev"].datadog_dashboard_json.service',
               "datadog_dashboard_json", ["no-op"], 'module.team_monitoring["orders-service-dev"]'),
    ]
}


def test_counts_per_service():
    summary = summarize(PLAN)
    assert summary["payments-api-dev"][("create", "monitor")] == 2
    assert summary["payments-api-dev"][("create", "dashboard")] == 1
    assert summary["orders-service-dev"][("update", "monitor")] == 1
    assert ("no-op", "dashboard") not in summary["orders-service-dev"]


def test_markdown_table():
    md = to_markdown(summarize(PLAN))
    assert "| payments-api-dev | +1 dashboard, +2 monitors |" in md
    assert "| orders-service-dev | ~1 monitor |" in md
    assert "Warning" not in md


def test_deletes_trigger_warning():
    plan = {"resource_changes": [
        change('module.team_monitoring["old-svc-dev"].datadog_monitor.no_traffic[0]',
               "datadog_monitor", ["delete"], 'module.team_monitoring["old-svc-dev"]'),
        change('module.team_monitoring["old-svc-dev"].datadog_dashboard_json.service',
               "datadog_dashboard_json", ["delete", "create"], 'module.team_monitoring["old-svc-dev"]'),
    ]}
    md = to_markdown(summarize(plan))
    assert "-1 monitor" in md and "±1 dashboard" in md
    assert "deletes or replaces 2 resource(s)" in md


def test_no_changes():
    assert "No changes" in to_markdown(summarize({"resource_changes": []}))
