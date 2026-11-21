import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const reviews = "/api/v1/reviews";
function rememberRun(id: string) {
  const url = new URL(window.location.href);
  url.searchParams.set("run", id);
  window.history.replaceState(null, "", url);
}
const active = ["queued", "ingesting", "reviewing", "synthesizing"];
const sections = [
  ["strength", "Strengths"],
  ["limitation", "Limitations"],
  ["closest_work", "Closest work"],
] as const;
const labels: Record<string, string> = {
  queued: "Queued", ingesting: "Building evidence", reviewing: "Specialists reviewing",
  synthesizing: "Preparing report", completed: "Completed", failed: "Failed", cancelled: "Cancelled",
};
const paperStages = [
  ["queue", "Wait for worker"], ["extract", "Read paper"], ["retrieve", "Search prior work"],
  ["novelty", "Review novelty and contribution"], ["methodology", "Review methodology"],
  ["dataset", "Review datasets and evidence"], ["critique", "Challenge and close findings"], ["synthesis", "Rank revisions"], ["publish", "Validate and save report"],
] as const;
const legacyStage: Record<string, string> = {
  queued: "queue", ingesting: "extract", reviewing: "novelty", synthesizing: "synthesis",
};
const coverage: Record<string, string> = {
  abstracts_only: "Literature coverage is limited to retrieved arXiv abstracts.",
  no_results: "arXiv returned no eligible work for this query and cutoff.",
  provider_unavailable: "arXiv was unavailable. The review used submission evidence.",
};

type Run = {
  id: string; question: string; mode: string; status?: string; report_version?: number; error?: string;
  stage?: string; stage_started_at?: string; activity?: string; created_at?: string;
  can_retry?: boolean;
};
type Citation = { passage_id: string; locator: string; quote: string; char_start: number; char_end: number };
type Finding = {
  id: string; role: string; category: string; assessment: string; status: string;
  uncertainty: string; revision: string; citations: Citation[];
};
type Report = {
  critique?: { original: Finding; final: Finding; challenge: string; reply_action: string; reply_reason: string; disposition: string }[];
  version: number; summary: string; coverage: string; findings: Finding[]; prioritized_revisions: string[];
};
type Passage = { title: string; locator: string; text: string; url: string; char_start: number };

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "The request could not be completed.");
  return data;
}

function PaperReport({ run, report }: { run: Run; report: Report }) {
  const base = `${reviews}/${run.id}`;
  const version = `version=${report.version}`;
  const [opened, setOpened] = useState<{ passage: Passage; citation: Citation } | null>(null);
  const passagePanel = useRef<HTMLElement>(null);
  useEffect(() => { if (opened) passagePanel.current?.focus(); }, [opened]);
  const [error, setError] = useState("");
  async function open(citation: Citation) {
    setError("");
    setOpened(null);
    try {
      const { passage } = await request<{ passage: Passage }>(
        `${base}/passages/${citation.passage_id}?${version}`,
      );
      setOpened({ passage, citation });
    } catch (err) {
      setError((err as Error).message);
    }
  }
  const example = report.critique?.find((entry) => entry.disposition === "revised") || report.critique?.[0];
  const byId = new Map(report.findings.map((finding) => [finding.id, finding]));
  return (
    <>
      <p>{report.summary}</p>
      <p className="warning">{coverage[report.coverage]}</p>
      <nav className="exports" aria-label="Report downloads">
        <a href={`${base}/report.json?${version}`}>Download JSON</a>
        <a href={`${base}/report.md?${version}`}>Download Markdown</a>
        <span>Version {report.version}</span>
      </nav>
      {error && <p role="alert">{error}</p>}
      {opened && (
        <section ref={passagePanel} tabIndex={-1} className="passage" aria-label="Cited passage">
          <button type="button" onClick={() => setOpened(null)}>Close passage</button>
          <h3>{opened.passage.title} · {opened.passage.locator}</h3>
          <p>Characters {opened.citation.char_start}–{opened.citation.char_end}</p>
          <blockquote>
            {Array.from(opened.passage.text).slice(0, opened.citation.char_start - opened.passage.char_start).join("")}
            <mark>{opened.citation.quote}</mark>
            {Array.from(opened.passage.text).slice(opened.citation.char_end - opened.passage.char_start).join("")}
          </blockquote>
          {opened.passage.url && <a href={opened.passage.url}>Open source</a>}
        </section>
      )}
      {example && (
        <section className="finding" aria-label="Finding before and after critique">
          <h3>Finding before and after critique</h3>
          <p>{example.original.role} ? {example.disposition}</p>
          <dl>
            <dt>Before</dt><dd>{example.original.assessment}</dd>
            <dt>Challenge</dt><dd>{example.challenge}</dd>
            <dt>Specialist response ({example.reply_action})</dt><dd>{example.reply_reason}</dd>
            <dt>After</dt><dd>{example.final.assessment}</dd>
          </dl>
        </section>
      )}
      {sections.map(([category, heading]) => {
        const findings = report.findings.filter((finding) => finding.category === category);
        return (
          <section key={category}>
            <h3>{heading}</h3>
            {findings.length === 0 && <p>No findings recorded.</p>}
            {findings.map((finding) => (
              <div className="finding" key={finding.id}>
                <strong>{finding.role} · {finding.status}</strong>
                <p>{finding.assessment}</p>
                {finding.uncertainty && <p className="warning">{finding.uncertainty}</p>}
                {finding.citations.map((citation) => (
                  <button className="citation" type="button" key={`${citation.passage_id}:${citation.char_start}:${citation.char_end}`} onClick={() => void open(citation)}>
                    Open cited passage · {citation.locator}
                  </button>
                ))}
              </div>
            ))}
          </section>
        );
      })}
      <h3>Prioritized revisions</h3>
      {report.prioritized_revisions.length ? (
        <ol>{report.prioritized_revisions.map((id) => <li key={id}>{byId.get(id)?.revision}</li>)}</ol>
      ) : <p>No revisions proposed.</p>}
    </>
  );
}

