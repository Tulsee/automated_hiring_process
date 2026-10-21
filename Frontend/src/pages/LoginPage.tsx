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
import { entryHref } from "../lib/entry";

type Mode = "signin" | "signup";

/**
 * The sign-in screen. `audience` decides what it offers:
 *   - "admin" is sign-in only (hiring-team accounts are created by an admin);
 *   - "candidate" also offers self-signup.
 * Each links across to the other's URL, and back to the public job board.
 */
export function LoginPage({
  audience = "candidate",
}: {
  audience?: "admin" | "candidate";
}) {
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

        <p className="login-audience">
          {audience === "admin" ? "Hiring team sign-in" : "Candidate access"}
        </p>

        {audience === "candidate" ? (
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
        ) : null}

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
          {audience === "admin" ? (
            <>
              Hiring-team access only. Are you a candidate?{" "}
              <a href={entryHref("apply")}>Apply or sign in here</a>.
            </>
          ) : (
            <>
              Candidates sign in or create an account here. Hiring team?{" "}
              <a href={entryHref("admin")}>Sign in here</a>.
            </>
          )}
        </p>

        <p className="login-foot">
          <a href={entryHref("root")}>← Back to open roles</a>
        </p>
      </div>
    </div>
  );
}
