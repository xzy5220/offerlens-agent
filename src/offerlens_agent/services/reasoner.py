"""Reasoning adapters for deterministic demos and live LangChain models."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Protocol, TypeVar

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from offerlens_agent.config import Settings
from offerlens_agent.domain.models import (
    AnalysisPreferences,
    CandidateProfile,
    CareerReport,
    InterviewQuestion,
    JobProfile,
    QualityReview,
    RequirementAssessment,
    ResearchFinding,
    ResearchPlan,
    ResearchTask,
    ResumeSuggestion,
    Source,
)
from offerlens_agent.services.quality import ReportQualityGate
from offerlens_agent.services.text_analysis import parse_candidate_profile, parse_job_profile, unique_preserving_order

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class CareerReasoner(Protocol):
    """Operations assigned to specialized nodes in the career graph."""

    async def parse_candidate(self, resume_text: str) -> CandidateProfile: ...

    async def parse_job(self, company: str, title: str, description: str) -> JobProfile: ...

    async def plan_research(self, job: JobProfile, preferences: AnalysisPreferences) -> list[ResearchTask]: ...

    async def summarize_research(self, task: ResearchTask, sources: list[Source]) -> ResearchFinding: ...

    async def build_report(
        self,
        candidate: CandidateProfile,
        job: JobProfile,
        assessments: list[RequirementAssessment],
        findings: list[ResearchFinding],
        match_score: float,
    ) -> CareerReport: ...

    async def review_report(self, report: CareerReport) -> QualityReview: ...

    async def revise_report(self, report: CareerReport, review: QualityReview) -> CareerReport: ...


class DemoReasoner:
    """Deterministic implementation that exposes the full workflow without paid APIs."""

    def __init__(self) -> None:
        self._quality_gate = ReportQualityGate()

    async def parse_candidate(self, resume_text: str) -> CandidateProfile:
        return parse_candidate_profile(resume_text)

    async def parse_job(self, company: str, title: str, description: str) -> JobProfile:
        return parse_job_profile(company, title, description)

    async def plan_research(self, job: JobProfile, preferences: AnalysisPreferences) -> list[ResearchTask]:
        targets = [
            ("company", f"{job.company} 产品 商业模式 团队 近期动态", "了解公司业务和面试语境"),
            ("role", f"{job.title} 核心能力 技术栈 发展趋势", "校准岗位要求和能力优先级"),
            ("interview", f"{job.company} {job.title} 面试经验 高频问题", "生成针对性面试准备材料"),
            ("market", f"{job.title} {preferences.target_city or ''} 招聘市场 薪资 要求", "建立岗位市场基线"),
        ]
        return [
            ResearchTask(id=f"research-{index}", topic=topic, query=query.strip(), rationale=rationale)
            for index, (topic, query, rationale) in enumerate(targets, start=1)
        ]

    async def summarize_research(self, task: ResearchTask, sources: list[Source]) -> ResearchFinding:
        facts = unique_preserving_order(source.snippet for source in sources if source.snippet)
        summary = "；".join(facts)[:1600] or "当前检索没有返回可用资料。"
        return ResearchFinding(task_id=task.id, topic=task.topic, summary=summary, key_facts=facts, sources=sources)

    async def build_report(
        self,
        candidate: CandidateProfile,
        job: JobProfile,
        assessments: list[RequirementAssessment],
        findings: list[ResearchFinding],
        match_score: float,
    ) -> CareerReport:
        strengths = [item.requirement for item in assessments if item.score >= 0.75]
        gaps = [item.gap for item in assessments if item.gap]
        all_sources = _deduplicate_sources([source for finding in findings for source in finding.sources])
        company_insights = unique_preserving_order(
            fact for finding in findings if finding.topic == "company" for fact in finding.key_facts
        )

        resume_suggestions = [
            ResumeSuggestion(
                section="项目经历",
                current_evidence="未在当前简历中找到直接证据",
                suggestion=f"如果确实做过 {item.requirement}，补充包含任务、行动和量化结果的真实项目描述；否则不要虚构。",
                reason=f"该岗位将 {item.requirement} 作为要求，但证据覆盖不足。",
                invents_experience=False,
            )
            for item in assessments
            if item.score < 0.75
        ][:6]

        interview_questions = [
            InterviewQuestion(
                category="项目深挖" if item.evidence else "能力补缺",
                question=(
                    f"请基于简历中的真实项目说明你如何使用 {item.requirement}，遇到了什么问题？"
                    if item.evidence
                    else f"岗位需要 {item.requirement}。你会如何设计一个最小项目证明自己具备这项能力？"
                ),
                why_asked=f"验证 {item.requirement} 是否达到岗位要求",
                answer_outline=["背景与目标", "关键设计与取舍", "可量化结果", "复盘与改进"],
                evidence_ids=[evidence.source_id for evidence in item.evidence],
            )
            for item in assessments[:8]
        ]

        recommendation = _recommendation(match_score)
        summary = (
            f"候选人与 {job.company} 的 {job.title} 岗位匹配度为 {match_score:.1f}%。"
            f"已验证优势 {len(strengths)} 项，待补证或补齐能力 {len(gaps)} 项。"
            "结论仅使用简历原文、岗位描述和列出的研究资料。"
        )
        return CareerReport(
            company=job.company,
            job_title=job.title,
            match_score=match_score,
            recommendation=recommendation,
            executive_summary=summary,
            strengths=strengths,
            gaps=[gap for gap in gaps if gap],
            requirement_assessments=assessments,
            company_insights=company_insights,
            resume_suggestions=resume_suggestions,
            interview_questions=interview_questions,
            seven_day_plan=_seven_day_plan(gaps, job),
            sources=all_sources,
            caveats=["离线演示模式使用明确标注的样例资料，不代表实时网络事实。"],
        )

    async def review_report(self, report: CareerReport) -> QualityReview:
        return self._quality_gate.review(report)

    async def revise_report(self, report: CareerReport, review: QualityReview) -> CareerReport:
        # Deterministic mode can only remove unsupported content; it never fabricates a replacement.
        clean_suggestions = [item for item in report.resume_suggestions if not item.invents_experience]
        caveats = unique_preserving_order([*report.caveats, *review.revision_instructions])
        return report.model_copy(update={"resume_suggestions": clean_suggestions, "caveats": caveats})


class LangChainReasoner(DemoReasoner):
    """Live implementation using LangChain structured output at every generative boundary."""

    def __init__(self, model_name: str) -> None:
        super().__init__()
        self._model = init_chat_model(model_name)

    async def _structured(self, schema: type[SchemaT], system: str, payload: object) -> SchemaT:
        runnable = self._model.with_structured_output(schema).with_retry(stop_after_attempt=3)
        response = await runnable.ainvoke(
            [
                SystemMessage(content=system),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False, default=str)),
            ]
        )
        if not isinstance(response, schema):
            return schema.model_validate(response)
        return response

    async def parse_candidate(self, resume_text: str) -> CandidateProfile:
        return await self._structured(
            CandidateProfile,
            "提取简历中的候选人信息。只能使用输入原文，不得补充或推断不存在的经历。",
            {"resume": resume_text},
        )

    async def parse_job(self, company: str, title: str, description: str) -> JobProfile:
        profile = await self._structured(
            JobProfile,
            "将岗位描述提取为结构化要求。合并重复技能，并区分必须项和加分项。",
            {"company": company, "title": title, "job_description": description},
        )
        return profile.model_copy(update={"company": company, "title": title})

    async def plan_research(self, job: JobProfile, preferences: AnalysisPreferences) -> list[ResearchTask]:
        plan = await self._structured(
            ResearchPlan,
            "你是研究主管。创建 3-6 个互不重复、可通过公开网页验证的研究任务，必须覆盖公司、岗位和面试。",
            {"job": job.model_dump(mode="json"), "preferences": preferences.model_dump(mode="json")},
        )
        return plan.tasks

    async def summarize_research(self, task: ResearchTask, sources: list[Source]) -> ResearchFinding:
        finding = await self._structured(
            ResearchFinding,
            "仅根据给出的搜索结果归纳事实。不得创造链接或搜索结果中不存在的事实。",
            {"task": task.model_dump(mode="json"), "sources": [item.model_dump(mode="json") for item in sources]},
        )
        return finding.model_copy(update={"task_id": task.id, "topic": task.topic, "sources": sources})

    async def build_report(
        self,
        candidate: CandidateProfile,
        job: JobProfile,
        assessments: list[RequirementAssessment],
        findings: list[ResearchFinding],
        match_score: float,
    ) -> CareerReport:
        report = await self._structured(
            CareerReport,
            """你是求职决策 Agent。生成中文报告。禁止虚构候选人的技能或经历；每个正向能力结论必须来自给定 assessment 的简历原文证据；不得创造新来源。简历建议只能建议如何呈现真实经历。""",
            {
                "candidate": candidate.model_dump(mode="json"),
                "job": job.model_dump(mode="json"),
                "assessments": [item.model_dump(mode="json") for item in assessments],
                "findings": [item.model_dump(mode="json") for item in findings],
                "fixed_match_score": match_score,
            },
        )
        allowed_sources = _deduplicate_sources([source for finding in findings for source in finding.sources])
        return report.model_copy(
            update={
                "company": job.company,
                "job_title": job.title,
                "match_score": match_score,
                "requirement_assessments": assessments,
                "sources": allowed_sources,
            }
        )

    async def review_report(self, report: CareerReport) -> QualityReview:
        model_review = await self._structured(
            QualityReview,
            "审查报告是否回答岗位问题、是否引用充分、是否可能夸大候选人经历。严格列出问题。",
            report.model_dump(mode="json"),
        )
        guard_review = self._quality_gate.review(report)
        issues = unique_preserving_order([*model_review.issues, *guard_review.issues])
        return QualityReview(
            passed=model_review.passed and guard_review.passed,
            citation_coverage=min(model_review.citation_coverage, guard_review.citation_coverage),
            evidence_coverage=min(model_review.evidence_coverage, guard_review.evidence_coverage),
            issues=issues,
            revision_instructions=unique_preserving_order(
                [*model_review.revision_instructions, *guard_review.revision_instructions]
            ),
        )

    async def revise_report(self, report: CareerReport, review: QualityReview) -> CareerReport:
        revised = await self._structured(
            CareerReport,
            "根据审查意见修订报告。只删除或重写没有依据的结论，不得发明新的简历经历或网页来源。",
            {"report": report.model_dump(mode="json"), "review": review.model_dump(mode="json")},
        )
        return revised.model_copy(
            update={
                "company": report.company,
                "job_title": report.job_title,
                "match_score": report.match_score,
                "requirement_assessments": report.requirement_assessments,
                "sources": report.sources,
            }
        )


def _recommendation(score: float) -> str:
    if score >= 80:
        return "strong_apply"
    if score >= 60:
        return "apply"
    if score >= 35:
        return "prepare_then_apply"
    return "low_fit"


def _seven_day_plan(gaps: Sequence[str | None], job: JobProfile) -> list[str]:
    priorities = [gap for gap in gaps if gap][:3]
    while len(priorities) < 3:
        priorities.append(f"梳理 {job.title} 的核心能力证据")
    return [
        f"第1天：拆解岗位要求，确认三个优先事项：{'；'.join(priorities)}",
        f"第2天：围绕 {priorities[0]} 完成知识梳理和最小练习",
        f"第3天：围绕 {priorities[1]} 完成可展示的代码或案例",
        f"第4天：围绕 {priorities[2]} 准备 STAR 项目故事",
        "第5天：按证据原则修改简历，不添加未做过的经历",
        "第6天：完成一次技术面试模拟并记录薄弱点",
        f"第7天：复盘并提交 {job.company} 的 {job.title} 岗位申请",
    ]


def _deduplicate_sources(sources: list[Source]) -> list[Source]:
    return list({source.id: source for source in sources}.values())


def build_reasoner(settings: Settings) -> CareerReasoner:
    """Select a free deterministic adapter or a real model-backed adapter."""
    if settings.mode == "demo":
        return DemoReasoner()
    return LangChainReasoner(settings.model)
