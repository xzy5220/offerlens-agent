"""Deterministic text analysis used for evidence grounding and demo mode."""

from __future__ import annotations

import re
from collections.abc import Iterable

from offerlens_agent.domain.models import (
    CandidateProfile,
    JobProfile,
    JobRequirement,
    ProjectExperience,
    RequirementPriority,
)

SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "Java": ("java",),
    "Go": ("golang", " go "),
    "JavaScript": ("javascript", "js"),
    "TypeScript": ("typescript", "ts"),
    "React": ("react", "react.js"),
    "Next.js": ("next.js", "nextjs"),
    "FastAPI": ("fastapi",),
    "Django": ("django",),
    "LangChain": ("langchain",),
    "LangGraph": ("langgraph",),
    "Agent": ("agent", "智能体"),
    "RAG": ("rag", "检索增强"),
    "MCP": ("mcp", "model context protocol"),
    "LLM": ("llm", "大模型"),
    "Prompt Engineering": ("prompt", "提示词"),
    "Tool Calling": ("tool calling", "function calling", "工具调用"),
    "Vector Database": ("vector database", "vector db", "向量数据库", "pgvector", "chroma", "milvus"),
    "PostgreSQL": ("postgresql", "postgres", "pgvector"),
    "Redis": ("redis",),
    "Docker": ("docker", "容器"),
    "Kubernetes": ("kubernetes", "k8s"),
    "Git": ("git", "github", "gitlab"),
    "CI/CD": ("ci/cd", "github actions", "持续集成"),
    "REST API": ("rest api", "restful", "接口开发"),
    "SSE": ("sse", "server-sent events"),
    "WebSocket": ("websocket",),
    "Pydantic": ("pydantic",),
    "SQL": ("sql", "mysql", "postgresql", "数据库"),
    "Testing": ("pytest", "unit test", "测试"),
    "LangSmith": ("langsmith", "agent eval", "智能体评测"),
}

_MUST_MARKERS = ("必须", "熟练", "精通", "required", "must", "至少", "年以上")
_NICE_MARKERS = ("优先", "加分", "preferred", "nice to have", "bonus")


def normalize_text(text: str) -> str:
    """Normalize whitespace without destroying line-level evidence."""
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line)


def extract_skills(text: str) -> list[str]:
    """Extract a stable skill vocabulary from Chinese or English text."""
    padded = f" {text.lower()} "
    found = [canonical for canonical, aliases in SKILL_ALIASES.items() if any(alias in padded for alias in aliases)]
    return sorted(found, key=str.casefold)


def evidence_lines(text: str, skill: str, limit: int = 3) -> list[str]:
    """Return exact resume lines that support a skill claim."""
    aliases = SKILL_ALIASES.get(skill, (skill.lower(),))
    matches: list[str] = []
    for line in normalize_text(text).splitlines():
        padded = f" {line.lower()} "
        if any(alias in padded for alias in aliases):
            matches.append(line[:500])
        if len(matches) == limit:
            break
    return matches


def _bullet_lines(text: str) -> list[str]:
    lines = normalize_text(text).splitlines()
    return [re.sub(r"^[\-•*\d.)、\s]+", "", line).strip() for line in lines if len(line.strip()) >= 4]


def parse_candidate_profile(text: str) -> CandidateProfile:
    """Create an evidence-preserving candidate profile for offline runs."""
    cleaned = normalize_text(text)
    lines = cleaned.splitlines()
    name = None
    if lines and len(lines[0]) <= 30 and not any(char.isdigit() for char in lines[0]):
        name = lines[0]

    projects: list[ProjectExperience] = []
    project_markers = ("项目", "project", "作品")
    for index, line in enumerate(lines):
        if any(marker in line.lower() for marker in project_markers):
            context = " ".join(lines[index : index + 4])
            projects.append(
                ProjectExperience(
                    name=line[:80],
                    description=context[:800],
                    technologies=extract_skills(context),
                    highlights=[item for item in lines[index + 1 : index + 4] if item],
                )
            )
            if len(projects) >= 5:
                break

    return CandidateProfile(
        name=name,
        summary="；".join(lines[:3])[:600],
        skills=extract_skills(cleaned),
        projects=projects,
        education=[
            line
            for line in lines
            if any(word in line.lower() for word in ("大学", "学院", "本科", "硕士", "bachelor", "master"))
        ][:5],
    )


def parse_job_profile(company: str, title: str, text: str) -> JobProfile:
    """Extract weighted, deduplicated requirements from a job description."""
    lines = _bullet_lines(text)
    requirements: list[JobRequirement] = []
    seen: set[str] = set()
    for line in lines:
        line_skills = extract_skills(line)
        for skill in line_skills:
            if skill in seen:
                continue
            lower = line.lower()
            is_nice = any(marker in lower for marker in _NICE_MARKERS)
            is_must = any(marker in lower for marker in _MUST_MARKERS)
            priority = RequirementPriority.NICE_TO_HAVE if is_nice else RequirementPriority.MUST_HAVE
            weight = 1.4 if is_must else (0.7 if is_nice else 1.0)
            requirements.append(
                JobRequirement(
                    id=f"req-{len(requirements) + 1}",
                    skill=skill,
                    description=line[:500],
                    priority=priority,
                    weight=weight,
                )
            )
            seen.add(skill)

    if not requirements:
        for index, line in enumerate(lines[:8], start=1):
            requirements.append(JobRequirement(id=f"req-{index}", skill=line[:50], description=line[:500], weight=1.0))

    return JobProfile(
        company=company,
        title=title,
        summary="；".join(lines[:4])[:800],
        responsibilities=lines[:8],
        requirements=requirements[:20],
    )


def unique_preserving_order(values: Iterable[str]) -> list[str]:
    """Deduplicate strings while retaining the first evidence order."""
    return list(dict.fromkeys(value for value in values if value))
