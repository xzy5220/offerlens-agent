"use client";

import {
  ArrowRight,
  Bot,
  BriefcaseBusiness,
  Check,
  ChevronRight,
  CircleAlert,
  FileText,
  Github,
  LoaderCircle,
  Radar,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  Upload,
} from "lucide-react";
import { useMemo, useState } from "react";

import { API_URL, createAnalysis } from "@/lib/api";
import type { AgentEvent, Analysis, CareerReport } from "@/lib/types";

const SAMPLE_RESUME = `张三
计算机科学与技术本科

项目经历
ServiceOps Agent：使用 Python、FastAPI 和 Pydantic 构建工单处理服务，编写 pytest 自动化测试，并通过 GitHub Actions 完成持续集成。
个人知识库：使用 LangChain 和 RAG 完成文档检索与问答，使用 Docker 部署。

技能
Python、FastAPI、LangChain、RAG、Docker、Git、SQL`;

const SAMPLE_JD = `Agent 开发工程师
1. 熟练使用 Python，能够使用 FastAPI 开发后端服务；
2. 熟悉 LangChain、LangGraph、多智能体编排和 Tool Calling；
3. 掌握 RAG、向量数据库及检索效果评测；
4. 熟悉 Redis、PostgreSQL、Docker 和 CI/CD；
5. 有 LangSmith、MCP 或生产级 Agent 项目经验者优先。`;

const RECOMMENDATION_LABELS: Record<CareerReport["recommendation"], string> = {
  strong_apply: "强烈建议投递",
  apply: "建议投递",
  prepare_then_apply: "准备后投递",
  low_fit: "当前匹配较低",
};

export default function Home() {
  const [company, setCompany] = useState("示例科技");
  const [jobTitle, setJobTitle] = useState("Agent 开发工程师");
  const [resumeText, setResumeText] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"overview" | "evidence" | "interview">("overview");

  const isRunning = analysis?.status === "queued" || analysis?.status === "running";

  async function runAnalysis() {
    setError("");
    setEvents([]);
    setAnalysis(null);
    try {
      const created = await createAnalysis({ resumeText, resumeFile, jobDescription, company, jobTitle });
      setAnalysis(created);
      const source = new EventSource(`${API_URL}/api/v1/analyses/${created.id}/events`);
      source.addEventListener("agent", (raw) => {
        const event = JSON.parse((raw as MessageEvent).data) as AgentEvent;
        setEvents((current) => [...current, event]);
      });
      source.addEventListener("status", (raw) => {
        setAnalysis(JSON.parse((raw as MessageEvent).data) as Analysis);
        source.close();
      });
      source.onerror = () => {
        setError("与 Agent 事件流的连接中断，请确认后端服务已启动。");
        source.close();
      };
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "分析启动失败");
    }
  }

  function loadSample() {
    setResumeFile(null);
    setResumeText(SAMPLE_RESUME);
    setJobDescription(SAMPLE_JD);
    setCompany("示例科技");
    setJobTitle("Agent 开发工程师");
  }

  const canSubmit = company.trim() && jobTitle.trim() && jobDescription.length >= 20 && (resumeFile || resumeText.length >= 20);

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#">
          <span className="brand-mark"><Radar size={19} /></span>
          <span>OfferLens</span>
          <span className="beta">AGENT LAB</span>
        </a>
        <div className="topbar-meta">
          <span className="mode"><span /> Evidence-grounded</span>
          <a href="https://github.com/xzy5220" target="_blank" rel="noreferrer"><Github size={18} /></a>
        </div>
      </header>

      <section className="hero">
        <div className="eyebrow"><Sparkles size={14} /> LANGGRAPH MULTI-AGENT CAREER INTELLIGENCE</div>
        <h1>别只问“我适合吗？”<br /><em>让证据回答。</em></h1>
        <p>上传简历和岗位描述，10 个专业 Agent 并行完成岗位拆解、公司研究、能力匹配和面试准备。</p>
      </section>

      <section className="workspace">
        <div className="input-panel panel">
          <div className="panel-heading">
            <div><span className="step-number">01</span><h2>创建岗位分析</h2></div>
            <button className="text-button" onClick={loadSample}>载入演示数据</button>
          </div>

          <div className="two-columns">
            <label>目标公司<input value={company} onChange={(event) => setCompany(event.target.value)} placeholder="例如：字节跳动" /></label>
            <label>岗位名称<input value={jobTitle} onChange={(event) => setJobTitle(event.target.value)} placeholder="例如：Agent 开发工程师" /></label>
          </div>

          <label>简历</label>
          <div className="upload-row">
            <label className="upload-button"><Upload size={16} />选择 PDF / DOCX / TXT<input type="file" accept=".pdf,.docx,.txt,.md" onChange={(event) => setResumeFile(event.target.files?.[0] ?? null)} /></label>
            <span>{resumeFile?.name ?? "也可以直接粘贴简历文本"}</span>
          </div>
          {!resumeFile && <textarea className="resume-input" value={resumeText} onChange={(event) => setResumeText(event.target.value)} placeholder="粘贴你的简历内容…" />}

          <label>岗位描述（JD）<textarea value={jobDescription} onChange={(event) => setJobDescription(event.target.value)} placeholder="粘贴完整的岗位职责和任职要求…" /></label>

          {error && <div className="error-box"><CircleAlert size={16} />{error}</div>}
          <button className="primary-button" disabled={!canSubmit || isRunning} onClick={runAnalysis}>
            {isRunning ? <><LoaderCircle className="spin" size={18} />Agent 团队分析中</> : <><Sparkles size={18} />开始深度分析<ArrowRight size={18} /></>}
          </button>
          <p className="privacy-note"><ShieldCheck size={14} />简历仅发送到本地 OfferLens API；离线演示模式不调用外部模型。</p>
        </div>

        <AgentTimeline events={events} running={Boolean(isRunning)} />
      </section>

      {analysis?.status === "failed" && <section className="failure panel"><CircleAlert />{analysis.error}</section>}
      {analysis?.report && <ReportView report={analysis.report} analysis={analysis} activeTab={activeTab} setActiveTab={setActiveTab} />}

      <footer><span>OfferLens / Built with LangGraph + LangChain</span><span>Every match needs evidence.</span></footer>
    </main>
  );
}

