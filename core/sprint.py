"""
Sprint boundary utilities (B1).

Sprints are defined by a calendar: a start-date anchor plus a sprint
length in days. Given any date, `SprintCalendar` derives which sprint it
falls in. Every check that needs a `sprint_id` or sprint window (UAT
signoff, per-sprint history, traceability, promotion streaks) must go
through this module rather than inventing its own boundary logic.

Sprint ids are date-anchored and stable: the sprint beginning on
2026-08-22 has sprint_id "sprint-2026-08-22". Signoff artifacts should
carry that id (or a date that maps to the same sprint).

Configuration (first match wins):
1. Per-project override: config/projects.yaml
   repos.<repo_id>.sprint_calendar.{sprint_length_days, sprint_start_date}
2. Global default: config/master.yaml
   sprint_calendar.{sprint_length_days, sprint_start_date}
3. Fallback: default_sprint_duration_days (14), anchored to
   2020-01-06 (the first Monday of 2020) — only used when no calendar
   is configured at all.
"""

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Optional


@dataclass(frozen=True)
class Sprint:
    sprint_id: str
    start: date
    end: date          # inclusive

    def contains(self, d: date) -> bool:
        return self.start <= d <= self.end

    def window_start(self) -> datetime:
        return datetime.combine(self.start, time.min)

    def window_end(self) -> datetime:
        return datetime.combine(self.end, time.max)


def _parse_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


class SprintCalendar:
    def __init__(self, sprint_length_days: int, start_anchor: date):
        if sprint_length_days <= 0:
            raise ValueError("sprint_length_days must be a positive integer")
        self.sprint_length_days = int(sprint_length_days)
        self.start_anchor = start_anchor

    def sprint_containing(self, d: date) -> Sprint:
        # Floor division buckets both post-anchor and pre-anchor dates
        # correctly (pre-anchor dates land in earlier numbered sprints).
        offset_days = (d - self.start_anchor).days
        index = offset_days // self.sprint_length_days
        start = date.fromordinal(self.start_anchor.toordinal() + index * self.sprint_length_days)
        end = date.fromordinal(start.toordinal() + self.sprint_length_days - 1)
        return Sprint(sprint_id=f"sprint-{start.isoformat()}", start=start, end=end)

    def current_sprint(self, now: Optional[datetime] = None) -> Sprint:
        return self.sprint_containing((now or datetime.now()).date())

    def sprint_for_datetime(self, dt: datetime) -> Sprint:
        return self.sprint_containing(dt.date())


def calendar_from_config(master_config: dict, project_meta: Optional[dict] = None) -> SprintCalendar:
    """
    Build the effective SprintCalendar for a repo: per-project sprint_calendar
    (config/projects.yaml repos.<id>.sprint_calendar) wins over the global
    sprint_calendar (config/master.yaml); falls back to
    default_sprint_duration_days anchored at 2020-01-06.
    """
    cfg = {}
    if project_meta and isinstance(project_meta.get("sprint_calendar"), dict):
        cfg = project_meta["sprint_calendar"]
    elif isinstance(master_config.get("sprint_calendar"), dict):
        cfg = master_config["sprint_calendar"]

    length = cfg.get("sprint_length_days")
    if length is None:
        length = master_config.get("default_sprint_duration_days", 14)
    anchor = _parse_date(cfg.get("sprint_start_date"))
    if anchor is None:
        anchor = date(2020, 1, 6)
    return SprintCalendar(sprint_length_days=length, start_anchor=anchor)


def normalize_sprint_id(token: str) -> str:
    """
    Normalize a sprint reference from a signoff artifact so it can be
    compared with calendar sprint ids: lowercased, accepts 'S-2026-08-22',
    'sprint-2026-08-22', 'Sprint 2026-08-22', or a bare '2026-08-22'.
    """
    t = token.strip().lower()
    for prefix in ("sprint-", "sprint:", "sprint ", "s-"):
        if t.startswith(prefix):
            t = t[len(prefix):]
            break
    t = t.replace("_", "-").strip()
    return f"sprint-{t}"


def sprint_id_matches(token: str, sprint: Sprint) -> bool:
    """True if a sprint reference from an artifact denotes the given sprint."""
    if not token:
        return False
    return normalize_sprint_id(token) == sprint.sprint_id
