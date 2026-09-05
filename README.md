# Navadhiti Project Hygiene System

This system evaluates projects for hygiene standards across two agents that share a core logic:
- **Observer** (read-only): Runs against existing projects.
- **Enforcer** (CI gate): Runs on new projects or promoted projects to block non-compliant merges.

## Architecture

The system uses a Master-Subagent architecture:
- `master_agent.py`: Queries git providers for all repos, filters out dormant ones (no commits in last 60 days), and dispatches sub-agents.
- `sub_agents/observer_agent.py`: Runs the checks and reports on the state.
- `sub_agents/enforcer_agent.py`: (Stubbed) Runs as a CI gate.

## Current State (Milestone 1)

- ✅ Master agent repo discovery (mocked with 3 projects).
- ✅ Activity window filtering (dormant projects are skipped).
- ✅ Schema defined in `core/schema.py` using Pydantic.
- ✅ Live checks simulated for `cost` and `deployment_history`.
- ✅ Stubbed checks for `environment_separation`, `ci_cd_gates`, `uat_signoff`, `security_baseline`.
- ✅ Aggregate report generation.

## Configuration
- `config/master.yaml`: Master settings (activity window, scoring weights).
- `config/projects.yaml`: Project metadata (timesheet code, mailbox pattern).
- `config/standard.yaml`: Environment and security standards definition.
- `config/integrations.yaml`: Stubs for integration credentials.

## Getting Started

1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the master agent:
   ```bash
   python master_agent.py
   ```

3. View reports in the `reports/` directory.
