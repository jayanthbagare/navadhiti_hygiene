"""Tests for tools/verify_baseline.py — the repository's own baseline verifier.

These tests build throwaway git repositories and run the verifier against
them as a subprocess, because the exit-code contract is part of the tool's
public surface: a caller trusts 0, distinguishes "the repository is wrong"
from "I could not look" without parsing prose, and must never see a broken
verifier reported as a healthy repository.

The denied identifiers are never written out literally here — not even in a
fixture. They are read from the verifier's own module-level denylist, for the
same reason the denylist is base64-encoded inside the verifier: this file is
tracked content that the verifier scans, so a plaintext identifier anywhere in
it would make the check fail against its own test suite.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
VERIFIER_PATH = REPO_ROOT / "tools" / "verify_baseline.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_baseline", VERIFIER_PATH)
    module = importlib.util.module_from_spec(spec)
    # Registered before exec: @dataclass resolves the defining module through
    # sys.modules, and an unregistered module has no entry to look up.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verify_baseline = _load_verifier()

DENIED_IDENTIFIER = verify_baseline.DENIED_IDENTIFIERS[0]
SECOND_DENIED_IDENTIFIER = verify_baseline.DENIED_IDENTIFIERS[1]
PLACEHOLDER_MAILBOX = "signoffs@example.com"

# A token-shaped string. Never a real credential: the shape is what matters,
# and a real one must never be typed into this file.
FAKE_TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"

COMPLETE_RECORD = """# Confidentiality and Data-Handling Decision

## Decision
The repository remains public under a no-real-data policy.

## Date
2026-10-05

## Accountable Owner
Role, not yet a named individual.

## Rationale
Public with a written policy, rather than private, which was rejected because
no external reviewer would have access.

## What This Repository Must Never Contain
- live run output
- real project names with budgets
- real headcount and salary-derived rates
- live credential or token values
- internal correspondence

## Accepted Exposures

| Identifier | Category | Rationale |
| :--- | :--- | :--- |

An empty table means nothing is deliberately exposed. It is still required:
a missing section and an empty section are different statements.

## Revisit Triggers
- any accepted exposure is added
- a real identifier is found in history

## Related
- README.md
"""

DEPENDABOT_YAML = """version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
"""

PRE_COMMIT_YAML = """repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
        files: ^config/.*\\.ya?ml$
"""

PROJECTS_YAML = """# Sample metadata only. Budgets below are commented out on purpose.
repos:
  # "navadhiti/web-frontend":
  #   timesheet_code: "WEB-UI-01"
  #   budget: 150000.0
  #   headcount: 5
"""

PASSING_TEST = """def test_fixture_is_green():
    assert True
