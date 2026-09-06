# Upstream provenance

OfferLens started from [`langchain-ai/open_deep_research`](https://github.com/langchain-ai/open_deep_research), cloned at commit `1b7d2e80db9faa586165c60e09096dbbfd483a64`.

The original MIT copyright notice remains in [LICENSE](LICENSE). The upstream repository is configured locally as the `upstream` Git remote.

## What remains from upstream

- `src/open_deep_research/`: reference deep-research implementation
- `src/legacy/`: upstream historical graph variants
- upstream research benchmark examples under `tests/`
- the original Git history and MIT license

## What OfferLens adds or replaces

- a job-search domain model with strict Pydantic contracts
- a new LangGraph specialized for resume/JD analysis
- parallel resume and JD parsing
- dynamic company, role, interview, and market research fan-out
- local and live LangChain reasoners
- resume vector retrieval and exact evidence citations
- deterministic grounding and anti-fabrication quality gates
- LangGraph checkpointing and human interrupt/resume
- FastAPI, SSE execution events, and document upload
- a complete Next.js career intelligence interface
- an MCP server for external agents
- task-specific evaluation data and metrics
- independent CI, container, security, and learning documentation

This file is intentionally explicit so reviewers can distinguish upstream code from the work completed in this fork.