type LegacyReport = { warnings?: string[]; reviews?: Record<string, { findings: { assessment: string; quote: string; action: string }[] }> };

function ReviewProgress({ run, connected }: { run: Run; connected: boolean }) {
  const running = active.includes(run.status || "");
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [running]);
  const finished = run.status === "completed";
  const current = finished ? paperStages.length : paperStages.findIndex(([key]) => key === (run.stage || legacyStage[run.status || ""]));
  const started = Date.parse(run.stage_started_at || run.created_at || "");
  const seconds = Math.max(0, Math.floor((now - started) / 1000));
  return (
    <section className="review-progress" aria-label="Review progress">
      <h3>Review progress</h3>
      <ol>
        {paperStages.map(([key, label], i) => {
          const state = i < current ? "Done" : i !== current ? "Waiting" : running ? "In progress" : "Stopped";
          return <li key={key} aria-current={i === current ? "step" : undefined}><span>{label}</span><span>{state}</span></li>;
        })}
      </ol>
      <p role="status">
        {finished ? "Report saved." : run.activity || (running && current >= 0 ? paperStages[current][1] + " in progress." : "Review stopped.")}
      </p>
      {running && Number.isFinite(seconds) && <p>{Math.floor(seconds / 60)}m {seconds % 60}s in this stage</p>}
      {running && seconds >= 300 && connected && <p role="alert">This stage has taken longer than expected. Check History for a completed review.</p>}
    </section>
  );
}

