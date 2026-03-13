import { type FormEvent, useState } from "react";
import { login, register } from "./api";

interface Props {
  onLogin: (accessToken: string, refreshToken: string) => void;
}

export function AuthPage({ onLogin }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === "register") {
        await register(email, password);
        setMode("login");
        setPassword("");
        setLoading(false);
        return;
      }

      const tokens = await login(email, password);
      onLogin(tokens.access_token, tokens.refresh_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-center">
      <div className="card">
        <h1>{mode === "login" ? "Sign In" : "Create Account"}</h1>

        <form onSubmit={handleSubmit}>
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          {error && <p className="error">{error}</p>}

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "..." : mode === "login" ? "Sign In" : "Register"}
          </button>
        </form>

        <p className="toggle-text">
          {mode === "login" ? "No account? " : "Have an account? "}
          <button
            type="button"
            className="btn-link"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError(null);
            }}
          >
            {mode === "login" ? "Register" : "Sign In"}
          </button>
        </p>
      </div>
    </div>
  );
}
