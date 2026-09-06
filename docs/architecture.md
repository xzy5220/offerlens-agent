# Architecture

## Design goals

OfferLens is designed around four properties that are easy to lose in an LLM demo:

1. **Grounding** — positive candidate claims must point to exact resume text.
2. **Observability** — every graph node emits a user-visible execution event.
3. **Recoverability** — graph state is checkpointed and human review can pause/resume a thread.
4. **Provider isolation** — the workflow does not depend on a particular model or search API.

## Graph topology

`create_graph()` in `src/offerlens_agent/workflow/graph.py` compiles the workflow. Its important LangGraph mechanisms are:

- two edges from `START` run resume and JD parsing in parallel;
- a list edge joins both results before research planning;
- the supervisor returns `Send` objects to create a variable number of research workers;
- `research_results` and `timeline` use annotated reducers to merge parallel writes;
- the critic conditionally routes to revision or approval;
- the approval node calls `interrupt()` and resumes through `Command(resume=...)`;
- the API assigns a stable `thread_id` and uses SQLite checkpointing.

## State ownership

| State field | Producer | Consumer |
|---|---|---|
| `candidate` | Resume Analyst | Career Strategist |
| `job` | JD Analyst | Supervisor, Evidence Matcher |
| `research_tasks` | Research Supervisor | dynamic research workers |
| `research_results` | research workers | Career Strategist |
| `assessments` | Resume RAG & Evidence Matcher | Strategist, Critic |
| `report` | Strategist / Reviser | Critic, Human Reviewer |
| `quality_review` | Grounding Critic | router, Human Reviewer |
| `timeline` | every node | SSE API and web UI |

Pydantic objects form the contracts between nodes. Extra fields are rejected to catch accidental schema drift.

## Reasoning boundary

`CareerReasoner` is the port used by graph nodes:

- `DemoReasoner` is deterministic and costs nothing. It is used by tests, CI, and live demos without credentials.
- `LangChainReasoner` uses `init_chat_model`, structured output and retry. It can be switched through environment configuration.

Even in live mode, three fields are protected from model rewriting: the numeric match score, exact resume assessments, and retrieved source list. They are produced by deterministic code and reattached after generation.

## Retrieval and evidence

The resume is split with LangChain's `RecursiveCharacterTextSplitter`. Chunks are embedded into `InMemoryVectorStore` with deterministic feature-hashing embeddings in demo mode. Exact skill evidence has priority; vector retrieval supplies related context but cannot by itself produce a strong match.

This separates two often-confused ideas:

- retrieval answers “which resume passage is relevant?”;
- the evidence policy answers “is that passage strong enough to support this claim?”

## Failure handling

- A failed research worker returns a marked, source-free finding and a warning; it never fabricates a substitute.
- Pydantic rejects malformed model output.
- LangChain retries structured output up to three times.
- the quality loop is bounded by `OFFERLENS_MAX_REVISIONS`;
- unsupported document types and oversized uploads fail before parsing;
- offline mode has no dependency on external APIs.

## Runtime views

The same graph can be used through three transports:

1. FastAPI/SSE for the web product;
2. LangGraph Studio through `langgraph.json`;
3. MCP stdio tools for another Agent client.
