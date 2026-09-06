"""In-process analysis coordinator with LangGraph checkpoint/resume support."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, cast

import aiosqlite
from fastapi.encoders import jsonable_encoder
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from offerlens_agent.config import Settings
from offerlens_agent.domain.models import AnalysisRequest, ApprovalDecision
from offerlens_agent.workflow.graph import create_graph

AnalysisStatus = Literal["queued", "running", "awaiting_approval", "completed", "failed"]

_CHECKPOINT_TYPES = [
    ("offerlens_agent.domain.models", name)
    for name in (
        "AnalysisPreferences",
        "AnalysisRequest",
        "ApprovalDecision",
        "CandidateProfile",
        "CareerReport",
        "Evidence",
        "EvidenceStrength",
        "InterviewQuestion",
        "JobProfile",
        "JobRequirement",
        "ProjectExperience",
        "QualityReview",
        "RequirementAssessment",
        "RequirementPriority",
        "ResearchFinding",
        "ResearchPlan",
        "ResearchTask",
        "ResumeSuggestion",
        "Source",
        "WorkExperience",
    )
]


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class AnalysisRecord:
    id: str
    request: AnalysisRequest
    status: AnalysisStatus = "queued"
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    events: list[dict[str, Any]] = field(default_factory=list)
    report: dict[str, Any] | None = None
    quality_review: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    interrupt: dict[str, Any] | None = None

    def public(self) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            jsonable_encoder(
                {
                    "id": self.id,
                    "status": self.status,
                    "created_at": self.created_at,
                    "updated_at": self.updated_at,
                    "report": self.report,
                    "quality_review": self.quality_review,
                    "warnings": self.warnings,
                    "error": self.error,
                    "interrupt": self.interrupt,
                },
            ),
        )


class AnalysisNotFoundError(KeyError):
    """Raised when an API request references an unknown analysis."""


class AnalysisConflictError(RuntimeError):
    """Raised when a transition is invalid for the current analysis state."""


class AnalysisManager:
    """Own active graph runs and expose their node events to HTTP clients."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._serializer = JsonPlusSerializer(allowed_msgpack_modules=_CHECKPOINT_TYPES)
        self._checkpointer: BaseCheckpointSaver = MemorySaver(serde=self._serializer)
        self._graph = create_graph(settings=settings, checkpointer=self._checkpointer)
        self._records: dict[str, AnalysisRecord] = {}
        self._sqlite_connection: aiosqlite.Connection | None = None

    async def start(self) -> None:
        """Initialize durable local checkpointing when configured."""
        if self._settings.checkpoint_backend != "sqlite" or self._sqlite_connection is not None:
            return
        self._settings.data_dir.mkdir(parents=True, exist_ok=True)
        connection = await aiosqlite.connect(self._settings.data_dir / "checkpoints.sqlite")
        checkpointer = AsyncSqliteSaver(connection, serde=self._serializer)
        await checkpointer.setup()
        self._sqlite_connection = connection
        self._checkpointer = checkpointer
        self._graph = create_graph(settings=self._settings, checkpointer=checkpointer)

    async def stop(self) -> None:
        """Close persistence resources during application shutdown."""
        if self._sqlite_connection is not None:
            await self._sqlite_connection.close()
            self._sqlite_connection = None

    def create(self, request: AnalysisRequest) -> AnalysisRecord:
        analysis_id = uuid.uuid4().hex
        record = AnalysisRecord(id=analysis_id, request=request)
        self._records[analysis_id] = record
        asyncio.create_task(self._execute(record, {"request": request}))
        return record

    def get(self, analysis_id: str) -> AnalysisRecord:
        try:
            return self._records[analysis_id]
        except KeyError as exc:
            raise AnalysisNotFoundError(analysis_id) from exc

    async def decide(self, analysis_id: str, decision: ApprovalDecision) -> AnalysisRecord:
        record = self.get(analysis_id)
        if record.status != "awaiting_approval":
            raise AnalysisConflictError(f"analysis is {record.status}, not awaiting approval")
        asyncio.create_task(self._execute(record, Command(resume=decision.model_dump(mode="json"))))
        return record

    async def _execute(self, record: AnalysisRecord, graph_input: dict | Command) -> None:
        record.status = "running"
        record.interrupt = None
        record.updated_at = _now()
        config = {"configurable": {"thread_id": record.id}}
        try:
            async for update in self._graph.astream(graph_input, config=config, stream_mode="updates"):
                self._capture_update(record, update)

            snapshot = await self._graph.aget_state(config)
            interrupts = [item for task in snapshot.tasks for item in task.interrupts]
            if interrupts:
                record.status = "awaiting_approval"
                record.interrupt = jsonable_encoder(interrupts[0].value)
            else:
                values = snapshot.values
                record.report = jsonable_encoder(values.get("report"))
                record.quality_review = jsonable_encoder(values.get("quality_review"))
                record.warnings = list(values.get("warnings", []))
                record.status = "completed"
        except Exception as exc:
            record.status = "failed"
            record.error = f"{type(exc).__name__}: {exc}"
            record.events.append({"node": "workflow", "agent": "Runtime", "status": "failed", "message": record.error})
        finally:
            record.updated_at = _now()

    @staticmethod
    def _capture_update(record: AnalysisRecord, update: dict[str, Any]) -> None:
        for value in update.values():
            if not isinstance(value, dict):
                continue
            for event in value.get("timeline", []):
                encoded = jsonable_encoder(event)
                if encoded not in record.events:
                    record.events.append(encoded)
            for warning in value.get("warnings", []):
                if warning not in record.warnings:
                    record.warnings.append(str(warning))
        record.updated_at = _now()
