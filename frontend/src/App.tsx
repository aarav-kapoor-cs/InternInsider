import { useEffect, useRef, useState } from "react";
import {
  ChatMessage, Health, Job, JobDetail, SkillGap,
  extractSkills, getHealth, getJob, getSkillGap, listJobs, matchResume, searchJobs, sendChat,
} from "./api";

type Page = "jobs" | "agent" | "resume";

// DEMO ONLY: an invented resume so the app can be shown without typing one.
const SAMPLE_RESUME = `Computing Science student, third year.
Projects: a REST API in Python and FastAPI with PostgreSQL, packaged with Docker and tested with pytest.
A React and TypeScript dashboard. Coursework in SQL, statistics and machine learning with pandas.
Tools: Git, Linux.`;

const SUGGESTIONS = [
  "Which jobs fit my resume best?",
  "What am I missing for job 5?",
  "Give me interview questions for job 9",
  "Find internships that work with data",
];

export default function App() {
  const [page, setPage] = useState<Page>("jobs");
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);

  // The resume is kept in the browser (localStorage) so a refresh doesn't lose it.
  const [resume, setResume] = useState(() => localStorage.getItem("resume") ?? "");
  const [resumeSkills, setResumeSkills] = useState<string[]>([]);

  // Chat state lives here, not in the chat page, so it survives switching pages.
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [chatError, setChatError] = useState("");

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setOffline(true));
  }, []);

  // Whenever the saved resume changes, ask the backend which skills it contains.
  useEffect(() => {
    localStorage.setItem("resume", resume);
    if (!resume.trim()) return setResumeSkills([]);
    extractSkills(resume).then(setResumeSkills).catch(() => setResumeSkills([]));
  }, [resume]);

  // Send one message to the LangGraph agent. Any page can call this.
  async function ask(text: string) {
    if (!text.trim() || busy) return;
    setPage("agent");
    const history = messages;
    const userMessage: ChatMessage = { role: "user", content: text };
    setMessages([...history, userMessage]);
    setBusy(true);
    setChatError("");
    try {
      const result = await sendChat(text, resume, history);
      setMessages([...history, userMessage, { role: "assistant", content: result.reply, tool_calls: result.tool_calls }]);
    } catch (e) {
      setChatError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const tabs: [Page, string][] = [["jobs", "Jobs"], ["agent", "AI copilot"], ["resume", "My resume"]];

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">intern<span>insider</span></div>
        <nav>
          {tabs.map(([id, label]) => (
            <button key={id} className={page === id ? "nav active" : "nav"} onClick={() => setPage(id)}>
              {label}
              {id === "resume" && !resume.trim() && <span className="badge">add</span>}
            </button>
          ))}
        </nav>
        <div className="status">
          {offline && <div className="bad">Backend is not running</div>}
          {health && <div>{health.jobs} postings loaded</div>}
          {health && <div className={health.llm_configured ? "good" : "warn"}>AI copilot {health.llm_configured ? "ready" : "off (no API key)"}</div>}
          <div className="demo-note">DEMO: no login. Sample postings unless real ones were loaded.</div>
        </div>
      </aside>

      <main className="content">
        {page === "jobs" && <JobsPage resume={resume} resumeSkills={resumeSkills} onAsk={ask} goResume={() => setPage("resume")} />}
        {page === "agent" && <AgentPage messages={messages} busy={busy} error={chatError} onAsk={ask} hasResume={!!resume.trim()} />}
        {page === "resume" && <ResumePage resume={resume} resumeSkills={resumeSkills} onSave={setResume} />}
      </main>
    </div>
  );
}

// ------------------------------------------------------------------ Jobs page

