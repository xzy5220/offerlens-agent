# Learning guide

Read the project in this order after the product is running:

1. `domain/models.py` — understand the data contracts before the Agent logic.
2. `workflow/state.py` — identify shared state and reducers.
3. `workflow/graph.py` — trace edges, `Send`, conditional routing and `interrupt`.
4. `services/reasoner.py` — compare deterministic and LLM-backed implementations.
5. `services/retrieval.py` and `matcher.py` — separate RAG retrieval from evidence strength.
6. `services/quality.py` — see which rules are deterministic guardrails.
7. `api/manager.py` — learn checkpoint `thread_id`, background execution and resume.
8. `api/app.py` — follow REST, upload and SSE boundaries.
9. `evaluation/metrics.py` — understand how Agent behavior becomes testable.
10. `apps/web/app/page.tsx` — see how graph events become a product experience.

For each file, answer three interview questions:

- What failure does this component prevent?
- Why is this deterministic code or LLM reasoning?
- What would change when moving from a single machine to production?

The final production discussion should mention PostgreSQL checkpointers, object storage for encrypted resumes, authentication, retention policies, queue-based workers, rate limits, and a larger human-reviewed evaluation set. Those are deliberate deployment extensions, not features falsely claimed by the local demo.
