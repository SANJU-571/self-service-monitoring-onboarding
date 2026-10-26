# Every teams/*.yaml file is one onboarding request.
# Adding a file adds monitoring; deleting it removes that service's monitoring.

locals {
  team_files = fileset("${path.root}/${var.teams_dir}", "*.yaml")

  requests = [
    for f in local.team_files : yamldecode(file("${path.root}/${var.teams_dir}/${f}"))
  ]

  # Keyed by "<service>-<env>" so the same service can be onboarded per environment.
  # tools/validate_teams.py rejects duplicates before Terraform runs.
  services = {
    for r in local.requests : "${r.service}-${r.env}" => r
  }
}

module "team_monitoring" {
  source   = "./modules/team_monitoring"
  for_each = local.services

  team        = each.value.team
  service     = each.value.service
  env         = each.value.env
  owner       = each.value.owner
  notify      = each.value.notify
  runbook_url = try(each.value.runbook_url, "")
  monitors    = each.value.monitors
}
