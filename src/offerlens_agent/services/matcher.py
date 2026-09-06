"""Evidence-first matching between a resume and a job profile."""

from __future__ import annotations

from rapidfuzz.fuzz import partial_ratio

from offerlens_agent.domain.models import (
    Evidence,
    EvidenceStrength,
    JobProfile,
    RequirementAssessment,
)
from offerlens_agent.services.retrieval import ResumeEvidenceIndex
from offerlens_agent.services.text_analysis import evidence_lines


class EvidenceMatcher:
    """Calculate explainable requirement scores from exact resume excerpts."""

    def assess(self, resume_text: str, job: JobProfile) -> list[RequirementAssessment]:
        assessments: list[RequirementAssessment] = []
        lowered_resume = resume_text.lower()
        resume_index = ResumeEvidenceIndex(resume_text)

        for requirement in job.requirements:
            quotes = evidence_lines(resume_text, requirement.skill)
            if quotes:
                score = 1.0
                strength = EvidenceStrength.STRONG
            else:
                fuzzy_score = partial_ratio(requirement.skill.lower(), lowered_resume) / 100
                score = round(fuzzy_score * 0.55, 2) if fuzzy_score >= 0.72 else 0.0
                strength = EvidenceStrength.PARTIAL if score else EvidenceStrength.MISSING

            evidence = [
                Evidence(
                    claim=f"候选人的简历体现了 {requirement.skill}",
                    quote=quote,
                    source_id=f"resume-line-{index}",
                    source_type="resume",
                )
                for index, quote in enumerate(quotes, start=1)
            ]
            if not quotes:
                related = resume_index.search(f"{requirement.skill} {requirement.description}", k=1)
                if related and related[0][1] >= 0.28:
                    document, similarity = related[0]
                    score = max(score, round(min(0.49, similarity * 0.7), 2))
                    strength = EvidenceStrength.PARTIAL
                    evidence = [
                        Evidence(
                            claim=f"简历存在与 {requirement.skill} 相关但不足以直接证明掌握程度的内容",
                            quote=document.page_content[:500],
                            source_id=str(document.metadata["source_id"]),
                            source_type="resume",
                        )
                    ]
            assessments.append(
                RequirementAssessment(
                    requirement_id=requirement.id,
                    requirement=requirement.skill,
                    weight=requirement.weight,
                    score=score,
                    strength=strength,
                    evidence=evidence,
                    gap=None if score >= 0.75 else f"简历中缺少可验证的 {requirement.skill} 项目证据",
                )
            )
        return assessments

    @staticmethod
    def weighted_score(job: JobProfile, assessments: list[RequirementAssessment]) -> float:
        """Return a 0-100 score weighted by must-have importance."""
        by_id = {item.requirement_id: item for item in assessments}
        denominator = sum(requirement.weight for requirement in job.requirements)
        if not denominator:
            return 0.0
        numerator = sum(
            requirement.weight
            * by_id.get(
                requirement.id,
                RequirementAssessment(
                    requirement_id=requirement.id,
                    requirement=requirement.skill,
                    weight=requirement.weight,
                    score=0,
                    strength=EvidenceStrength.MISSING,
                ),
            ).score
            for requirement in job.requirements
        )
        return round(100 * numerator / denominator, 1)
