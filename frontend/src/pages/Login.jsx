import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { Alert, Button, Logo, PasswordInput } from "../components/ui";

export default function Login() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!/^\S+@\S+\.\S+$/.test(email)) return setError("Enter a valid email address.");
    if (!password) return setError("Enter your password.");
    setLoading(true);
    try {
      const data = await api.login({ email, password, remember_me: remember });
      await signIn(data, remember);
      navigate(data.user.onboarded ? "/" : "/onboarding", { replace: true });
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
        <h1>Welcome back</h1>
        <p className="muted">Sign in to analyse deployments and recall past incidents.</p>
        <Alert>{error}</Alert>
        <label htmlFor="email">Email</label>
        <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
        <label htmlFor="password">Password</label>
        <PasswordInput id="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <div className="row" style={{ alignItems: "center", justifyContent: "space-between" }}>
          <label className="check" style={{ flex: "none" }}>
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} /> Remember me
          </label>
          <Link to="/forgot-password" className="small" style={{ flex: "none", minWidth: 0 }}>Forgot password?</Link>
        </div>
        <Button className="btn block" loading={loading} type="submit">Sign in</Button>
        <p className="small muted" style={{ textAlign: "center", marginTop: 18 }}>
          New here? <Link to="/register">Create an account</Link>
        </p>
      </form>
    </div>
  );
}
