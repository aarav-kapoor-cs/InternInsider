import { useEffect, useState } from "react";
import { Bot, Briefcase, FileText } from "lucide-react";
import { ChatMessage, Health, ResumeResult, Skills, extractSkills, getHealth, sendChat } from "./api";
import JobsPage from "./pages/JobsPage";
import ResumePage from "./pages/ResumePage";
import CopilotPage from "./pages/CopilotPage";

type Page = "jobs" | "resume" | "copilot";

export default function App() {
  const [page, setPage] = useState<Page>("jobs");
  const [health, setHealth] = useState<Health | null>(null);

  // The resume text is kept in the browser (localStorage) so a page refresh keeps it.
  const [resume, setResume] = useState(localStorage.getItem("resume") ?? "");
  const [upload, setUpload] = useState<ResumeResult | null>(null); // how the last file was read
  const [skills, setSkills] = useState<Skills>({ skills: [], groups: {} });

  // The chat lives here, not in the Copilot page, so it survives switching pages.
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [chatError, setChatError] = useState("");

  useEffect(() => { getHealth().then(setHealth).catch(() => setHealth(null)); }, []);

  // Whenever the resume changes: save it, and ask the backend which skills it contains.
  useEffect(() => {
    localStorage.setItem("resume", resume);
    if (resume.trim()) extractSkills(resume).then(setSkills);
    else setSkills({ skills: [], groups: {} });
  }, [resume]);

  // Send one message to the LangGraph agent.
  async function ask(text: string) {
    if (!text.trim() || busy) return;
    setPage("copilot");
    const question: ChatMessage = { role: "user", content: text };
    setMessages([...messages, question]);
    setBusy(true);
    setChatError("");
    try {
      const answer = await sendChat(text, resume, messages);
      setMessages([...messages, question, { role: "assistant", content: answer.reply, tool_calls: answer.tool_calls, tokens: answer.tokens }]);
    } catch (error) {
      setChatError((error as Error).message);
    }
    setBusy(false);
  }

  const tabs = [
    { id: "jobs" as Page, label: "Jobs", icon: Briefcase },
    { id: "resume" as Page, label: "Resume", icon: FileText },
    { id: "copilot" as Page, label: "Copilot", icon: Bot },
  ];

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand"><span className="brand-mark">ii</span><span>Intern<b>Insider</b></span></div>
          <nav className="tabs">
            {tabs.map((tab) => (
              <button key={tab.id} className={"tab" + (page === tab.id ? " active" : "")} onClick={() => setPage(tab.id)}>
                <tab.icon size={16} /><span>{tab.label}</span>
              </button>
            ))}
          </nav>
          <div className="status">
            {!health && <span className="pill bad">Backend offline</span>}
            {health && <span className="pill"><i className="dot good" />{health.jobs} {health.linkedin ? "LinkedIn" : "sample"} postings</span>}
            {health && <span className="pill"><i className={"dot " + (health.llm_configured ? "good" : "warn")} />AI {health.llm_configured ? "ready" : "off"}</span>}
          </div>
        </div>
      </header>

      <main className={"page page-" + page}>
        {page === "jobs" && <JobsPage resume={resume} resumeSkills={skills.skills} onAsk={ask} goResume={() => setPage("resume")} />}
        {page === "resume" && (
          <ResumePage resume={resume} upload={upload} skills={skills} ocrAvailable={health?.ocr_available ?? true}
            onUpload={(result) => { setUpload(result); setResume(result.text); }}
            onSaveText={setResume} goJobs={() => setPage("jobs")} />
        )}
        {page === "copilot" && (
          <CopilotPage messages={messages} busy={busy} error={chatError} onAsk={ask}
            llmReady={health?.llm_configured ?? true} onClear={() => setMessages([])} />
        )}
      </main>
    </>
  );
}