"""


class FixtureRepo:
    """A throwaway git repository holding a configurable set of files.

    A `None` value means "this path must not exist", which is how the
    absence cases are expressed — layering a healthy baseline over a fixture
    cannot delete a file.
    """

    def __init__(self, files=None, commit=True):
        self.path = Path(tempfile.mkdtemp(prefix="nh-baseline-"))
        self.files = dict(files or {})
        self.commit = commit
        self._build()

    def _build(self):
        files = dict(self.files)
        # The verifier resolves the repository root from its own location, so
        # it must sit at <repo>/tools/verify_baseline.py in the fixture too.
        (self.path / "tools").mkdir(parents=True, exist_ok=True)
        shutil.copy2(VERIFIER_PATH, self.path / "tools" / "verify_baseline.py")

        for relative, content in files.items():
            if content is None:
                continue
            target = self.path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        env = dict(os.environ)
        env.update({
            "GIT_AUTHOR_NAME": "fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.com",
            "GIT_COMMITTER_NAME": "fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.com",
        })
        self._git("init", "-q", "-b", "main", env=env)
        self._git("add", "-A", env=env)
        if self.commit:
            self._git("commit", "-q", "-m", "fixture", env=env)

    def _git(self, *args, env=None):
        proc = subprocess.run(
            ["git", "-C", str(self.path), *args],
            capture_output=True, text=True, env=env,
        )
        if proc.returncode != 0:
            raise AssertionError(f"git {args} failed: {proc.stderr}")

    def run_verifier(self):
        return subprocess.run(
            [sys.executable, str(self.path / "tools" / "verify_baseline.py")],
            capture_output=True, text=True, cwd=str(self.path),
        )

    def cleanup(self):
        shutil.rmtree(self.path, ignore_errors=True)


def healthy_files(**overrides):
    """The smallest file set that satisfies all seven criteria."""
    files = {
        "README.md": (
            "# Fixture\n\nSee [CONFIDENTIALITY.md](CONFIDENTIALITY.md).\n"
        ),
        "NOTICE": "Navadhiti internal-use notice. Restricted internal use.\n",
        ".github/dependabot.yml": DEPENDABOT_YAML,
        ".pre-commit-config.yaml": PRE_COMMIT_YAML,
        ".secrets.baseline": "{}\n",
        "CONFIDENTIALITY.md": COMPLETE_RECORD,
        "config/projects.yaml": PROJECTS_YAML,
        "config/standard.yaml": "version: 1\n",
        "tests/test_fixture.py": PASSING_TEST,
    }
    files.update(overrides)
    return files


class VerifierFixture(unittest.TestCase):
    def setUp(self):
        self.repos = []

    def tearDown(self):
        for repo in self.repos:
            repo.cleanup()

    def make_repo(self, **kwargs):
        repo = FixtureRepo(**kwargs)
        self.repos.append(repo)
        return repo

    def check(self, criterion, files=None, replace=False):
        """Run one criterion against a fixture repository.

        `files` layers over the healthy baseline. Pass replace=True to supply
        the complete file set instead — needed when the point of the test is
        that something is *absent*, since layering cannot delete a file.
        """
        files = dict(files or {})
        if not replace:
            files = healthy_files(**files)
        repo = self.make_repo(files=files)
        return criterion(verify_baseline.Repository(repo.path))

    def criterion_line(self, proc, criterion_id):
        for line in proc.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith(("pass", "fail", "unverifiable")) and \
                    criterion_id in stripped:
                return stripped
        self.fail(f"no line for criterion {criterion_id!r} in:\n{proc.stdout}")


# ---------------------------------------------------------------------------
# T008 — the exit-code contract
# ---------------------------------------------------------------------------

class ExitCodeTests(VerifierFixture):
    def test_healthy_repository_exits_zero(self):
        repo = self.make_repo(files=healthy_files())
        proc = repo.run_verifier()
        self.assertEqual(
            proc.returncode, 0,
            f"a repository meeting every criterion must exit 0:\n{proc.stdout}")
        self.assertIn("verdict: PASS (7 of 7 criteria passed)", proc.stdout)
        self.assertIn(verify_baseline.DISCLAIMER, proc.stdout)

    def test_non_compliant_repository_exits_one(self):
        repo = self.make_repo(files=healthy_files())
        with repo.path.joinpath("NOTICE").open("w") as handle:
            handle.write("")
        subprocess.run(["git", "-C", str(repo.path), "add", "-A"],
                       capture_output=True, check=True)
        subprocess.run(["git", "-C", str(repo.path), "commit", "-q", "-m", "x"],
                       capture_output=True, check=True)
        proc = repo.run_verifier()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("verdict: FAIL (1 of 7 criteria failed)", proc.stdout)
        self.assertIn(verify_baseline.DISCLAIMER, proc.stdout)

    def test_verifier_outside_a_repository_exits_two(self):
        # Not 0, not 1: "I could not look" is a different statement from
        # "it is fine", and a broken verifier must never read as healthy.
        stray = Path(tempfile.mkdtemp(prefix="nh-stray-"))
        self.addCleanup(shutil.rmtree, stray, True)
        (stray / "tools").mkdir()
        shutil.copy2(VERIFIER_PATH, stray / "tools" / "verify_baseline.py")
        proc = subprocess.run(
            [sys.executable, str(stray / "tools" / "verify_baseline.py")],
            capture_output=True, text=True, cwd=str(stray),
        )
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertNotIn("verdict:", proc.stdout)
        self.assertIn("could not run", proc.stderr)

    def test_arguments_are_refused_so_local_and_ci_cannot_diverge(self):
        repo = self.make_repo(files=healthy_files())
        proc = subprocess.run(
            [sys.executable, str(repo.path / "tools" / "verify_baseline.py"),
             "--quiet"],
            capture_output=True, text=True, cwd=str(repo.path),
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("takes no arguments", proc.stderr)

    def test_verdict_fails_the_run_when_a_criterion_is_unverifiable(self):
        # An unverifiable criterion is not a passing one. Verified through the
        # registry rather than by provoking a genuinely unevaluable repository
        # state, which is not reachable without breaking the verifier itself.
        registry = [
            verify_baseline._criterion(
                "one", "one", ("FR-001",),
                lambda repo: verify_baseline.CriterionResult(
                    "one", "pass", "fine")),
            verify_baseline._criterion(
                "two", "two", ("FR-002",),
                lambda repo: verify_baseline.CriterionResult(
                    "two", "unverifiable", "the runner was not installed")),
        ]

        class _StubRepo:
            def tracked_files(self_inner):
                return ()

            def commit_sha(self_inner):
                return None

        report = verify_baseline.evaluate(_StubRepo(), registry)
        self.assertEqual(report.verdict, "fail")
        self.assertEqual(report.failed, 1)


class VerdictRuleTests(unittest.TestCase):
    def test_any_unverifiable_result_fails_the_run(self):
        class _StubRepo:
            def tracked_files(self):
                return ()

            def commit_sha(self):
                return None

        registry = [
            verify_baseline._criterion(
                "one", "one", ("FR-001",),
                lambda repo: verify_baseline.CriterionResult(
                    "one", "pass", "fine")),
            verify_baseline._criterion(
                "two", "two", ("FR-002",),
                lambda repo: verify_baseline.CriterionResult(
                    "two", "unverifiable", "the runner was not installed")),
        ]
        report = verify_baseline.evaluate(_StubRepo(), registry)
        self.assertEqual(report.verdict, "fail")
        self.assertEqual(report.failed, 1)
        self.assertIn("FAIL (1 of 2 criteria failed)",
                      verify_baseline.format_report(report))
        self.assertFalse(report.blocking)

    def test_duplicate_criterion_ids_are_rejected_at_startup(self):
        criterion = verify_baseline._criterion(
            "dup", "dup", ("FR-001",),
            lambda repo: verify_baseline.CriterionResult("dup", "pass", "fine"))
        with self.assertRaises(verify_baseline.VerifierCannotStart):
            verify_baseline._validated_registry([criterion, criterion])

    def test_a_criterion_tracing_to_no_requirement_is_rejected(self):
        with self.assertRaises(verify_baseline.VerifierCannotStart):
            verify_baseline.Criterion(
                id="nope", label="nope", requirements=(),
                determination="observed", cannot_determine_action="fail",
                check=lambda repo: None,
            )

    def test_a_criterion_whose_determination_is_undecided_is_rejected(self):
        with self.assertRaises(verify_baseline.VerifierCannotStart):
            verify_baseline.Criterion(
                id="undecided", label="undecided", requirements=("FR-001",),
                determination="assumed", cannot_determine_action="fail",
                check=lambda repo: None,
            )

    def test_a_non_kebab_case_id_is_rejected(self):
        with self.assertRaises(verify_baseline.VerifierCannotStart):
            verify_baseline.Criterion(
                id="Not_Kebab", label="x", requirements=("FR-001",),
                determination="observed", cannot_determine_action="fail",
                check=lambda repo: None,
            )


class NoSecretLeakageTests(VerifierFixture):
    def test_output_never_contains_a_denied_identifier(self):
        repo = self.make_repo(files=healthy_files(
            **{"config/integrations.yaml": (
                f'mailbox: "{DENIED_IDENTIFIER}"\n')},
        ))
        proc = repo.run_verifier()
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn(DENIED_IDENTIFIER, proc.stdout)
        self.assertNotIn(DENIED_IDENTIFIER, proc.stderr)
        # What it reports instead: a path, a line number, and a shape.
        self.assertIn("config/integrations.yaml:1", proc.stdout)
        self.assertIn("denied identifier", proc.stdout)

    def test_output_never_contains_a_token_shaped_string(self):
        repo = self.make_repo(files=healthy_files(
            **{"config/integrations.yaml": f'api_token: "{FAKE_TOKEN}"\n'},
        ))
        proc = repo.run_verifier()
        self.assertNotIn(FAKE_TOKEN, proc.stdout)
        self.assertNotIn(FAKE_TOKEN[:20], proc.stdout)
        self.assertNotIn(FAKE_TOKEN[20:40], proc.stdout)

    def test_a_second_denied_identifier_is_also_withheld(self):
        repo = self.make_repo(files=healthy_files(
            **{"config/integrations.yaml": (
                f'api_url: "https://{SECOND_DENIED_IDENTIFIER}/rest"\n')},
        ))
        proc = repo.run_verifier()
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn(SECOND_DENIED_IDENTIFIER, proc.stdout)
        self.assertIn("config/integrations.yaml:1", proc.stdout)

    def test_the_verifier_source_contains_no_denylist_identifier_in_plaintext(self):
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        for identifier in verify_baseline.DENIED_IDENTIFIERS:
            self.assertNotIn(
                identifier, source,
                "the denylist must stay encoded, or the check matches its own "
                "source and can never pass")

    def test_stale_exposure_is_reported_by_position_not_by_value(self):
        record = COMPLETE_RECORD.replace(
            "| :--- | :--- | :--- |\n",
            "| :--- | :--- | :--- |\n"
            "| `a-name-that-no-longer-exists` | Organisation name | "
            "Already gone; the record was not updated. |\n",
        )
        repo = self.make_repo(files=healthy_files(
            **{"CONFIDENTIALITY.md": record}))
        proc = repo.run_verifier()
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("a-name-that-no-longer-exists", proc.stdout)
        self.assertIn("accepted exposure #1 is stale", proc.stdout)

    def test_a_current_exposure_passes_and_is_not_reported_stale(self):
        record = COMPLETE_RECORD.replace(
            "| :--- | :--- | :--- |\n",
            "| :--- | :--- | :--- |\n"
            "| `navadhiti` | Organisation name | Already public via the "
            "repository address. |\n",
        )
        repo = self.make_repo(files=healthy_files(
            **{"CONFIDENTIALITY.md": record,
               "config/integrations.yaml": 'org: "navadhiti"\n'}))
        proc = repo.run_verifier()
        self.assertIn("pass         no-real-data", proc.stdout)
        self.assertNotIn("stale", proc.stdout)

    def test_an_empty_exposure_table_is_complete_not_missing(self):
        repo = self.make_repo(files=healthy_files())
        proc = repo.run_verifier()
        self.assertIn("pass         confidentiality-record", proc.stdout)
        self.assertNotIn("stale", proc.stdout)


class NoEnvTrackedTests(VerifierFixture):
    def test_a_tracked_environment_file_fails_and_is_named(self):
        repo = self.make_repo(files=healthy_files(
            **{"venv/bin/python": "#!/bin/sh\n"}))
        result = verify_baseline.check_no_env_tracked(
            verify_baseline.Repository(repo.path))
        self.assertEqual(result.status, "fail")
        self.assertIn("venv/bin/python", result.evidence)
        self.assertEqual(result.observed["found"], 1)

    def test_removing_the_environment_from_tracking_passes(self):
        repo = self.make_repo(files=healthy_files(
            **{"venv/bin/python": "#!/bin/sh\n"}))
        self.assertEqual(
            verify_baseline.check_no_env_tracked(
                verify_baseline.Repository(repo.path)).status, "fail")

        # The directory stays on disk — that is the point of untracking — and
        # only stops being tracked. Tracked and ignored are independent.
        subprocess.run(["git", "-C", str(repo.path), "rm", "-r", "--cached",
                        "-q", "venv"], capture_output=True, check=True)
        subprocess.run(["git", "-C", str(repo.path), "commit", "-q", "-m",
                        "untrack"], capture_output=True, check=True)
        self.assertTrue((repo.path / "venv" / "bin" / "python").exists())

        result = verify_baseline.check_no_env_tracked(
            verify_baseline.Repository(repo.path))
        self.assertEqual(result.status, "pass")
        self.assertIn("0 found", result.detail)

    def test_every_common_environment_directory_is_caught(self):
        repo = self.make_repo(files=healthy_files(**{
            ".venv/pyvenv.cfg": "\n",
            "env/lib/x.py": "\n",
            ".tox/py311/log/x": "\n",
        }))
        result = verify_baseline.check_no_env_tracked(
            verify_baseline.Repository(repo.path))
        self.assertEqual(result.status, "fail")
        self.assertEqual(result.observed["found"], 3)

    def test_a_path_that_merely_mentions_venv_is_not_an_environment_file(self):
        repo = self.make_repo(files=healthy_files(
            **{"tools/venv_report.py": "\n", "docs/notes.txt": "venv/\n"}))
        result = verify_baseline.check_no_env_tracked(
            verify_baseline.Repository(repo.path))
        self.assertEqual(result.status, "pass")

    def test_the_real_repository_tracks_no_environment_files(self):
        result = verify_baseline.check_no_env_tracked(
            verify_baseline.Repository(REPO_ROOT))
        self.assertEqual(result.status, "pass", result.detail)


class LicensingArtifactTests(VerifierFixture):
    def test_a_missing_notice_fails(self):
        result = self.check(verify_baseline.check_licensing_artifact,
                            {"NOTICE": None}, replace=True)
        self.assertEqual(result.status, "fail")
        self.assertIn("is absent", result.detail)

    def test_an_empty_notice_fails(self):
        result = self.check(verify_baseline.check_licensing_artifact,
                            {"NOTICE": "   \n"})
        self.assertEqual(result.status, "fail")

    def test_a_populated_internal_use_notice_passes(self):
        result = self.check(verify_baseline.check_licensing_artifact, {})
        self.assertEqual(result.status, "pass")
        self.assertIn("NOTICE", result.evidence)


class DependencyScanningTests(VerifierFixture):
    def test_a_missing_dependabot_config_fails(self):
        result = self.check(verify_baseline.check_dependency_scanning,
                            {"README.md": "# Fixture\n"}, replace=True)
        self.assertEqual(result.status, "fail")
        self.assertIn(".github/dependabot.yml", result.detail)

    def test_a_config_without_the_pip_ecosystem_fails(self):
        result = self.check(verify_baseline.check_dependency_scanning, {
            ".github/dependabot.yml":
                'version: 2\nupdates:\n  - package-ecosystem: "npm"\n'
                '    directory: "/"\n',
        })
        self.assertEqual(result.status, "fail")
        self.assertIn("'pip'", result.detail)

    def test_a_config_with_no_ecosystem_at_all_fails(self):
        result = self.check(verify_baseline.check_dependency_scanning, {
            ".github/dependabot.yml": "version: 2\nupdates: []\n",
        })
        self.assertEqual(result.status, "fail")
        self.assertIn("no update ecosystem", result.detail)

    def test_invalid_yaml_fails_rather_than_being_skipped(self):
        result = self.check(verify_baseline.check_dependency_scanning, {
            ".github/dependabot.yml": "version: 2\nupdates:\n  - [unclosed\n",
        })
        self.assertEqual(result.status, "fail")
        self.assertIn("not valid YAML", result.detail)

    def test_a_valid_config_passes_but_never_claims_to_be_active(self):
        result = self.check(verify_baseline.check_dependency_scanning, {})
        self.assertEqual(result.status, "pass")
        self.assertIn("configured for pip", result.detail)
        self.assertIn("activation not verifiable from the repository",
                      result.detail)
        self.assertNotIn("active", result.detail)
        self.assertEqual(result.observed["activation"], "not_verifiable")

    def test_the_repository_ships_a_pip_scanner(self):
        text = (REPO_ROOT / ".github" / "dependabot.yml").read_text()
        data = yaml.safe_load(text)
        self.assertEqual(data["version"], 2)
        ecosystems = [u["package-ecosystem"] for u in data["updates"]]
        self.assertIn("pip", ecosystems)
        self.assertEqual(
            [u["directory"] for u in data["updates"]], ["/"],
            "requirements.txt is one flat file at the root; a second directory "
            "entry would create two sources of truth")


class SecretGuardTests(VerifierFixture):
    def test_a_missing_pre_commit_config_fails(self):
        result = self.check(verify_baseline.check_secret_guard,
                            {"README.md": "# Fixture\n"}, replace=True)
        self.assertEqual(result.status, "fail")
        self.assertIn("nothing runs at commit time", result.detail)

    def test_a_config_without_a_secret_detector_fails(self):
        result = self.check(verify_baseline.check_secret_guard, {
            ".pre-commit-config.yaml": PRE_COMMIT_YAML.replace(
                "detect-secrets", "trailing-whitespace"),
        })
        self.assertEqual(result.status, "fail")
        self.assertIn("no detect-secrets hook", result.detail)

    def test_a_secret_hook_that_is_not_scoped_to_config_files_fails(self):
        result = self.check(verify_baseline.check_secret_guard, {
            ".pre-commit-config.yaml": PRE_COMMIT_YAML.replace(
                r"files: ^config/.*\.ya?ml$", "files: ^docs/"),
        })
        self.assertEqual(result.status, "fail")
        self.assertIn("files scope does not cover", result.detail)

    def test_a_secret_hook_with_no_files_filter_fails(self):
        result = self.check(verify_baseline.check_secret_guard, {
            ".pre-commit-config.yaml": PRE_COMMIT_YAML.replace(
                r"files: ^config/.*\.ya?ml$", "exclude: __never__"),
        })
        self.assertEqual(result.status, "fail")

    def test_a_hook_that_ignores_the_reviewed_baseline_fails(self):
        result = self.check(verify_baseline.check_secret_guard, {
            ".pre-commit-config.yaml": PRE_COMMIT_YAML.replace(
                "args: ['--baseline', '.secrets.baseline']",
                "args: ['--no-verify']"),
        })
        self.assertEqual(result.status, "fail")
        self.assertIn(".secrets.baseline", result.detail)

    def test_a_scoped_hook_with_a_reviewed_baseline_passes(self):
        result = self.check(verify_baseline.check_secret_guard, {})
        self.assertEqual(result.status, "pass")
        self.assertIn("config/*.yaml", result.detail)
        self.assertIn(".secrets.baseline", result.detail)


class TestSuiteCriterionTests(VerifierFixture):
    def test_a_green_suite_passes_and_reports_the_count(self):
        result = self.check(verify_baseline.check_test_suite, {})
        self.assertEqual(result.status, "pass")
        self.assertIn("tests passed via pytest", result.detail)

    def test_a_failing_suite_is_a_failure(self):
        result = self.check(verify_baseline.check_test_suite, {
            "tests/test_fixture.py": "def test_broken():\n    assert False\n",
        })
        self.assertEqual(result.status, "fail")
        self.assertIn("1 failed", result.detail)

    def test_a_suite_with_no_tests_is_a_failure_not_a_silent_pass(self):
        result = self.check(verify_baseline.check_test_suite,
                            {"README.md": "# Fixture\n"}, replace=True)
        self.assertEqual(result.status, "fail")

    def test_a_missing_runner_is_reported_by_name_and_is_a_distinct_failure(self):
        original = verify_baseline.TEST_RUNNER
        try:
            verify_baseline.TEST_RUNNER = "a-runner-that-does-not-exist"
            result = verify_baseline.check_test_suite(
                verify_baseline.Repository(REPO_ROOT))
        finally:
            verify_baseline.TEST_RUNNER = original
        self.assertEqual(result.status, "fail")
        self.assertIn("a-runner-that-does-not-exist", result.detail)
        self.assertIn("not installed", result.detail)
        self.assertFalse(result.observed["installed"])


class ConfidentialityRecordTests(VerifierFixture):
    def test_a_missing_record_fails(self):
        result = self.check(verify_baseline.check_confidentiality_record,
                            {"README.md": "# Fixture\n"}, replace=True)
        self.assertEqual(result.status, "fail")
        self.assertIn("not recorded", result.detail)

    def test_every_required_section_heading_is_required(self):
        for section in verify_baseline.REQUIRED_RECORD_SECTIONS:
            record = COMPLETE_RECORD.replace(f"## {section}\n", "")
            result = self.check(verify_baseline.check_confidentiality_record,
                                {"CONFIDENTIALITY.md": record})
            self.assertEqual(result.status, "fail",
                             f"a record without '## {section}' must fail")
            self.assertIn("required sections", result.detail)
            self.assertIn(section, str(result.observed["missing"]))

    def test_a_record_missing_from_the_readme_is_not_findable(self):
        result = self.check(verify_baseline.check_confidentiality_record,
                            {"README.md": "# Fixture\n\nNo link here.\n"})
        self.assertEqual(result.status, "fail")
        self.assertIn("never links to it", result.detail)

    def test_a_complete_and_linked_record_passes(self):
        result = self.check(verify_baseline.check_confidentiality_record, {})
        self.assertEqual(result.status, "pass")
        self.assertIn("linked from README.md", result.detail)

    def test_the_verifier_never_judges_the_record_s_content(self):
        # Same headings, deliberately careless prose, same verdict. The
        # criterion checks presence and completeness; whether the reasoning is
        # good is a human act, and automating that judgement is the failure
        # mode this design exists to avoid.
        flippant = COMPLETE_RECORD.replace(
            "The repository remains public under a no-real-data policy.",
            "Whatever, it is public.")
        result = self.check(verify_baseline.check_confidentiality_record,
                            {"CONFIDENTIALITY.md": flippant})
        self.assertEqual(result.status, "pass")


class NoRealDataTests(VerifierFixture):
    def test_a_compliant_repository_passes(self):
        self.assertEqual(
            self.check(verify_baseline.check_no_real_data, {}).status, "pass")

    def test_a_placeholder_looking_like_a_mailbox_is_not_a_violation(self):
        result = self.check(verify_baseline.check_no_real_data, {
            "config/integrations.yaml": f'mailbox: "{PLACEHOLDER_MAILBOX}"\n',
        })
        self.assertEqual(result.status, "pass")

    def test_commented_budget_entries_pass(self):
        result = self.check(verify_baseline.check_no_real_data, {
            "config/projects.yaml": PROJECTS_YAML,
        })
        self.assertEqual(result.status, "pass")
        self.assertIn("budget", result.detail + str(PROJECTS_YAML))

    def test_an_uncommented_budget_under_repos_fails_and_names_the_line(self):
        result = self.check(verify_baseline.check_no_real_data, {
            "config/projects.yaml": PROJECTS_YAML + (
                '  "navadhiti/service-a":\n    budget: 150000.0\n'),
        })
        self.assertEqual(result.status, "fail")
        self.assertTrue(
            any(e.startswith("config/projects.yaml:") and e.endswith("budget")
                for e in result.evidence), result.evidence)

    def test_uncommented_headcount_and_timesheet_code_both_fail(self):
        for key in ("headcount", "timesheet_code"):
            result = self.check(verify_baseline.check_no_real_data, {
                "config/projects.yaml": PROJECTS_YAML + (
                    f'  "navadhiti/service-a":\n    {key}: 5\n'),
            })
            self.assertEqual(result.status, "fail", f"{key} must fail")
            self.assertTrue(any(e.endswith(key) for e in result.evidence))

    def test_a_tracked_file_under_reports_fails(self):
        repo = self.make_repo(files=healthy_files())
        report = repo.path / "reports" / "aggregate.json"
        report.parent.mkdir(exist_ok=True)
        report.write_text("{}\n")
        subprocess.run(["git", "-C", str(repo.path), "add", "-A"],
                       capture_output=True, check=True)
        subprocess.run(["git", "-C", str(repo.path), "commit", "-q", "-m", "x"],
                       capture_output=True, check=True)
        result = verify_baseline.check_no_real_data(
            verify_baseline.Repository(repo.path))
        self.assertEqual(result.status, "fail")
        self.assertIn("reports/aggregate.json  generated run output is tracked",
                      result.evidence)

    def test_a_denied_identifier_is_caught_by_content_not_by_directory(self):
        # A denied identifier in a file the scanner would otherwise treat as
        # documentation is still a violation.
        result = self.check(verify_baseline.check_no_real_data, {
            "docs/notes.md": f"Contact {DENIED_IDENTIFIER} for access.\n",
        })
        self.assertEqual(result.status, "fail")


class GeneratedOutputTests(VerifierFixture):
    """FR-025 — reports/ is excluded from tracking, and still written at runtime."""

    def test_reports_is_ignored_in_this_repository(self):
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "check-ignore", "-v", "--no-index",
             "reports/", "reports/aggregate.json", "reports/history/x.json"],
            capture_output=True, text=True, check=True)
        self.assertEqual(proc.stdout.count(".gitignore:"), 3, proc.stdout)

    def test_no_report_output_is_tracked(self):
        tracked = verify_baseline.Repository(REPO_ROOT).tracked_files()
        offenders = [p for p in tracked if p.split("/")[0] == "reports"]
        self.assertEqual(offenders, [])

    def test_a_run_still_writes_reports_even_though_they_are_ignored(self):
        # The exclusion is a version-control rule, not a filesystem one. This
        # drives the real write path with no network, and asserts the directory
        # tree the documented run produces actually appears.
        sys.path.insert(0, str(REPO_ROOT))
        self.addCleanup(sys.path.remove, str(REPO_ROOT))
        import master_agent

        sandbox = Path(tempfile.mkdtemp(prefix="nh-reports-"))
        self.addCleanup(shutil.rmtree, sandbox, True)
        shutil.copytree(REPO_ROOT / "config", sandbox / "config")
        previous = os.getcwd()
        os.chdir(sandbox)
        try:
            master = master_agent.MasterAgent()
            master.generate_aggregate_report([], [], [])
        finally:
            os.chdir(previous)

        self.assertTrue((sandbox / "reports").is_dir())
        self.assertTrue((sandbox / "reports" / "aggregate.json").is_file())
        history = list((sandbox / "reports" / "history").glob("*-aggregate.json"))
        self.assertEqual(len(history), 1, history)


class ReadOnlyTests(VerifierFixture):
    def test_a_run_writes_nothing_and_changes_no_tracked_file(self):
        repo = self.make_repo(files=healthy_files())
        before = subprocess.run(
            ["git", "-C", str(repo.path), "status", "--porcelain"],
            capture_output=True, text=True, check=True).stdout
        listing_before = sorted(p.name for p in repo.path.iterdir())
        repo.run_verifier()
        after = subprocess.run(
            ["git", "-C", str(repo.path), "status", "--porcelain"],
            capture_output=True, text=True, check=True).stdout
        listing_after = sorted(p.name for p in repo.path.iterdir())
        self.assertEqual(before, after, "the verifier must not modify the repository")
        self.assertEqual(listing_before, listing_after,
                         "the verifier must not create files")

    def test_two_runs_against_one_commit_are_identical(self):
        repo = self.make_repo(files=healthy_files())
        first = repo.run_verifier()
        second = repo.run_verifier()
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first.returncode, second.returncode)

    def test_the_commit_sha_is_printed_when_there_is_one(self):
        repo = self.make_repo(files=healthy_files())
        sha = subprocess.run(
            ["git", "-C", str(repo.path), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
        self.assertIn(f"commit: {sha}", repo.run_verifier().stdout)


if __name__ == "__main__":
    unittest.main()