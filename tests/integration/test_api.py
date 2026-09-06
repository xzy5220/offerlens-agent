import time

from fastapi.testclient import TestClient

from offerlens_agent.api.app import create_app
from offerlens_agent.config import Settings

PAYLOAD = {
    "resume_text": "张三。项目使用 Python、LangChain、LangGraph 和 RAG 构建 Agent，并使用 Docker 完成部署。",
    "job_description": "招聘 Agent 开发工程师，必须熟悉 Python、LangChain、LangGraph、RAG、Redis 和向量数据库。",
    "company": "示例科技",
    "job_title": "Agent 开发工程师",
}


def test_create_and_poll_analysis(tmp_path) -> None:
    app = create_app(Settings(mode="demo", search_provider="fixture", data_dir=tmp_path))
    with TestClient(app) as client:
        response = client.post("/api/v1/analyses", json=PAYLOAD)
        assert response.status_code == 202
        analysis_id = response.json()["id"]

        result = {}
        for _ in range(50):
            result = client.get(f"/api/v1/analyses/{analysis_id}").json()
            if result["status"] in {"completed", "failed"}:
                break
            time.sleep(0.02)

        assert result["status"] == "completed", result.get("error")
        assert result["report"]["company"] == "示例科技"
        assert result["quality_review"]["passed"] is True


def test_rejects_unknown_analysis(tmp_path) -> None:
    app = create_app(Settings(mode="demo", data_dir=tmp_path))
    with TestClient(app) as client:
        response = client.get("/api/v1/analyses/does-not-exist")
    assert response.status_code == 404
