# Runbook: alerts from self-service monitoring

Every alert names the service, environment and owner. Start with the service's
dashboard: **[ENV] service - Service Overview** in Datadog.

## High latency
1. Open the dashboard and check whether latency rose alone or together with errors and CPU.
2. Latency and CPU both high: the service is likely overloaded. Check recent traffic and scale out.
3. Latency high, CPU normal: check downstream dependencies (database, external APIs).
4. Check for a deployment in the last hour and roll back if the timing matches.

## High error rate
1. Find out whether errors started with a deployment or a config change.
2. Check the service logs for the most common error.
3. If one dependency is failing, contact that dependency's owner.
4. Roll back if a recent release caused it.

## High CPU
1. Check whether request volume went up at the same time (expected load) or not (a runaway process).
2. Scale out for expected load; restart or roll back for a runaway process.

## No traffic
1. Check that the service is running and reachable (health check, load balancer).
2. Check DNS and network changes.
3. In the demo environment, this usually means `tools/emit_demo_metrics.py` was stopped.

## Changing a threshold or who gets paged
Edit the service's file in `teams/` and open a pull request. Don't edit monitors in the
Datadog UI: the next pipeline run will overwrite manual changes.
