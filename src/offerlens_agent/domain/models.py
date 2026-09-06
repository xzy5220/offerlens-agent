"""Typed contracts exchanged between OfferLens agents."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictModel(BaseModel):
    """Base model that rejects accidental schema drift between graph nodes."""

    model_config = ConfigDict(extra="forbid")


class RequirementPriority(StrEnum):
    MUST_HAVE = "must_have"
    NICE_TO_HAVE = "nice_to_have"


class EvidenceStrength(StrEnum):
    STRONG = "strong"
    PARTIAL = "partial"
    MISSING = "missing"


class AnalysisPreferences(StrictModel):
    target_city: str | None = None
    target_salary: str | None = None
    language: Literal["zh-CN", "en"] = "zh-CN"
    focus: list[str] = Field(default_factory=list)


class AnalysisRequest(StrictModel):
    """Input accepted by the graph and API."""

    resume_text: str = Field(min_length=20, max_length=120_000)
    job_description: str = Field(min_length=20, max_length=50_000)
    company: str = Field(min_length=1, max_length=120)
    job_title: str = Field(min_length=1, max_length=120)
    preferences: AnalysisPreferences = Field(default_factory=AnalysisPreferences)


class WorkExperience(StrictModel):
    organization: str = ""
    role: str = ""
    period: str = ""
    highlights: list[str] = Field(default_factory=list)


class ProjectExperience(StrictModel):
    name: str
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class CandidateProfile(StrictModel):
    name: str | None = None
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experiences: list[WorkExperience] = Field(default_factory=list)
    projects: list[ProjectExperience] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)


class JobRequirement(StrictModel):
    id: str
    skill: str
    description: str
    priority: RequirementPriority = RequirementPriority.MUST_HAVE
    weight: float = Field(default=1.0, ge=0.1, le=5.0)


class JobProfile(StrictModel):
    company: str
    title: str
    summary: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[JobRequirement] = Field(default_factory=list)


class ResearchTask(StrictModel):
    id: str
    topic: Literal["company", "role", "interview", "market"]
    query: str
    rationale: str


class ResearchPlan(StrictModel):
    tasks: list[ResearchTask] = Field(min_length=1, max_length=8)


class Source(StrictModel):
    id: str
    title: str
    url: HttpUrl | None = None
    snippet: str
    source_type: Literal["web", "resume", "job_description", "fixture"] = "web"


class ResearchFinding(StrictModel):
    task_id: str
    topic: str
    summary: str
    key_facts: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)


class Evidence(StrictModel):
    claim: str
    quote: str
    source_id: str
    source_type: Literal["resume", "job_description", "web"]


class RequirementAssessment(StrictModel):
    requirement_id: str
    requirement: str
    weight: float = Field(default=1.0, ge=0.1, le=5.0)
    score: float = Field(ge=0, le=1)
    strength: EvidenceStrength
    evidence: list[Evidence] = Field(default_factory=list)
    gap: str | None = None

    @model_validator(mode="after")
    def require_evidence_for_positive_match(self) -> RequirementAssessment:
        """Prevent unsupported positive claims from reaching the report."""
        if self.score >= 0.5 and not self.evidence:
            raise ValueError("a positive requirement match must include resume evidence")
        return self


class ResumeSuggestion(StrictModel):
    section: str
    current_evidence: str
    suggestion: str
    reason: str
    invents_experience: bool = False


class InterviewQuestion(StrictModel):
    category: str
    question: str
    why_asked: str
    answer_outline: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class QualityReview(StrictModel):
    passed: bool
    citation_coverage: float = Field(ge=0, le=1)
    evidence_coverage: float = Field(ge=0, le=1)
    issues: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)


class ApprovalDecision(StrictModel):
    approved: bool
    feedback: str = ""


class CareerReport(StrictModel):
    company: str
    job_title: str
    match_score: float = Field(ge=0, le=100)
    recommendation: Literal["strong_apply", "apply", "prepare_then_apply", "low_fit"]
    executive_summary: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    requirement_assessments: list[RequirementAssessment] = Field(default_factory=list)
    company_insights: list[str] = Field(default_factory=list)
    resume_suggestions: list[ResumeSuggestion] = Field(default_factory=list)
    interview_questions: list[InterviewQuestion] = Field(default_factory=list)
    seven_day_plan: list[str] = Field(default_factory=list, min_length=1, max_length=7)
    sources: list[Source] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
