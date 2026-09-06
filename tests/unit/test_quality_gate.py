from offerlens_agent.domain.models import AnalysisPreferences, CareerReport, Source
from offerlens_agent.services.matcher import EvidenceMatcher
from offerlens_agent.services.quality import ReportQualityGate
from offerlens_agent.services.reasoner import DemoReasoner
from offerlens_agent.services.text_analysis import parse_candidate_profile, parse_job_profile


async def test_demo_report_passes_grounding_gate() -> None:
    reasoner = DemoReasoner()
    resume = "项目：使用 Python、LangGraph 和 RAG 开发带引用的 Agent。"
    job = parse_job_profile("Example", "Agent Engineer", "必须熟悉 Python、LangGraph、RAG 和 Redis。")
    candidate = parse_candidate_profile(resume)
    matcher = EvidenceMatcher()
    assessments = matcher.assess(resume, job)
    score = matcher.weighted_score(job, assessments)
    tasks = await reasoner.plan_research(job, preferences=AnalysisPreferences())
    findings = [
        await reasoner.summarize_research(
            tasks[0],
            [Source(id="source-1", title="Fixture", snippet="Grounded source", source_type="fixture")],
        )
    ]
    report = await reasoner.build_report(candidate, job, assessments, findings, score)

    assert isinstance(report, CareerReport)
    assert ReportQualityGate().review(report).passed
