"""Deterministic guardrails for claims, citations, and score consistency."""

from __future__ import annotations

from offerlens_agent.domain.models import CareerReport, QualityReview


class ReportQualityGate:
    """Reject reports that cannot explain positive conclusions with evidence."""

    def review(self, report: CareerReport) -> QualityReview:
        issues: list[str] = []
        positive = [item for item in report.requirement_assessments if item.score >= 0.5]
        evidenced = [item for item in positive if item.evidence]
        evidence_coverage = len(evidenced) / len(positive) if positive else 1.0

        source_backed_sections = int(bool(report.sources)) + int(bool(report.company_insights))
        citation_coverage = source_backed_sections / 2
        if evidence_coverage < 1:
            issues.append("存在没有简历原文证据的正向匹配结论")
        if citation_coverage < 1:
            issues.append("公司调研结论缺少可追溯来源")
        if any(suggestion.invents_experience for suggestion in report.resume_suggestions):
            issues.append("简历建议包含无法从原简历验证的经历")

        expected = _score_from_assessments(report)
        if abs(expected - report.match_score) > 1:
            issues.append(f"总匹配分与逐项证据不一致，应接近 {expected}")

        return QualityReview(
            passed=not issues,
            citation_coverage=round(citation_coverage, 2),
            evidence_coverage=round(evidence_coverage, 2),
            issues=issues,
            revision_instructions=[f"修复：{issue}" for issue in issues],
        )


def _score_from_assessments(report: CareerReport) -> float:
    if not report.requirement_assessments:
        return 0.0
    denominator = sum(item.weight for item in report.requirement_assessments)
    return round(100 * sum(item.score * item.weight for item in report.requirement_assessments) / denominator, 1)
