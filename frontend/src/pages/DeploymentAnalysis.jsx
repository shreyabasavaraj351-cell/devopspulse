import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { Alert, Badge, Button, MemoryList } from "../components/ui";

const MAX_BYTES = 2 * 1024 * 1024;

export default function DeploymentAnalysis() {
  const { projectId, project } = useAuth();
  const fileRef = useRef(null);
  const [f, setF] = useState({ name: "", version: "", environment: project?.environment || "staging", log: "" });
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const pickFile = (e) => {
    const picked = e.target.files?.[0];
    setError("");
    if (!picked) return setFile(null);
    if (!/\.(log|txt|out)$/i.test(picked.name)) {
      e.target.value = "";
      return setError("Unsupported file type. Use .log, .txt or .out.");
    }
    if (picked.size > MAX_BYTES) {
      e.target.value = "";
      return setError("File is larger than 2 MB.");
    }
    setFile(picked);
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setResult(null);
    if (!f.name.trim()) return setError("Enter a deployment name.");
    if (!file && !f.log.trim()) return setError("Upload a log file or paste log text.");
    const form = new FormData();
    form.set("project_id", projectId);
    form.set("deployment_name", f.name.trim());
    form.set("version", f.version.trim());
    form.set("environment", f.environment);
    if (file) form.set("file", file);
    else form.set("log_text", f.log);
    setLoading(true);
    try {
      setResult(await api.analyze(form));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const inc = result?.incident;
  const rec = result?.recommendation;

  return (
    <>
      <div className="page-head">
        <h1>Analyse deployment</h1>
        <span className="muted">Upload or paste a deployment log. Secrets are redacted before anything is stored or sent to the AI.</span>
      </div>

      <form className="card" onSubmit={submit}>
        <div className="row">
          <div><label htmlFor="n">Deployment name</label><input id="n" value={f.name} onChange={set("name")} placeholder="e.g. checkout-service" /></div>
          <div><label htmlFor="v">Version / build ID</label><input id="v" value={f.version} onChange={set("version")} placeholder="e.g. v2.4.1 or #1873" /></div>
          <div>
            <label htmlFor="e">Environment</label>
            <select id="e" value={f.environment} onChange={set("environment")}>
              <option value="development">Development</option><option value="testing">Testing</option><option value="staging">Staging</option>
            </select>
          </div>
        </div>
        <p className="small muted" style={{ marginBottom: 0 }}>Application: <strong>{project?.name}</strong></p>

        <label htmlFor="file">Upload log file (.log, .txt, .out, max 2 MB)</label>
        <div className="drop">
          <input id="file" ref={fileRef} type="file" accept=".log,.txt,.out" onChange={pickFile} />
          {file && <div className="small" style={{ marginTop: 6 }}>Using {file.name}. Pasted text is ignored. <a href="#clear" onClick={(ev) => { ev.preventDefault(); setFile(null); if (fileRef.current) fileRef.current.value = ""; }}>Remove</a></div>}
        </div>
        <label htmlFor="log">Or paste logs</label>
        <textarea id="log" value={f.log} onChange={set("log")} disabled={!!file} placeholder="Paste your deployment log here…" />
        <Alert>{error}</Alert>
        <Button loading={loading} type="submit">{loading ? "Analysing logs…" : "Analyse logs"}</Button>
        {loading && <span className="small muted" style={{ marginLeft: 12 }}>Scanning for errors, asking the AI, recalling similar incidents…</span>}
      </form>

      {result && !inc && (
        <div className="card"><Alert kind="ok">{result.message}</Alert></div>
      )}

      {inc && (
        <>
          {result.ai_status === "fallback" && <Alert kind="warn">The AI service was unavailable, so this is a basic pattern-based result.</Alert>}
          {result.ai_status === "partial" && <Alert kind="warn">The initial AI analysis succeeded, but the AI service was unavailable to refine the recommendation using recalled memories.</Alert>}
          {result.memory.recall === "unavailable" && <Alert kind="warn">Memory service was unavailable, so past incidents could not be recalled.</Alert>}
          {result.memory.retain === "failed" && <Alert kind="warn">This incident could not be saved to memory. It is stored in your incident history.</Alert>}

          <div className="card">
            <div className="row" style={{ alignItems: "center", justifyContent: "space-between" }}>
              <h2 style={{ margin: 0 }}>Analysis for incident <Link to={`/incidents/${inc.id}`}>#{inc.id}</Link></h2>
              <div style={{ flex: "none" }}><Badge value={inc.severity} /> <Badge value={inc.category} /></div>
            </div>
            <h3 style={{ marginTop: 16 }}>Likely root cause</h3>
            <p style={{ marginTop: 0 }}>{result.analysis.root_cause}</p>
            <h3>In simple terms</h3>
            <p style={{ marginTop: 0 }}>{result.analysis.simple_explanation || result.analysis.summary}</p>
            <h3>Detected errors</h3>
            <div className="pre">{inc.error_lines.join("\n")}</div>
          </div>

          <div className="card">
            <h2>Recommended actions <Badge value="unverified" /></h2>
            <ol className="steps">{rec.actions.map((a, i) => <li key={i}>{a}</li>)}</ol>
            {rec.used_memory ? (
              <div className="memory-box">
                <strong>Informed by memory.</strong> {rec.memory_influence}
              </div>
            ) : rec.recalled_memories.length === 0 ? (
              <p className="small muted">No similar past incidents were found, so this advice comes from the AI analysis alone.</p>
            ) : (
              <p className="small muted">{rec.memory_influence || "Similar memories were recalled but did not change the advice."}</p>
            )}
            {rec.recalled_memories.length > 0 && (
              <details open><summary className="small">Memories recalled ({rec.recalled_memories.length})</summary><MemoryList memories={rec.recalled_memories} /></details>
            )}
            <p className="small muted">{result.note}</p>
            <Link className="btn ghost sm" to={`/incidents/${inc.id}`}>Open incident and confirm the outcome</Link>
          </div>
        </>
      )}
    </>
  );
}
