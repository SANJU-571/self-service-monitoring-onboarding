terraform {
  required_version = ">= 1.6.0"

  required_providers {
    datadog = {
      source  = "DataDog/datadog"
      version = "~> 3.40"
    }
  }

  # State lives in an Azure Storage account. Values are passed at init time:
  #   terraform init -backend-config=backend.hcl
  # See backend.hcl.example and tools/bootstrap_state.sh.
  backend "azurerm" {}
}

# Credentials come from the DD_API_KEY and DD_APP_KEY environment variables.
provider "datadog" {
  api_url = var.datadog_api_url
}
