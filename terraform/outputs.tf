output "dashboards" {
  description = "Dashboard URL per onboarded service."
  value       = { for k, m in module.team_monitoring : k => m.dashboard_url }
}

output "monitor_ids" {
  description = "Datadog monitor IDs per onboarded service."
  value       = { for k, m in module.team_monitoring : k => m.monitor_ids }
}
