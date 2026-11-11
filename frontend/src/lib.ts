// Small helpers used by the pages.

/** "2026-11-06" -> "4d ago" */
export function timeAgo(date: string | null): string {
  if (!date) return "";
  const days = Math.floor((Date.now() - new Date(date).getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

/** Share of the job's skills that are on the resume, 0-100. null if there is nothing to compare. */
export function matchPercent(jobSkills: string[], resumeSkills: string[]): number | null {
  if (!jobSkills.length || !resumeSkills.length) return null;
  const have = jobSkills.filter((skill) => resumeSkills.includes(skill));
  return Math.round((100 * have.length) / jobSkills.length);
}

/** Colour of a score: green from 70%, amber from 40%, grey below. */
export const scoreColor = (percent: number) => (percent >= 70 ? "good" : percent >= 40 ? "warn" : "low");
