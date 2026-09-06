# Evaluation

OfferLens keeps a small, version-controlled regression set in `data/evals/career_cases.jsonl`. Each row contains:

- a resume, company, title, and JD;
- skills expected to be supported by the resume;
- skills expected to remain gaps.

## Metrics

| Metric | Why it matters |
|---|---|
| `skill_recall` | Does the system find relevant candidate strengths? |
| `gap_recall` | Does it avoid hiding missing job requirements? |
| `evidence_coverage` | Is every positive or partial claim tied to resume text? |
| `citation_coverage` | Are company insights tied to research sources? |
| `no_fabricated_resume_claims` | Did suggestions avoid inventing candidate experience? |

Run the deterministic suite:

```powershell
offerlens-eval --dataset data/evals/career_cases.jsonl
```

Write machine-readable results:

```powershell
offerlens-eval --dataset data/evals/career_cases.jsonl --output artifacts/eval.json
```

## LangSmith

Set `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT` to record live graph traces. The deterministic metrics remain the release gate; model-as-judge experiments can be added for answer usefulness and interview-question quality without replacing grounding checks.

## Adding a case

Add one JSONL row, then run both `pytest` and `offerlens-eval`. Prefer cases that expose a known failure mode: aliases, mixed Chinese/English JDs, weak evidence, or a resume that is strong in backend engineering but weak in Agent orchestration.
