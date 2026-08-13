# AGENTS.md - operations runbook

Operational guidance for the human-approved travel hypothesis workflow. See
[README.md](README.md) for the architecture and user flow.

## Components

| Component | Runs on | Entry point | Key output |
|---|---|---|---|
| Hypothesis agent | Microsoft Foundry hosted container | `scripts.deploy_hosted_hypothesis_agent` | `HYPOTHESIS_HOSTED_AGENT_NAME` |
| Workflow state | Azure Blob Storage | Provisioned by `azd up` | `AZURE_STORAGE_ACCOUNT_NAME` |
| Travel MCP host | Azure Container Apps | `scripts.deploy_travel_mcp_server` | `TRAVEL_MCP_HOST_URL` |
| Travel toolboxes | Foundry management plane | `scripts.register_hypothesis_toolboxes` | Three `*_TOOLBOX_ENDPOINT` values |
| Workflow console | Local Python and React | `src.hypothesis_ag_ui` | <http://127.0.0.1:5178> |

All Python scripts run from the repository root, load `./.env`, and authenticate
with `DefaultAzureCredential`. Run `az login` and `azd auth login` first.

## Provision and deploy

```bash
azd up
python3 -m scripts.deploy_travel_mcp_server
python3 -m scripts.register_hypothesis_toolboxes
python3 -m scripts.deploy_hosted_hypothesis_agent
```

Order matters: the public travel host must exist before toolbox registration,
and toolboxes must exist before the hosted agent version is created. The host
serves independent weather, hotel, and transportation MCP instances at
`/weather/mcp`, `/hotels/mcp`, and `/travel/mcp`. It uses static 30-city catalogs
and calendar modulo formulas, so identical inputs always return identical data.
The coordinator harness delegates approved steps to three independent specialist
agents, each restricted to its matching MCP toolbox.

The deployment creates uniquely tagged images, waits up to 15 minutes for the
hosted agent version to become `Active`, grants its identity Foundry User,
Cognitive Services OpenAI User, and Storage Blob Data Contributor, then routes
100 percent of traffic to the new version.

Optional controls:

```dotenv
TRAVEL_MCP_CPU=1
TRAVEL_MCP_MEMORY=2.0Gi
TRAVEL_MCP_MIN_REPLICAS=1
HOSTED_AGENT_CPU=1
HOSTED_AGENT_MEMORY=2Gi
WORKFLOW_STORAGE_CONTAINER=agent-workflows
WORKFLOW_TTL_HOURS=24
HARNESS_MAX_ITERATIONS=12
```

## Update

After changing a service, rebuild the host and recreate the toolboxes:

```bash
python3 -m scripts.deploy_travel_mcp_server
python3 -m scripts.register_hypothesis_toolboxes
python3 -m scripts.deploy_hosted_hypothesis_agent
```

After changing only agent code, rerun `scripts.deploy_hosted_hypothesis_agent`.
Use `--tag <tag>` only when an explicit image tag is operationally useful.

## Approval and what-if contract

Planning returns `workflow_id`, `plan_revision`, and `plan_digest`. A decision
must echo all three values. The agent rejects stale revisions, mismatched
digests, duplicate conflicting requests, missing caller identity, and expired
workflow records.

```bash
python3 -m scripts.invoke_hypothesis_agent plan \
  "Compare a four-night Berlin or Prague trip starting 2026-09-14, including weather, a hotel with a pool, and transportation from Amsterdam."
python3 -m scripts.invoke_hypothesis_agent decide \
  <workflow-id> <revision> <sha256:digest> approved
python3 -m scripts.invoke_hypothesis_agent status <workflow-id>
```

After the baseline completes, a what-if creates a new linked workflow, replans
all required evidence, and pauses for a separate approval. The baseline remains
immutable.

```bash
python3 -m scripts.invoke_hypothesis_agent what-if <completed-workflow-id> \
  "Move the trip to 2026-10-12, require golf, and prioritize emissions over cost."
```

## Validate

```bash
.venv/bin/python -m unittest discover -s tests/hosted_hypothesis_agent -p 'test_*.py'
.venv/bin/python -m unittest discover -s tests/hypothesis_ag_ui -p 'test_*.py'
.venv/bin/python -m unittest discover -s tests/travel_mcp_server -p 'test_*.py'
cd src/hypothesis_ag_ui/frontend && npm run build
```

For deployed checks, run `scripts.test_hypothesis_plan` and then
`scripts.test_hypothesis_approval` against the saved plan artifact.

## Troubleshoot

- **Toolbox returns 401 or 403**: rerun agent deployment to restore identity grants.
- **Model returns 403**: confirm Cognitive Services OpenAI User is assigned.
- **Workflow state fails**: confirm the storage URL and Blob Contributor role.
- **Approval is rejected**: retrieve status and use its exact revision/digest.
- **Travel service is unavailable**: call `${TRAVEL_MCP_HOST_URL}/health`.

## Tear down

```bash
python3 -m scripts.delete_agents
azd down
```
