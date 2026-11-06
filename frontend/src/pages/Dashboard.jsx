import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { Alert, Badge, IncidentTable, Spinner, fmtDate } from "../components/ui";

export default function Dashboard() {
  const { projectId, project } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!projectId) return;
    setData(null);
    api.dashboard(projectId).then(setData).catch((e) => setError(e.message));
  }, [projectId]);

  if (error) return <Alert>{error}</Alert>;
  if (!data) return <Spinner dark />;

  const stats = [
    ["Deployments analysed", data.total_deployments],
    ["Successful", data.successful_deployments],
    ["Failed", data.failed_deployments],
    ["Open incidents", data.open_incidents],
    ["Risk alerts (30 days)", data.risk_alerts],
  ];

  return (
    <>
      <div className="page-head row" style={{ alignItems: "center" }}>
        <div>
          <h1>Dashboard</h1>
          <span className="muted">{project?.name}</span>
        </div>
        <div style={{ textAlign: "right" }}>
          <Link to="/analyze" className="btn">Analyse deployment logs</Link>
        </div>
      </div>

      <div className="grid g5" style={{ marginBottom: 18 }}>
        {stats.map(([l, n]) => (
          <div className="card stat" key={l} style={{ marginBottom: 0 }}>
            <div className="n">{n}</div>
            <div className="l">{l}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>Insights</h2>
        <ul className="steps">{data.insights.map((t) => <li key={t}>{t}</li>)}</ul>
        <p className="small muted" style={{ marginBottom: 0 }}>Calculated from your stored incidents.</p>
      </div>

      <div className="card">
        <h2>Recent incidents</h2>
        <IncidentTable incidents={data.recent_incidents} onOpen={(id) => navigate(`/incidents/${id}`)} />
      </div>

      <div className="card">
        <h2>Recent deployment activity</h2>
        {data.recent_deployments.length === 0 ? (
          <p className="muted">No deployments analysed yet.</p>
        ) : (
          <table>
            <thead><tr><th>Deployment</th><th>Version</th><th>Env</th><th>Status</th><th>Errors</th><th>When</th></tr></thead>
            <tbody>
              {data.recent_deployments.map((d) => (
                <tr key={d.id}>
                  <td>{d.name}</td><td>{d.version || "-"}</td><td>{d.environment}</td>
                  <td><Badge value={d.status} /></td><td>{d.error_count}</td><td className="small">{fmtDate(d.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
