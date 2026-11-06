import { useState } from "react";
import { Link } from "react-router-dom";

export const Logo = () => (
  <div className="logo">
    <div className="logo-mark">DP</div>
    <span>DevOpsPulse</span>
  </div>
);

export const Alert = ({ kind = "error", children }) =>
  children ? <div className={`alert ${kind}`} role={kind === "error" ? "alert" : undefined}>{children}</div> : null;

export const Badge = ({ value, label }) =>
  value ? <span className={`badge ${String(value).toLowerCase()}`}>{(label || String(value)).replace(/_/g, " ")}</span> : null;

export const Spinner = ({ dark }) => <span className={`spinner ${dark ? "dark" : ""}`} aria-hidden="true" />;

export function Button({ loading, children, ...rest }) {
  return (
    <button className="btn" {...rest} disabled={loading || rest.disabled}>
      {loading && <Spinner />}
      {children}
    </button>
  );
}

export function PasswordInput({ value, onChange, id, autoComplete = "current-password", placeholder }) {
  const [show, setShow] = useState(false);
  return (
    <div className="pw">
      <input id={id} type={show ? "text" : "password"} value={value} onChange={onChange} autoComplete={autoComplete} placeholder={placeholder} />
      <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide password" : "Show password"}>
        {show ? "Hide" : "Show"}
      </button>
    </div>
  );
}

export const fmtDate = (d) => (d ? new Date(d).toLocaleString() : "");

export function IncidentTable({ incidents, onOpen }) {
  if (!incidents?.length) return <p className="muted">No incidents to show.</p>;
  return (
    <table>
      <thead>
        <tr><th>ID</th><th>When</th><th>Application</th><th>Category</th><th>Severity</th><th>Root cause</th><th>Status</th></tr>
      </thead>
      <tbody>
        {incidents.map((i) => (
          <tr key={i.id} className="clickable" onClick={() => onOpen(i.id)}>
            <td><Link to={`/incidents/${i.id}`} onClick={(e) => e.stopPropagation()}>#{i.id}</Link></td>
            <td className="small">{fmtDate(i.created_at)}</td>
            <td>{i.deployment_name}</td>
            <td><Badge value={i.category} /></td>
            <td><Badge value={i.severity} /></td>
            <td style={{ maxWidth: 320 }}>{i.root_cause.length > 120 ? i.root_cause.slice(0, 120) + "…" : i.root_cause}</td>
            <td><Badge value={i.status} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function MemoryList({ memories }) {
  if (!memories?.length) return null;
  return memories.map((m, i) => (
    <div className="mem-item" key={i}>
      <strong>M{i + 1}</strong> {m.text}
    </div>
  ));
}
