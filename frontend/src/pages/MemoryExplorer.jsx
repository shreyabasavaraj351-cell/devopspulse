import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { Alert, Badge, Button, MemoryList, Spinner, fmtDate } from "../components/ui";

const LABELS = {
  "memory.retain": ["Retained incident (unverified)", ""],
  "memory.retain_outcome": ["Retained confirmed outcome", ""],
  "memory.recall": ["Recalled past experience", "recall"],
  "memory.explore": ["Memory search", "recall"],
  "memory.retain_failed": ["Could not retain (memory unavailable)", "fail"],
};

function describe(e) {
  const d = e.detail || {};
  switch (e.action) {
    case "memory.retain":
      return `Incident #${d.incident_id}: ${d.summary || ""}`;
    case "memory.retain_outcome":
      return `Incident #${d.incident_id}: outcome "${(d.outcome || "").replace(/_/g, " ")}"${d.verified ? ", verified resolution stored" : ""}`;
    case "memory.recall":
      return `${d.purpose ? `For ${d.purpose}` : `While analysing incident #${d.incident_id}`}: ${d.hits} memor${d.hits === 1 ? "y" : "ies"} found${d.status === "unavailable" ? " (memory service unavailable)" : ""}`;
    case "memory.explore":
      return `Searched "${d.query}": ${d.hits} result(s)`;
    default:
      return d.incident_id ? `Incident #${d.incident_id}` : "";
  }
}

export default function MemoryExplorer() {
  const { projectId } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [found, setFound] = useState(null);

  const load = () => api.memory(projectId).then(setData).catch((e) => setError(e.message));
  useEffect(() => { if (projectId) { setData(null); setFound(null); load(); } }, [projectId]); // eslint-disable-line

  const search = async (e) => {
    e.preventDefault();
    if (query.trim().length < 2) return;
    setSearching(true);
    setError("");
    try {
      setFound(await api.recall(projectId, query.trim()));
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSearching(false);
    }
  };

  if (!data && !error) return <Spinner dark />;

  return (
    <>
      <div className="page-head">
        <h1>Memory explorer</h1>
        <span className="muted">What the agent has retained for this project. Successfully retained memories persist across sessions and are private to your organisation.</span>
      </div>
      <Alert>{error}</Alert>

      {data && (
        <>
          {!data.service.reachable && <Alert kind="warn">The Hindsight memory service is not reachable right now. Existing records below are from your database.</Alert>}
          <div className="grid g5" style={{ marginBottom: 18 }}>
            <div className="card stat" style={{ marginBottom: 0 }}><div className="n">{data.retained_incidents}</div><div className="l">Incidents retained</div></div>
            <div className="card stat" style={{ marginBottom: 0 }}><div className="n">{data.influenced_incidents.length}</div><div className="l">Advice shaped by memory</div></div>
            <div className="card stat" style={{ marginBottom: 0 }}><div className="n">{data.service.reachable ? "Healthy" : "Unavailable"}</div><div className="l">Hindsight health endpoint</div></div>
          </div>

          <form className="card" onSubmit={search}>
            <p className="small muted">Health status only checks the Hindsight endpoint. Successful retain and recall operations are reported separately in the timeline and analysis results.</p>
            <h2>Recall similar incidents</h2>
            <div className="row">
              <div style={{ flex: 3 }}><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Describe a failure, e.g. database connection timeout during migration" aria-label="Memory query" /></div>
              <div style={{ flex: "none" }}><Button loading={searching} type="submit">Recall</Button></div>
            </div>
            {found && (
              <div style={{ marginTop: 14 }}>
                {found.status === "unavailable" && <Alert kind="warn">Memory service unavailable, so nothing could be recalled.</Alert>}
                {found.status === "ok" && found.memories.length === 0 && <p className="muted">No related memories found.</p>}
                <MemoryList memories={found.memories} />
                {found.related_incidents.length > 0 && (
                  <p className="small">Linked incidents: {found.related_incidents.map((i) => <Link key={i.id} to={`/incidents/${i.id}`} style={{ marginRight: 10 }}>#{i.id} {i.title}</Link>)}</p>
                )}
              </div>
            )}
          </form>

          <div className="card">
            <h2>How memory influenced recommendations</h2>
            {data.influenced_incidents.length === 0 ? (
              <p className="muted">No recommendation has been shaped by memory yet. Analyse a failure similar to an earlier one to see this.</p>
            ) : (
              data.influenced_incidents.map((i) => (
                <div className="memory-box" key={i.id}>
                  <Link to={`/incidents/${i.id}`}><strong>Incident #{i.id}</strong></Link> <Badge value={i.category} />
                  <div style={{ marginTop: 4 }}>{i.memory_explanation}</div>
                  {i.recalled_incident_ids.length > 0 && <div className="small muted">Recalled: {i.recalled_incident_ids.map((n) => `#${n}`).join(", ")}</div>}
                </div>
              ))
            )}
          </div>

          <div className="card">
            <h2>Memory timeline</h2>
            {data.timeline.length === 0 ? (
              <p className="muted">Nothing retained yet.</p>
            ) : (
              <ul className="timeline">
                {data.timeline.map((e) => {
                  const [label, cls] = LABELS[e.action] || [e.action, ""];
                  return (
                    <li key={e.id} className={cls}>
                      <strong>{label}</strong> <span className="small muted">{fmtDate(e.created_at)}</span>
                      <div className="small">{describe(e)}</div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </>
      )}
    </>
  );
}
