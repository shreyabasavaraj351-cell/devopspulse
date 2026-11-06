import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { Alert, Badge, Button, PasswordInput } from "../components/ui";

export default function Settings() {
  const { user, setUser, logout } = useAuth();
  const navigate = useNavigate();
  const [profile, setProfile] = useState({ full_name: user.full_name, email: user.email });
  const [pwd, setPwd] = useState({ current_password: "", new_password: "" });
  const [integ, setInteg] = useState(null);
  const [pNote, setPNote] = useState(null);
  const [wNote, setWNote] = useState(null);
  const [busy, setBusy] = useState("");

  useEffect(() => { api.integrations().then(setInteg).catch(() => setInteg(false)); }, []);

  const saveProfile = async (e) => {
    e.preventDefault();
    setBusy("profile");
    setPNote(null);
    try {
      setUser(await api.updateProfile(profile));
      setPNote({ kind: "ok", text: "Profile updated." });
    } catch (err) {
      setPNote({ kind: "error", text: err.message });
    } finally { setBusy(""); }
  };

  const savePassword = async (e) => {
    e.preventDefault();
    setBusy("pw");
    setWNote(null);
    try {
      await api.changePassword(pwd);
      setPwd({ current_password: "", new_password: "" });
      setWNote({ kind: "ok", text: "Password changed." });
    } catch (err) {
      setWNote({ kind: "error", text: err.message });
    } finally { setBusy(""); }
  };

  return (
    <>
      <div className="page-head"><h1>Settings</h1></div>
      <div className="grid g2">
        <form className="card" onSubmit={saveProfile}>
          <h2>Profile</h2>
          <label htmlFor="fn">Full name</label><input id="fn" value={profile.full_name} onChange={(e) => setProfile({ ...profile, full_name: e.target.value })} />
          <label htmlFor="em">Email</label><input id="em" type="email" value={profile.email} onChange={(e) => setProfile({ ...profile, email: e.target.value })} />
          {pNote && <Alert kind={pNote.kind}>{pNote.text}</Alert>}
          <div style={{ marginTop: 16 }}><Button loading={busy === "profile"} type="submit">Save profile</Button></div>
        </form>

        <form className="card" onSubmit={savePassword}>
          <h2>Change password</h2>
          <label htmlFor="cp">Current password</label>
          <PasswordInput id="cp" value={pwd.current_password} onChange={(e) => setPwd({ ...pwd, current_password: e.target.value })} />
          <label htmlFor="np">New password</label>
          <PasswordInput id="np" value={pwd.new_password} onChange={(e) => setPwd({ ...pwd, new_password: e.target.value })} autoComplete="new-password" />
          {wNote && <Alert kind={wNote.kind}>{wNote.text}</Alert>}
          <div style={{ marginTop: 16 }}><Button loading={busy === "pw"} type="submit">Change password</Button></div>
        </form>
      </div>

      <div className="card">
        <h2>Organization</h2>
        <p style={{ margin: 0 }}>{user.organization_name}</p>
      </div>

      <div className="card">
        <h2>Integrations and memory</h2>
        {integ === null && <p className="muted">Checking…</p>}
        {integ === false && <Alert>Could not load integration status.</Alert>}
        {integ && (
          <table>
            <tbody>
              <tr><td>Groq (AI analysis)</td><td><Badge value={integ.groq.configured ? "success" : "failed"} label={integ.groq.configured ? "Configured" : "Not configured"} /> <span className="small muted">{integ.groq.model}</span></td></tr>
              <tr><td>Hindsight health endpoint</td><td><Badge value={integ.hindsight.reachable ? "success" : "failed"} label={integ.hindsight.reachable ? "Healthy" : "Unavailable"} /></td></tr>
              <tr><td>Database</td><td>{integ.database}</td></tr>
              {integ.memory_banks.map((b) => (
                <tr key={b.project_id}><td>Memory bank: {b.project}</td><td className="mono">{b.bank}</td></tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="small muted">Hindsight health does not verify retain, recall or reflect operations. API keys are stored on the server only and are never sent to the browser.</p>
      </div>

      <div className="card">
        <button className="btn danger" onClick={() => { logout(); navigate("/login"); }}>Log out</button>
      </div>
    </>
  );
}
