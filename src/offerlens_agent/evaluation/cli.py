"""Command-line regression runner for the bundled evaluation dataset."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from offerlens_agent.config import Settings
from offerlens_agent.evaluation.metrics import ExpectedOutcome, evaluate_report
from offerlens_agent.workflow.graph import create_graph


async def run_dataset(dataset: Path) -> dict:
    graph = create_graph(settings=Settings(mode="demo", search_provider="fixture"))
    rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = []
    for row in rows:
        state = await graph.ainvoke({"request": row["input"]})
        metrics = evaluate_report(state["report"], ExpectedOutcome.model_validate(row["expected"]))
        results.append({"id": row["id"], **metrics.model_dump(), "overall_score": metrics.overall_score})

    summary = {
        "cases": len(results),
        "mean_score": round(sum(item["overall_score"] for item in results) / len(results), 4) if results else 0,
        "all_grounded": all(item["no_fabricated_resume_claims"] for item in results),
        "results": results,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OfferLens offline regression evaluation")
    parser.add_argument("--dataset", type=Path, default=Path("data/evals/career_cases.jsonl"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    summary = asyncio.run(run_dataset(args.dataset))
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
