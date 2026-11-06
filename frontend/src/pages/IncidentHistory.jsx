import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { Alert, IncidentTable, Spinner } from "../components/ui";

export default function IncidentHistory() {
  const { projectId } = useAuth();
  const navigate = useNavigate();
  const [filters, setFilters] = useState({ q: "", severity: "", category: "", status: "" });
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const set = (k) => (e) => setFilters({ ...filters, [k]: e.target.value });

  useEffect(() => {
    if (!projectId) return;
    const t = setTimeout(() => {
      setError("");
      api.incidents({ project_id: projectId, ...filters }).then(setRows).catch((e) => setError(e.message));
    }, 250);
    return () => clearTimeout(t);
  }, [projectId, filters]);

  return (
    <>
      <div className="page-head"><h1>Incident history</h1><span className="muted">Every failure analysed for this project.</span></div>
      <div className="card">
        <div className="row">
          <div style={{ flex: 2 }}><input placeholder="Search root cause or title…" value={filters.q} onChange={set("q")} aria-label="Search" /></div>
          <select value={filters.severity} onChange={set("severity")} aria-label="Severity">
            <option value="">All severities</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
          </select>
          <select value={filters.category} onChange={set("category")} aria-label="Category">
            <option value="">All categories</option>
            {["dependency", "build", "test", "configuration", "permissions", "network", "database", "resource", "timeout", "container", "other"].map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select value={filters.status} onChange={set("status")} aria-label="Status">
            <option value="">All statuses</option><option value="open">Open</option><option value="partially_resolved">Partially resolved</option><option value="resolved">Resolved</option>
          </select>
        </div>
      </div>
      <div className="card">
        <Alert>{error}</Alert>
        {rows === null ? <Spinner dark /> : <IncidentTable incidents={rows} onOpen={(id) => navigate(`/incidents/${id}`)} />}
      </div>
    </>
  );
}
