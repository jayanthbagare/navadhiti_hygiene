"""
Smoke tests for the Milestone 2 build.

All GitHub / ticketing HTTP traffic is mocked at the requests.Session
layer, so these tests run offline. They exercise the real check
implementations end-to-end: discovery, the six original dimensions,
traceability, promotion streaks, report history archiving, and weight
validation.

Run: pytest
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.checks.ci_gates import check_ci_gates
from core.checks.deploy_history import check_deploy_history
from core.checks.environment import check_environment_separation
from core.checks.security import check_security_baseline
from core.checks.signoff import check_uat_signoff
from core.checks.traceability_issue import check_feature_issue_trace
from core.checks.traceability_ticket import check_issue_ticket_trace
from core.github_client import GitHubClient
from core.promotion import load_state, repo_qualifies, update_streak
from core.schema import ProjectHygieneReport, Dimensions
from core.sprint import SprintCalendar, calendar_from_config, normalize_sprint_id
from sub_agents.enforcer_agent import EnforcerAgent

REPO_ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 9, 5, 12, 0, 0)
DAY = timedelta(days=1)

# Calendar matching config/master.yaml: 14-day sprints anchored 2026-08-24.
# Current sprint containing NOW: 2026-08-24 .. 2026-09-06.
CALENDAR = SprintCalendar(14, datetime(2026, 8, 24).date())
CURRENT_SPRINT_ID = CALENDAR.sprint_containing(NOW.date()).sprint_id  # sprint-2026-08-24


class FrozenDatetime(datetime):
    """datetime whose "now" is a value this test controls.

    The end-to-end fixtures write a sign-off artifact for the sprint
    containing NOW, but core.sprint.current_sprint() resolves the sprint
    containing the *real* current date. Once real time left that 14-day window,
    the artifact stopped matching the current sprint and the suite began failing
    on a calendar that had not changed — a time bomb, not a check regression.
    Freezing every module that reads the wall clock makes the suite deterministic
    on any run date, forever.

    The frozen value advances one second per end-to-end run, because each run
    writes its own reports/history/<timestamp>-aggregate.json and two runs
    sharing a timestamp would overwrite one another.
    """

    frozen_now = NOW

    @classmethod
    def now(cls, tz=None):
        return cls.frozen_now if tz is None else cls.frozen_now.astimezone(tz)

    @classmethod
    def utcnow(cls):
        return cls.frozen_now


def tick_clock(seconds: int = 1) -> None:
    """Advance the frozen clock so the next run gets a distinct timestamp."""
    FrozenDatetime.frozen_now = FrozenDatetime.frozen_now + timedelta(seconds=seconds)


# Modules whose "now" the end-to-end run depends on. master_agent is patched
# separately, after its importlib.reload(), because a reload rebinds the name.
FROZEN_CLOCK_MODULES = ("core.sprint", "core.promotion", "sub_agents.observer_agent")


class FakeResponse:
    def __init__(self, status_code=200, body=None, raw=None, headers=None):
        self.status_code = status_code
        self._body = body
        self.text = raw if raw is not None else (
            json.dumps(body) if body is not None else ""
        )
        self.headers = headers or {}

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakeGitHub:
    """
    A small in-memory GitHub org. Routes GET requests like the real API.
    """

    def __init__(self):
        self.calls = []
        self.repos = {}          # "owner/repo" -> {default_branch, pushed_at, ...}
        self.trees = {}          # "owner/repo" -> [path, ...]
        self.protection = {}     # "owner/repo" -> protection dict | None (404)
        self.protection_error = {}  # "owner/repo" -> status_code (e.g. 403)
        self.pulls = {}
        self.issues = {}         # issue number -> issue dict or None (404)
        self.issue_list = {}
        self.releases = {}
        self.tags = {}
        self.commits = {}        # sha -> {"commit": {"message": ...}}
        self.commit_dates = {}   # sha -> committer date string
        self.files = {}         # "owner/repo:path" -> raw content
        self.pull_files = {}     # (repo, number) -> [{"filename": ...}]

    def add_repo(self, repo_id, default_branch="main", pushed_days_ago=2,
                 created="2025-01-01T00:00:00Z"):
        owner, name = repo_id.split("/")
        self.repos[repo_id] = {
            "full_name": repo_id,
            "html_url": f"https://github.com/{repo_id}",
            "default_branch": default_branch,
            "pushed_at": (NOW - timedelta(days=pushed_days_ago)).isoformat() + "Z",
            "created_at": created,
            "archived": False,
        }
        return self.repos[repo_id]

    # ------------------------------------------------------------------

    def route(self, method, url, params=None, headers=None, **kwargs):
        self.calls.append(url.split("api.github.com")[-1].split("?")[0])
        assert method == "GET"
        params = params or {}
        path = url.split("api.github.com")[-1]

        if "/orgs/" in path and path.endswith("/repos"):
            return FakeResponse(200, list(self.repos.values()))

        # /repos/{owner}/{repo}/...
        parts = path.split("/")
        if parts[1] == "repos":
            repo_id = f"{parts[2]}/{parts[3]}"
            rest = "/".join(parts[4:])

            if rest == "":
                if repo_id in self.repos:
                    return FakeResponse(200, self.repos[repo_id])
                return FakeResponse(404, {"message": "Not Found"})

            if repo_id not in self.repos:
                return FakeResponse(404, {"message": "Not Found"})

            if rest.startswith("git/trees/"):
                branch = rest[len("git/trees/"):]
                tree = [{"path": p, "type": "blob"} for p in self.trees.get(repo_id, [])]
                return FakeResponse(200, {"tree": tree, "truncated": False})

            if rest.startswith("branches/") and rest.endswith("/protection"):
                if repo_id in self.protection_error:
                    return FakeResponse(self.protection_error[repo_id], {"message": "forbidden"})
                protection = self.protection.get(repo_id, "UNSET")
                if protection == "UNSET" or protection is None:
                    return FakeResponse(404, {"message": "Not Found"})
                return FakeResponse(200, protection)

            if rest == "pulls":
                state = params.get("state")
                assert state == "closed"
                page = int(params.get("page", 1))
                all_prs = self.pulls.get(repo_id, [])
                batch = all_prs[(page - 1) * 100: page * 100]
                return FakeResponse(200, batch)

            if rest == "issues" and params.get("state") == "closed":
                page = int(params.get("page", 1))
                items = self.issue_list.get(repo_id, [])
                return FakeResponse(200, items[(page - 1) * 100: page * 100])

            if rest.startswith("issues/") and rest.split("/")[1].isdigit():
                number = int(rest.split("/")[1])
                if self.issues.get(repo_id, {}).get(number, "MISSING") == "MISSING":
                    return FakeResponse(404, {"message": "Not Found"})
                return FakeResponse(200, self.issues[repo_id][number])

            if rest.startswith("pulls/") and rest.endswith("/files"):
                number = int(rest.split("/")[1])
                return FakeResponse(200, self.pull_files.get((repo_id, number), []))

            if rest == "releases":
                return FakeResponse(200, self.releases.get(repo_id, []))

            if rest == "tags":
                return FakeResponse(200, self.tags.get(repo_id, []))

            if rest == "commits":
                return FakeResponse(200, [])  # not used by these tests

            if rest.startswith("contents/"):
                file_path = rest[len("contents/"):]
                key = f"{repo_id}:{file_path}"
                if key in self.files:
                    return FakeResponse(200, raw=self.files[key])
                return FakeResponse(404, {"message": "Not Found"})

            if rest.startswith("commits/"):
                sha = rest[len("commits/"):]
                if sha in self.commits:
                    body = {
                        "commit": {
                            "message": self.commits[sha],
                            "committer": {"date": self.commit_dates.get(sha)},
                        }
                    }
                    return FakeResponse(200, body)
                return FakeResponse(404, {"message": "Not Found"})

        return FakeResponse(404, {"message": f"unexpected path: {path}"})


def make_client(fake):
    client = GitHubClient(api_url="https://api.github.com", token="test-token")
    session = client._session
    original_request = session.request

    def patched_request(method, url, **kwargs):
        return fake.route(method, url, **kwargs)

    session.request = patched_request
    return client


# ---------------------------------------------------------------------------
# Sprint utilities
# ---------------------------------------------------------------------------

class SprintTests(unittest.TestCase):
    def test_bucketing_and_ids(self):
        cal = SprintCalendar(14, datetime(2026, 8, 24).date())
        self.assertEqual(cal.sprint_containing(datetime(2026, 9, 1).date()).sprint_id,
                         "sprint-2026-08-24")
        self.assertEqual(cal.sprint_containing(datetime(2026, 9, 7).date()).sprint_id,
                         "sprint-2026-09-07")
        self.assertEqual(cal.sprint_containing(datetime(2026, 8, 23).date()).sprint_id,
                         "sprint-2026-08-10")

    def test_normalize_sprint_id(self):
        self.assertEqual(normalize_sprint_id("S-2026-08-24"), "sprint-2026-08-24")
        self.assertEqual(normalize_sprint_id("Sprint 2026-08-24"), "sprint-2026-08-24")
        self.assertEqual(normalize_sprint_id("2026-08-24"), "sprint-2026-08-24")
        self.assertEqual(normalize_sprint_id("sprint-2026-08-24"), "sprint-2026-08-24")

    def test_calendar_from_config_overrides(self):
        master = {"default_sprint_duration_days": 14}
        cal = calendar_from_config(master, {"sprint_calendar": {
            "sprint_length_days": 10, "sprint_start_date": "2026-08-20"}})
        self.assertEqual(cal.sprint_length_days, 10)
        self.assertEqual(cal.sprint_containing(datetime(2026, 8, 20).date()).sprint_id,
                         "sprint-2026-08-20")


# ---------------------------------------------------------------------------
# Promotion streaks (B2)
# ---------------------------------------------------------------------------

class PromotionTests(unittest.TestCase):
    def _report(self, env="pass", method="repo_artifact", signoff="pass",
                ft="undefined_standard", it="undefined_standard"):
        return ProjectHygieneReport(
            id="org/x", repo_url="u", last_evaluated=NOW,
            dimensions=Dimensions.model_validate({
                "environment_separation": {"status": env},
                "uat_signoff": {"status": signoff, "method": method},
                "traceability": {"feature_to_issue": {"status": ft},
                                 "issue_to_ticket": {"status": it}},
            }),
        )

    def test_qualification_rules(self):
        self.assertTrue(repo_qualifies(self._report()))
        self.assertFalse(repo_qualifies(self._report(env="fail")))
        self.assertFalse(repo_qualifies(self._report(method="none", signoff="unverifiable")))
        self.assertFalse(repo_qualifies(self._report(signoff="fail")))
        # traceability only required when the toggle is on
        self.assertTrue(repo_qualifies(self._report(ft="fail"), require_traceability=False))
        self.assertFalse(repo_qualifies(self._report(ft="fail"), require_traceability=True))
        self.assertFalse(repo_qualifies(self._report(it="fail"), require_traceability=True))
        self.assertTrue(repo_qualifies(self._report(ft="pass", it="pass"),
                                        require_traceability=True))

    def test_streak_increments_resets_and_is_idempotent_per_sprint(self):
        state = {"repos": {}}
        entry = update_streak(state, "org/x", "sprint-A", True, threshold=3)
        self.assertEqual(entry["qualifying_streak"], 1)
        # same sprint re-run: no double count
        entry = update_streak(state, "org/x", "sprint-A", True, threshold=3)
        self.assertEqual(entry["qualifying_streak"], 1)
        # mid-sprint regression then recovery: still the sprint's single shot
        entry = update_streak(state, "org/x", "sprint-A", False, threshold=3)
        self.assertEqual(entry["qualifying_streak"], 0)
        entry = update_streak(state, "org/x", "sprint-A", True, threshold=3)
        self.assertEqual(entry["qualifying_streak"], 1)
        # next sprints
        update_streak(state, "org/x", "sprint-B", True, threshold=3)
        entry = update_streak(state, "org/x", "sprint-C", True, threshold=3)
        self.assertEqual(entry["qualifying_streak"], 3)
        self.assertTrue(entry["enforcement_eligible"])
        # a bad sprint resets
        entry = update_streak(state, "org/x", "sprint-D", False, threshold=3)
        self.assertEqual(entry["qualifying_streak"], 0)
        self.assertFalse(entry["enforcement_eligible"])

    def test_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "state.json")
            state = {"repos": {}}
            update_streak(state, "org/x", "sprint-A", True, threshold=3)
            from core.promotion import save_state
            save_state(state, path)
            loaded = load_state(path)
            self.assertEqual(loaded["repos"]["org/x"]["qualifying_streak"], 1)


# ---------------------------------------------------------------------------
# File-tree checks (A2, A4) — shared single round-trip
# ---------------------------------------------------------------------------

TREE = [
    "README.md",
    "terraform/workspaces/prod.tf",
    ".github/dependabot.yml",
    ".github/workflows/ci.yml",
    "src/main.py",
]


class TreeChecksTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeGitHub()
        self.fake.add_repo("org/x")
        self.fake.trees["org/x"] = list(TREE)
        self.client = make_client(self.fake)
        self.standard = {
            "environment_separation": {"required_artifacts": [
                "terraform/workspaces", "k8s/namespaces", "docker-compose.*.yml"]},
            "security_baseline": {"required_scanners": ["dependabot", "snyk", "trivy"]},
        }

    def test_environment_pass_on_any_match(self):
        result = check_environment_separation("org/x", self.client, self.standard, "main")
        self.assertEqual(result.status, "pass")
        self.assertTrue(any("terraform/workspaces" in e for e in result.evidence))

    def test_environment_fail_when_nothing_matches(self):
        self.fake.trees["org/x"] = ["README.md", "src/main.py"]
        result = check_environment_separation("org/x", self.client, self.standard, "main")
        self.assertEqual(result.status, "fail")
        self.assertEqual(len([e for e in result.evidence if e.startswith("No artifact")]), 3)

    def test_environment_tree_fetch_failure_is_undefined(self):
        self.fake.repos.pop("org/x")
        result = check_environment_separation("org/x", self.client, self.standard, "main")
        self.assertEqual(result.status, "undefined_standard")

    def test_security_pass_on_any_scanner(self):
        result = check_security_baseline("org/x", self.client, self.standard, "main")
        self.assertEqual(result.status, "pass")
        self.assertTrue(any("dependabot" in e for e in result.evidence))

    def test_security_fail_when_no_scanners(self):
        self.fake.trees["org/x"] = ["README.md", "src/main.py"]
        result = check_security_baseline("org/x", self.client, self.standard, "main")
        self.assertEqual(result.status, "fail")

    def test_env_and_security_share_one_tree_call(self):
        check_environment_separation("org/x", self.client, self.standard, "main")
        check_security_baseline("org/x", self.client, self.standard, "main")
        tree_calls = [c for c in self.fake.calls if "/git/trees/" in c]
        self.assertEqual(len(tree_calls), 1)


# ---------------------------------------------------------------------------
# CI gates (A3)
# ---------------------------------------------------------------------------

class CiGatesTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeGitHub()
        self.fake.add_repo("org/x")
        self.client = make_client(self.fake)

    def test_pass(self):
        self.fake.protection["org/x"] = {
            "required_pull_request_reviews": {"required_approving_review_count": 2},
            "required_status_checks": {"contexts": ["build", "test"]},
        }
        result = check_ci_gates("org/x", self.client, "main")
        self.assertEqual(result.status, "pass")

    def test_fail_unprotected(self):
        self.fake.protection["org/x"] = None  # 404
        result = check_ci_gates("org/x", self.client, "main")
        self.assertEqual(result.status, "fail")
        self.assertIn("not enabled", result.evidence[0])

    def test_fail_no_reviews(self):
        self.fake.protection["org/x"] = {
            "required_pull_request_reviews": {"required_approving_review_count": 0},
            "required_status_checks": {"contexts": ["build"]},
        }
        result = check_ci_gates("org/x", self.client, "main")
        self.assertEqual(result.status, "fail")
        self.assertTrue(any("review" in e for e in result.evidence))

    def test_fail_no_status_checks(self):
        self.fake.protection["org/x"] = {
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_status_checks": {"contexts": [], "checks": []},
        }
        result = check_ci_gates("org/x", self.client, "main")
        self.assertEqual(result.status, "fail")
        self.assertTrue(any("status checks" in e for e in result.evidence))

    def test_forbidden_is_undefined_not_fail(self):
        self.fake.protection_error["org/x"] = 403
        result = check_ci_gates("org/x", self.client, "main")
        self.assertEqual(result.status, "undefined_standard")


# ---------------------------------------------------------------------------
# UAT signoff (A5)
# ---------------------------------------------------------------------------

class SignoffTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeGitHub()
        self.fake.add_repo("org/x")
        self.client = make_client(self.fake)
        self.standard = {"uat_signoff": {"artifact_pattern": "docs/signoffs/*.md"}}

    def _signoff_file(self, sprint_id=CURRENT_SPRINT_ID, reviewer="Jane Doe",
                      date="2026-09-04"):
        content = f"# UAT Signoff\n\nsprint_id: {sprint_id}\nreviewer: {reviewer}\ndate: {date}\n"
        self.fake.trees["org/x"] = ["docs/signoffs/sprint-1.md"]
        self.fake.files["org/x:docs/signoffs/sprint-1.md"] = content

    def test_pass_current_sprint_artifact(self):
        self._signoff_file()
        result = check_uat_signoff("org/x", self.client, self.standard, CALENDAR, "main", now=NOW)
        self.assertEqual(result.status, "pass")
        self.assertEqual(result.method, "repo_artifact")
        self.assertEqual(len(result.per_sprint), 1)
        self.assertEqual(result.per_sprint[0].status, "pass")

    def test_fail_when_artifact_covers_other_sprint(self):
        self._signoff_file(sprint_id="sprint-2026-08-10", date="2026-08-12")
        result = check_uat_signoff("org/x", self.client, self.standard, CALENDAR, "main", now=NOW)
        self.assertEqual(result.status, "fail")
        self.assertEqual(result.method, "repo_artifact")

    def test_fail_malformed_current_sprint_artifact(self):
        self._signoff_file(reviewer=None, date="2026-09-04")
        self.fake.files["org/x:docs/signoffs/sprint-1.md"] = (
            f"# UAT Signoff\n\nsprint_id: {CURRENT_SPRINT_ID}\n")
        result = check_uat_signoff("org/x", self.client, self.standard, CALENDAR, "main", now=NOW)
        self.assertEqual(result.status, "fail")
        self.assertTrue(any("malformed" in e for e in result.evidence))

    def test_fail_no_artifacts(self):
        self.fake.trees["org/x"] = ["README.md"]
        result = check_uat_signoff("org/x", self.client, self.standard, CALENDAR, "main", now=NOW)
        self.assertEqual(result.status, "fail")
        self.assertEqual(result.method, "none")

    def test_unverifiable_when_api_unavailable(self):
        self.fake.repos.pop("org/x")
        result = check_uat_signoff("org/x", self.client, self.standard, CALENDAR, "main", now=NOW)
        self.assertEqual(result.status, "unverifiable")

    def test_date_only_artifact_maps_via_calendar(self):
        self.fake.trees["org/x"] = ["docs/signoffs/sprint-1.md"]
        self.fake.files["org/x:docs/signoffs/sprint-1.md"] = (
            "reviewer: Jane Doe\ndate: 2026-09-01\n")
        result = check_uat_signoff("org/x", self.client, self.standard, CALENDAR, "main", now=NOW)
        self.assertEqual(result.status, "pass")
        self.assertEqual(result.per_sprint[0].sprint_id, CURRENT_SPRINT_ID)


# ---------------------------------------------------------------------------
# Deployment history (B3)
# ---------------------------------------------------------------------------

class DeployHistoryTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeGitHub()
        self.fake.add_repo("org/x")
        self.client = make_client(self.fake)
        self.standard = {"deployment_history": {
            "deploy_marker": "releases", "tag_pattern": r'^v\d+\.\d+\.\d+$'}}

    def _release(self, published):
        self.fake.releases["org/x"] = [{
            "draft": False, "prerelease": False,
            "published_at": published.isoformat() + "Z",
        }]

    def _artifact(self, date_str):
        from core.checks.signoff import SignoffArtifact
        from datetime import date
        return SignoffArtifact(path="docs/signoffs/s.md", sprint_id=CURRENT_SPRINT_ID,
                               reviewer="Jane", date=date.fromisoformat(date_str), valid=True)

    def test_deploy_with_signoff_in_sprint_window_passes(self):
        self._release(NOW - DAY)
        result = check_deploy_history("org/x", self.client, self.standard,
                                      [self._artifact("2026-09-03")], CALENDAR, "main")
        self.assertEqual(result.status, "pass")
        self.assertFalse(result.gap_flag)
        self.assertEqual(result.method, "releases")

    def test_deploy_without_signoff_flags_gap(self):
        self._release(NOW - DAY)
        result = check_deploy_history("org/x", self.client, self.standard,
                                      [self._artifact("2026-08-01")], CALENDAR, "main")
        self.assertEqual(result.status, "fail")
        self.assertTrue(result.gap_flag)
        self.assertEqual(result.last_deploy.date(), (NOW - DAY).date())

    def test_signoff_after_deploy_does_not_clear_gap(self):
        self._release(NOW - 2 * DAY)
        result = check_deploy_history("org/x", self.client, self.standard,
                                      [self._artifact("2026-09-05")], CALENDAR, "main")
        self.assertTrue(result.gap_flag)

    def test_no_releases_no_matching_tags_is_undefined(self):
        self.fake.tags["org/x"] = [{"name": "nightly-20260901", "commit": {"sha": "s1"}}]
        self.fake.commits["s1"] = "build"
        self.fake.commit_dates["s1"] = NOW.isoformat() + "Z"
        result = check_deploy_history("org/x", self.client, self.standard, [], CALENDAR, "main")
        self.assertEqual(result.status, "undefined_standard")
        self.assertFalse(result.gap_flag)
        self.assertIn("No deployment evidence", result.evidence[0])

    def test_tag_route_used_when_no_releases(self):
        self.fake.releases["org/x"] = []
        self.fake.tags["org/x"] = [{"name": "v1.2.3", "commit": {"sha": "s1"}}]
        self.fake.commits["s1"] = "release"
        self.fake.commit_dates["s1"] = (NOW - DAY).isoformat() + "Z"
        result = check_deploy_history("org/x", self.client, self.standard,
                                      [self._artifact("2026-09-03")], CALENDAR, "main")
        self.assertEqual(result.status, "pass")
        self.assertEqual(result.method, "tags")

    def test_signoff_api_failure_does_not_falsely_flag_gap(self):
        self._release(NOW - DAY)
        result = check_deploy_history("org/x", self.client, self.standard, None, CALENDAR, "main")
        self.assertEqual(result.status, "undefined_standard")
        self.assertFalse(result.gap_flag)


# ---------------------------------------------------------------------------
# Traceability (C2, C3)
# ---------------------------------------------------------------------------

class TraceabilityTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeGitHub()
        self.fake.add_repo("org/x")
        self.client = make_client(self.fake)
        self.standard = {"traceability": {
            "spec_directory": "specs/",
            "ticket_ref_pattern": r"[A-Z][A-Z0-9]*-\d+",
            "ticket_label_prefix": "ticket:",
        }}

    def _pr(self, number, title, body=None, merged_days_ago=1, sha=None):
        return {
            "number": number, "title": title, "body": body,
            "state": "closed",
            "merged_at": (NOW - timedelta(days=merged_days_ago)).isoformat() + "Z",
            "updated_at": (NOW - timedelta(days=merged_days_ago)).isoformat() + "Z",
            "base": {"ref": "main"},
            "merge_commit_sha": sha or f"sha{number}",
        }

    def test_feature_to_issue_pass_when_all_prs_linked(self):
        self.fake.pulls["org/x"] = [self._pr(12, "Add feature", "Closes #34")]
        self.fake.issues["org/x"] = {34: {"number": 34, "title": "Feature request"}}
        result = check_feature_issue_trace("org/x", self.client, self.standard,
                                          CALENDAR, "main", now=NOW)
        self.assertEqual(result.status, "pass")
        self.assertEqual(result.method, "pr_linked")
        self.assertEqual(result.unlinked_count, 0)
        self.assertEqual(result.total_checked, 1)

    def test_feature_to_issue_fail_on_unlinked_pr(self):
        self.fake.pulls["org/x"] = [
            self._pr(12, "Add feature", "Closes #34"),
            self._pr(13, "Typo fix", None, sha="sha13"),
        ]
        self.fake.issues["org/x"] = {34: {"number": 34}}
        self.fake.commits["sha13"] = "Typo fix (#13)"  # PR-suffix is NOT an issue link
        result = check_feature_issue_trace("org/x", self.client, self.standard,
                                          CALENDAR, "main", now=NOW)
        self.assertEqual(result.status, "fail")
        self.assertEqual(result.unlinked_count, 1)
        self.assertEqual(result.total_checked, 2)

    def test_reference_to_missing_issue_counts_unlinked(self):
        self.fake.pulls["org/x"] = [self._pr(12, "Add feature", "Closes #99")]
        self.fake.issues["org/x"] = {}  # issue 99 -> 404
        result = check_feature_issue_trace("org/x", self.client, self.standard,
                                          CALENDAR, "main", now=NOW)
        self.assertEqual(result.status, "fail")
        self.assertEqual(result.unlinked_count, 1)

    def test_merge_commit_keyword_links_via_commit_linked(self):
        self.fake.pulls["org/x"] = [self._pr(13, "Typo fix", None, sha="sha13")]
        self.fake.commits["sha13"] = "Typo fix\n\nCloses #34"
        self.fake.issues["org/x"] = {34: {"number": 34}}
        result = check_feature_issue_trace("org/x", self.client, self.standard,
                                          CALENDAR, "main", now=NOW)
        self.assertEqual(result.status, "pass")
        self.assertEqual(result.method, "commit_linked")

    def test_spec_file_route_links_pr(self):
        self.fake.pulls["org/x"] = [self._pr(13, "Add spec", None)]
        self.fake.pull_files[("org/x", 13)] = [{"filename": "specs/feature-a/spec.md"}]
        self.fake.files["org/x:specs/feature-a/spec.md"] = "# Spec\n\nResolves #34\n"
        self.fake.issues["org/x"] = {34: {"number": 34}}
        result = check_feature_issue_trace("org/x", self.client, self.standard,
                                          CALENDAR, "main", now=NOW)
        self.assertEqual(result.status, "pass")
        self.assertTrue(any("spec file" in e for e in result.evidence))

    def test_direct_to_main_is_undefined_and_flagged(self):
        self.fake.pulls["org/x"] = []
        self.fake.commits["sha1"] = "direct commit"
        # branch commits endpoint returns one direct commit
        original_route = self.fake.route
        def route_with_commits(method, url, **kwargs):
            if url.endswith("/commits") and "sha" in (kwargs.get("params") or {}):
                return FakeResponse(200, [{"sha": "sha1"}])
            return original_route(method, url, **kwargs)
        self.fake.route = route_with_commits
        result = check_feature_issue_trace("org/x", self.client, self.standard,
                                          CALENDAR, "main", now=NOW)
        self.assertEqual(result.status, "undefined_standard")
        self.assertTrue(any("direct-to-main" in e for e in result.evidence))

    def test_issue_to_ticket_undefined_without_integration(self):
        result = check_issue_ticket_trace("org/x", self.client, self.standard,
                                          {}, CALENDAR, "main", now=NOW)
        self.assertEqual(result.status, "undefined_standard")
        self.assertIn("No ticketing integration", result.evidence[0])

    def test_issue_to_ticket_pass_and_fail(self):
        integrations = {"ticketing_system": {"type": "jira", "api_url": "https://jira.example/rest/api/3"}}
        self.fake.issue_list["org/x"] = [
            {"number": 34, "title": "Bug", "body": "Jira: NAV-101", "closed_at": NOW.isoformat() + "Z"},
            {"number": 35, "title": "Bug 2", "body": "no ref here", "labels": [],
             "closed_at": NOW.isoformat() + "Z"},
        ]
        # no TICKETING_TOKEN -> pattern-only (degraded, not verifying)
        result = check_issue_ticket_trace("org/x", self.client, self.standard,
                                          integrations, CALENDAR, "main", now=NOW)
        self.assertEqual(result.status, "fail")
        self.assertEqual(result.unlinked_count, 1)
        self.assertEqual(result.total_checked, 2)
        self.assertTrue(any("pattern-match only" in e for e in result.evidence))

        # with a valid label prefix the second issue links too
        self.fake.issue_list["org/x"][1]["labels"] = [{"name": "ticket:NAV-102"}]
        result = check_issue_ticket_trace("org/x", self.client, self.standard,
                                          integrations, CALENDAR, "main", now=NOW)
        self.assertEqual(result.status, "pass")
        self.assertEqual(result.unlinked_count, 0)

    def test_issue_to_ticket_undefined_when_no_issues_closed(self):
        integrations = {"ticketing_system": {"type": "jira", "api_url": "https://jira.example/rest/api/3"}}
        self.fake.issue_list["org/x"] = []
        result = check_issue_ticket_trace("org/x", self.client, self.standard,
                                          integrations, CALENDAR, "main", now=NOW)
        self.assertEqual(result.status, "undefined_standard")


# ---------------------------------------------------------------------------
# End-to-end master run (A1, B2, B4, B5, B6) with a fake org
# ---------------------------------------------------------------------------

class MasterEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        shutil.copytree(REPO_ROOT / "config", os.path.join(self.tmp, "config"))
        os.makedirs(os.path.join(self.tmp, "reports"))
        # keep the repo's own reports/ out of the test sandbox
        os.chdir(self.tmp)
        self._old_env = os.environ.get("GIT_TOKEN")
        os.environ["GIT_TOKEN"] = "test-token"

        self._clock_patches = [patch(f"{mod}.datetime", FrozenDatetime)
                               for mod in FROZEN_CLOCK_MODULES]
        FrozenDatetime.frozen_now = NOW
        for clock_patch in self._clock_patches:
            clock_patch.start()

        self.fake = FakeGitHub()
        self.fake.add_repo("navadhiti/service-a", pushed_days_ago=2, created="2025-01-01T00:00:00Z")
        self.fake.add_repo("navadhiti/service-b", pushed_days_ago=5, created="2026-09-02T00:00:00Z")
        self.fake.add_repo("navadhiti/dormant-service", pushed_days_ago=100)

        # service-a: clean repo — env artifacts, dependabot, protection,
        # current-sprint signoff, linked PRs, recent release.
        self.fake.trees["navadhiti/service-a"] = [
            "README.md",
            "terraform/workspaces/prod.tf",
            ".github/dependabot.yml",
            f"docs/signoffs/{CURRENT_SPRINT_ID}.md",
            "src/main.py",
        ]
        self.fake.files[f"navadhiti/service-a:docs/signoffs/{CURRENT_SPRINT_ID}.md"] = (
            f"# UAT Signoff\n\nsprint_id: {CURRENT_SPRINT_ID}\n"
            "reviewer: Jane Doe (jane@navadhiti.com)\ndate: 2026-09-03\n"
        )
        self.fake.protection["navadhiti/service-a"] = {
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_status_checks": {"contexts": ["ci"]},
        }
        self.fake.pulls["navadhiti/service-a"] = [
            {"number": 12, "title": "Add feature", "body": "Closes #34",
             "merged_at": (NOW - DAY).isoformat() + "Z",
             "updated_at": (NOW - DAY).isoformat() + "Z",
             "base": {"ref": "main"}, "merge_commit_sha": "m1"},
        ]
        self.fake.issues["navadhiti/service-a"] = {34: {"number": 34, "title": "Feature"}}
        self.fake.issue_list["navadhiti/service-a"] = []
        self.fake.releases["navadhiti/service-a"] = [{
            "draft": False, "prerelease": False,
            "published_at": (NOW - DAY).isoformat() + "Z",
        }]
        self.fake.commits["m1"] = "Add feature (#12)"

        # service-b: bare repo — fails most checks.
        self.fake.trees["navadhiti/service-b"] = ["README.md"]
        self.fake.pulls["navadhiti/service-b"] = []
        self.fake.issue_list["navadhiti/service-b"] = []
        self.fake.releases["navadhiti/service-b"] = []

    def tearDown(self):
        for clock_patch in reversed(self._clock_patches):
            clock_patch.stop()
        os.chdir(self.old_cwd)
        if self._old_env is None:
            os.environ.pop("GIT_TOKEN", None)
        else:
            os.environ["GIT_TOKEN"] = self._old_env
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_master(self, extra_args=None):
        extra_args = extra_args or []
        tick_clock()  # each run needs its own history-archive timestamp
        with patch("sys.argv", ["master_agent.py"] + extra_args), \
                patch("requests.Session.request") as mock_request:
            fake = self.fake

            def route(method, url, **kwargs):
                return fake.route(method, url, **kwargs)

            mock_request.side_effect = route
            import importlib
            import master_agent
            importlib.reload(master_agent)
            # reload rebinds master_agent.datetime, so re-freeze after it
            master_clock = patch("master_agent.datetime", FrozenDatetime)
            master_clock.start()
            self._clock_patches.append(master_clock)
            master = master_agent.MasterAgent()
            include_ids = [extra_args[i + 1] for i, a in enumerate(extra_args)
                           if a == "--include" and i + 1 < len(extra_args)]
            master.run(include_ids=include_ids or None)
            return master

    def test_full_run_scores_vary_and_state_persists(self):
        self._run_master()

        with open("reports/aggregate.json") as f:
            aggregate = json.load(f)
        projects = {p["id"]: p for p in aggregate["projects"]}
        self.assertEqual(len(projects), 2)
        self.assertNotIn("navadhiti/dormant-service", projects)
        self.assertEqual(projects["navadhiti/service-a"]["score"], 90.0)
        self.assertEqual(projects["navadhiti/service-b"]["score"], 0.0)

        # weight warning for unweighted traceability is surfaced
        self.assertTrue(any("traceability" in w.lower() for w in aggregate["weight_warnings"]))

        # dormant repo reported with reason
        self.assertEqual(len(aggregate["excluded_repos"]), 1)
        self.assertIn("dormant", aggregate["excluded_repos"][0]["reason"])

        # per-repo detail report
        with open("reports/navadhiti_service-a.json") as f:
            report = json.load(f)
        self.assertEqual(report["dimensions"]["environment_separation"]["status"], "pass")
        self.assertEqual(report["dimensions"]["ci_cd_gates"]["status"], "pass")
        self.assertEqual(report["dimensions"]["uat_signoff"]["status"], "pass")
        self.assertEqual(report["dimensions"]["uat_signoff"]["method"], "repo_artifact")
        self.assertEqual(report["dimensions"]["security_baseline"]["status"], "pass")
        self.assertEqual(report["dimensions"]["deployment_history"]["status"], "pass")
        self.assertFalse(report["dimensions"]["deployment_history"]["gap_flag"])
        self.assertEqual(report["dimensions"]["traceability"]["feature_to_issue"]["status"], "pass")
        self.assertEqual(
            report["dimensions"]["traceability"]["feature_to_issue"]["unlinked_count"], 0)
        self.assertEqual(
            report["dimensions"]["traceability"]["issue_to_ticket"]["status"],
            "undefined_standard")

        # promotion state: streak 1 after first qualifying run
        state = load_state("reports/promotion_state.json")
        entry = state["repos"]["navadhiti/service-a"]
        self.assertEqual(entry["qualifying_streak"], 1)
        self.assertEqual(entry["last_sprint_id"], CURRENT_SPRINT_ID)
        self.assertFalse(entry["enforcement_eligible"])  # threshold is 3

        # second run in the same sprint: idempotent streak; history keeps
        # one snapshot per run (more than one after two runs)
        self._run_master()
        state = load_state("reports/promotion_state.json")
        self.assertEqual(state["repos"]["navadhiti/service-a"]["qualifying_streak"], 1)
        history = sorted(os.listdir("reports/history"))
        self.assertEqual(len(history), 2)
        self.assertTrue(all(f.endswith("-aggregate.json") for f in history))
        # each archived snapshot is a valid, distinct aggregate
        with open(f"reports/history/{history[0]}") as f:
            first_archived = json.load(f)
        self.assertIn("projects", first_archived)
        self.assertNotEqual(history[0], history[1])

        # third+fourth runs advance into new sprints via forced state
        from core.promotion import update_streak
        update_streak(state, "navadhiti/service-a", "sprint-2026-09-07", True, 3)
        entry = update_streak(state, "navadhiti/service-a", "sprint-2026-09-21", True, 3)
        self.assertTrue(entry["enforcement_eligible"])

    def test_include_flag_overrides_activity_window(self):
        self._run_master(extra_args=["--include", "navadhiti/dormant-service"])
        with open("reports/aggregate.json") as f:
            aggregate = json.load(f)
        ids = [p["id"] for p in aggregate["projects"]]
        self.assertIn("navadhiti/dormant-service", ids)

    def test_weight_validation_fails_loudly(self):
        with open("config/master.yaml") as f:
            content = f.read()
        with open("config/master.yaml", "w") as f:
            f.write(content.replace("security_baseline: 0.2", "security_baseline: 0.3"))
        with self.assertRaises(SystemExit) as ctx:
            self._run_master()
        self.assertIn("sum to", str(ctx.exception))

    def test_missing_token_fails_loudly(self):
        os.environ.pop("GIT_TOKEN")
        with self.assertRaises(SystemExit) as ctx:
            self._run_master()
        self.assertIn("GIT_TOKEN", str(ctx.exception))


# ---------------------------------------------------------------------------
# Enforcer (C4)
# ---------------------------------------------------------------------------

class EnforcerTests(MasterEndToEndTests):
    def test_enforcer_existing_project_ignores_traceability_gate(self):
        self._run_master()  # ensure nothing explodes; enforcer re-runs everything
        # service-a is created 2025-01-01, before the 2026-09-01 cutoff:
        # even a traceability fail would not block it.
        self.fake.pulls["navadhiti/service-a"] = [
            {"number": 15, "title": "no link here", "body": None,
             "merged_at": (NOW - DAY).isoformat() + "Z",
             "updated_at": (NOW - DAY).isoformat() + "Z",
             "base": {"ref": "main"}, "merge_commit_sha": "m2"},
        ]
        agent = EnforcerAgent("navadhiti/service-a", "https://github.com/navadhiti/service-a")
        with patch("requests.Session.request") as mock_request:
            fake = self.fake
            mock_request.side_effect = lambda method, url, **kw: fake.route(method, url, **kw)
            code = agent.run()
        self.assertEqual(code, 0)

    def test_enforcer_new_project_blocked_by_unlinked_pr(self):
        # service-b created 2026-09-02 (after cutoff) — new project.
        self.fake.trees["navadhiti/service-b"] = [
            "README.md",
            "terraform/workspaces/prod.tf",
            ".github/dependabot.yml",
            f"docs/signoffs/{CURRENT_SPRINT_ID}.md",
        ]
        self.fake.files[f"navadhiti/service-b:docs/signoffs/{CURRENT_SPRINT_ID}.md"] = (
            f"# UAT Signoff\n\nsprint_id: {CURRENT_SPRINT_ID}\n"
            "reviewer: Jane Doe\ndate: 2026-09-04\n"
        )
        self.fake.protection["navadhiti/service-b"] = {
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_status_checks": {"contexts": ["ci"]},
        }
        self.fake.pulls["navadhiti/service-b"] = [
            {"number": 21, "title": "unlinked work", "body": None,
             "merged_at": (NOW - DAY).isoformat() + "Z",
             "updated_at": (NOW - DAY).isoformat() + "Z",
             "base": {"ref": "main"}, "merge_commit_sha": "m9"},
        ]
        self.fake.commits["m9"] = "unlinked work (#21)"
        self.fake.releases["navadhiti/service-b"] = [{
            "draft": False, "prerelease": False,
            "published_at": (NOW - DAY).isoformat() + "Z",
        }]

        agent = EnforcerAgent("navadhiti/service-b", "https://github.com/navadhiti/service-b")
        with patch("requests.Session.request") as mock_request:
            fake = self.fake
            mock_request.side_effect = lambda method, url, **kw: fake.route(method, url, **kw)
            code = agent.run()
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
