from core.schema import CiCdGates

def check_ci_gates(repo_id: str, repo_path: str) -> CiCdGates:
    return CiCdGates(
        status="undefined_standard",
        evidence=["CI/CD gates check not implemented yet (stubbed)"]
    )
