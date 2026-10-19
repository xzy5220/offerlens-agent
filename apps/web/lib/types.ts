export type AgentEvent = {
  node: string;
  agent: string;
  status: "completed" | "failed" | "needs_revision" | string;
  message: string;
};

export type Evidence = {
  claim: string;
  quote: string;
  source_id: string;
  source_type: string;
};

export type RequirementAssessment = {
  requirement_id: string;
  requirement: string;
  score: number;
  strength: "strong" | "partial" | "missing";
  evidence: Evidence[];
  gap: string | null;
};

export type Source = {
  id: string;
  title: string;
  url: string | null;
  snippet: string;
  source_type: string;
};

export type CareerReport = {
  company: string;
  job_title: string;
  match_score: number;
  recommendation: "strong_apply" | "apply" | "prepare_then_apply" | "low_fit";
  executive_summary: string;
  strengths: string[];
  gaps: string[];
  requirement_assessments: RequirementAssessment[];
  company_insights: string[];
  resume_suggestions: Array<{ section: string; current_evidence: string; suggestion: string; reason: string }>;
  interview_questions: Array<{
    category: string;
    question: string;
    why_asked: string;
    answer_outline: string[];
    evidence_ids: string[];
  }>;
  seven_day_plan: string[];
  sources: Source[];
  caveats: string[];
};

export type Analysis = {
  id: string;
  status: "queued" | "running" | "awaiting_approval" | "completed" | "failed";
  report: CareerReport | null;
  quality_review: { passed: boolean; citation_coverage: number; evidence_coverage: number; issues: string[] } | null;
  warnings: string[];
  error: string | null;
};
