# Presenting this project

How to explain the project in an interview or a demo: short versions to say out loud, a
five-minute demo route through the repo, and answers to the questions that usually come up.

## The pitch

**30 seconds, for anyone:**

> "Apps need alarms that go off when they get slow or start failing. Setting those up used
> to mean waiting for an expert. I built a system where a team fills in a short form, opens
> a pull request, and after one approval their alarms and a live dashboard are created
> automatically, the same way for every team."

**One minute, technical:**

> "I built a self-service observability onboarding platform. A team onboards a service to
> Datadog by opening a pull request with one YAML file. An Azure DevOps pipeline validates
> it with a Python and JSON Schema validator and pytest, runs `terraform plan`, and posts a
> per-service summary. `main` is protected, so a failing check blocks the merge. After
> merge, Apply waits on an environment approval and then applies the saved plan through a
> shared Terraform module that creates standard monitors and a dashboard. State is in
> versioned Azure Blob Storage, the pipeline signs in to Azure with workload identity
> federation, and Datadog keys are secret pipeline variables, so there are no long-lived
> credentials in the repo."

## A five-minute demo route

1. **The form** (`teams/inventory-service.yaml`): one file per service; teams choose which
   monitors and the numbers.
2. **The guardrail** (`tools/validate_teams.py`, `schema/team.schema.json`): rules such as
   warning below critical, valid environment, file name matching the service, runbook for
   prod.
3. **The template** (`terraform/main.tf` and `terraform/modules/team_monitoring/`):
   `for_each` over the team files, one module per service, a fixed catalogue of queries.
4. **The pipeline** (`azure-pipelines.yml`): Validate, Plan with `-out=tfplan`, Apply as a
   deployment job to an environment with an approval check.
5. **The proof** (README Demo section): the blocked pull request, the green run, the new
   team's dashboard, and the alert going OK, WARN, ALERT and back to OK.

## Design decisions and why

| Decision | Why |
| --- | --- |
| YAML files plus a validator instead of Terraform for teams | Teams describe what they need; the platform owns how it's built. Mistakes fail in seconds with a clear message |
| One Terraform module, `for_each` over files | Every team gets identical alert logic. Onboarding is adding a file, not writing code |
| Remote state in Azure Blob Storage with versioning and locking | The laptop and the pipeline share one truth; old versions can be restored; two runs can't corrupt it |
| Plan saved with `-out`, Apply runs that file | What the reviewer approved is exactly what gets built |
| Branch protection with a required check | A red pipeline physically blocks the merge |
| Environment approval before Apply | A human signs off on the change to Datadog, with an audit trail |
| Workload identity federation for Azure | Short-lived OIDC tokens instead of stored client secrets |
| 5-minute evaluation windows | Balances detection speed against alert noise and fatigue |
| `managed_by:terraform` tag | Tells everyone not to edit monitors by hand; drift is corrected on the next apply |

## Questions you're likely to get

| Question | Answer |
| --- | --- |
| Why not click in the Datadog UI? | Clicking can't be reviewed, repeated or undone cleanly. Code in Git can, and it rebuilt everything in seconds when we moved to a new Datadog account |
| What happens if someone edits a monitor by hand? | The next apply puts it back to match the YAML. Git is the source of truth |
| How do you stop bad config? | Schema and rule checks in the PR, a required status check on `main`, a plan reviewers can read, and an approval before Apply |
| How are secrets handled? | Datadog keys are secret variables in an Azure DevOps variable group, masked in logs and never in the repo. Azure access uses workload identity federation, so there's no Azure secret at all. Next step would be linking the variable group to Key Vault |
| How would you separate dev and prod? | The environment is a field in the YAML today, tagged and named by environment with stricter prod rules. At scale I'd split state per environment, with separate backend keys or workspaces, credentials and approvers |
| Could this work with CloudWatch or Azure Monitor? | Yes. Keep the files, validator and pipeline, and swap the Terraform provider and module |
| What went wrong while building it? | A hidden Tab in a pipeline variable broke the Datadog URL; the demo emitter crashed on a dropped connection, so I made it retry transient errors and added tests; a trial account expired and Terraform rebuilt everything from Git |
| What would you add next? | Key Vault-backed secrets, per-environment state, SLO monitors, and routing alerts to Slack or PagerDuty from the YAML |

## Numbers worth remembering

- 3 services onboarded, 10 monitors and 3 dashboards, all from YAML
- 33 automated tests
- Every merge goes through Validate, Plan and an approval before Apply
- About 10 seconds to rebuild all monitoring in a new Datadog account
