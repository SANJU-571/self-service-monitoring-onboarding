variable "team" {
  description = "Owning team name."
  type        = string
}

variable "service" {
  description = "Service name; used in the service: tag on metrics."
  type        = string
}

variable "env" {
  description = "Environment: dev, qa or prod."
  type        = string
}

variable "owner" {
  description = "Owner contact email."
  type        = string
}

variable "notify" {
  description = "Datadog notification handles, e.g. @team@example.com or @slack-channel."
  type        = list(string)
}

variable "runbook_url" {
  description = "Optional runbook link included in alert messages."
  type        = string
  default     = ""
}

variable "monitors" {
  description = "Monitor settings from the onboarding file. Keys: latency_ms, error_rate_pct, cpu_pct ({warning, critical}) and no_traffic ({enabled})."
  type        = any
}
