#!/usr/bin/env bash
# Source this inside an AzureCLI@2 step that has addSpnToEnvironment: true.
#
# It hands the service connection's identity to Terraform's azurerm backend
# through ARM_* variables, so Terraform can read and lock its state in Azure
# Storage. No secret is stored in the repo or in pipeline variables:
#   * Workload identity federation (recommended): a short-lived OIDC token
#   * Older secret-based service connections: the client secret
if [ -n "${idToken:-}" ]; then
  export ARM_USE_OIDC=true
  export ARM_OIDC_TOKEN="$idToken"
elif [ -n "${servicePrincipalKey:-}" ]; then
  export ARM_CLIENT_SECRET="$servicePrincipalKey"
else
  echo "##vso[task.logissue type=error]No credentials from the service connection. Set addSpnToEnvironment: true on this AzureCLI@2 step."
  exit 1
fi

export ARM_CLIENT_ID="${servicePrincipalId:?servicePrincipalId not set}"
export ARM_TENANT_ID="${tenantId:?tenantId not set}"
ARM_SUBSCRIPTION_ID="$(az account show --query id --output tsv)"
export ARM_SUBSCRIPTION_ID
