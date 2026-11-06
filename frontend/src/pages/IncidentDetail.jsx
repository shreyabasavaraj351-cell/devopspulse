import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../services/api";
import { Alert, Badge, Button, Spinner, fmtDate } from "../components/ui";

export default function IncidentDetail() {
  const { id } = useParams();
  const [inc, setInc] = useState(null);
  const [error, setError] = useState("");
  const [fb, setFb] = useState({ outcome: "resolved", followed_suggestion: true, notes: "" });
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    setInc(null);
    api.incident(id).then(setInc).catch((e) => setError(e.message));
  }, [id]);

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setNotice(null);
    try {
      const res = await api.feedback(id, fb);
      setInc(res.incident);
      setFb({ ...fb, notes: "" });
      setNotice(
        res.memory_status === "failed"
          ? { kind: "warn", text: "Outcome saved, but the memory service was unavailable, so the agent has not retained it yet." }
          : { kind: "ok", text: res.verified ? "Outcome confirmed. The verified resolution has been retained in memory for future incidents." : "Outcome recorded and retained in memory." }
      );
    } catch (err) {
      setNotice({ kind: "error", text: err.message });
    } finally {
      setSaving(false);
    }
  };

  if (error) return <Alert>{error}</Alert>;
  if (!inc) return <Spinner dark />;

  return (
    <>
      <p className="small"><Link to="/incidents">← Incident history</Link></p>
      <div className="page-head">
        <h1>Incident #{inc.id}: {inc.title}</h1>
        <Badge value={inc.severity} /> <Badge value={inc.category} /> <Badge value={inc.status} />{" "}
        <span className="small muted">{inc.deployment_name} {inc.version} · {inc.environment} · {fmtDate(inc.created_at)}</span>
      </div>

      {inc.ai_status === "fallback" && <Alert kind="warn">This incident was analysed without the AI service (pattern-based result).</Alert>}

      <div className="card">
        <h2>Root cause</h2><p style={{ marginTop: 0 }}>{inc.root_cause}</p>
        {inc.simple_explanation && <><h3>In simple terms</h3><p style={{ marginTop: 0 }}>{inc.simple_explanation}</p></>}
        <h3>Detected errors</h3><div className="pre">{inc.error_lines.join("\n")}</div>
      </div>

      <div className="card">
        <h2>Resolutions</h2>
        {inc.resolutions.map((r) => (
          <div key={r.id} style={{ marginBottom: 12 }}>
            <Badge value={r.verified ? "verified" : "unverified"} label={r.verified ? "Verified by you" : "AI suggestion (unverified)"} />
            <div style={{ whiteSpace: "pre-wrap", marginTop: 6 }}>{r.text}</div>
          </div>
        ))}
        {inc.memory_explanation && <div className="memory-box"><strong>Memory influence.</strong> {inc.memory_explanation}</div>}
        {inc.recalled_incident_ids.length > 0 && (
          <p className="small">Related past incidents: {inc.recalled_incident_ids.map((n) => <Link key={n} to={`/incidents/${n}`} style={{ marginRight: 8 }}>#{n}</Link>)}</p>
        )}
        <p className="small muted">Memory status: <Badge value={inc.memory_status} /></p>
      </div>

      <form className="card" onSubmit={submit}>
        <h2>Did the suggested fix work?</h2>
        <p className="muted small">The agent only learns a resolution as verified once you confirm the outcome here.</p>
        <label htmlFor="o">Outcome</label>
        <select id="o" value={fb.outcome} onChange={(e) => setFb({ ...fb, outcome: e.target.value })}>
          <option value="resolved">Resolved</option><option value="partially_resolved">Partially resolved</option><option value="not_resolved">Not resolved</option>
        </select>
        <label className="check"><input type="checkbox" checked={fb.followed_suggestion} onChange={(e) => setFb({ ...fb, followed_suggestion: e.target.checked })} /> I followed the suggested resolution</label>
        <label htmlFor="nt">What actually fixed it (or what happened)? Optional</label>
        <textarea id="nt" style={{ minHeight: 90, fontFamily: "inherit", fontSize: "inherit" }} value={fb.notes} onChange={(e) => setFb({ ...fb, notes: e.target.value })} />
        {notice && <Alert kind={notice.kind}>{notice.text}</Alert>}
        <Button loading={saving} type="submit">Submit outcome</Button>
        {inc.feedback.length > 0 && (
          <ul className="small muted" style={{ marginTop: 16 }}>
            {inc.feedback.map((f) => <li key={f.id}>{fmtDate(f.created_at)}: {f.outcome.replace(/_/g, " ")}{f.notes ? ` — ${f.notes}` : ""}</li>)}
          </ul>
        )}
      </form>
    </>
  );
}
