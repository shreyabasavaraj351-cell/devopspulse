import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { Alert, Button, Logo } from "../components/ui";

export default function Onboarding() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [f, setF] = useState({ organization_name: "", project_name: "", environment: "staging" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (f.organization_name.trim().length < 2 || f.project_name.trim().length < 2) return setError("Enter a team name and an application name.");
    setLoading(true);
    try {
      await api.onboard(f);
      await refresh();
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrap">
      <form className="auth-card" style={{ maxWidth: 520 }} onSubmit={submit} noValidate>
        <Logo />
        <h1>Welcome, {user?.full_name?.split(" ")[0]}</h1>
        <p className="muted">Set up your team and the first application DevOpsPulse will watch.</p>
        <div className="memory-box small">
          <strong>How the agent works.</strong> You upload deployment logs. It diagnoses the failure, recalls similar past incidents from
          memory, and recommends a fix. It only treats a fix as verified after you confirm the outcome, and then remembers it for next time.
        </div>
        <Alert>{error}</Alert>
        <label htmlFor="org">Organization or team name</label>
        <input id="org" value={f.organization_name} onChange={set("organization_name")} />
        <label htmlFor="proj">Project / application name</label>
        <input id="proj" value={f.project_name} onChange={set("project_name")} />
        <label htmlFor="env">Deployment environment</label>
        <select id="env" value={f.environment} onChange={set("environment")}>
          <option value="development">Development</option>
          <option value="testing">Testing</option>
          <option value="staging">Staging</option>
        </select>
        <Button className="btn block" loading={loading} type="submit">Go to dashboard</Button>
      </form>
    </div>
  );
}
