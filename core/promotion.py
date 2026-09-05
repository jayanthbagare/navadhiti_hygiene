"""
Promotion-state persistence (B2).

`reports/promotion_state.json` is the single piece of state the system
persists across runs. Everything else stays stateless and idempotent.

Per repo, it tracks the consecutive qualifying-sprint streak. On each
run the master agent recomputes whether the repo qualifies this sprint:

    environment_separation: pass
    AND uat_signoff.method == repo_artifact (with a passing current-sprint
        artifact)
    AND, when config/master.yaml sets
        require_traceability_for_promotion: true,
        both traceability checks pass.

If yes the streak increments; if no it resets to 0.
`enforcement_eligible` becomes true once the streak reaches
`promotion_threshold_sprints`.

Re-running within the same sprint is idempotent: the streak is always
recomputed from `streak_before_sprint` (the streak as of the sprint's
first evaluation), so a mid-sprint re-run cannot double-count or double
reset. Only a run in a new sprint advances the streak.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Optional

from core.schema import ProjectHygieneReport

logger = logging.getLogger("hygiene.promotion")

DEFAULT_STATE_PATH = "reports/promotion_state.json"


def load_state(path: str = DEFAULT_STATE_PATH) -> Dict:
    if not os.path.exists(path):
        return {"repos": {}}
    try:
        with open(path, "r") as f:
            state = json.load(f)
        if not isinstance(state, dict):
            return {"repos": {}}
        state.setdefault("repos", {})
        return state
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Could not read promotion state %s (%s); starting fresh", path, exc)
        return {"repos": {}}


def save_state(state: Dict, path: str = DEFAULT_STATE_PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    state["updated_at"] = datetime.now().isoformat()
    with open(path, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def repo_qualifies(report: ProjectHygieneReport,
                   require_traceability: bool = False) -> bool:
    """Does this report qualify as a clean sprint for promotion purposes?"""
    dims = report.dimensions
    if dims.environment_separation.status != "pass":
        return False
    signoff = dims.uat_signoff
    if signoff.method != "repo_artifact" or signoff.status != "pass":
        return False
    if require_traceability:
        if dims.traceability.feature_to_issue.status != "pass":
            return False
        if dims.traceability.issue_to_ticket.status != "pass":
            return False
    return True


def update_streak(state: Dict, repo_id: str, sprint_id: Optional[str],
                  qualifies: bool, threshold: int) -> Dict:
    """
    Update one repo's streak entry. Same-sprint re-evaluations recompute
    from streak_before_sprint instead of incrementing again.
    """
    repos = state.setdefault("repos", {})
    entry = repos.setdefault(repo_id, {
        "qualifying_streak": 0,
        "streak_before_sprint": 0,
        "last_sprint_id": None,
        "last_qualifying_sprint": None,
        "enforcement_eligible": False,
    })

    if sprint_id is not None and entry.get("last_sprint_id") != sprint_id:
        entry["streak_before_sprint"] = entry.get("qualifying_streak", 0)
        entry["last_sprint_id"] = sprint_id

    entry["qualifying_streak"] = entry["streak_before_sprint"] + 1 if qualifies else 0
    if qualifies and sprint_id:
        entry["last_qualifying_sprint"] = sprint_id
    entry["enforcement_eligible"] = entry["qualifying_streak"] >= threshold
    entry["updated_at"] = datetime.now().isoformat()
    return entry


def update_promotion_state(reports, state: Dict, sprint_ids: Dict[str, Optional[str]],
                           threshold: int, require_traceability: bool = False,
                           path: str = DEFAULT_STATE_PATH) -> Dict:
    """
    Recompute streaks for every evaluated repo, flip each report's
    enforcement_eligible from the persisted streak (not just this
    sprint's snapshot), and persist the state file.
    """
    for report in reports:
        qualifies = repo_qualifies(report, require_traceability=require_traceability)
        entry = update_streak(state, report.id, sprint_ids.get(report.id), qualifies, threshold)
        report.overall.enforcement_eligible = bool(entry.get("enforcement_eligible"))
    save_state(state, path)
    return state
