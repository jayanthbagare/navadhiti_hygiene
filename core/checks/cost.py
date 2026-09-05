from core.schema import CostTracking
from typing import Optional

def check_cost(repo_id: str, project_meta: dict, sprint_duration_days: int = 14) -> CostTracking:
    """
    Live check for cost tracking.
    In a real implementation, this would call the timesheet API using timesheet_code.
    """
    # Fallback/stub values if metadata is missing
    headcount = project_meta.get("headcount", 0)
    budget = project_meta.get("budget", None)
    
    # Simple role rate simulation (e.g. average $800/day per person)
    average_daily_rate = 800
    estimated_cost = headcount * sprint_duration_days * average_daily_rate
    
    variance_pct = None
    if budget and budget > 0:
        variance_pct = ((estimated_cost - budget) / budget) * 100
        
    status = "pass" if headcount > 0 else "undefined_standard"
    
    return CostTracking(
        status=status,
        headcount=headcount,
        sprint_duration_days=sprint_duration_days,
        estimated_cost=estimated_cost,
        budget=budget,
        variance_pct=variance_pct
    )
