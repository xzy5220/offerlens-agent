"""State and event contracts for the OfferLens graph."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from offerlens_agent.domain.models import (
    AnalysisRequest,
    ApprovalDecision,
    CandidateProfile,
    CareerReport,
    JobProfile,
    QualityReview,
    RequirementAssessment,
    ResearchFinding,
    ResearchTask,
)


class WorkflowEvent(TypedDict):
    node: str
    agent: str
    status: str
    message: str


class CareerState(TypedDict, total=False):
    request: AnalysisRequest | dict[str, Any]
    candidate: CandidateProfile
    job: JobProfile
    research_tasks: list[ResearchTask]
    research_task: ResearchTask
    research_results: Annotated[list[ResearchFinding], operator.add]
    assessments: list[RequirementAssessment]
    match_score: float
    report: CareerReport
    quality_review: QualityReview
    revision_count: int
    approval: ApprovalDecision
    timeline: Annotated[list[WorkflowEvent], operator.add]
    warnings: Annotated[list[str], operator.add]
