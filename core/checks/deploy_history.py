from core.schema import DeploymentHistory
from datetime import datetime, timedelta

def check_deploy_history(repo_id: str, repo_path_or_url: str) -> DeploymentHistory:
    """
    Live check for deployment history vs signoff.
    In a real implementation, this checks CI/CD logs and PR tags.
    """
    # Simulated data for milestone 1
    # Let's say active-project-1 has a gap, and active-project-2 does not.
    now = datetime.now()
    
    if "active-project-1" in repo_id:
        last_deploy = now - timedelta(days=2)
        last_signoff = now - timedelta(days=5)
        # Gap flag logic: if deploy happened but signoff was earlier...
        # Actually gap means deploy happened with NO preceding signoff within the sprint window.
        # Or perhaps signoff was for a different release. 
        # For simplicity, if last_signoff is None or too old compared to deploy.
        gap_flag = True
    elif "active-project-2" in repo_id:
        last_deploy = now - timedelta(days=1)
        last_signoff = now - timedelta(hours=25)
        gap_flag = False
    else:
        last_deploy = None
        last_signoff = None
        gap_flag = False
        
    return DeploymentHistory(
        last_deploy=last_deploy,
        last_signoff_before_deploy=last_signoff,
        gap_flag=gap_flag
    )
