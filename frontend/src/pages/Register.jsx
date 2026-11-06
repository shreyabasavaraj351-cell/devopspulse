import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { Alert, Button, Logo, PasswordInput } from "../components/ui";

const rules = (pw) => [
  ["At least 8 characters", pw.length >= 8],
  ["Contains a letter", /[A-Za-z]/.test(pw)],
  ["Contains a number", /\d/.test(pw)],
];

export default function Register() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [f, setF] = useState({ full_name: "", email: "", password: "", confirm_password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (f.full_name.trim().length < 2) return setError("Enter your full name.");
    if (!/^\S+@\S+\.\S+$/.test(f.email)) return setError("Enter a valid work email.");
    if (!rules(f.password).every(([, ok]) => ok)) return setError("Password does not meet the requirements.");
    if (f.password !== f.confirm_password) return setError("Passwords do not match.");
    setLoading(true);
    try {
      const data = await api.register(f);
      await signIn(data, false);
      navigate("/onboarding", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={submit} noValidate>
        <Logo />
        <h1>Create your account</h1>
        <Alert>{error}</Alert>
        <label htmlFor="name">Full name</label>
        <input id="name" value={f.full_name} onChange={set("full_name")} autoComplete="name" />
        <label htmlFor="email">Work email</label>
        <input id="email" type="email" value={f.email} onChange={set("email")} autoComplete="email" />
        <label htmlFor="pw">Password</label>
        <PasswordInput id="pw" value={f.password} onChange={set("password")} autoComplete="new-password" />
        <ul className="small muted" style={{ margin: "8px 0 0", paddingLeft: 18 }}>
          {rules(f.password).map(([label, ok]) => (
            <li key={label} style={{ color: ok ? "var(--ok)" : undefined }}>{label}</li>
          ))}
        </ul>
        <label htmlFor="pw2">Confirm password</label>
        <PasswordInput id="pw2" value={f.confirm_password} onChange={set("confirm_password")} autoComplete="new-password" />
        <Button className="btn block" loading={loading} type="submit">Create account</Button>
        <p className="small muted" style={{ textAlign: "center", marginTop: 18 }}>
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
