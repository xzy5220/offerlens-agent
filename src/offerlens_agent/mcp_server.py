"""MCP tools that expose OfferLens to other agent applications."""

from __future__ import annotations

from offerlens_agent.domain.models import AnalysisRequest
from offerlens_agent.services.text_analysis import parse_job_profile
from offerlens_agent.workflow.graph import create_graph


def build_server():
    """Create the FastMCP server lazily so MCP remains an optional extra."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError('MCP support is optional. Install it with: pip install -e ".[mcp]"') from exc

    server = FastMCP("OfferLens", instructions="Evidence-grounded resume and job analysis tools")

    @server.tool()
    def extract_job_requirements(company: str, job_title: str, job_description: str) -> dict:
        """Extract normalized, weighted requirements from a job description."""
        profile = parse_job_profile(company, job_title, job_description)
        return profile.model_dump(mode="json")

    @server.tool()
    async def analyze_job_fit(
        resume_text: str,
        company: str,
        job_title: str,
        job_description: str,
    ) -> dict:
        """Run the complete multi-agent analysis and return a grounded career report."""
        request = AnalysisRequest(
            resume_text=resume_text,
            company=company,
            job_title=job_title,
            job_description=job_description,
        )
        result = await create_graph().ainvoke({"request": request})
        return {
            "report": result["report"].model_dump(mode="json"),
            "quality_review": result["quality_review"].model_dump(mode="json"),
            "timeline": result["timeline"],
        }

    return server


def main() -> None:
    """Run OfferLens over the standard MCP stdio transport."""
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
