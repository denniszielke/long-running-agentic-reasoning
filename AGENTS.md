# AGENTS.md - operations runbook

Operational guidance for the human-approved hypothesis workflow. See
[README.md](README.md) for the architecture and user flow.

## Components

| Component | Runs on | Entry point | Key output |
|---|---|---|---|
| Hypothesis agent | Microsoft Foundry hosted container | `scripts.deploy_hosted_hypothesis_agent` | `HYPOTHESIS_HOSTED_AGENT_NAME` |
| Workflow state | Azure Blob Storage | Provisioned by `azd up` | `AZURE_STORAGE_ACCOUNT_NAME` |
| Research toolboxes | Foundry management plane | `scripts.register_hypothesis_toolboxes` | Three `*_TOOLBOX_ENDPOINT` values |
| Weather MCP server | Azure Container Apps | `scripts.deploy_weather_mcp_server` | `WEATHER_MCP_URL` |
| Weather toolbox | Foundry management plane | `scripts.register_weather_toolbox` | `FOUNDRY_TOOLBOX_ENDPOINT` |
| Workflow console | Local Python and React | `src.hypothesis_ag_ui` | <http://127.0.0.1:5178> |

All Python scripts run from the repository root, load `./.env`, and authenticate
with `DefaultAzureCredential`. Run `az login` and `azd auth login` first.

## Provision

```bash
azd up
```

The postdeploy hook copies the azd environment into `./.env`. Provisioning
creates:

- a Microsoft Foundry project and model deployment,
- an Azure Container Registry connected to the project,
- Azure Blob Storage for workflow state,
- a Container Apps environment and image-pull identity for the weather service,
- Application Insights and Log Analytics,
- the hosted-agent capability host and required baseline role assignments.

Set these source endpoints in `.env` after provisioning:

```dotenv
INTERNET_RESEARCH_MCP_URL=https://<service>/mcp
CONTEXT_API_MCP_URL=https://<service>/mcp
DOCUMENT_SEARCH_MCP_URL=https://<service>/mcp
```

For test deployments, deploy the included weather service and leave any source
URL unset. The registration script uses `WEATHER_MCP_URL` for each unset source.
This verifies wiring only; it does not emulate the source service's semantics.

## Deploy

Order matters: source services must exist before toolbox registration, and
toolboxes must exist before the agent version is created.

```bash
python3 -m scripts.deploy_weather_mcp_server
python3 -m scripts.register_weather_toolbox  # optional standalone weather toolbox
python3 -m scripts.register_hypothesis_toolboxes
python3 -m scripts.deploy_hosted_hypothesis_agent
```

The weather deploy script builds a uniquely tagged image, deploys the public
anonymous Container App with a `/health` readiness probe, and saves its `/mcp`
URL. Optional controls are `WEATHER_SEED`, `WEATHER_MCP_CPU`,
`WEATHER_MCP_MEMORY`, and `WEATHER_MCP_MIN_REPLICAS`.

The deploy script builds a uniquely tagged image in ACR, creates a hosted agent
version, waits up to 15 minutes for `Active`, grants the version identity
Foundry User, Cognitive Services OpenAI User, and Storage Blob Data Contributor,
then routes 100 percent of traffic to the new version.

Optional sizing and workflow controls:

```dotenv
HOSTED_AGENT_CPU=1
HOSTED_AGENT_MEMORY=2Gi
WORKFLOW_STORAGE_CONTAINER=agent-workflows
WORKFLOW_TTL_HOURS=24
HARNESS_MAX_ITERATIONS=12
```

## Update

### Change an MCP endpoint

Update the relevant `*_MCP_URL`, then recreate the toolboxes and deploy a new
agent version:

```bash
python3 -m scripts.register_hypothesis_toolboxes
python3 -m scripts.deploy_hosted_hypothesis_agent
```

### Update the weather service

Rebuild and redeploy the Container App, then recreate its toolbox if used:

```bash
python3 -m scripts.deploy_weather_mcp_server
python3 -m scripts.register_weather_toolbox
```

### Change agent code

Re-run the deployment script. Use an explicit image tag only when operationally
useful; otherwise the script generates a Git SHA and UTC timestamp tag.

```bash
python3 -m scripts.deploy_hosted_hypothesis_agent
python3 -m scripts.deploy_hosted_hypothesis_agent --tag <tag>
```

### Restore shared permissions

The deployment grants the active version identity directly. To restore the AI
Services account's shared toolbox or optional Agent 365 observability grant:

```bash
python3 -m scripts.grant_agent_permissions
python3 -m scripts.grant_agent_permissions --skip-observability
python3 -m scripts.grant_agent_permissions --skip-toolbox
```

The observability grant requires an appropriately privileged tenant
administrator. Application Insights telemetry does not depend on that optional
Agent 365 grant.

## Approval contract

Planning returns `workflow_id`, `plan_revision`, and `plan_digest`. A decision
must echo all three values. The agent rejects stale revisions, mismatched
digests, duplicate conflicting requests, missing caller identity, and expired
workflow records.

Use the CLI for operational checks:

```bash
python3 -m scripts.invoke_hypothesis_agent plan "Investigate the scenario"
python3 -m scripts.invoke_hypothesis_agent decide \
  <workflow-id> <revision> <sha256:digest> approved
python3 -m scripts.invoke_hypothesis_agent status <workflow-id>
```

`ALLOW_INSECURE_LOCAL_CALLER=true` and `ALLOW_IN_MEMORY_WORKFLOW_STORE=true`
exist only for local tests. Do not set them on the hosted deployment.

## Validate

Run the local test suite before deploying:

```bash
python3 -m unittest discover -s tests/hosted_hypothesis_agent -p 'test_*.py'
python3 -m unittest discover -s tests/hypothesis_ag_ui -p 'test_*.py'
cd src/hypothesis_ag_ui/frontend && npm run build
```

For an end-to-end deployed check, plan first and approve the saved artifact:

```bash
python3 -m scripts.test_hypothesis_plan
python3 -m scripts.test_hypothesis_approval
```

## Troubleshoot

- **Agent version does not become Active**: inspect the version in the Foundry
  portal and confirm the project ACR connection can pull the generated image.
- **Toolbox call returns 401 or 403**: rerun the deployment to restore the
  version identity grants, or run `scripts.grant_agent_permissions` for the
  shared account identity.
- **Model call returns 403**: confirm the active version identity has Cognitive
  Services OpenAI User on the AI Services account.
- **Workflow state fails to load or save**: confirm
  `WORKFLOW_STORAGE_ACCOUNT_URL` was injected by the deployment and the active
  version identity has Storage Blob Data Contributor on the storage account.
- **Approval is rejected**: retrieve current status and use its exact revision
  and digest. Do not reuse approval data after a revision.
- **Caller identity is missing**: invoke through the authenticated Foundry
  endpoint. The gateway must provide `x-ms-client-object-id`,
  `x-ms-client-principal-id`, or `x-ms-client-principal-name`.
- **No traces appear**: confirm `APPLICATIONINSIGHTS_CONNECTION_STRING` is
  present in the provisioned environment and monitoring is enabled.
- **Weather service is unavailable**: check the Container App revision and call
  the URL formed by replacing `/mcp` in `WEATHER_MCP_URL` with `/health`.

## Tear down

```bash
python3 -m scripts.delete_agents
azd down
```

The first command removes the hosted agent and all registered toolboxes,
including `weather-tools`. The second removes the Container App and other Azure
resource group resources.