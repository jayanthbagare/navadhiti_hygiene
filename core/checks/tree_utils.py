"""
Shared tree-path pattern matching for file-presence checks.

`config/standard.yaml` expresses artifacts as glob-ish path patterns
(e.g. "terraform/workspaces", ".github/dependabot.yml",
"docker-compose.*.yml"). A pattern matches a repo file tree if:

- fnmatch matches the full path (glob semantics), OR
- the pattern names a directory prefix: some path lives under
  "pattern/" (so "terraform/workspaces" matches both a file at that
  exact path and anything nested inside it).

The recursive tree is fetched once per repo via GitHubClient's cache —
the environment and security checks share the same round-trip.
"""

from fnmatch import fnmatch
from typing import List

from core.github_client import GitHubClient


def path_matches_pattern(path: str, pattern: str) -> bool:
    pattern = pattern.strip().strip("/")
    if not pattern:
        return False
    if fnmatch(path, pattern):
        return True
    # Directory-prefix match: pattern denotes a directory in the tree.
    return path.startswith(pattern + "/")


def find_pattern_matches(paths: List[str], pattern: str) -> List[str]:
    return [p for p in paths if path_matches_pattern(p, pattern)]


def tree_paths_for_repo(github: GitHubClient, owner: str, repo: str, branch: str) -> List[str]:
    """All blob paths on the default branch; [] when tree is unavailable."""
    tree = github.get_tree(owner, repo, branch) or {}
    return [
        entry["path"] for entry in tree.get("tree", [])
        if entry.get("type") == "blob" and entry.get("path")
    ]
