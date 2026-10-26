#!/usr/bin/env bash
# One-time setup: create the Azure Storage account that holds Terraform state.
#
# Usage:
#   az login
#   ./tools/bootstrap_state.sh [location]
#
# Cost: a few cents a month (Standard_LRS, one small blob).
set -euo pipefail

LOCATION="${1:-canadacentral}"
RESOURCE_GROUP="rg-monitoring-tfstate"
CONTAINER="tfstate"
# Storage account names must be globally unique, 3-24 lowercase letters/digits.
ACCOUNT="stmontfstate$(openssl rand -hex 4)"

echo "Creating resource group $RESOURCE_GROUP in $LOCATION"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

echo "Creating storage account $ACCOUNT"
az storage account create \
  --name "$ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false \
  --output none

echo "Turning on blob versioning so earlier state can be recovered"
az storage account blob-service-properties update \
  --account-name "$ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --enable-versioning true \
  --output none

echo "Creating container $CONTAINER"
az storage container create \
  --name "$CONTAINER" \
  --account-name "$ACCOUNT" \
  --auth-mode login \
  --output none

cat <<EOF

Done. Put these in terraform/backend.hcl (local runs) and in the
"datadog-onboarding" variable group (pipeline):

  TFSTATE_RESOURCE_GROUP  = $RESOURCE_GROUP
  TFSTATE_STORAGE_ACCOUNT = $ACCOUNT

backend.hcl:
  resource_group_name  = "$RESOURCE_GROUP"
  storage_account_name = "$ACCOUNT"
  container_name       = "$CONTAINER"
  key                  = "monitoring-onboarding.tfstate"
EOF
