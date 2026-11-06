import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../services/api";
import { Alert, Button, Logo, PasswordInput } from "../components/ui";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (pw.length < 8 || !/[A-Za-z]/.test(pw) || !/\d/.test(pw)) return setError("Password needs 8+ characters with a letter and a number.");
    if (pw !== pw2) return setError("Passwords do not match.");
    setLoading(true);
    try {
      await api.resetPassword(token, pw);
      setDone(true);
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
        {!token ? (
          <Alert>This reset link is missing its token. Request a new one.</Alert>
        ) : done ? (
          <>
            <h1>Password updated</h1>
            <Alert kind="ok">You can now sign in with your new password.</Alert>
          </>
        ) : (
          <>
            <h1>Set a new password</h1>
            <Alert>{error}</Alert>
            <label htmlFor="pw">New password</label>
            <PasswordInput id="pw" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="new-password" />
            <label htmlFor="pw2">Confirm new password</label>
            <PasswordInput id="pw2" value={pw2} onChange={(e) => setPw2(e.target.value)} autoComplete="new-password" />
            <Button className="btn block" loading={loading} type="submit">Update password</Button>
          </>
        )}
        <p className="small" style={{ textAlign: "center", marginTop: 18 }}>
          <Link to={token ? "/login" : "/forgot-password"}>{token ? "Go to sign in" : "Request a new link"}</Link>
        </p>
      </form>
    </div>
  );
}
