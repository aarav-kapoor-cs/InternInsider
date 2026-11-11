// Everything the frontend knows about talking to the backend lives here.
const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8001";

// These types mirror the JSON the FastAPI backend returns.
export type Job = {
  id: number;
  title: string;
  company: string;
  location: string;
  skills: string[];
  similarity?: number; // 0 to 1 from pgvector; only present on search results
};

export type JobDetail = Job & { description: string; category: string; url: string };

export type SkillGap = {
  job_id: number;
  have: string[];
  missing: string[];
  match_percent: number;
};

export type Health = { jobs: number; llm_configured: boolean };
export type ToolCall = { name: string; args: Record<string, unknown> };
export type ChatMessage = { role: "user" | "assistant"; content: string; tool_calls?: ToolCall[] };

// One helper for every request. Throws the server's error message on 4xx/5xx.
async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(API_URL + path, {
    method: body ? "POST" : "GET",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed");
  return data;
}

export const getHealth = () => request<Health>("/api/health");
export const listJobs = () => request<Job[]>("/api/jobs");
export const getJob = (id: number) => request<JobDetail>(`/api/jobs/${id}`);
export const searchJobs = (query: string) =>
  request<Job[]>("/api/jobs/search?limit=8&q=" + encodeURIComponent(query));
export const matchResume = (resume_text: string) => request<Job[]>("/api/match", { resume_text });
export const extractSkills = (text: string) => request<string[]>("/api/skills", { text });
export const getSkillGap = (resume_text: string, job_id: number) =>
  request<SkillGap>("/api/skill-gap", { resume_text, job_id });

export const sendChat = (message: string, resume_text: string, history: ChatMessage[]) =>
  request<{ reply: string; tool_calls: ToolCall[] }>("/api/chat", {
    message,
    resume_text,
    // The backend is stateless, so earlier messages are sent along every time.
    history: history.map(({ role, content }) => ({ role, content })),
  });
