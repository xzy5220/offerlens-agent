from offerlens_agent.domain.models import (
    CareerReport,
    Evidence,
    EvidenceStrength,
    RequirementAssessment,
    Source,
)
from offerlens_agent.evaluation.metrics import ExpectedOutcome, evaluate_report


def test_evaluation_penalizes_missing_expected_skill() -> None:
    report = CareerReport(
        company="Example",
        job_title="Agent Engineer",
        match_score=50,
        recommendation="prepare_then_apply",
        executive_summary="summary",
        strengths=["Python"],
        gaps=["LangGraph"],
        requirement_assessments=[
            RequirementAssessment(
                requirement_id="1",
                requirement="Python",
                score=1,
                strength=EvidenceStrength.STRONG,
                evidence=[Evidence(claim="Python", quote="used Python", source_id="resume-1", source_type="resume")],
            ),
            RequirementAssessment(
                requirement_id="2",
                requirement="LangGraph",
                score=0,
                strength=EvidenceStrength.MISSING,
            ),
        ],
        seven_day_plan=["day 1"],
        company_insights=["insight"],
        sources=[Source(id="s1", title="source", snippet="fact", source_type="fixture")],
    )

    result = evaluate_report(
        report,
        ExpectedOutcome(matched_skills=["Python", "LangGraph"], missing_skills=["LangGraph"]),
    )

    assert result.skill_recall == 0.5
    assert result.gap_recall == 1
    assert result.evidence_coverage == 1
