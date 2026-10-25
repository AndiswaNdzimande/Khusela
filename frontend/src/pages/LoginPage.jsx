import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { API_MODE, MODE_LABEL } from "../api/client";
import Icon from "../components/Icon";
import Logo from "../components/Logo";
import { useAuth } from "../context/AuthContext";

const DEMO_BUSINESS = "Thandi's Threads";
const DEMO_PASSWORD = "demo1234";

export default function LoginPage() {
  const { signIn, signUp } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [tab, setTab] = useState("signin");
  const [businessName, setBusinessName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function goNext() {
    const from = location.state?.from;
    navigate(from && from !== "/login" ? from : "/check", { replace: true });
  }

  async function handleSignIn(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await signIn({ businessName, password });
      goNext();
    } catch (err) {
      setError(err.message || "Could not sign in. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRegister(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await signUp(businessName, password);
      goNext();
    } catch (err) {
      setError(err.message || "Could not create the workspace. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function useDemo() {
    setTab("signin");
    setBusinessName(DEMO_BUSINESS);
    setPassword(DEMO_PASSWORD);
    setError("");
    setBusy(true);
    try {
      await signIn({ businessName: DEMO_BUSINESS, password: DEMO_PASSWORD });
      goNext();
    } catch (err) {
      setError(err.message || "Could not open the demo workspace. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <section className="auth-art">
        <div className="auth-art-top">
          <Logo to="/login" variant="full" />
          <span className="auth-mode">
            <span className="mode-dot" />
            {MODE_LABEL}
          </span>
        </div>
        <div className="auth-art-copy">
          <p className="eyebrow">Payment-risk verification</p>
          <h1>Secure the bag. Protect the business.</h1>
          <p className="auth-lede">
            Check a buyer&apos;s payment screenshot before the parcel leaves your
            hands. Khusela looks for edited documents, mismatched claims and
            reused fakes.
          </p>
          <ul className="auth-points">
            <li>
              <span><Icon name="file" size={18} /></span>
              Document check for editing traces
            </li>
            <li>
              <span><Icon name="search" size={18} /></span>
              Payment claim cross-reference
            </li>
            <li>
              <span><Icon name="shieldCheck" size={18} /></span>
              STOP, WAIT or MATCH with a clear next step
            </li>
          </ul>
        </div>
        <p className="auth-art-foot">
          A MATCH still needs your banking app. Khusela never says PAID.
        </p>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <Logo to="/login" className="auth-form-logo" />
          <div className="auth-card-head">
            <p className="eyebrow">Seller console</p>
            <h2>{tab === "signin" ? "Sign in to Khusela" : "Create your workspace"}</h2>
            <p>
              {tab === "signin"
                ? "Sign in with the business name and password you registered."
                : "Protect your sales with a seller workspace."}
            </p>
          </div>

          <div className="tabs" role="tablist" aria-label="Authentication">
            <button
              type="button"
              role="tab"
              aria-selected={tab === "signin"}
              className={tab === "signin" ? "tab is-active" : "tab"}
              onClick={() => {
                setTab("signin");
                setError("");
              }}
            >
              Sign in
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "register"}
              className={tab === "register" ? "tab is-active" : "tab"}
              onClick={() => {
                setTab("register");
                setError("");
              }}
            >
              Create account
            </button>
          </div>

          {error && (
            <div className="alert alert-error" role="alert">
              <Icon name="alert" size={18} />
              <span>{error}</span>
            </div>
          )}

          {tab === "signin" ? (
            <form className="form-stack" onSubmit={handleSignIn}>
              <label className="field">
                <span className="field-label">Business name</span>
                <input
                  className="input"
                  value={businessName}
                  onChange={(event) => setBusinessName(event.target.value)}
                  placeholder="e.g. Thandi's Threads"
                  autoComplete="username"
                  required
                />
              </label>
              <label className="field">
                <span className="field-label">Password</span>
                <input
                  className="input"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Your password"
                  autoComplete="current-password"
                  required
                />
              </label>
              <button className="button button-primary button-block" disabled={busy}>
                {busy ? <span className="spinner" /> : <Icon name="arrowRight" size={17} />}
                {busy ? "Signing in…" : "Sign in"}
              </button>
              {API_MODE === "mock" && (
                <button type="button" className="demo-token" onClick={useDemo} disabled={busy}>
                  <Icon name="spark" size={16} />
                  Open the demo workspace
                </button>
              )}
            </form>
          ) : (
            <form className="form-stack" onSubmit={handleRegister}>
              <label className="field">
                <span className="field-label">Business name</span>
                <input
                  className="input"
                  value={businessName}
                  onChange={(event) => setBusinessName(event.target.value)}
                  placeholder="e.g. Thandi's Threads"
                  autoComplete="organization"
                  required
                />
              </label>
              <label className="field">
                <span className="field-label">Password</span>
                <input
                  className="input"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="At least 8 characters"
                  autoComplete="new-password"
                  minLength={8}
                  required
                />
              </label>
              <button className="button button-primary button-block" disabled={busy}>
                {busy ? <span className="spinner" /> : <Icon name="shieldCheck" size={17} />}
                {busy ? "Creating workspace…" : "Create workspace"}
              </button>
              <p className="field-hint center">
                {API_MODE === "live"
                  ? "Your workspace is created on the live API, then your checks use its session token."
                  : "The mock stores this seller in the local json-server database."}
              </p>
            </form>
          )}

          <p className="auth-smallprint">
            By continuing you agree to check every payment in your own banking app
            before releasing goods.
          </p>
        </div>
      </section>
    </div>
  );
}
