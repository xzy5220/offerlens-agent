import pytest
from pydantic import ValidationError

from offerlens_agent.domain.models import EvidenceStrength, RequirementAssessment
from offerlens_agent.services.matcher import EvidenceMatcher
from offerlens_agent.services.text_analysis import extract_skills, parse_job_profile


def test_extracts_agent_engineering_skills() -> None:
    skills = extract_skills("使用 Python、LangGraph、RAG、FastAPI 和 pgvector 构建 Agent")
    assert {"Python", "LangGraph", "RAG", "FastAPI", "Vector Database"} <= set(skills)


def test_matcher_quotes_exact_resume_evidence() -> None:
    resume = "项目：使用 Python 和 LangGraph 构建多智能体工作流，并通过 Docker 部署。"
    job = parse_job_profile("Example", "Agent Engineer", "必须熟练 Python、LangGraph、Redis 和 Docker。")

    assessments = EvidenceMatcher().assess(resume, job)
    by_requirement = {item.requirement: item for item in assessments}

    assert by_requirement["LangGraph"].strength == EvidenceStrength.STRONG
    assert "LangGraph" in by_requirement["LangGraph"].evidence[0].quote
    assert by_requirement["Redis"].strength == EvidenceStrength.MISSING
    assert by_requirement["Redis"].evidence == []


def test_positive_claim_without_evidence_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must include resume evidence"):
        RequirementAssessment(
            requirement_id="req-1",
            requirement="LangGraph",
            score=0.8,
            strength=EvidenceStrength.STRONG,
            evidence=[],
        )
