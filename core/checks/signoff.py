from core.schema import UatSignoff

def check_uat_signoff(repo_id: str, repo_path: str, project_meta: dict) -> UatSignoff:
    return UatSignoff(
        status="unverifiable",
        method="none",
        evidence=["UAT signoff check not implemented yet (stubbed)"]
    )
