"""HTTP and SSE interface for OfferLens."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from offerlens_agent import __version__
from offerlens_agent.api.manager import (
    AnalysisConflictError,
    AnalysisManager,
    AnalysisNotFoundError,
    AnalysisRecord,
)
from offerlens_agent.config import Settings, get_settings
from offerlens_agent.domain.models import AnalysisPreferences, AnalysisRequest, ApprovalDecision
from offerlens_agent.services.documents import ResumeExtractionError, extract_resume_text


class CreateAnalysisBody(BaseModel):
    resume_text: str = Field(min_length=20, max_length=120_000)
    job_description: str = Field(min_length=20, max_length=50_000)
    company: str = Field(min_length=1, max_length=120)
    job_title: str = Field(min_length=1, max_length=120)
    target_city: str | None = None
    target_salary: str | None = None

    def to_request(self) -> AnalysisRequest:
        return AnalysisRequest(
            resume_text=self.resume_text,
            job_description=self.job_description,
            company=self.company,
            job_title=self.job_title,
            preferences=AnalysisPreferences(target_city=self.target_city, target_salary=self.target_salary),
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    manager = AnalysisManager(runtime_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        runtime_settings.data_dir.mkdir(parents=True, exist_ok=True)
        await manager.start()
        try:
            yield
        finally:
            await manager.stop()

    application = FastAPI(
        title="OfferLens API",
        version=__version__,
        description="Evidence-grounded multi-agent career intelligence API",
        lifespan=lifespan,
    )
    application.state.manager = manager
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health")
    async def health() -> dict:
        return {"status": "ok", "version": __version__, "mode": runtime_settings.mode}

    @application.get("/api/v1/capabilities")
    async def capabilities() -> dict:
        return {
            "mode": runtime_settings.mode,
            "model": runtime_settings.model if runtime_settings.mode == "live" else None,
            "search_provider": runtime_settings.search_provider,
            "human_approval": runtime_settings.require_approval,
            "agents": [
                "Resume Analyst",
                "JD Analyst",
                "Research Supervisor",
                "Company Researcher",
                "Role Researcher",
                "Interview Researcher",
                "Market Researcher",
                "Resume RAG & Evidence Matcher",
                "Career Strategist",
                "Grounding Critic",
            ],
        }

    @application.post("/api/v1/analyses", status_code=status.HTTP_202_ACCEPTED)
    async def create_analysis(body: CreateAnalysisBody) -> dict:
        return manager.create(body.to_request()).public()

    @application.post("/api/v1/analyses/upload", status_code=status.HTTP_202_ACCEPTED)
    async def create_analysis_from_upload(
        resume: UploadFile = File(...),
        job_description: str = Form(..., min_length=20, max_length=50_000),
        company: str = Form(..., min_length=1, max_length=120),
        job_title: str = Form(..., min_length=1, max_length=120),
        target_city: str | None = Form(default=None),
        target_salary: str | None = Form(default=None),
    ) -> dict:
        try:
            resume_text = extract_resume_text(
                resume.filename or "resume.txt",
                await resume.read(runtime_settings.max_resume_bytes + 1),
                runtime_settings.max_resume_bytes,
            )
        except ResumeExtractionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        request = AnalysisRequest(
            resume_text=resume_text,
            job_description=job_description,
            company=company,
            job_title=job_title,
            preferences=AnalysisPreferences(target_city=target_city, target_salary=target_salary),
        )
        return manager.create(request).public()

    @application.get("/api/v1/analyses/{analysis_id}")
    async def get_analysis(analysis_id: str) -> dict:
        return _get_record(manager, analysis_id).public()

    @application.get("/api/v1/analyses/{analysis_id}/events")
    async def analysis_events(analysis_id: str) -> EventSourceResponse:
        record = _get_record(manager, analysis_id)

        async def generate() -> AsyncIterator[dict]:
            cursor = 0
            terminal = {"completed", "failed", "awaiting_approval"}
            while True:
                while cursor < len(record.events):
                    yield {"event": "agent", "data": json.dumps(record.events[cursor], ensure_ascii=False)}
                    cursor += 1
                if record.status in terminal:
                    yield {"event": "status", "data": json.dumps(record.public(), ensure_ascii=False)}
                    break
                yield {"event": "heartbeat", "data": json.dumps({"status": record.status})}
                await asyncio.sleep(0.25)

        return EventSourceResponse(generate())

    @application.post("/api/v1/analyses/{analysis_id}/decision", status_code=status.HTTP_202_ACCEPTED)
    async def decide_analysis(analysis_id: str, decision: ApprovalDecision) -> dict:
        try:
            return (await manager.decide(analysis_id, decision)).public()
        except AnalysisNotFoundError as exc:
            raise HTTPException(status_code=404, detail="analysis not found") from exc
        except AnalysisConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return application


def _get_record(manager: AnalysisManager, analysis_id: str) -> AnalysisRecord:
    try:
        return manager.get(analysis_id)
    except AnalysisNotFoundError as exc:
        raise HTTPException(status_code=404, detail="analysis not found") from exc


app = create_app()


def run() -> None:
    """Start the local API server from the project console script."""
    uvicorn.run("offerlens_agent.api.app:app", host="127.0.0.1", port=8000, reload=False)
