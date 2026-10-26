variable "datadog_api_url" {
  description = "Datadog API URL for your site, e.g. https://api.datadoghq.com/ (US1) or https://api.us5.datadoghq.com/ (US5)."
  type        = string
  default     = "https://api.datadoghq.com/"
}

variable "teams_dir" {
  description = "Folder holding the onboarding YAML files, relative to this Terraform root."
  type        = string
  default     = "../teams"
}
