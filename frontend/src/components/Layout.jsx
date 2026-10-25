import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { API_MODE, MODE_LABEL } from "../api/client";
import Icon from "./Icon";
import Logo from "./Logo";

function initials(name) {
  return String(name || "K")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

export default function Layout() {
  const { session, signOut } = useAuth();

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-inner">
          <Logo />
          <nav className="main-nav" aria-label="Main navigation">
            <NavLink
              to="/check"
              className={({ isActive }) => (isActive ? "nav-link is-active" : "nav-link")}
            >
              <Icon name="plus" size={16} />
              <span>New check</span>
            </NavLink>
            <NavLink
              to="/history"
              className={({ isActive }) => (isActive ? "nav-link is-active" : "nav-link")}
            >
              <Icon name="history" size={16} />
              <span>History</span>
            </NavLink>
          </nav>
          <div className="header-actions">
            <span className={`mode-pill mode-${API_MODE}`}>
              <span className="mode-dot" />
              <span className="mode-text">{MODE_LABEL}</span>
            </span>
            <span className="seller-chip" title={session?.business_name}>
              <span className="seller-avatar" aria-hidden="true">
                {initials(session?.business_name)}
              </span>
              <span className="seller-name">{session?.business_name}</span>
            </span>
            <button
              type="button"
              className="icon-button"
              onClick={signOut}
              aria-label="Sign out"
              title="Sign out"
            >
              <Icon name="logout" size={18} />
            </button>
          </div>
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
      <footer className="app-footer">
        <span>Khusela protects the seller before the parcel leaves.</span>
        <span>Never release goods on a screenshot alone.</span>
      </footer>
    </div>
  );
}
