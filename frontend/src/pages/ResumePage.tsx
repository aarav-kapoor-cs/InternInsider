import { useEffect, useState } from "react";
import { ArrowRight, FileUp, ScanText } from "lucide-react";
import { ResumeResult, Skills, uploadResume } from "../api";
import { SkillChips, Spinner } from "../components/ui";

type Props = {
  resume: string;
  upload: ResumeResult | null;
  skills: Skills;
  ocrAvailable: boolean;
  onUpload: (result: ResumeResult) => void;
  onSaveText: (text: string) => void;
  goJobs: () => void;
};

const METHOD = {
  text: "Read from the PDF's text layer",
  ocr: "Read with OCR (Tesseract)",
  mixed: "Text layer + OCR",
};

export default function ResumePage({ resume, upload, skills, ocrAvailable, onUpload, onSaveText, goJobs }: Props) {
  const [draft, setDraft] = useState(resume);
  const [reading, setReading] = useState("");  // name of the file being read
  const [error, setError] = useState("");

  useEffect(() => setDraft(resume), [resume]);

  async function read(file: Blob, name: string) {
    setReading(name);
    setError("");
    try {
      onUpload(await uploadResume(file, name));
    } catch (e) {
      setError((e as Error).message);
    }
    setReading("");
  }

  // The demo file: a resume saved as an image-only PDF, so it has no text layer.
  async function tryScannedSample() {
    const file = await fetch("/demo/scanned-resume.pdf").then((r) => r.blob());
    read(file, "scanned-resume.pdf");
  }

  return (
    <>
      <h1>Your resume</h1>
      <p className="lead">Upload a PDF or a photo. A normal PDF is read directly from its text layer; a scanned page is read with Tesseract OCR.</p>

      <div className="resume-grid">
        <div className="stack">
          <label className="dropzone"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) read(f, f.name); }}>
            <input type="file" hidden accept=".pdf,.png,.jpg,.jpeg"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) read(f, f.name); e.target.value = ""; }} />
            {reading ? <Spinner label={`Reading ${reading}…`} /> : (
              <>
                <div className="dz-icon"><FileUp size={24} /></div>
                <b>Drop your resume here, or click to browse</b>
                <span className="hint">PDF, PNG or JPG · up to 10 MB</span>
              </>
            )}
          </label>
          <button className="link-btn" onClick={tryScannedSample} disabled={!!reading}><ScanText size={15} />Try a scanned sample (an image-only PDF)</button>
          {!ocrAvailable && <div className="notice warn">Tesseract is not installed, so scans can't be read. Run <code>brew install tesseract</code>.</div>}
          {error && <div className="notice bad">{error}</div>}

          {upload && (
            <div className="card">
              <div className="card-head">
                <h3>{upload.filename}</h3>
                <span className="hint">saved as resume #{upload.id}</span>
                <span className={"method " + upload.method}>{METHOD[upload.method]}</span>
              </div>
              <div className="stat-grid">
                <div><b>{upload.pages}</b><span>page{upload.pages === 1 ? "" : "s"}</span></div>
                <div><b>{upload.text.length.toLocaleString()}</b><span>characters</span></div>
                <div><b>{upload.ocr_confidence === null ? "n/a" : upload.ocr_confidence + "%"}</b><span>OCR confidence</span></div>
                <div><b>{upload.seconds}s</b><span>to read</span></div>
              </div>
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-head"><h3>Skills found</h3><span className="count-badge">{skills.skills.length}</span></div>
          {skills.skills.length === 0 && <p className="hint">Upload or paste a resume to see the skills it mentions.</p>}
          {Object.entries(skills.groups).map(([group, list]) => (
            <div key={group} className="skill-group">
              <span className="section-label">{group}</span>
              <SkillChips skills={list} have={list} />
            </div>
          ))}
          {skills.skills.length > 0 && <button className="btn btn-primary" onClick={goJobs}>See matching jobs<ArrowRight size={16} /></button>}
        </div>
      </div>

      <div className="card">
        <div className="card-head"><h3>Resume text</h3><span className="hint">Fix OCR mistakes here, or paste your resume instead of uploading.</span></div>
        <textarea rows={12} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Paste your resume here" />
        <div><button className="btn btn-primary" disabled={draft === resume} onClick={() => onSaveText(draft)}>Save text</button></div>
      </div>
    </>
  );
}
