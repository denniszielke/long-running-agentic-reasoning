# Lambert — History

## Learnings
- Team created 2026-10-09 for long-running-agentic-reasoning (Python, Bicep, Node.js).

## Onboarding
- **Preserve the approval boundary exactly:** decisions must carry the current `workflow_id`, `plan_revision`, and `plan_digest`; keep these visible and forward them unchanged (`AGENTS.md`; `src/hypothesis_ag_ui/frontend/src/App.tsx`).
- **Make human review legible and explicit:** render the hypothesis, assumptions, evidence, success criteria, risks, plan steps, status, and digest; execution stays blocked until the user decides (`README.md`; `src/hypothesis_ag_ui/frontend/src/App.tsx`).
- **Keep the UI adapter a narrow protocol bridge:** validate workflow state, invoke the upstream agent, and translate results to AG-UI state events (`src/hypothesis_ag_ui/server.py`; contract checks in `tests/hypothesis_ag_ui/test_server.py`).
- **Risk:** `server.py`'s `BearerAuth.auth_flow` currently assigns literal `******` to `Authorization` rather than using `_token_provider`; upstream auth may fail. Tests cover a successful plan stream and missing state, but no frontend behavior.
