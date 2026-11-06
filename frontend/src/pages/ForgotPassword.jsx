import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { Alert, Button, Logo } from "../components/ui";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!/^\S+@\S+\.\S+$/.test(email)) return setError("Enter a valid email address.");
    setLoading(true);
    try {
      await api.forgotPassword(email);
      setSent(true);
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
        {sent ? (
          <>
            <h1>Check your email</h1>
            <Alert kind="ok">If an account exists for {email}, a password reset link has been sent. It expires in 30 minutes.</Alert>
            <p className="small muted">Running locally with no email provider? The reset link is printed in the backend server console.</p>
          </>
        ) : (
          <>
            <h1>Forgot your password?</h1>
            <p className="muted">Enter your email and we'll send a reset link.</p>
            <Alert>{error}</Alert>
            <label htmlFor="email">Email</label>
            <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            <Button className="btn block" loading={loading} type="submit">Send password reset link</Button>
          </>
        )}
        <p className="small" style={{ textAlign: "center", marginTop: 18 }}><Link to="/login">Back to sign in</Link></p>
      </form>
    </div>
  );
}
