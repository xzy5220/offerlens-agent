import type { Analysis } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export async function createAnalysis(payload: {
  resumeText: string;
  resumeFile: File | null;
  jobDescription: string;
  company: string;
  jobTitle: string;
}): Promise<Analysis> {
  let response: Response;
  if (payload.resumeFile) {
    const form = new FormData();
    form.set("resume", payload.resumeFile);
    form.set("job_description", payload.jobDescription);
    form.set("company", payload.company);
    form.set("job_title", payload.jobTitle);
    response = await fetch(`${API_URL}/api/v1/analyses/upload`, { method: "POST", body: form });
  } else {
    response = await fetch(`${API_URL}/api/v1/analyses`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resume_text: payload.resumeText,
        job_description: payload.jobDescription,
        company: payload.company,
        job_title: payload.jobTitle,
      }),
    });
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `创建分析失败 (${response.status})`);
  }
  return response.json();
}
