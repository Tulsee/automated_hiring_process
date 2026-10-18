/**
 * The sign-in screen, shown when nobody is authenticated.
 *
 * Two audiences share it: administration users sign in, and candidates can
 * sign in or create an account. The candidate tab only ever calls
 * `/auth/register`, which the server restricts to candidate accounts, so the
 * public signup cannot mint an administration user.
 */

import { useState } from "react";
import { useAuth } from "../auth/context";
import { Icon } from "../components/Icon";
import { ApiError } from "../api/client";

type Mode = "signin" | "signup";

export function LoginPage() {
  const { signIn, register } = useAuth();

  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setPending(true);

    try {
      if (mode === "signup") {
        await register(email.trim(), password, name.trim());
      } else {
        await signIn(email.trim(), password);
      }
    } catch (caught: unknown) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Something went wrong signing in.",
      );
      setPending(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        <div className="login-brand">
          <span className="brand-mark">
            <Icon name="sparkles" size={20} />
          </span>
          <div>
            <strong>Hirewise</strong>
            <small>AI-assisted, human-decided hiring</small>
          </div>
        </div>

        <div className="login-tabs" role="tablist" aria-label="Sign in or sign up">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "signin"}
            className={mode === "signin" ? "is-active" : ""}
            onClick={() => {
              setMode("signin");
              setError(null);
            }}
          >
            Sign in
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "signup"}
            className={mode === "signup" ? "is-active" : ""}
            onClick={() => {
              setMode("signup");
              setError(null);
            }}
          >
            Create candidate account
          </button>
        </div>

        <form className="form-stack" onSubmit={submit}>
          {mode === "signup" ? (
            <label>
              Full name
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                autoComplete="name"
                required
              />
            </label>
          ) : null}

          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </label>

          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={
                mode === "signup" ? "new-password" : "current-password"
              }
              required
              minLength={mode === "signup" ? 8 : undefined}
            />
            {mode === "signup" ? (
              <span className="privacy-note">At least 8 characters.</span>
            ) : null}
          </label>

          {error ? (
            <div className="notice" role="alert">
              <Icon name="alert" size={16} />
              <div>
                <strong>Could not continue</strong>
                <p>{error}</p>
              </div>
            </div>
          ) : null}

          <button
            type="submit"
            className="button button--primary button--wide"
            disabled={pending}
          >
            {pending
              ? "Please wait…"
              : mode === "signup"
                ? "Create account"
                : "Sign in"}
          </button>
        </form>

        <p className="login-foot">
          {mode === "signin"
            ? "Recruiters and administrators sign in here. Candidates can create an account to track their applications."
            : "Creating an account is for candidates. Hiring-team access is granted by an administrator."}
        </p>
      </div>
    </div>
  );
}
