from offerlens_agent.services.retrieval import HashEmbeddings, ResumeEvidenceIndex


def test_hash_embeddings_are_deterministic_and_normalized() -> None:
    embeddings = HashEmbeddings(dimensions=64)
    first = embeddings.embed_query("LangGraph 多智能体编排")
    second = embeddings.embed_query("LangGraph 多智能体编排")

    assert first == second
    assert abs(sum(value * value for value in first) - 1.0) < 1e-6


def test_resume_vector_index_returns_relevant_chunk() -> None:
    resume = (
        "教育经历\n计算机本科\n\n项目经历\n使用 LangGraph 实现多智能体状态编排和人工审批。\n\n其他\n参加校园志愿活动。"
    )
    index = ResumeEvidenceIndex(resume)

    results = index.search("LangGraph Agent 状态编排", k=1)

    assert results
    assert "LangGraph" in results[0][0].page_content
