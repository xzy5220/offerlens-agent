"""Deterministic evaluation metrics for career-agent regressions."""

from __future__ import annotations

from pydantic import BaseModel, Field

from offerlens_agent.domain.models import CareerReport


class ExpectedOutcome(BaseModel):
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    skill_recall: float
    gap_recall: float
    evidence_coverage: float
    citation_coverage: float
    no_fabricated_resume_claims: bool

    @property
    def overall_score(self) -> float:
        values = [self.skill_recall, self.gap_recall, self.evidence_coverage, self.citation_coverage]
        return round(sum(values) / len(values), 4)


def evaluate_report(report: CareerReport, expected: ExpectedOutcome) -> EvaluationResult:
    """Score recall and grounding without using another LLM as judge."""
    assessments = {item.requirement.casefold(): item for item in report.requirement_assessments}
    expected_matches = {item.casefold() for item in expected.matched_skills}
    expected_gaps = {item.casefold() for item in expected.missing_skills}

    predicted_matches = {name for name, item in assessments.items() if item.score >= 0.75}
    predicted_gaps = {name for name, item in assessments.items() if item.score < 0.75}
    positive = [item for item in assessments.values() if item.score >= 0.5]

    skill_recall = _recall(predicted_matches, expected_matches)
    gap_recall = _recall(predicted_gaps, expected_gaps)
    evidence_coverage = sum(bool(item.evidence) for item in positive) / len(positive) if positive else 1.0
    citation_coverage = 1.0 if report.sources and report.company_insights else 0.0
    no_fabrication = all(not suggestion.invents_experience for suggestion in report.resume_suggestions)
    return EvaluationResult(
        skill_recall=round(skill_recall, 4),
        gap_recall=round(gap_recall, 4),
        evidence_coverage=round(evidence_coverage, 4),
        citation_coverage=citation_coverage,
        no_fabricated_resume_claims=no_fabrication,
    )


def _recall(predicted: set[str], expected: set[str]) -> float:
    if not expected:
        return 1.0
    return len(predicted & expected) / len(expected)
