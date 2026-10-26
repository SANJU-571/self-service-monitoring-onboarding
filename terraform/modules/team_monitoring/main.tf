locals {
  scope  = "service:${var.service},env:${var.env}"
  label  = "[${upper(var.env)}] ${var.service}"
  notify = join(" ", var.notify)

  tags = [
    "team:${var.team}",
    "service:${var.service}",
    "env:${var.env}",
    "managed_by:terraform",
    "onboarding:self-service",
  ]

  runbook_line = var.runbook_url != "" ? "Runbook: ${var.runbook_url}" : "No runbook provided."

  # Monitor catalog. Teams pick from these in their YAML file; the queries
  # stay standard so every team's alerts behave the same way.
  catalog = {
    latency_ms = {
      title = "High latency"
      unit  = " ms"
      query = "avg(last_5m):avg:app.latency_ms{${local.scope}}"
    }
    error_rate_pct = {
      title = "High error rate"
      unit  = "%"
      query = "sum(last_5m):sum:app.errors{${local.scope}}.as_count() / sum:app.requests{${local.scope}}.as_count() * 100"
    }
    cpu_pct = {
      title = "High CPU"
      unit  = "%"
      query = "avg(last_10m):avg:app.cpu_pct{${local.scope}}"
    }
  }

  # Only the threshold monitors this team asked for.
  thresholds = {
    for name, def in local.catalog :
    name => merge(def, try(var.monitors[name], {}))
    if try(var.monitors[name], null) != null
  }

  no_traffic_enabled = try(var.monitors.no_traffic.enabled, false)
}

resource "datadog_monitor" "threshold" {
  for_each = local.thresholds

  name  = "${local.label} - ${each.value.title}"
  type  = "query alert"
  query = "${each.value.query} > ${each.value.critical}"

  message = <<-EOT
    {{#is_alert}}${each.value.title} on ${var.service} (${var.env}): {{value}}${each.value.unit}, above the critical threshold of ${each.value.critical}${each.value.unit}.{{/is_alert}}
    {{#is_warning}}${each.value.title} on ${var.service} (${var.env}): {{value}}${each.value.unit}, above the warning threshold of ${each.value.warning}${each.value.unit}.{{/is_warning}}
    {{#is_recovery}}${var.service} (${var.env}) has recovered.{{/is_recovery}}

    Owner: ${var.owner}
    ${local.runbook_line}

    ${local.notify}
  EOT

  monitor_thresholds {
    warning  = each.value.warning
    critical = each.value.critical
  }

  require_full_window = false
  notify_no_data      = false
  renotify_interval   = 60
  include_tags        = true

  tags = local.tags
}

resource "datadog_monitor" "no_traffic" {
  count = local.no_traffic_enabled ? 1 : 0

  name  = "${local.label} - No traffic"
  type  = "query alert"
  query = "sum(last_15m):sum:app.requests{${local.scope}}.as_count() < 1"

  message = <<-EOT
    {{#is_alert}}${var.service} (${var.env}) has received no requests in 15 minutes. The service may be down or unreachable.{{/is_alert}}
    {{#is_recovery}}${var.service} (${var.env}) is receiving traffic again.{{/is_recovery}}

    Owner: ${var.owner}
    ${local.runbook_line}

    ${local.notify}
  EOT

  monitor_thresholds {
    critical = 1
  }

  notify_no_data    = true
  no_data_timeframe = 20
  renotify_interval = 60
  include_tags      = true

  tags = local.tags
}
