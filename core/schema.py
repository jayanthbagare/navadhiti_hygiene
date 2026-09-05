from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Union
from datetime import datetime

class EnvironmentSeparation(BaseModel):
    status: Literal["pass", "fail", "undefined_standard"] = "undefined_standard"
    evidence: List[str] = Field(default_factory=list)

class CiCdGates(BaseModel):
    status: Literal["pass", "fail", "undefined_standard"] = "undefined_standard"
    evidence: List[str] = Field(default_factory=list)

class UatSprintSignoff(BaseModel):
    sprint_id: str
    status: Literal["pass", "fail", "unverifiable"] = "unverifiable"
    evidence: List[str] = Field(default_factory=list)

class UatSignoff(BaseModel):
    status: Literal["pass", "fail", "unverifiable"] = "unverifiable"
    method: Literal["repo_artifact", "email_parsed", "none"] = "none"
    evidence: List[str] = Field(default_factory=list)
    per_sprint: List[UatSprintSignoff] = Field(default_factory=list)

class CostTracking(BaseModel):
    status: Literal["pass", "fail", "undefined_standard"] = "undefined_standard"
    headcount: int = 0
    sprint_duration_days: int = 14
    estimated_cost: float = 0.0
    budget: Optional[float] = None
    variance_pct: Optional[float] = None

class SecurityBaseline(BaseModel):
    status: Literal["pass", "fail", "undefined_standard"] = "undefined_standard"
    evidence: List[str] = Field(default_factory=list)

class DeploymentHistory(BaseModel):
    status: Literal["pass", "fail", "undefined_standard"] = "undefined_standard"
    method: Literal["releases", "tags", "none"] = "none"
    last_deploy: Optional[datetime] = None
    last_signoff_before_deploy: Optional[datetime] = None
    gap_flag: bool = False
    evidence: List[str] = Field(default_factory=list)

class FeatureIssueTrace(BaseModel):
    status: Literal["pass", "fail", "undefined_standard"] = "undefined_standard"
    method: Literal["pr_linked", "commit_linked", "none"] = "none"
    evidence: List[str] = Field(default_factory=list)
    unlinked_count: int = 0          # merged PRs/commits with no issue reference
    total_checked: int = 0

class IssueTicketTrace(BaseModel):
    status: Literal["pass", "fail", "undefined_standard"] = "undefined_standard"
    evidence: List[str] = Field(default_factory=list)
    unlinked_count: int = 0          # issues with no external ticket reference
    total_checked: int = 0

class Traceability(BaseModel):
    feature_to_issue: FeatureIssueTrace = Field(default_factory=FeatureIssueTrace)
    issue_to_ticket: IssueTicketTrace = Field(default_factory=IssueTicketTrace)

class Dimensions(BaseModel):
    environment_separation: EnvironmentSeparation = Field(default_factory=EnvironmentSeparation)
    ci_cd_gates: CiCdGates = Field(default_factory=CiCdGates)
    uat_signoff: UatSignoff = Field(default_factory=UatSignoff)
    cost_tracking: CostTracking = Field(default_factory=CostTracking)
    security_baseline: SecurityBaseline = Field(default_factory=SecurityBaseline)
    deployment_history: DeploymentHistory = Field(default_factory=DeploymentHistory)
    traceability: Traceability = Field(default_factory=Traceability)

class Overall(BaseModel):
    hygiene_score: float = 0.0
    enforcement_eligible: bool = False

class ProjectHygieneReport(BaseModel):
    id: str
    repo_url: str
    last_evaluated: datetime
    dimensions: Dimensions = Field(default_factory=Dimensions)
    overall: Overall = Field(default_factory=Overall)
