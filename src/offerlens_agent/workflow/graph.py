"""Production-oriented LangGraph orchestration for OfferLens."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, StateGraph
from langgraph.types import Command, Send, interrupt

from offerlens_agent.config import Settings, get_settings
from offerlens_agent.domain.models import (
    AnalysisRequest,
    ApprovalDecision,
    QualityReview,
    ResearchFinding,
)
from offerlens_agent.services.matcher import EvidenceMatcher
from offerlens_agent.services.reasoner import CareerReasoner, build_reasoner
from offerlens_agent.services.search import SearchProvider, build_search_provider
from offerlens_agent.workflow.state import CareerState, WorkflowEvent


@dataclass(frozen=True)
class WorkflowServices:
    """Explicit dependencies keep graph nodes testable and provider-neutral."""

    settings: Settings
    reasoner: CareerReasoner
    search: SearchProvider
    matcher: EvidenceMatcher


def _event(node: str, agent: str, message: str, status: str = "completed") -> list[WorkflowEvent]:
    return [{"node": node, "agent": agent, "status": status, "message": message}]


def _request(state: CareerState) -> AnalysisRequest:
    value = state["request"]
    return value if isinstance(value, AnalysisRequest) else AnalysisRequest.model_validate(value)


def create_graph(
    *,
    settings: Settings | None = None,
    reasoner: CareerReasoner | None = None,
    search: SearchProvider | None = None,
    matcher: EvidenceMatcher | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Build the graph, optionally injecting fakes or persistent checkpointing."""
    runtime_settings = settings or get_settings()
    services = WorkflowServices(
        settings=runtime_settings,
        reasoner=reasoner or build_reasoner(runtime_settings),
        search=search or build_search_provider(runtime_settings),
        matcher=matcher or EvidenceMatcher(),
    )

    async def parse_resume(state: CareerState) -> dict:
        request = _request(state)
        candidate = await services.reasoner.parse_candidate(request.resume_text)
        return {
            "candidate": candidate,
            "timeline": _event("parse_resume", "Resume Analyst", f"提取到 {len(candidate.skills)} 项技能"),
        }

    async def parse_job(state: CareerState) -> dict:
        request = _request(state)
        job = await services.reasoner.parse_job(request.company, request.job_title, request.job_description)
        return {
            "job": job,
            "timeline": _event("parse_job", "JD Analyst", f"识别到 {len(job.requirements)} 项岗位要求"),
        }

    async def plan_research(state: CareerState) -> dict:
        request = _request(state)
        tasks = await services.reasoner.plan_research(state["job"], request.preferences)
        return {
            "research_tasks": tasks,
            "timeline": _event("plan_research", "Research Supervisor", f"拆分为 {len(tasks)} 个并行研究任务"),
        }

    def dispatch_research(state: CareerState) -> list[Send]:
        return [Send("research_agent", {"research_task": task}) for task in state["research_tasks"]]

    async def research_agent(state: CareerState) -> dict:
        task = state["research_task"]
        try:
            sources = await services.search.search(task)
            finding = await services.reasoner.summarize_research(task, sources)
            return {
                "research_results": [finding],
                "timeline": _event(
                    f"research_{task.topic}",
                    f"{task.topic.title()} Researcher",
                    f"完成研究并保留 {len(sources)} 个来源",
                ),
            }
        except Exception as exc:
            finding = ResearchFinding(
                task_id=task.id,
                topic=task.topic,
                summary="该研究任务执行失败，最终报告不得把它当作事实来源。",
                key_facts=[],
                sources=[],
            )
            return {
                "research_results": [finding],
                "warnings": [f"{task.topic} research failed: {exc}"],
                "timeline": _event(
                    f"research_{task.topic}",
                    f"{task.topic.title()} Researcher",
                    "研究失败，已降级并保留诊断信息",
                    "failed",
                ),
            }

    async def match_evidence(state: CareerState) -> dict:
        request = _request(state)
        assessments = services.matcher.assess(request.resume_text, state["job"])
        score = services.matcher.weighted_score(state["job"], assessments)
        evidenced = sum(bool(item.evidence) for item in assessments)
        return {
            "assessments": assessments,
            "match_score": score,
            "timeline": _event(
                "match_evidence",
                "Resume RAG & Evidence Matcher",
                f"向量检索后，{evidenced}/{len(assessments)} 项要求找到简历原文证据",
            ),
        }

    async def draft_report(state: CareerState) -> dict:
        report = await services.reasoner.build_report(
            state["candidate"],
            state["job"],
            state["assessments"],
            state.get("research_results", []),
            state["match_score"],
        )
        return {
            "report": report,
            "revision_count": 0,
            "timeline": _event("draft_report", "Career Strategist", "生成求职决策、简历建议和面试计划"),
        }

    async def critic_agent(state: CareerState) -> dict:
        review = await services.reasoner.review_report(state["report"])
        return {
            "quality_review": review,
            "timeline": _event(
                "critic_agent",
                "Grounding Critic",
                "质量门禁通过" if review.passed else f"发现 {len(review.issues)} 个质量问题",
                "completed" if review.passed else "needs_revision",
            ),
        }

    def route_after_review(state: CareerState) -> Literal["revise_report", "human_approval"]:
        review = state["quality_review"]
        if review.passed or state.get("revision_count", 0) >= services.settings.max_revisions:
            return "human_approval"
        return "revise_report"

    async def revise_report(state: CareerState) -> dict:
        report = await services.reasoner.revise_report(state["report"], state["quality_review"])
        count = state.get("revision_count", 0) + 1
        return {
            "report": report,
            "revision_count": count,
            "timeline": _event("revise_report", "Report Reviser", f"完成第 {count} 轮有依据修订"),
        }

    async def human_approval(
        state: CareerState,
    ) -> Command[Literal["revise_report", "__end__"]]:
        if not services.settings.require_approval:
            decision = ApprovalDecision(approved=True, feedback="自动批准：当前配置未启用人工中断")
        else:
            payload = interrupt(
                {
                    "type": "report_approval",
                    "match_score": state["report"].match_score,
                    "recommendation": state["report"].recommendation,
                    "quality": state["quality_review"].model_dump(mode="json"),
                    "question": "是否批准该报告？可返回 approved 和 feedback。",
                }
            )
            decision = ApprovalDecision.model_validate(payload)

        if decision.approved:
            return Command(
                goto="__end__",
                update={
                    "approval": decision,
                    "timeline": _event("human_approval", "Human Reviewer", "报告已批准"),
                },
            )

        feedback_review = QualityReview(
            passed=False,
            citation_coverage=state["quality_review"].citation_coverage,
            evidence_coverage=state["quality_review"].evidence_coverage,
            issues=[decision.feedback or "人工审核要求修改"],
            revision_instructions=[decision.feedback or "根据人工审核意见修改报告"],
        )
        return Command(
            goto="revise_report",
            update={
                "approval": decision,
                "quality_review": feedback_review,
                "timeline": _event("human_approval", "Human Reviewer", "报告被退回修改", "needs_revision"),
            },
        )

    builder = StateGraph(CareerState)
    builder.add_node("parse_resume", parse_resume)
    builder.add_node("parse_job", parse_job)
    builder.add_node("plan_research", plan_research)
    builder.add_node("research_agent", research_agent)
    builder.add_node("match_evidence", match_evidence)
    builder.add_node("draft_report", draft_report)
    builder.add_node("critic_agent", critic_agent)
    builder.add_node("revise_report", revise_report)
    builder.add_node("human_approval", human_approval)

    builder.add_edge(START, "parse_resume")
    builder.add_edge(START, "parse_job")
    builder.add_edge(["parse_resume", "parse_job"], "plan_research")
    builder.add_conditional_edges("plan_research", dispatch_research, ["research_agent"])
    builder.add_edge("research_agent", "match_evidence")
    builder.add_edge("match_evidence", "draft_report")
    builder.add_edge("draft_report", "critic_agent")
    builder.add_conditional_edges(
        "critic_agent",
        route_after_review,
        {"revise_report": "revise_report", "human_approval": "human_approval"},
    )
    builder.add_edge("revise_report", "critic_agent")
    return builder.compile(checkpointer=checkpointer)


# LangGraph Studio entry point. The API builds a separate graph with checkpointing.
graph = create_graph()
