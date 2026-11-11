// Every call the frontend makes to the FastAPI backend lives in this file.
const API_URL = "http://localhost:8001";

// These types match the JSON the backend sends back.
export type Job = {
  id: number;
  title: string;
  company: string;
  location: string;
  category: string;
  url: string;
  logo_url: string;
  posted_at: string | null; // "2026-11-06"
  skills: string[];
  similarity?: number; // 0 to 1, from pgvector. Only on search and match results.
};
export type JobDetail = Job & { description: string };
export type SkillGap = { have: string[]; missing: string[]; match_percent: number };
export type Skills = { skills: string[]; groups: Record<string, string[]> };
export type ResumeResult = Skills & {
  id: number; // the row saved in the resumes table
  filename: string;
  text: string;
  method: "text" | "ocr" | "mixed";
  pages: number;
  ocr_confidence: number | null;
  seconds: number;
};
export type Health = { jobs: number; linkedin: number; llm_configured: boolean; ocr_available: boolean };
export type ToolCall = { name: string; args: Record<string, unknown> };
export type Tokens = { prompt: number; completion: number };
export type ChatMessage = { role: "user" | "assistant"; content: string; tool_calls?: ToolCall[]; tokens?: Tokens };

// GET when there is no body, POST when there is. Throws the backend's error message.
async function request<T>(path: string, body?: unknown): Promise<T> {
  const options: RequestInit = body === undefined ? {} : {
    method: "POST",
    // A file upload (FormData) sets its own Content-Type. Everything else is JSON.
    headers: body instanceof FormData ? {} : { "Content-Type": "application/json" },
    body: body instanceof FormData ? body : JSON.stringify(body),
  };
  const response = await fetch(API_URL + path, options).catch(() => {
    throw new Error("Can't reach the backend. Is it running?");
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed");
  return data;
}

export const getHealth = () => request<Health>("/api/health");
export const listJobs = () => request<Job[]>("/api/jobs");
export const getJob = (id: number) => request<JobDetail>(`/api/jobs/${id}`);
export const searchJobs = (query: string) => request<Job[]>("/api/jobs/search?limit=12&q=" + encodeURIComponent(query));
export const matchResume = (resume_text: string) => request<Job[]>("/api/match", { resume_text });
export const getSkillGap = (resume_text: string, job_id: number) => request<SkillGap>("/api/skill-gap", { resume_text, job_id });
export const extractSkills = (text: string) => request<Skills>("/api/skills", { text });

export function uploadResume(file: Blob, filename: string) {
  const form = new FormData();
  form.append("file", file, filename);
  return request<ResumeResult>("/api/resume/parse", form);
}

// The backend keeps no chat state, so the earlier messages are sent every time.
export const sendChat = (message: string, resume_text: string, history: ChatMessage[]) =>
  request<{ reply: string; tool_calls: ToolCall[]; tokens: Tokens }>("/api/chat", {
    message,
    resume_text,
    history: history.map(({ role, content }) => ({ role, content })),
  });