function JobsPage(props: { resume: string; resumeSkills: string[]; onAsk: (text: string) => void; goResume: () => void }) {
  const { resume, resumeSkills, onAsk, goResume } = props;
  const [query, setQuery] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [heading, setHeading] = useState("All postings");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);

  // Run one of the three ways of loading jobs and show the result.
  async function load(title: string, fetchJobs: () => Promise<Job[]>) {
    setLoading(true);
    setError("");
    try {
      setJobs(await fetchJobs());
      setHeading(title);
    } catch (e) {
      setError((e as Error).message === "Failed to fetch" ? "Can't reach the backend. Is it running?" : (e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load("All postings", listJobs); }, []);

  return (
    <>
      <h1>Find a role that fits</h1>
      <p className="lead">Search by what you want to do, in your own words. It matches on meaning, so the posting doesn't need to contain your exact words.</p>

      <form className="searchbar" onSubmit={(e) => { e.preventDefault(); load(`Closest to "${query}"`, () => searchJobs(query)); }}>
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder='e.g. "making apps for phones" or "working with data"' required />
        <button className="primary" type="submit">Search</button>
        <button type="button" disabled={!resume.trim()} title={resume.trim() ? "" : "Add your resume first"}
          onClick={() => load("Best matches for your resume", () => matchResume(resume))}>
          Match my resume
        </button>
        <button type="button" className="link" onClick={() => { setQuery(""); load("All postings", listJobs); }}>Show all</button>
      </form>

      {!resume.trim() && (
        <p className="hint">Add your resume to see which skills you already have for each job. <button className="link" onClick={goResume}>Add resume</button></p>
      )}
      {error && <p className="error">{error}</p>}

      <h2>{heading} <span className="count">{loading ? "loading…" : jobs.length}</span></h2>
      <div className="grid">
        {jobs.map((job) => {
          const have = job.skills.filter((s) => resumeSkills.includes(s));
          return (
            <button className="card" key={job.id} data-testid="job" onClick={() => setOpenId(job.id)}>
              <div className="card-top">
                <span className="job-id">#{job.id}</span>
                {job.similarity !== undefined && <span className="sim" title="Cosine similarity from pgvector">similarity {job.similarity.toFixed(2)}</span>}
              </div>
              <h3>{job.title}</h3>
              <div className="company">{job.company} · {job.location}</div>
              <Chips skills={job.skills} have={resumeSkills} />
              {resumeSkills.length > 0 && job.skills.length > 0 && (
                <Meter percent={Math.round((100 * have.length) / job.skills.length)} label={`${have.length} of ${job.skills.length} skills`} />
              )}
            </button>
          );
        })}
      </div>
      {!loading && jobs.length === 0 && !error && <p className="hint">No postings. Run the backend start script to load them.</p>}

      {openId !== null && <JobDrawer id={openId} resume={resume} onClose={() => setOpenId(null)} onAsk={onAsk} />}
    </>
  );
}

// Slide-in panel with one job's details and the skill gap.
function JobDrawer({ id, resume, onClose, onAsk }: { id: number; resume: string; onClose: () => void; onAsk: (text: string) => void }) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [gap, setGap] = useState<SkillGap | null>(null);

  useEffect(() => {
    getJob(id).then(setJob).catch(() => setJob(null));
    if (resume.trim()) getSkillGap(resume, id).then(setGap).catch(() => setGap(null));
  }, [id, resume]);

  return (
    <div className="overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <section className="drawer" role="dialog" aria-label="Job details" data-testid="drawer">
        <button className="close" onClick={onClose} aria-label="Close">×</button>
        {!job ? <p className="hint">Loading…</p> : (
          <>
            <div className="job-id">Posting #{job.id}</div>
            <h2>{job.title}</h2>
            <div className="company">{job.company} · {job.location}</div>
            <p className="description">{job.description}</p>

            <h4>Skill gap</h4>
            {!resume.trim() && <p className="hint">Add your resume to see what you have and what's missing.</p>}
            {gap && (
              <div data-testid="gap">
                <Meter percent={gap.match_percent} label={`${gap.match_percent}% of listed skills`} />
                <div className="gap-row"><span className="gap-label">You have</span><Chips skills={gap.have} have={gap.have} empty="none yet" /></div>
                <div className="gap-row"><span className="gap-label">To learn</span><Chips skills={gap.missing} have={[]} missing empty="nothing, you cover them all" /></div>
                <p className="fine">This is skill overlap from a word list, not a prediction of getting hired.</p>
              </div>
            )}

            <h4>Ask the AI copilot about this job</h4>
            <div className="actions">
              <button onClick={() => { onClose(); onAsk(`Give me interview questions for job ${job.id}`); }}>Interview questions</button>
              <button onClick={() => { onClose(); onAsk(`What am I missing for job ${job.id}, and what should I learn first?`); }}>What should I learn first?</button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}

// ------------------------------------------------------------------ Chat page

function AgentPage(props: { messages: ChatMessage[]; busy: boolean; error: string; onAsk: (text: string) => void; hasResume: boolean }) {
  const { messages, busy, error, onAsk, hasResume } = props;
  const [input, setInput] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  // Scroll to the newest message whenever the list changes.
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy]);

  return (
    <>
      <h1>AI copilot</h1>
      <p className="lead">A LangGraph agent with five tools. It decides which tool to call, and the grey line above each answer shows what it used.</p>
      {!hasResume && <p className="hint">No resume added yet. Resume questions will work better once you add one.</p>}

      <div className="chat">
        {messages.length === 0 && (
          <div className="empty-chat">
            <p>Try one of these:</p>
            {SUGGESTIONS.map((s) => <button key={s} className="suggestion" onClick={() => onAsk(s)}>{s}</button>)}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={"bubble-row " + m.role}>
            <div>
              {m.tool_calls && m.tool_calls.length > 0 && (
                <div className="tools" data-testid="tools">
                  {m.tool_calls.map((t, j) => <span key={j} className="tool" title={JSON.stringify(t.args)}>used {t.name}</span>)}
                </div>
              )}
              <div className="bubble">{m.content}</div>
            </div>
          </div>
        ))}
        {busy && <div className="bubble-row assistant"><div className="bubble typing"><i /><i /><i /></div></div>}
        {error && <p className="error" data-testid="chat-error">{error}</p>}
        <div ref={bottom} />
      </div>

      <form className="composer" onSubmit={(e) => { e.preventDefault(); onAsk(input); setInput(""); }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about jobs, skill gaps or interview prep" disabled={busy} required />
        <button className="primary" type="submit" disabled={busy}>Send</button>
      </form>
    </>
  );
}

// ---------------------------------------------------------------- Resume page

function ResumePage({ resume, resumeSkills, onSave }: { resume: string; resumeSkills: string[]; onSave: (text: string) => void }) {
  const [draft, setDraft] = useState(resume);
  const saved = draft === resume;

  return (
    <>
      <h1>My resume</h1>
      <p className="lead">Paste your resume as plain text. It stays in this browser and is sent to the backend only when you search, match or chat.</p>
      <textarea rows={12} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Paste your resume here" />
      <div className="actions">
        <button className="primary" disabled={saved} onClick={() => onSave(draft)}>{saved && resume ? "Saved" : "Save resume"}</button>
        <button onClick={() => { setDraft(SAMPLE_RESUME); onSave(SAMPLE_RESUME); }}>Use sample resume</button>
        <span className="fine">DEMO: the sample resume is invented.</span>
      </div>

      <h2>Skills found in your resume <span className="count">{resumeSkills.length}</span></h2>
      <Chips skills={resumeSkills} have={resumeSkills} empty="Save a resume to see the skills it mentions." />
      <p className="fine">Found by matching against a fixed list of skills, so a skill written in an unusual way can be missed.</p>
    </>
  );
}

// ------------------------------------------------------------ small pieces

function Chips({ skills, have, missing, empty }: { skills: string[]; have: string[]; missing?: boolean; empty?: string }) {
  if (skills.length === 0) return <span className="fine">{empty ?? ""}</span>;
  return (
    <div className="chips">
      {skills.map((s) => (
        <span key={s} className={"chip" + (have.includes(s) ? " have" : missing ? " missing" : "")}>{s}</span>
      ))}
    </div>
  );
}

function Meter({ percent, label }: { percent: number; label: string }) {
  return (
    <div className="meter" aria-label={label}>
      <div className="meter-track"><div className="meter-fill" style={{ width: percent + "%" }} /></div>
      <span>{label}</span>
    </div>
  );
}
