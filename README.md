# Human-approved hypothesis workflow

A Microsoft Foundry hosted agent that turns a scenario into an evidence-gathering
plan, pauses for explicit human approval, and then executes the exact approved
revision. The workflow is designed for long-running reasoning where planning and
execution must be separated by a durable, auditable approval boundary.

## How it works

1. A caller submits a scenario with the `plan` action.
2. The agent formulates a hypothesis and a tool-backed execution plan.
3. The plan is stored in Azure Blob Storage with a revision and SHA-256 digest.
4. The caller approves, rejects, or requests revision using that exact revision
   and digest.
5. An approved plan resumes in execute mode and returns the evidence-backed
   result.

The agent fails closed when the approval does not match the current stored plan
or when the Foundry gateway does not provide an authenticated caller identity.
Workflow records use optimistic concurrency and expire after a configurable TTL.

```mermaid
flowchart LR
    U[CLI or AG-UI] -->|plan| A[Hosted hypothesis agent]
    A -->|save revision and digest| S[(Azure Blob Storage)]
  A --> H[Coordinator harness]
  H --> W[Weather specialist agent]
  H --> O[Hotel specialist agent]
  H --> R[Transportation specialist agent]
  W --> I[Weather MCP]
  O --> C[Hotels MCP]
  R --> D[Transportation MCP]
    U -->|approve exact plan| A
    A -->|load and verify| S
  A -->|execute approved plan| H
```

## Repository layout

```text
infra/                         Foundry, model, ACR, storage, and monitoring
scripts/                       Provisioned-resource deployment and CLI tools
src/hosted_hypothesis_agent/   Agent host, orchestration, models, and Blob store
src/hypothesis_ag_ui/          Local React console and authenticated adapter
src/travel_mcp_server/         Deterministic travel scenario MCP services
tests/                         Workflow, orchestration, and adapter tests
```

## Prerequisites

- Python 3.13+
- Azure CLI and Azure Developer CLI
- An Azure subscription with model quota in the selected region
- The included deterministic weather, hotel, and transportation MCP services

Authenticate and install the local dependencies:

```bash
az login
azd auth login
python3 -m pip install -r requirements.txt
```

## Configure

Provisioning writes Azure settings to `.env`. The travel host exposes three
independent MCP paths:

```dotenv
WEATHER_MCP_URL=https://<travel-host>/weather/mcp
HOTELS_MCP_URL=https://<travel-host>/hotels/mcp
TRAVEL_MCP_URL=https://<travel-host>/travel/mcp
```

See [.env.sample](.env.sample) for all supported settings. Optional
comma-separated allowlists can restrict the tools exposed from each toolbox.

Each service owns its own 30-city catalog and uses calendar modulo calculations,
so identical city/date inputs are stable while date changes are predictable.
During execution, the coordinator delegates approved steps to three bounded
specialist agents. Specialists can access only their corresponding MCP toolbox;
the coordinator combines their returned evidence into the final comparison.

## Deploy

Provision the Foundry project, model, container registry, Blob Storage,
Container Apps environment, and monitoring resources:

```bash
azd up
```

Deploy the travel MCP host and register its path-specific toolboxes:

```bash
python3 -m scripts.deploy_travel_mcp_server
python3 -m scripts.register_hypothesis_toolboxes
```

The deployment records `TRAVEL_MCP_HOST_URL` and all three MCP URLs in `.env`.

Build and deploy the hosted agent after toolbox registration:

```bash
python3 -m scripts.deploy_hosted_hypothesis_agent
```

The deployment waits for the new agent version to become active, grants its
instance identity access to the model, toolboxes, and workflow storage, then
routes all traffic to that version.

## Invoke

Create a plan:

```bash
python3 -m scripts.invoke_hypothesis_agent plan \
  "Compare a four-night Berlin or Prague trip starting 2026-09-14, including weather, a hotel with a pool, and transportation from Amsterdam."
```

Approve the exact revision and digest returned by the plan call:

```bash
python3 -m scripts.invoke_hypothesis_agent decide \
  <workflow-id> <revision> <sha256:digest> approved
```

Use `rejected` or `revise` instead of `approved` when appropriate. Inspect the
latest durable state with:

```bash
python3 -m scripts.invoke_hypothesis_agent status <workflow-id>
```

After completing a baseline, create a linked what-if workflow that replans and
requires a new approval while retaining the original result for comparison:

```bash
python3 -m scripts.invoke_hypothesis_agent what-if <workflow-id> \
  "Move the trip to 2026-10-12, require golf, and prioritize emissions over cost."
```

## Run the UI

Build the React frontend and start the local authenticated adapter:

```bash
cd src/hypothesis_ag_ui/frontend
npm install
npm run build
cd ../../..
python3 -m pip install -r src/hypothesis_ag_ui/requirements.txt
python3 -m src.hypothesis_ag_ui.server
```

Open <http://127.0.0.1:5178>. The adapter uses `DefaultAzureCredential` and the
deployed agent name from `.env`.

## Test

```bash
python3 -m unittest discover -s tests/hosted_hypothesis_agent -p 'test_*.py'
python3 -m unittest discover -s tests/hypothesis_ag_ui -p 'test_*.py'
python3 -m unittest discover -s tests/travel_mcp_server -p 'test_*.py'
cd src/hypothesis_ag_ui/frontend && npm run build
```

The deployed two-phase flow also has smoke-test scripts:

```bash
python3 -m scripts.test_hypothesis_plan
python3 -m scripts.test_hypothesis_approval
```

See [AGENTS.md](AGENTS.md) for operational procedures and troubleshooting.

## Clean up

```bash
python3 -m scripts.delete_agents
azd down
```