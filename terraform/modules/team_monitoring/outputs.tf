output "dashboard_url" {
  description = "Link to this service's dashboard."
  value       = datadog_dashboard_json.service.url
}

output "monitor_ids" {
  description = "IDs of the monitors created for this service."
  value = concat(
    [for m in datadog_monitor.threshold : m.id],
    [for m in datadog_monitor.no_traffic : m.id],
  )
}
