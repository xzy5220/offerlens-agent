from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from offerlens_agent.config import Settings
from offerlens_agent.workflow.graph import create_graph

REQUEST = {
    "request": {
        "resume_text": "张三\n计算机本科\n项目：使用 Python、FastAPI、LangChain、LangGraph 和 RAG 开发 Agent，并使用 Docker 部署。",
        "job_description": "招聘 Agent 开发工程师。必须熟悉 Python、LangChain、LangGraph、RAG 和工具调用；Redis、向量数据库优先。",
        "company": "示例科技",
        "job_title": "Agent 开发工程师",
    }
}


async def test_graph_runs_parallel_research_and_returns_grounded_report(tmp_path) -> None:
    settings = Settings(mode="demo", search_provider="fixture", data_dir=tmp_path)
    graph = create_graph(settings=settings)

    result = await graph.ainvoke(REQUEST)

    assert len(result["research_results"]) == 4
    assert result["quality_review"].passed
    assert result["approval"].approved
    assert 0 <= result["report"].match_score <= 100
    assert all(item.evidence for item in result["report"].requirement_assessments if item.score >= 0.5)
    agents = {event["agent"] for event in result["timeline"]}
    assert {"Resume Analyst", "JD Analyst", "Research Supervisor", "Grounding Critic"} <= agents


async def test_graph_can_interrupt_and_resume_human_approval(tmp_path) -> None:
    settings = Settings(mode="demo", search_provider="fixture", require_approval=True, data_dir=tmp_path)
    graph = create_graph(settings=settings, checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "approval-test"}}

    interrupted = await graph.ainvoke(REQUEST, config=config)
    assert interrupted["__interrupt__"]

    completed = await graph.ainvoke(
        Command(resume={"approved": True, "feedback": "looks good"}),
        config=config,
    )
    assert completed["approval"].approved
    assert completed["report"].company == "示例科技"
