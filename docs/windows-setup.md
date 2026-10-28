# Windows setup (CMD)

The main README uses bash. These are the same steps for Windows Command Prompt.

## 1. Install the tools

Run CMD as Administrator:

```cmd
winget install Git.Git
winget install Python.Python.3.11
winget install Hashicorp.Terraform
winget install Microsoft.AzureCLI
winget install Microsoft.VisualStudioCode
```

Open a **new** CMD window, then check:

```cmd
git --version
python --version
terraform --version
az --version
```

If `python --version` opens the Microsoft Store, turn off the python entries under
Settings > Apps > Advanced app settings > App execution aliases.

## 2. Clone and run the checks

Keep the project outside OneDrive (for example on `D:\projects`). OneDrive syncing
`.venv` and `.terraform` causes slow runs and "file in use" errors.

```cmd
mkdir D:\projects
cd /d D:\projects
git clone https://github.com/SANJU-571/self-service-monitoring-onboarding.git
cd self-service-monitoring-onboarding

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python tools\validate_teams.py teams
python -m pytest
```

Installing `datadog-api-client` can take several minutes on Windows while Defender scans its files.

## 3. Create Terraform state storage in Azure

`tools/bootstrap_state.sh` is a bash script. In CMD, run the same steps directly.
Pick a storage account name that is unique across Azure (3-24 lowercase letters and digits).

```cmd
az login
az provider register --namespace Microsoft.Storage --wait
az group create --name rg-monitoring-tfstate --location canadacentral --output table
az storage account create --name <your-account-name> --resource-group rg-monitoring-tfstate --location canadacentral --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 --allow-blob-public-access false --output table
az storage account blob-service-properties update --account-name <your-account-name> --resource-group rg-monitoring-tfstate --enable-versioning true --output table
az storage container-rm create --storage-account <your-account-name> --name tfstate --output table
```

Then point Terraform at it:

```cmd
copy terraform\backend.hcl.example terraform\backend.hcl
```

Edit `terraform\backend.hcl` and set `storage_account_name` to your account name.
The file is git-ignored, so it never reaches GitHub.

## 4. Set Datadog keys for the current CMD window

CMD uses `set` instead of `export`. Keys set this way disappear when the window closes,
so they never land in a file.

```cmd
set DD_API_KEY=<your-api-key>
set DD_APP_KEY=<your-application-key>
set DD_SITE=datadoghq.com
```

Use your site from the Datadog URL (for example `us5.datadoghq.com`). From here, continue
with step 3 of the README (`terraform init`, `plan`, `apply`), running the commands in CMD.