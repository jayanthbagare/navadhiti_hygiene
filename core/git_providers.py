"""
Git provider abstraction for repository discovery.

`discover_repos(provider_config)` is the common interface the MasterAgent
calls; provider-specific implementations live behind it so GitLab / Azure
Repos can be added later without touching `master_agent.py`.

GitHub implementation (A1):
- Auth via GIT_TOKEN env var (per repo convention in config/integrations.yaml).
- Pagination via per_page=100 (orgs with >100 repos).
- last_commit_date comes from `pushed_at` (GitHub's last-push timestamp).
- A repo that fails API lookup is logged and excluded, never crashes the run.
- Archived repos are excluded as inactive (logged with reason).
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from core.github_client import GitHubApiError, GitHubClient, parse_github_timestamp

logger = logging.getLogger("hygiene.git_providers")


class RepoInfo(BaseModel):
    id: str                                  # "owner/repo"
    url: str = ""
    last_commit_date: Optional[datetime] = None
    default_branch: Optional[str] = None
    created_at: Optional[datetime] = None
    archived: bool = False


class GitProvider(ABC):
    """Common interface: return the full org-wide repo catalog."""

    @abstractmethod
    def discover_repos(self) -> List[RepoInfo]:
        ...


class GitHubProvider(GitProvider):
    def __init__(self, provider_config: dict):
        self.org = provider_config.get("org") or ""
        self.client = GitHubClient.from_config(provider_config)
        self.api_url = provider_config.get("api_url", "https://api.github.com")

    def discover_repos(self) -> List[RepoInfo]:
        if not self.org:
            raise ValueError(
                "git_provider.org is not set in config/integrations.yaml — "
                "cannot discover repositories."
            )
        if not self.client.authenticated:
            raise ValueError(
                "GIT_TOKEN environment variable is not set — cannot query the GitHub API. "
                "Set GIT_TOKEN to a PAT with repo read access."
            )
        repos: List[RepoInfo] = []
        try:
            raw_repos = self.client.list_org_repos(self.org)
        except GitHubApiError as exc:
            raise ValueError(f"GitHub repo discovery failed for org '{self.org}': {exc}") from exc

        for item in raw_repos:
            repo_id = item.get("full_name")
            if not repo_id:
                continue
            if item.get("archived"):
                logger.info("Excluding archived repo: %s", repo_id)
                continue
            repos.append(RepoInfo(
                id=repo_id,
                url=item.get("html_url") or f"https://github.com/{repo_id}",
                last_commit_date=parse_github_timestamp(item.get("pushed_at")),
                default_branch=item.get("default_branch"),
                created_at=parse_github_timestamp(item.get("created_at")),
                archived=False,
            ))
        return repos


PROVIDERS = {
    "github": GitHubProvider,
}


def get_provider(provider_config: dict) -> GitProvider:
    provider_type = (provider_config or {}).get("type", "github")
    provider_cls = PROVIDERS.get(provider_type)
    if provider_cls is None:
        raise ValueError(
            f"Unsupported git_provider.type '{provider_type}'. "
            f"Supported: {', '.join(PROVIDERS)}"
        )
    return provider_cls(provider_config)


def discover_repos(provider_config: dict) -> List[RepoInfo]:
    """Common entry point: discover all repos for the configured provider."""
    return get_provider(provider_config).discover_repos()
