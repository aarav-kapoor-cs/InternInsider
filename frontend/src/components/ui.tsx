// Small display pieces shared by the pages.
import { useState } from "react";
import { LoaderCircle } from "lucide-react";
import { scoreColor } from "../lib";

/** The company logo from LinkedIn, or the company's initials if there is no logo. */
export function CompanyLogo({ name, url, size = 44 }: { name: string; url: string; size?: number }) {
  const [broken, setBroken] = useState(false);
  const style = { width: size, height: size, fontSize: size * 0.36 };
  if (url && !broken) return <img className="logo" src={url} alt="" style={style} onError={() => setBroken(true)} />;
  const initials = name.split(" ").slice(0, 2).map((word) => word[0]).join("").toUpperCase();
  return <div className="logo logo-initials" style={style}>{initials}</div>;
}

/** Skill chips. Skills in `have` are green; with `missing`, the rest are red. */
export function SkillChips({ skills, have = [], missing = false, max }: { skills: string[]; have?: string[]; missing?: boolean; max?: number }) {
  const shown = max ? skills.slice(0, max) : skills;
  return (
    <div className="chips">
      {shown.map((skill) => (
        <span key={skill} className={"chip" + (have.includes(skill) ? " have" : missing ? " missing" : "")}>{skill}</span>
      ))}
      {max && skills.length > max && <span className="chip">+{skills.length - max}</span>}
    </div>
  );
}

/** A circle that fills up to `percent`, drawn with SVG. */
export function MatchRing({ percent }: { percent: number }) {
  const radius = 34;
  const circumference = 2 * Math.PI * radius;
  return (
    <div className={"ring " + scoreColor(percent)}>
      <svg width="76" height="76" viewBox="0 0 76 76">
        <circle cx="38" cy="38" r={radius} className="ring-track" />
        <circle cx="38" cy="38" r={radius} className="ring-fill"
          strokeDasharray={circumference} strokeDashoffset={circumference * (1 - percent / 100)} />
      </svg>
      <span>{percent}%</span>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return <span className="spinner"><LoaderCircle size={16} className="spin" />{label}</span>;
}
