import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { Alert, Badge, Button, MemoryList } from "../components/ui";

export default function RiskPrediction() {
  const { projectId } = useAuth();
  const fileRef = useRef(null);
  const [f, setF] = useState({ name: "", version: "", environment: "staging", notes: "", log: "" });
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [res, setRes] = useState(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setRes(null);
    if (!f.name.trim()) return setError("Enter a deployment name.");
    if (!file && !f.log.trim()) return setError("Upload a log file or paste log text.");
    if (file && !/\.(log|txt|out)$/i.test(file.name)) return setError("Unsupported file type. Use .log, .txt or .out.");
    if (file && file.size > 2 * 1024 * 1024) return setError("File is larger than 2 MB.");
    const form = new FormData();
    form.set("project_id", projectId);
    form.set("deployment_name", f.name.trim());
    form.set("version", f.version.trim());
    form.set("environment", f.environment);
    form.set("notes", f.notes);
    if (file) form.set("file", file);
    else form.set("log_text", f.log);
    setLoading(true);
    try {
      setRes(await api.risk(form));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="page-head">
        <h1>Risk prediction</h1>
        <span className="muted">Check an upcoming deployment against patterns from past incidents.</span>
      </div>
      <Alert kind="info">Results are AI-generated risk assessments based on your logs and past incidents. They are not guaranteed predictions.</Alert>

      <form className="card" onSubmit={submit}>
        <div className="row">
          <div><label htmlFor="n">Deployment name</label><input id="n" value={f.name} onChange={set("name")} /></div>
          <div><label htmlFor="v">Version / build ID</label><input id="v" value={f.version} onChange={set("version")} /></div>
          <div>
            <label htmlFor="e">Target environment</label>
            <select id="e" value={f.environment} onChange={set("environment")}><option value="development">Development</option><option value="testing">Testing</option><option value="staging">Staging</option></select>
          </div>
        </div>
        <label htmlFor="notes">Change notes (optional)</label>
        <input id="notes" value={f.notes} onChange={set("notes")} placeholder="e.g. upgraded DB driver, added a migration" />
        <label htmlFor="file">Upload build or pre-deploy log</label>
        <input id="file" ref={fileRef} type="file" accept=".log,.txt,.out" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        <label htmlFor="log">Or paste logs</label>
        <textarea id="log" value={f.log} onChange={set("log")} disabled={!!file} />
        <Alert>{error}</Alert>
        <Button loading={loading} type="submit">Assess risk</Button>
      </form>

      {res && (
        <>
          {res.ai_status === "fallback" && <Alert kind="warn">AI was unavailable. The level below is based only on error and warning counts.</Alert>}
          {res.memory_status === "unavailable" && <Alert kind="warn">Memory service unavailable, so past incidents were not considered.</Alert>}
          <div className="card">
            <h2>Risk level: <Badge value={res.risk_level} /></h2>
            <p>{res.explanation}</p>
            {res.risks.length > 0 && (<><h3>Potential risks</h3><ul className="steps">{res.risks.map((r, i) => <li key={i}><strong>{r.title}</strong>{r.detail ? `: ${r.detail}` : ""}</li>)}</ul></>)}
            {res.preventive_actions.length > 0 && (<><h3>Preventive actions</h3><ol className="steps">{res.preventive_actions.map((a, i) => <li key={i}>{a}</li>)}</ol></>)}
            <p className="small muted">{res.disclaimer}</p>
          </div>
          <div className="card">
            <h2>Related historical incidents</h2>
            {res.related_incidents.length === 0 && res.recalled_memories.length === 0 ? (
              <p className="muted">No matching past incidents found.</p>
            ) : (
              <>
                {res.related_incidents.map((i) => (
                  <p key={i.id}><Link to={`/incidents/${i.id}`}>#{i.id} {i.title}</Link> <Badge value={i.severity} /> <Badge value={i.status} /><br /><span className="small muted">{i.root_cause}</span></p>
                ))}
                <MemoryList memories={res.recalled_memories} />
              </>
            )}
          </div>
        </>
      )}
    </>
  );
}
