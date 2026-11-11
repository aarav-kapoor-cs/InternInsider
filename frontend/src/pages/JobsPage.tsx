import { useEffect, useState } from "react";
import { Clock, ExternalLink, FileUp, GraduationCap, MapPin, MessageSquareText, Search, Sparkles } from "lucide-react";
import { Job, JobDetail, SkillGap, getJob, getSkillGap, listJobs, matchResume, searchJobs } from "../api";
import { CompanyLogo, MatchRing, SkillChips, Spinner } from "../components/ui";
import { matchPercent, scoreColor, timeAgo } from "../lib";

// Queries that share almost no words with the postings: they show search by meaning.
const EXAMPLES = ["making apps for phones", "teaching computers to learn from data", "keeping cloud systems running"];

type Props = { resume: string; resumeSkills: string[]; onAsk: (text: string) => void; goResume: () => void };

export default function JobsPage({ resume, resumeSkills, onAsk, goResume }: Props) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [heading, setHeading] = useState("Latest postings");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // The three ways to fill the list: all postings, a search, or a resume match.
  async function load(title: string, fetchJobs: () => Promise<Job[]>) {
    setLoading(true);
    setError("");
    try {
      const result = await fetchJobs();
      setJobs(result);
      setHeading(title);
      setSelectedId(result[0]?.id ?? null);
    } catch (e) {
      setError((e as Error).message);
    }
    setLoading(false);
  }

  const showAll = () => load("Latest postings", listJobs);
  const search = (text: string) => { setQuery(text); if (text.trim()) load(`Closest to “${text}”`, () => searchJobs(text)); };
  const match = () => load("Best matches for your resume", () => matchResume(resume));

  useEffect(() => { showAll(); }, []);

  return (
    <>
      <h1>Find internships that fit you</h1>
      <p className="lead">Real postings from LinkedIn, ranked by meaning with pgvector. Search in your own words, or match your resume.</p>

      <form className="searchbar" onSubmit={(e) => { e.preventDefault(); search(query); }}>
        <div className="search-input">
          <Search size={18} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Describe the work you want, e.g. “building dashboards with data”" />
        </div>
        <button className="btn btn-primary btn-lg" type="submit">Search</button>
        <button className="btn btn-accent btn-lg" type="button" onClick={match} disabled={!resume.trim()}>
          <Sparkles size={16} />Match my resume
        </button>
      </form>
      <div className="examples">
        <span>Try</span>
        {EXAMPLES.map((text) => <button key={text} className="example" onClick={() => search(text)}>{text}</button>)}
      </div>

      {!resume.trim() && (
        <div className="banner">
          <FileUp size={18} />
          <span><b>Add your resume</b> to see a skill match on every posting.</span>
          <button className="btn btn-sm" onClick={goResume}>Upload resume</button>
        </div>
      )}
      {error && <div className="notice bad">{error}</div>}

      <div className="results-head">
        <h2>{heading}</h2>
        <span className="count">{jobs.length}</span>
        {heading !== "Latest postings" && <button className="link-btn" onClick={() => { setQuery(""); showAll(); }}>Show all</button>}
      </div>

      <div className="jobs-layout">
        <div className="job-list">
          {loading ? <Spinner label="Loading postings…" /> : jobs.map((job) => (
            <JobCard key={job.id} job={job} resumeSkills={resumeSkills} selected={job.id === selectedId} onClick={() => setSelectedId(job.id)} />
          ))}
        </div>
        <div className="detail-col">
          {selectedId !== null && <JobDetails id={selectedId} resume={resume} onAsk={onAsk} goResume={goResume} />}
        </div>
      </div>
    </>
  );
}

// One posting in the list on the left.
function JobCard({ job, resumeSkills, selected, onClick }: { job: Job; resumeSkills: string[]; selected: boolean; onClick: () => void }) {
  const percent = matchPercent(job.skills, resumeSkills);
  return (
    <button className={"job-card" + (selected ? " selected" : "")} onClick={onClick}>
      <CompanyLogo name={job.company} url={job.logo_url} />
      <div className="job-card-body">
        <div className="job-card-title">{job.title}</div>
        <div className="job-card-company">{job.company}</div>
        <div className="meta">
          <span><MapPin size={13} />{job.location.replace(", Canada", "")}</span>
          {job.posted_at && <span><Clock size={13} />{timeAgo(job.posted_at)}</span>}
        </div>
        <SkillChips skills={job.skills} have={resumeSkills} max={4} />
      </div>
      <div className="job-card-side">
        {percent !== null && <span className={"score " + scoreColor(percent)} title="Share of this posting's skills on your resume">{percent}%</span>}
        {job.similarity !== undefined && <span className="sim" title="Cosine similarity from pgvector">{job.similarity.toFixed(2)}</span>}
      </div>
    </button>
  );
}

// The selected posting on the right: details, skill gap, description.
function JobDetails({ id, resume, onAsk, goResume }: { id: number; resume: string; onAsk: (text: string) => void; goResume: () => void }) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [gap, setGap] = useState<SkillGap | null>(null);

  useEffect(() => {
    setJob(null);
    setGap(null);
    getJob(id).then(setJob);
    if (resume.trim()) getSkillGap(resume, id).then(setGap);
  }, [id, resume]);

  if (!job) return <div className="detail"><Spinner label="Loading posting…" /></div>;

  return (
    <article className="detail">
      <div className="detail-head">
        <CompanyLogo name={job.company} url={job.logo_url} size={56} />
        <div>
          <h2>{job.title}</h2>
          <div className="detail-company">{job.company}</div>
        </div>
      </div>
      <div className="meta">
        <span><MapPin size={14} />{job.location}</span>
        {job.posted_at && <span><Clock size={14} />Posted {timeAgo(job.posted_at)}</span>}
        <span className="tag">#{job.id}</span>
        {job.category && <span className="tag">{job.category}</span>}
      </div>
      <div className="actions">
        {job.url && <a className="btn btn-primary" href={job.url} target="_blank" rel="noreferrer">View on LinkedIn<ExternalLink size={15} /></a>}
        <button className="btn" onClick={() => onAsk(`Give me interview questions for job ${job.id}`)}><MessageSquareText size={15} />Interview prep</button>
        <button className="btn" onClick={() => onAsk(`What am I missing for job ${job.id}, and what should I learn first?`)}><GraduationCap size={15} />What to learn</button>
      </div>

      <section className="match-card">
        {!resume.trim() ? (
          <>
            <FileUp size={22} className="accent" />
            <div className="match-body"><b>See how you match</b><span className="hint">Upload your resume to compare skills.</span></div>
            <button className="btn btn-sm" onClick={goResume}>Add resume</button>
          </>
        ) : !gap ? <Spinner label="Comparing with your resume…" /> : (
          <>
            <MatchRing percent={gap.match_percent} />
            <div className="match-body">
              <b>{gap.have.length} of {gap.have.length + gap.missing.length} skills in this posting are on your resume</b>
              <div className="match-row"><span className="hint">You have</span><SkillChips skills={gap.have} have={gap.have} /></div>
              <div className="match-row"><span className="hint">To learn</span><SkillChips skills={gap.missing} missing /></div>
            </div>
          </>
        )}
      </section>

      <h4 className="section-label">About the role</h4>
      <div className="description">{job.description}</div>
    </article>
  );
}