function App() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [legacy, setLegacy] = useState<LegacyReport | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reportError, setReportError] = useState("");
  const [reportAttempt, setReportAttempt] = useState(0);
  const userSelected = useRef(false);
  const [tab, setTab] = useState("review");
  const refresh = () => request<Run[]>(reviews).then(setRuns).catch(() => {});
  useEffect(() => {
    let stopped = false;
    void request<Run[]>(reviews).then(async (items) => {
      if (stopped) return;
      setRuns(items);
      const selected = new URLSearchParams(window.location.search).get("run");
      const latestPaper = items.find((item) => item.mode === "paper" && item.status);
      const id = selected || latestPaper?.id;
      if (!id || userSelected.current) return;
      const latest = await request<Run>(`${reviews}/${encodeURIComponent(id)}`);
      if (!stopped && !userSelected.current) setRun(latest);
    }).catch(() => {});
    return () => { stopped = true; };
  }, []);

  useEffect(() => {
    if (!run?.status) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    if (active.includes(run.status)) {
      const poll = async () => {
        try {
          const next = await request<Run>(`${reviews}/${run.id}`);
          if (!stopped) {
            setError("");
            setRun(next);
          }
        } catch (err) {
          if (!stopped) {
            setError((err as Error).message);
            timer = setTimeout(poll, 1500);
          }
        }
      };
      timer = setTimeout(poll, 1000);
    } else if (run.status === "completed") {
      setReportError("");
      void request<Report>(`${reviews}/${run.id}/report?version=${run.report_version}`)
        .then((data) => { if (!stopped) setReport(data); })
        .catch(() => { if (!stopped) setReportError("The review finished, but the report could not be loaded."); });
      void refresh();
    } else if (run.status === "failed") {
      void refresh();
    }
    return () => { stopped = true; clearTimeout(timer); };
  }, [run, reportAttempt]);

  const dispatchKey = useRef<string | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    userSelected.current = true;
    setReportError("");
    setError("");
    setReport(null);
    setLegacy(null);
    setRun(null);
    setBusy(true);
    const form = new FormData(event.currentTarget);
    if (!(form.get("pdf") as File)?.size) form.delete("pdf");
    try {
      dispatchKey.current ??= crypto.randomUUID();
      const next = await request<Run & LegacyReport>(reviews, {
        method: "POST", body: form, headers: { "Idempotency-Key": dispatchKey.current },
      });
      dispatchKey.current = null;
      setRun(next);
      rememberRun(next.id);
      if (next.reviews) setLegacy(next);
      void refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function select(id: string) {
    userSelected.current = true;
    setReportError("");
    setError("");
    try {
      const next = await request<Run & LegacyReport>(`${reviews}/${id}`);
      setReport(null);
      setLegacy(next.reviews ? next : null);
      setRun(next);
      rememberRun(next.id);
      setTab("review");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function updateReview(runId: string, action: "retry" | "cancel") {
    setBusy(true);
    setError("");
    try {
      const next = await request<Run>(`${reviews}/${runId}/${action}`, { method: "POST" });
      setRun((current) => current?.id === runId ? next : current);
      void refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shell">
      <aside>
        <div className="brand">PaperLens</div>
        {["review", "library", "drafts", "history"].map((name) => (
          <button key={name} className={tab === name ? "active" : ""} onClick={() => setTab(name)}>{name}</button>
        ))}
      </aside>
      <main>
        <header>
          <h1>{tab === "review" ? "Review with evidence" : tab[0].toUpperCase() + tab.slice(1)}</h1>
          {tab === "review" && <span className="status" role="status">
            {busy ? "Submitting" : run?.status ? labels[run.status] || run.status : "Ready"}
          </span>}
        </header>
        {error && <p role="alert">{error}</p>}
        {tab === "review" && (
          <section className="grid">
            <form onSubmit={submit} onChange={() => { dispatchKey.current = null; }}>
              <label>Workflow<select name="mode"><option value="paper">Review a paper</option><option value="idea">Explore an idea</option></select></label>
              <label>Paper PDF<input type="file" name="pdf" accept="application/pdf" /></label>
              <label>Paper text or idea<textarea name="text" rows={8} maxLength={150000} /></label>
              <label>Research question or search terms<input name="question" maxLength={500} /></label>
              <label>Literature cutoff<input type="date" name="cutoff" defaultValue={new Date().toISOString().slice(0, 10)} required /></label>
              <button className="primary" disabled={busy || active.includes(run?.status || "")}>Run analysis</button>
            </form>
            <article>
              {run && <h2>{run.question}</h2>}
              {run?.error && <p role="alert">{run.error}</p>}
              {run?.mode === "paper" && active.includes(run.status || "") &&
                <button type="button" disabled={busy} onClick={() => void updateReview(run.id, "cancel")}>Cancel review</button>}
              {run?.can_retry && <button type="button" className="citation" disabled={busy} onClick={() => void updateReview(run.id, "retry")}>Retry using saved evidence</button>}
              {run?.mode === "paper" && (active.includes(run.status || "") || run.status === "failed") &&
                <ReviewProgress run={run} connected={!error} />}
              {run?.mode === "paper" && run.status === "completed" &&
                <details><summary>Review finished · View stages</summary><ReviewProgress run={run} connected /></details>}
              {active.includes(run?.status || "") && error && <p>Status connection interrupted. Reconnecting automatically.</p>}
              {run?.status === "completed" && !report && (reportError ?
                <div role="alert">{reportError} <button type="button" onClick={() => setReportAttempt((value) => value + 1)}>Reload report</button></div>
                : <p>Loading saved report…</p>)}
              {report && run && <PaperReport key={run.id} run={run} report={report} />}
              {legacy && <>
                {legacy.warnings?.map((warning) => <p className="warning" key={warning}>{warning}</p>)}
                {Object.entries(legacy.reviews || {}).map(([name, review]) => (
                  <section key={name}><h3>{name}</h3>{review.findings.map((finding, index) => (
                    <div className="finding" key={index}><strong>{finding.assessment}</strong><blockquote>{finding.quote}</blockquote><p>{finding.action}</p></div>
                  ))}</section>
                ))}
              </>}
              {!run && <div className="empty">Submit a PDF or paste paper text to begin a review.</div>}
            </article>
          </section>
        )}
        {tab === "history" && <section className="cards">
          {runs.map((item) => <button key={item.id} onClick={() => void select(item.id)}><b>{item.question}</b><span>{item.mode} · {item.status || "saved"}</span></button>)}
        </section>}
        {tab === "library" && <Library />}
        {tab === "drafts" && <div className="empty wide">Add sources to the library before drafting related work.</div>}
      </main>
    </div>
  );
}

function Library() {
  const [items, setItems] = useState<{ id: string; title: string }[]>([]);
  useEffect(() => { void request<typeof items>("/api/v1/library/papers").then(setItems).catch(() => {}); }, []);
  return <section className="cards">
    {items.length ? items.map((item) => <div key={item.id}><b>{item.title}</b></div>) : <div className="empty wide">Your research library is empty.</div>}
  </section>;
}

createRoot(document.getElementById("root")!).render(<App />);