function AgentTimeline({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const activeAgent = events.at(-1)?.agent;
  return (
    <aside className="agent-panel panel">
      <div className="panel-heading">
        <div><span className="step-number">02</span><h2>Agent 执行轨迹</h2></div>
        <span className={`status-pill ${running ? "running" : ""}`}>{running ? "LIVE" : events.length ? "DONE" : "READY"}</span>
      </div>
      <div className="graph-summary">
        <div><Bot size={18} /><strong>Supervisor Graph</strong></div>
        <span>动态并行 · 状态持久化 · 质量循环</span>
      </div>
      <div className="timeline">
        {!events.length && <div className="empty-state"><Search size={25} /><p>开始分析后，这里会实时显示<br />每个 Agent 的工作和交接。</p></div>}
        {events.map((event, index) => (
          <div className="timeline-item" key={`${event.node}-${index}`}>
            <span className={`timeline-dot ${event.status}`}>{event.status === "completed" ? <Check size={12} /> : <CircleAlert size={12} />}</span>
            <div><strong>{event.agent}</strong><p>{event.message}</p><code>{event.node}</code></div>
          </div>
        ))}
        {running && activeAgent && <div className="working"><LoaderCircle className="spin" size={15} />等待下一位 Agent 完成…</div>}
      </div>
    </aside>
  );
}

function ReportView({ report, analysis, activeTab, setActiveTab }: { report: CareerReport; analysis: Analysis; activeTab: "overview" | "evidence" | "interview"; setActiveTab: (tab: "overview" | "evidence" | "interview") => void }) {
  const circumference = 2 * Math.PI * 52;
  const quality = analysis.quality_review;
  return (
    <section className="report-section">
      <div className="report-title"><div><span className="step-number">03</span><h2>求职决策报告</h2></div><span className="generated"><Check size={14} /> Grounding check passed</span></div>
      <div className="score-card panel">
        <div className="score-ring">
          <svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="52" /><circle className="score-progress" cx="60" cy="60" r="52" style={{ strokeDasharray: circumference, strokeDashoffset: circumference * (1 - report.match_score / 100) }} /></svg>
          <div><strong>{report.match_score}</strong><span>匹配分</span></div>
        </div>
        <div className="score-copy"><span className="recommendation">{RECOMMENDATION_LABELS[report.recommendation]}</span><h3>{report.company} · {report.job_title}</h3><p>{report.executive_summary}</p></div>
        <div className="quality-metrics">
          <Metric label="证据覆盖" value={quality ? `${Math.round(quality.evidence_coverage * 100)}%` : "—"} />
          <Metric label="引用覆盖" value={quality ? `${Math.round(quality.citation_coverage * 100)}%` : "—"} />
          <Metric label="可追溯来源" value={String(report.sources.length)} />
        </div>
      </div>

      <div className="tabs">
        <button className={activeTab === "overview" ? "active" : ""} onClick={() => setActiveTab("overview")}>决策概览</button>
        <button className={activeTab === "evidence" ? "active" : ""} onClick={() => setActiveTab("evidence")}>逐项证据</button>
        <button className={activeTab === "interview" ? "active" : ""} onClick={() => setActiveTab("interview")}>面试作战室</button>
      </div>

      {activeTab === "overview" && <Overview report={report} />}
      {activeTab === "evidence" && <EvidenceView report={report} />}
      {activeTab === "interview" && <InterviewView report={report} />}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function Overview({ report }: { report: CareerReport }) {
  return <div className="report-grid">
    <article className="report-card panel"><div className="card-icon mint"><Target size={18} /></div><h3>已验证优势</h3><div className="tag-list">{report.strengths.map((item) => <span className="tag positive" key={item}><Check size={12} />{item}</span>)}</div></article>
    <article className="report-card panel"><div className="card-icon amber"><CircleAlert size={18} /></div><h3>优先能力缺口</h3><ul>{report.gaps.slice(0, 5).map((item) => <li key={item}><ChevronRight size={14} />{item}</li>)}</ul></article>
    <article className="report-card panel wide"><div className="card-icon violet"><BriefcaseBusiness size={18} /></div><h3>公司与岗位洞察</h3><ul>{report.company_insights.map((item) => <li key={item}><ChevronRight size={14} />{item}</li>)}</ul></article>
    <article className="report-card panel wide"><div className="card-icon blue"><FileText size={18} /></div><h3>7 天行动计划</h3><div className="day-grid">{report.seven_day_plan.map((item, index) => <div key={item}><span>D{index + 1}</span><p>{item.replace(/^第\d天：/, "")}</p></div>)}</div></article>
  </div>;
}

function EvidenceView({ report }: { report: CareerReport }) {
  const sorted = useMemo(() => [...report.requirement_assessments].sort((a, b) => b.score - a.score), [report]);
  return <div className="evidence-list">{sorted.map((item) => <article className="evidence-row panel" key={item.requirement_id}>
    <div className={`score-chip ${item.strength}`}>{Math.round(item.score * 100)}</div>
    <div className="evidence-main"><div><h3>{item.requirement}</h3><span className={`strength ${item.strength}`}>{item.strength === "strong" ? "强证据" : item.strength === "partial" ? "部分证据" : "缺少证据"}</span></div>
      {item.evidence.length ? item.evidence.map((evidence) => <blockquote key={evidence.source_id}>“{evidence.quote}”<cite>{evidence.source_id}</cite></blockquote>) : <p className="gap-text">{item.gap}</p>}
    </div>
  </article>)}</div>;
}

function InterviewView({ report }: { report: CareerReport }) {
  return <div className="interview-layout"><div className="question-list">{report.interview_questions.map((item, index) => <article className="question panel" key={`${item.question}-${index}`}><span>Q{String(index + 1).padStart(2, "0")}</span><div><small>{item.category}</small><h3>{item.question}</h3><p>{item.why_asked}</p><div className="outline">{item.answer_outline.map((point) => <em key={point}>{point}</em>)}</div></div></article>)}</div>
    <aside className="source-panel panel"><h3>研究来源</h3>{report.sources.map((source) => <a className={!source.url ? "disabled" : ""} href={source.url ?? undefined} target="_blank" rel="noreferrer" key={source.id}><Search size={14} /><span><strong>{source.title}</strong><small>{source.source_type}</small></span></a>)}</aside>
  </div>;
}
