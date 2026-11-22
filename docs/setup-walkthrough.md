# Setup walkthrough: from zero to self-service onboarding

This guide follows the project from an empty Windows laptop to Datadog monitors that
fire and recover, deployed by an approval-gated pipeline. Every step says **what** you do, **why** you do it, and **what the
output means**. Commands are for Windows Command Prompt (CMD); the
[README](../README.md) has the bash equivalents and
[windows-setup.md](windows-setup.md) is the short reference version.
For a plain-English explanation of what the project is for, see
[project-explained.md](project-explained.md), and for the story of how it was built, see
[project-journey.md](project-journey.md).

| Phase | Result | Time |
|---|---|---|
| [1. Install the tools](#phase-1-install-the-tools) | Git, Python, Terraform, Azure CLI, VS Code | ~1 h |
| [2. Run the project locally](#phase-2-run-the-project-locally) | Validator and 33 tests pass | ~30 min |
| [3. Azure account and login](#phase-3-azure-account-and-login) | CLI signed in to a subscription | ~30 min |
| [4. Terraform state storage](#phase-4-terraform-state-storage-in-azure) | Private, versioned storage for state | ~20 min |
| [5. Datadog and the first apply](#phase-5-datadog-and-the-first-terraform-apply) | 6 monitors and 2 dashboards | ~1 h |
| [6. Demo traffic and alerts](#phase-6-demo-traffic-and-alerts) | Alerts fire and recover | ~30 min |
| [7. Azure DevOps pipeline](#phase-7-the-azure-devops-pipeline) | Validate, plan and approval-gated apply on every change | ~1-2 h |
| [8. Self-service onboarding](#phase-8-onboard-a-new-service-through-a-pull-request) | A new team onboarded through a pull request | ~45 min |
| [Working with Git](#working-with-git-branch-commit-pull-request) | Changes reach `main` through pull requests | ~15 min each |

## The idea in one minute

App teams need alerts for their services: "tell me when my app gets slow, starts
failing, or stops receiving traffic". Setting those up by hand in Datadog is slow, and
every team ends up with slightly different alerts.

Here a team adds one YAML file (`teams/<service>.yaml`) and opens a pull request. A
pipeline checks the file, shows a Terraform plan for review, and after approval
Terraform creates standard Datadog monitors and a dashboard with the team's own
thresholds.

| Piece | Role |
|---|---|
| `teams/*.yaml` | The onboarding request a team writes |
| `tools/validate_teams.py` + `schema/` | Rejects bad requests before anything is built |
| `terraform/` | Turns each request into Datadog monitors and a dashboard |
| Azure Storage | Holds Terraform state: the record of what Terraform built |
| `azure-pipelines.yml` | Runs validate, plan and apply automatically |
| `tools/emit_demo_metrics.py` | Pretends to be an app so the monitors have data |

---

## Phase 1: Install the tools

**Why:** each tool has one job. Git downloads and tracks the code, Python runs the
validator and tests, Terraform builds the Datadog resources, the Azure CLI talks to
Azure, and VS Code is where you read and edit files.

1. Open CMD as Administrator: press the Windows key, type `cmd`, right-click
   **Command Prompt**, choose **Run as administrator**.
2. Install the tools, one at a time. Type `Y` if asked to accept terms.
   ```cmd
   winget install Git.Git
   winget install Python.Python.3.11
   winget install Hashicorp.Terraform
   winget install Microsoft.AzureCLI
   winget install Microsoft.VisualStudioCode
   ```
3. Close CMD and open a new window. Windows only finds newly installed programs in a
   fresh window.
4. Check each tool:
   ```cmd
   git --version
   python --version
   terraform --version
   az --version
   ```
   Every command should print a version number. The project needs Terraform 1.6 or
   newer.

**Notes**

- `Found an existing package already installed` means the tool is already there.
- `Your version of Terraform is out of date!` is a notice, not an error. Any version
  from 1.6 works.
- If `python --version` opens the Microsoft Store, go to Settings > Apps > Advanced app
  settings > App execution aliases and turn off the two python entries.
- If `winget` is not recognized, update **App Installer** from the Microsoft Store.

---

## Phase 2: Run the project locally

**Why:** before touching any cloud service, prove the code works on your machine. It is
quick, free, and teaches you what each part does.

### 2.1 Tell Git who you are

Git stamps every commit with a name and email, and refuses to commit without them.

```cmd
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

### 2.2 Download the code

Keep the project **outside OneDrive** (your Desktop and Documents usually sync to it).
OneDrive tries to upload the thousands of small files in `.venv` and `.terraform`,
which slows everything down and causes "file in use" errors. The whole project needs
about 400 MB.

```cmd
mkdir D:\projects
cd /d D:\projects
git clone https://github.com/SANJU-571/self-service-monitoring-onboarding.git
cd self-service-monitoring-onboarding
```

`/d` lets `cd` switch drives as well as folders.

### 2.3 Create a virtual environment

A virtual environment is a private folder of Python libraries for this project only, so
it cannot clash with other projects.

```cmd
python -m venv .venv
.venv\Scripts\activate
```

The prompt now starts with `(.venv)`. Run the activate line again every time you open a
new CMD window.

### 2.4 Install the libraries

```cmd
pip install -r requirements.txt
```

| Library | Used for |
|---|---|
| PyYAML | Reading the team YAML files |
| jsonschema | Checking them against `schema/team.schema.json` |
| datadog-api-client | Sending demo metrics to Datadog |
| pytest | Running the tests |

`datadog-api-client` can take 2 to 10 minutes on Windows because Defender scans each of
its many small files. It looks stuck but is not. The `A new release of pip is
available` notice can be ignored.

### 2.5 Run the validator

```cmd
python tools\validate_teams.py teams
```
```
Checked 2 file(s), 2 valid service(s)
All onboarding files are valid
```

This is the first check the pipeline runs on every pull request.

### 2.6 Run the tests

```cmd
python -m pytest
```
```
33 passed
```

### 2.7 Break a file on purpose

The best way to understand the validator is to watch it catch a mistake.

1. Open the project in VS Code: `code .`
2. In `teams\payments-api.yaml`, change the latency `warning: 400` to `warning: 900`
   and save.
3. Run the validator again:
   ```
   Checked 2 file(s), 1 valid service(s)
   ##vso[task.logissue type=error]payments-api.yaml: monitors/latency_ms: warning (900) must be below critical (800)
   FAIL payments-api.yaml: monitors/latency_ms: warning (900) must be below critical (800)
   1 problem(s) found
   ```
4. Undo the change: `git checkout teams\payments-api.yaml`

Reading the output:

- The message names the **file**, the **field** and **how to fix it**, so a team can
  fix its own file without asking anyone.
- The `##vso[...]` line is for Azure DevOps, which turns it into a red error on the
  pipeline run.
- The script exits with an error code, so the pipeline stops and Terraform never runs.

The validator also rejects unknown environments (only `dev`, `qa`, `prod`),
percentages over 100, the same service and environment onboarded twice, a file name
that does not match the service, and prod services without a runbook link.

---

## Phase 3: Azure account and login

**Why:** Terraform needs somewhere shared to keep its state. We use Azure Storage, so we
need an Azure subscription and a logged-in CLI.

- The **account** is your login. The **subscription** is the billing container that
  lets you create resources. You need an active subscription.
- A new Azure free account includes credit valid for 30 days. This project uses only a
  few cents of it.

```cmd
az login
```

A browser opens to sign in. Back in CMD you are asked to
`Select a subscription and tenant`: type the **number** next to your subscription, not
its name.

Check it:

```cmd
az account show --output table
```

The `State` column must say `Enabled`.

**Notes**

- `No subscriptions found` means the login worked but the account has no active
  subscription (for example, an expired free trial). Create or reactivate one in the
  Azure portal under **Subscriptions**.
- `Invalid selection` at the prompt means you typed the name; type the number.
- The `[Survey]` banner can be ignored.
- `AADSTS50076 ... you must use multi-factor authentication` followed by `No subscriptions
  found`: Azure now requires MFA for management sign-ins. Sign in to your tenant directly
  with `az login --tenant <tenant ID>` (the ID is printed in the error) and complete the
  MFA prompt.

---

## Phase 4: Terraform state storage in Azure

**Why:** Terraform keeps a **state file** recording everything it created, for example
"monitor 12345 belongs to payments-api". Without it, Terraform forgets what it built and
would create duplicates or fail to delete things. Storing it in Azure lets your laptop
and the pipeline share one copy.

What we build:

```
Subscription
└── rg-monitoring-tfstate              resource group: a folder for related resources
    └── <storage account>              private, encrypted, versioned
        └── tfstate                    container: where the state file lives
            └── monitoring-onboarding.tfstate   written by Terraform later
```

Pick a storage account name that is unique across all of Azure: 3 to 24 lowercase
letters and digits, for example `stmontfstate` plus your initials and a few digits.
Below it is written as `<account>`.

### 4.1 Register the storage provider

New subscriptions start with many services switched off.

```cmd
az provider register --namespace Microsoft.Storage --wait
```

No output means success.

### 4.2 Create the resource group

```cmd
az group create --name rg-monitoring-tfstate --location canadacentral --output table
```

`rg-` is the usual prefix for resource groups. `canadacentral` is the Toronto region;
pick the one closest to you.

### 4.3 Create the storage account

This is the only part of the project that costs money: a few cents a month.

```cmd
az storage account create --name <account> --resource-group rg-monitoring-tfstate --location canadacentral --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 --allow-blob-public-access false --output table
```

| Option | Why |
|---|---|
| `Standard_LRS` | Three copies in one data centre; the cheapest option |
| `StorageV2` | The current general-purpose type |
| `TLS1_2` | Only modern encrypted connections |
| `--allow-blob-public-access false` | Nobody on the internet can read files anonymously |

Look for `ProvisioningState: Succeeded`. If the name is taken, choose another.

### 4.4 Turn on versioning

Every time Terraform saves state, Azure keeps the previous copy, so a bad run can be
rolled back.

```cmd
az storage account blob-service-properties update --account-name <account> --resource-group rg-monitoring-tfstate --enable-versioning true --output table
```

Look for `IsVersioningEnabled: True`.

### 4.5 Create the container

```cmd
az storage container-rm create --storage-account <account> --name tfstate --output table
```

`container-rm` goes through Azure Resource Manager, where the subscription Owner role
is enough. The data-plane version (`az storage container create --auth-mode login`)
needs the extra **Storage Blob Data Contributor** role, which a new subscription owner
does not have.

### 4.6 Point Terraform at the storage

```cmd
copy terraform\backend.hcl.example terraform\backend.hcl
```

Open `terraform\backend.hcl` and set `storage_account_name` to your account name. The
four lines are the resource group, storage account, container and the state file's
name.

`backend.hcl` is listed in `.gitignore`, so it never reaches GitHub. Confirm with
`git status`: it should say `nothing to commit, working tree clean`. The pipeline gets
the same values from Azure DevOps instead.

**Bonus: locking.** While Terraform runs it locks the state file, so two runs at the
same time (your laptop and the pipeline) cannot corrupt it.

---

## Phase 5: Datadog and the first terraform apply

**Why:** this is where code turns into real monitors. Terraform reads every team file
and creates the monitors and dashboards in Datadog.

The 14-day Datadog trial starts at signup, so do Phases 5 and 6 together.

### 5.1 Sign up

1. Go to https://www.datadoghq.com and start a free trial. Any company name works.
2. Leave the region on the default (US1) unless you have a reason to change it.
3. Skip the "install the Datadog Agent" wizard and the "What do you want to do with
   Datadog?" screen. The Agent collects metrics from real servers; our demo script
   sends metrics directly. Go straight to `https://app.datadoghq.com/monitors/manage`.

### 5.2 Find your site

Datadog runs separate regions, and Terraform must call the one your account lives in.
Look at the browser address:

| Address starts with | Site | API address |
|---|---|---|
| `app.datadoghq.com` | US1 | `https://api.datadoghq.com/` (project default) |
| `us3.datadoghq.com` | US3 | `https://api.us3.datadoghq.com/` |
| `us5.datadoghq.com` | US5 | `https://api.us5.datadoghq.com/` |
| `app.datadoghq.eu` | EU1 | `https://api.datadoghq.eu/` |

For any site other than US1, add `-var="datadog_api_url=<API address>"` to the
`terraform plan` and `apply` commands, and set `DD_SITE` to the site's domain (for
example `us5.datadoghq.com`).

### 5.3 Create the two keys

Programs never use your personal password. Keys can be named, limited and revoked.

| Key | Allows | Used by |
|---|---|---|
| API key | Sending data in (metrics) | Demo script, Terraform |
| Application key | Reading and changing settings (monitors, dashboards) as your user | Terraform |

1. Open `https://app.datadoghq.com/organization-settings/api-keys` (or click your
   profile picture at the top right, then **Organization Settings**, then
   **API Keys**). Copy the existing key, or create one named `monitoring-onboarding`.
2. Open **Application Keys**, click **New Key**, name it `terraform-onboarding`, and
   copy it straight away. Datadog shows it only once. Leave scopes at the default.
3. Save both keys in a file **outside OneDrive and outside the project folder**, for
   example `D:\keys\datadog-keys.txt`, or in a password manager.

Never paste keys into chat, commit them, or save them inside the project. Bots scan
public GitHub repos for leaked keys within minutes.

### 5.4 Load the keys into CMD

Terraform's Datadog provider reads `DD_API_KEY` and `DD_APP_KEY` from environment
variables, which is why the code contains no keys. Variables set with `set` exist only
in the current window and disappear when it closes.

```cmd
cd /d D:\projects\self-service-monitoring-onboarding
.venv\Scripts\activate
notepad D:\keys\datadog-keys.txt
```

Type `set DD_API_KEY=` and paste the real API key straight after the `=`. Do the same
for `DD_APP_KEY`. Then:

```cmd
set DD_SITE=datadoghq.com
echo %DD_API_KEY:~0,4%...
echo %DD_APP_KEY:~0,4%...
az account show --output table
```

- `%DD_API_KEY:~0,4%` shows only the first four characters, enough to confirm the key
  is set without exposing it.
- If the echo prints the variable name itself, the variable is not set in this window.
- If it prints the start of a placeholder like `past`, you set the example text instead
  of your key.
- No spaces around `=` and no quotes around the value.
- Terraform also needs the Azure login, to reach the state storage.

### 5.5 terraform init

Prepares the working folder. Nothing is created in Datadog.

```cmd
cd terraform
terraform init -backend-config=backend.hcl
```

| Output | Meaning |
|---|---|
| `Successfully configured the backend "azurerm"` | Connected to the state storage in Azure |
| `team_monitoring in modules\team_monitoring` | Found the reusable monitor template |
| `Installing datadog/datadog v3.x` | Downloaded the provider that translates Terraform into Datadog API calls |
| `signed by a HashiCorp partner` | The provider is verified as Datadog's own |
| `created a lock file .terraform.lock.hcl` | Recorded the exact provider version and hashes |

Commit the lock file (see [Working with Git](#working-with-git-branch-commit-pull-request))
so every machine and the pipeline install exactly the same provider.

### 5.6 terraform plan

A preview: Terraform compares what the team files ask for with what its state says
exists, and prints the difference. Nothing changes.

```cmd
terraform plan
```

For the two example teams the summary is:

```
Plan: 8 to add, 0 to change, 0 to destroy.
```

That is six monitors (four for payments-api, two for orders-service) and two
dashboards. `+` means create, `~` change, `-` destroy. Always check the destroy count
before applying.

How one monitor reads:

```
avg(last_5m):avg:app.latency_ms{service:payments-api,env:dev} > 800
```

"Alert if the average latency of payments-api in dev over the last five minutes is
above 800 ms." The `service:` and `env:` tags keep each team's monitor to its own app.
The warning (400) and critical (800) values come straight from the team's YAML. The
five-minute average avoids paging someone for a single slow request.

### 5.7 terraform apply

```cmd
terraform apply
```

Check the plan again and type `yes`. Anything else cancels.

```
Apply complete! Resources: 8 added, 0 changed, 0 destroyed.

Outputs:

dashboards = {
  "orders-service-dev" = "/dashboard/<id>/dev-orders-service---service-overview"
  "payments-api-dev"   = "/dashboard/<id>/dev-payments-api---service-overview"
}
```

Open `https://app.datadoghq.com/monitors/manage` to see the six monitors, and add a
dashboard path to `https://app.datadoghq.com` to open it. Each monitor carries the tags
`team:`, `service:`, `env:` and `managed_by:terraform`. The last one tells everyone to
change the YAML file rather than edit the monitor by hand.

The monitors show **No Data** and the graphs are empty until something sends metrics.

### 5.8 Moving to a new Datadog account

If a trial ends or you switch accounts, everything can be rebuilt from the files.

1. Create an API key and an application key in the new account and save them.
2. Load them with `set DD_API_KEY=...` and `set DD_APP_KEY=...`.
3. Run `terraform plan`. The state still lists the old monitor IDs, but the new account
   has never heard of them, so the plan shows `8 to add, 0 to change, 0 to destroy`.
4. Run `terraform apply`. All monitors and dashboards are recreated; only the dashboard
   links change.
5. Update `DD_API_KEY` and `DD_APP_KEY` in the pipeline's variable group (Phase 7).

This is the payoff of infrastructure as code: nothing was configured by hand, so nothing
is lost.

---

## Phase 6: Demo traffic and alerts

**Why:** an alert you have never seen fire is an alert you cannot trust. This phase
shows the full cycle: OK, warning, alert, recovery.

The script plays the part of payments-api and sends four metrics every 10 seconds,
tagged `service:payments-api, env:dev`:

| Metric | Normal | `--incident` |
|---|---|---|
| `app.requests` | 80-120 per interval | 80-120 per interval |
| `app.errors` | 0-1% of requests | 8-15% |
| `app.latency_ms` | 120-250 ms | 900-1400 ms |
| `app.cpu_pct` | 25-45% | 88-97% |

### 6.1 Open a second CMD window

The script runs until you stop it, so it needs its own window. Press **Windows key + R**,
type `cmd`, press Enter. (If you get a `PS C:\...>` prompt you are in PowerShell; type
`cmd` to switch.)

Environment variables belong to one window, so set the key again. The script only needs
the API key:

```cmd
cd /d D:\projects\self-service-monitoring-onboarding
.venv\Scripts\activate
set DD_API_KEY=<API key>
set DD_SITE=datadoghq.com
```

### 6.2 Dry run

Prints samples without sending anything:

```cmd
python tools\emit_demo_metrics.py --service payments-api --env dev --dry-run --count 3
```
```
Sending metrics for payments-api (dev), every 10s
requests=94 errors=1 latency=197ms cpu=27%
...
Stopped after 3 submission(s)
```

### 6.3 Normal traffic

```cmd
python tools\emit_demo_metrics.py --service payments-api --env dev
```

After two or three minutes, refresh the payments-api dashboard (set the time range to
**Past 15 Minutes**). The lines sit below the dashed warning and critical lines, and the
monitor status widget turns **OK**.

### 6.4 Incident

Press Ctrl+C, then:

```cmd
python tools\emit_demo_metrics.py --service payments-api --env dev --incident
```

The graphs jump above the lines within a minute, but the monitors take a few minutes
because they judge a time window:

| Monitor | Window | Expected |
|---|---|---|
| High error rate | 5 min | ALERT after about 4 min |
| High latency | 5 min | WARN, then ALERT, after about 2-5 min |
| High CPU | 10 min | ALERT after about 5-10 min |
| No traffic | 15 min | Stays OK: the app is slow, not down |

Click an alerting monitor to see the notification text Terraform wrote: the service,
the value, the threshold, the owner and the runbook link. The example teams notify
`@...@example.com` addresses, so no real email is sent.

The window length is a trade-off: shorter detects faster but pages people for brief
blips; longer is calmer but slower.

### 6.5 Recovery

Press Ctrl+C and start normal traffic again. Within about 10 minutes every monitor
returns to **OK** and sends its recovery message.

If the script is stopped, **No traffic** moves to **No Data** after about 20 minutes and
notifies, because `notify_no_data` is on. That is the "app has gone silent" alert.

### Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `echo` prints `%DD_API_KEY:~0,4%...` | Key not set in this window; set it again |
| Dashboard stays empty | Wait 2-3 minutes, refresh, and check the script is running without `--dry-run` |
| `Datadog rejected the submission (403)` | Wrong API key or wrong `DD_SITE` |
| `Network error, will retry next interval` | A dropped connection; the script carries on by itself |
| Alerts stop when the laptop sleeps | Keep it plugged in and awake while the script runs |

---

## Phase 7: The Azure DevOps pipeline

**Why:** until now a person has been the pipeline, typing validate, test, plan and apply
by hand. The pipeline does the same steps automatically on every pull request and every
merge, and nothing reaches Datadog until someone approves the plan:

```
Pull request opened   ->  Validate  ->  Plan                    (result shown on the PR)
Merged to main        ->  Validate  ->  Plan  ->  approval  ->  Apply
```

Nobody needs Terraform on their laptop or holds the Datadog keys personally, and every
change is checked the same way.

### 7.1 Upgrade the Azure subscription and set a budget

Azure DevOps can't link to an Azure **free trial** subscription, and a free account is
disabled when its credit period ends, taking the Terraform state storage with it.
Upgrading to **pay-as-you-go** fixes both.

1. Azure portal > **Subscriptions** > your subscription > **Upgrade** (or, on the
   "Select an offer" page, the **Click here to upgrade** link on the Pay-As-You-Go card).
   Don't sign up for a new Free Trial.
2. Choose **no technical support** (free). Remaining free credit is kept until it expires.
3. Set a budget so you are emailed long before any real cost: **Cost Management** >
   **Budgets** > **Add**, monthly, $5, alerts at 50% and 100% of actual spend.

The project costs a few cents a month (the storage account). The budget only emails; it
never blocks anything.

### 7.2 Create the organization and project

1. Sign in at https://dev.azure.com with the **same Microsoft account as the Azure
   subscription**.
2. If a directory dropdown is shown, pick the directory that holds the subscription
   (for example **Default Directory**). Billing in 7.3 needs both in the same directory.
3. **Create new organization**, then a project named `monitoring-onboarding`,
   visibility **Private**.

The code stays on GitHub; Azure DevOps only runs the pipeline and reads the repo.

### 7.3 Link billing to turn on the free build machine

New organizations get no Microsoft-hosted build machines until they are linked to an
Azure subscription. The old request form is gone.

1. **Organization settings** > **Billing** > **Set up billing** > select the subscription
   > **Save** (direct link: `https://dev.azure.com/<organization>/_settings/billing`).
2. Check the page: **MS Hosted CI/CD** shows **1800 minutes** free, and **Paid parallel
   jobs** shows **0**. Leave the paid boxes at 0 and GitHub-hosted agents **Off**.

Linking buys nothing; it activates the free tier: one Microsoft-hosted job, up to
60 minutes per run, 1,800 minutes a month.

### 7.4 Create the service connection

A service connection is a non-human identity (a "staff badge for the robot") that lets
the pipeline reach Azure. People sign in with MFA; pipelines can't, so they use this.

1. **Project settings** (gear, bottom left) > **Service connections**
   (direct link: `https://dev.azure.com/<organization>/<project>/_settings/adminservices`).
2. **Create service connection** > **Azure Resource Manager** > **Next**.
3. Fill in:

| Field | Value |
|---|---|
| Identity type | App registration (automatic) |
| Credential | **Workload identity federation** |
| Scope level | Subscription |
| Subscription | your subscription |
| Resource group | `rg-monitoring-tfstate` |
| Name | `azure-monitoring-onboarding` (must match `azure-pipelines.yml`) |
| Grant access permission to all pipelines | Leave unchecked |

Azure DevOps creates an app registration and gives it **Contributor** on that one
resource group only (least privilege).

**How the pipeline uses it:** with workload identity federation there is no stored
password. On each run Azure DevOps gets a short-lived OIDC token from Microsoft Entra
ID. The `AzureCLI@2` steps set `addSpnToEnvironment: true`, and
`pipelines/scripts/arm-auth-env.sh` hands the token to Terraform's azurerm backend
through `ARM_USE_OIDC`, `ARM_OIDC_TOKEN`, `ARM_CLIENT_ID`, `ARM_TENANT_ID` and
`ARM_SUBSCRIPTION_ID`. Without that, Terraform couldn't read or lock its state inside the
pipeline.

### 7.5 Create the variable group

A variable group is a locked safe the pipeline reads at run time. Secret values are
encrypted, hidden in the web page and masked as `***` in logs. `azure-pipelines.yml`
looks for a group named exactly `datadog-onboarding`.

**Pipelines** > **Library** > **+ Variable group** > name `datadog-onboarding`:

| Name | Value | Secret? |
|---|---|---|
| `DD_API_KEY` | the Datadog API key itself (not the path to your keys file) | Yes: click the padlock |
| `DD_APP_KEY` | the Datadog application key | Yes: click the padlock |
| `DD_API_URL` | `https://api.datadoghq.com/` (or your site's API address) | No |
| `TFSTATE_RESOURCE_GROUP` | `rg-monitoring-tfstate` | No |
| `TFSTATE_STORAGE_ACCOUNT` | your storage account name | No |

Type the plain values by hand. A pasted invisible Tab or space at the end breaks the run
(see Troubleshooting). Only the keys are secret: the other values are addresses, and the
service connection controls access.

### 7.6 Create the approval gate

The Apply stage is a deployment job to an **environment** named `datadog-monitoring`.
An approval check on that environment pauses the run until a named person approves.

1. **Pipelines** > **Environments** > **Create environment** > name
   `datadog-monitoring`, resource **None** > **Create**.
2. **...** (top right) > **Approvals and checks** > **+** > **Approvals** > add yourself
   as approver > **Create**.

The check appears as "All approvers must approve", type Approvals, timeout 30 days. For a
solo project leave "allow approvers to approve their own runs" on; on a team, require a
different person than the author (separation of duties).

### 7.7 Create the pipeline

1. **Pipelines** > **Pipelines** > **Create Pipeline** > **GitHub (YAML)**.
2. Authorize Azure Pipelines on GitHub as the repo owner. When asked to install the
   **Azure Pipelines** GitHub app, choose **Only select repositories**, pick this repo,
   then **Approve & install**. The app lets pull requests trigger the pipeline and shows
   the result on the PR.
3. Select the repo > **Existing Azure Pipelines YAML file** > branch `main`, path
   `/azure-pipelines.yml` > **Continue**.
4. Don't edit the YAML on the review screen (edits there commit straight to `main`).
   Click **Run**.
5. The first run asks for permission to use the service connection, variable group and
   environment: **View** > **Permit** for each.

### 7.8 Read the first run

| Stage | What it does | Expected |
|---|---|---|
| Validate | Installs Python, validates team files, runs 33 tests, `terraform fmt -check` and `validate` | Green; test results on the **Tests** tab |
| Plan | Signs in with the OIDC token, `terraform init` against the Azure state, `terraform plan -out=tfplan`, publishes a per-service summary | Green. If you already applied from a laptop: **No changes** |
| Apply | Waits for approval, then applies the **saved** plan file | Approve with **Review** > **Approve**; green |

Apply runs the exact plan file the reviewer saw, so what was approved is exactly what is
built.

### Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `401 - Uh-oh, you do not have access` | The browser is signed in to a different Microsoft account. Sign out and sign in with the account that owns the organization, or use a separate browser profile |
| The old parallelism request link opens a Microsoft Forms welcome page | The form was retired; link billing instead (7.3) |
| Subscription not offered when linking billing | Free trial subscriptions aren't supported, or the organization is in a different directory (7.1, 7.2) |
| `invalid API URL ... "https://api.datadoghq.com/\t" ... invalid control character` | A hidden Tab was pasted at the end of `DD_API_URL`. Clear the value, type it by hand, save, **Rerun failed jobs** |
| `No credentials from the service connection` | An `AzureCLI@2` step is missing `addSpnToEnvironment: true` |
| `terraform fmt -check` fails in Validate | Run `terraform fmt -recursive` in `terraform/` and commit through a pull request |
| Datadog `403` or `invalid key` in Plan | Re-enter `DD_API_KEY` and `DD_APP_KEY` carefully; check they belong to the account your `DD_API_URL` points at |
| Warning: `ubuntu-latest` label will migrate to Ubuntu 26 | Only a notice. Pin `vmImage: ubuntu-24.04` for fully reproducible runs |

---

## Phase 8: Onboard a new service through a pull request

**Why:** this is the demo that proves the self-service claim. A new team gets monitoring
with one file and one approval, and a mistake is stopped before it reaches Datadog. Nobody
runs Terraform or clicks in Datadog.

### 8.1 Protect the main branch

Without protection a red check is only advice: GitHub would still let someone merge.

1. GitHub repo > **Settings** > **Branches** > **Add classic branch protection rule**.
2. Branch name pattern `main`.
3. Tick **Require a pull request before merging**. Set required approvals to **0** on a
   solo project: GitHub doesn't let authors approve their own pull requests.
4. Tick **Require status checks to pass before merging** and **Require branches to be up
   to date**. In the search box type the pipeline's name and **click** the check
   (`<owner>.<repo>`, provided by Azure Pipelines) so it appears under "Status checks that
   are required". Typing it without clicking saves nothing.
5. **Create**.

### 8.2 Open a pull request with a deliberate mistake

```cmd
git checkout main
git pull
git checkout -b onboard/inventory-service
```

Create `teams\inventory-service.yaml` (the file name must match the service):

```yaml
team: inventory
service: inventory-service
env: dev
owner: inventory-team@example.com
notify:
  - "@inventory-team@example.com"
runbook_url: https://github.com/SANJU-571/self-service-monitoring-onboarding/blob/main/docs/runbook.md
monitors:
  latency_ms:
    warning: 600     # deliberate mistake: above critical
    critical: 500
  error_rate_pct:
    warning: 2
    critical: 5
  cpu_pct:
    warning: 75
    critical: 90
  no_traffic:
    enabled: true
```

```cmd
git add teams\inventory-service.yaml
git commit -m "Onboard inventory-service to Datadog monitoring"
git push -u origin onboard/inventory-service
```

Open the pull request from the link Git prints.

### 8.3 Watch the pipeline block it

After a few minutes the PR shows **Required checks failing** and the **Merge pull request**
button is disabled. Validate failed, so Plan never ran. The run's Errors box in Azure
DevOps names the file, the field and the fix:

```
inventory-service.yaml: monitors/latency_ms: warning (600) must be below critical (500)
```

### 8.4 Fix it and review the plan

Change the warning to `250`, check locally, and push to the same branch:

```cmd
python tools\validate_teams.py teams
git add teams\inventory-service.yaml
git commit -m "Fix inventory-service latency thresholds"
git push
```

The pipeline restarts by itself. When it's green, open the run and read the plan summary
as a reviewer would: only `inventory-service-dev` appears, with 5 creates (4 monitors and
a dashboard), 0 updates and **0 deletes**. The PR shows **Ready to merge**.

### 8.5 Merge, then approve the deployment

1. **Merge pull request** > **Confirm merge** > **Delete branch**. As the author you can
   only leave a **Comment** review on GitHub.
2. The merge changes `teams/`, so a new run starts on `main`. Open it (branch `main`,
   description "Merge pull request #..."), not the earlier PR run.
3. When Apply shows **Waiting**, click **Review** > **Approve**. Apply runs the saved plan
   and its log ends with `Apply complete! Resources: 5 added`.

| Kind of approval | When | Protects |
| --- | --- | --- |
| GitHub pull request review | Before merge | The change going into `main` |
| Azure DevOps environment approval | After merge, before Apply | The real change in Datadog |

### 8.6 Check Datadog

- `https://app.datadoghq.com/monitors/manage?q=team%3Ainventory` lists the four new
  monitors, tagged `managed_by:terraform`.
- **Dashboards** > `[DEV] inventory-service - Service Overview` shows the team's own
  warning and critical lines.
- Optional: `python tools\emit_demo_metrics.py --service inventory-service --env dev`
  fills the dashboard and turns the monitors **OK**. Press Ctrl+C to stop.

### Troubleshooting

| Symptom | Cause and fix |
|---|---|
| A red PR can still be merged | No required status check is selected in the branch rule; click the check name in the dropdown and save |
| "Apply: Skipped due to conditions" | You're looking at the pull request's run; PR runs never apply. Open the run for the merge on `main` |
| Approve and Request changes are greyed out on GitHub | Authors can't review their own PRs; leave a Comment |
| No run starts after merging | The `main` trigger only watches `teams`, `terraform`, `schema`, `tools`, `pipelines` and `azure-pipelines.yml`; docs-only merges don't run the pipeline |

---

## Working with Git: branch, commit, pull request

Changes reach `main` only through a pull request, the same flow app teams use to
onboard a service.

```
main ── your branch ── commit ── push ── pull request ── review ── merge
```

```cmd
git checkout main
git pull
git checkout -b docs/my-change

rem ... edit files ...

git status
git diff
git add <file> <file>
git commit -m "Say what changed and why"
git push -u origin docs/my-change
```

Then open the link Git prints (or use **Compare & pull request** on GitHub), write a
description with **What**, **Why** and **Tested**, review **Files changed**, click
**Merge pull request**, then **Confirm merge**, then **Delete branch**. Finally update
your laptop:

```cmd
git checkout main
git pull
git branch -d docs/my-change
```

**Habits**

- Add files by name rather than `git add .`, so nothing unexpected is committed.
- Turn on **Settings > General > Automatically delete head branches**, so merged branches
  are removed on GitHub by themselves.
- Before committing, check `git status` does not list `backend.hcl`, `*.tfstate` or any
  key file.
- Review the pushed diff on GitHub before merging. That is how a leftover line in
  `tools/bootstrap_state.sh` was caught before it reached `main`.

**Notes**

- `Permission ... denied to <other-user>` with a 403: Windows has a saved login for a
  different GitHub account. Remove it with
  `cmdkey /delete:git:https://github.com` (find the exact name with
  `cmdkey /list | findstr github`), make sure the browser is signed in to the right
  account, and push again. Git Credential Manager opens the browser to sign in.
- `LF will be replaced by CRLF` is a harmless note about Windows line endings.
- Clicking **Merge pull request** only opens the message box; the merge happens when
  you click **Confirm merge**.

---

## Cleaning up

When you are finished, remove everything so nothing keeps costing money:

```cmd
cd terraform
terraform destroy
az group delete --name rg-monitoring-tfstate
```

`terraform destroy` deletes the monitors and dashboards; the second command deletes the
state storage.

If you set up the pipeline, also:

- delete the Azure DevOps project (Project settings > Overview > **Delete**), which removes
  the pipeline, variable group, environment and service connection;
- delete the service connection's app registration in Microsoft Entra ID if it remains
  (App registrations > the one named after your organization and project);
- remove the budget, or keep it as a safety net while the subscription exists.
