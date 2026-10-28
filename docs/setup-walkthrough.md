# Setup walkthrough: from zero to firing alerts

This guide follows the project from an empty Windows laptop to Datadog monitors that
fire and recover. Every step says **what** you do, **why** you do it, and **what the
output means**. Commands are for Windows Command Prompt (CMD); the
[README](../README.md) has the bash equivalents and
[windows-setup.md](windows-setup.md) is the short reference version.

| Phase | Result | Time |
|---|---|---|
| [1. Install the tools](#phase-1-install-the-tools) | Git, Python, Terraform, Azure CLI, VS Code | ~1 h |
| [2. Run the project locally](#phase-2-run-the-project-locally) | Validator and 33 tests pass | ~30 min |
| [3. Azure account and login](#phase-3-azure-account-and-login) | CLI signed in to a subscription | ~30 min |
| [4. Terraform state storage](#phase-4-terraform-state-storage-in-azure) | Private, versioned storage for state | ~20 min |
| [5. Datadog and the first apply](#phase-5-datadog-and-the-first-terraform-apply) | 6 monitors and 2 dashboards | ~1 h |
| [6. Demo traffic and alerts](#phase-6-demo-traffic-and-alerts) | Alerts fire and recover | ~30 min |
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
