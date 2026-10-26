# One overview dashboard per onboarded service, with the team's own
# thresholds drawn on the graphs so on-call can see how close they are.

locals {
  latency_markers = contains(keys(local.thresholds), "latency_ms") ? [
    { value = "y = ${local.thresholds.latency_ms.warning}", display_type = "warning dashed", label = "warning" },
    { value = "y = ${local.thresholds.latency_ms.critical}", display_type = "error dashed", label = "critical" },
  ] : []

  error_markers = contains(keys(local.thresholds), "error_rate_pct") ? [
    { value = "y = ${local.thresholds.error_rate_pct.warning}", display_type = "warning dashed", label = "warning" },
    { value = "y = ${local.thresholds.error_rate_pct.critical}", display_type = "error dashed", label = "critical" },
  ] : []

  cpu_markers = contains(keys(local.thresholds), "cpu_pct") ? [
    { value = "y = ${local.thresholds.cpu_pct.warning}", display_type = "warning dashed", label = "warning" },
    { value = "y = ${local.thresholds.cpu_pct.critical}", display_type = "error dashed", label = "critical" },
  ] : []
}

resource "datadog_dashboard_json" "service" {
  dashboard = jsonencode({
    title       = "${local.label} - Service Overview"
    description = "Created by self-service monitoring onboarding. Team: ${var.team}. Owner: ${var.owner}. Do not edit by hand; change teams/*.yaml instead."
    layout_type = "ordered"
    widgets = [
      {
        definition = {
          type                = "manage_status"
          title               = "Monitor status"
          summary_type        = "monitors"
          display_format      = "countsAndList"
          color_preference    = "text"
          hide_zero_counts    = true
          show_last_triggered = true
          sort                = "status,asc"
          query               = "tag:\"service:${var.service}\" tag:\"env:${var.env}\""
        }
      },
      {
        definition = {
          type      = "query_value"
          title     = "Requests (sum over window)"
          autoscale = true
          precision = 0
          requests = [
            { q = "sum:app.requests{${local.scope}}.as_count()", aggregator = "sum" }
          ]
        }
      },
      {
        definition = {
          type    = "timeseries"
          title   = "Latency (ms)"
          markers = local.latency_markers
          requests = [
            { q = "avg:app.latency_ms{${local.scope}}", display_type = "line" }
          ]
        }
      },
      {
        definition = {
          type    = "timeseries"
          title   = "Error rate (%)"
          markers = local.error_markers
          requests = [
            { q = "sum:app.errors{${local.scope}}.as_count() / sum:app.requests{${local.scope}}.as_count() * 100", display_type = "line" }
          ]
        }
      },
      {
        definition = {
          type    = "timeseries"
          title   = "CPU (%)"
          markers = local.cpu_markers
          requests = [
            { q = "avg:app.cpu_pct{${local.scope}}", display_type = "line" }
          ]
        }
      },
    ]
  })
}
