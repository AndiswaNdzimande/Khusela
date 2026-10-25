import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getHistory } from "../api/client";
import Icon from "../components/Icon";
import VerdictBadge from "../components/VerdictBadge";
import { useAuth } from "../context/AuthContext";

const FILTERS = ["ALL", "MATCH", "WAIT", "STOP"];

function money(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  return `R ${Number(value).toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function shortDate(value) {
  return new Date(value).toLocaleString("en-ZA", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function HistoryPage() {
  const { session } = useAuth();
  const navigate = useNavigate();
  const [checks, setChecks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("ALL");
  const [query, setQuery] = useState("");

  useEffect(() => {
    let active = true;
    getHistory({ token: session?.token }).then((items) => {
      if (active) {
        setChecks(items);
        setLoading(false);
      }
    });
    return () => {
      active = false;
    };
  }, [session?.token]);

  const counts = useMemo(() => {
    return checks.reduce(
      (result, check) => {
        result[check.verdict] = (result[check.verdict] || 0) + 1;
        return result;
      },
      { MATCH: 0, WAIT: 0, STOP: 0 },
    );
  }, [checks]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return checks.filter((check) => {
      const inFilter = filter === "ALL" || check.verdict === filter;
      const haystack = [
        check.check_id,
        check.expected?.recipient,
        check.expected?.reference,
        check.extracted?.recipient,
        check.extracted?.reference,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return inFilter && (!needle || haystack.includes(needle));
    });
  }, [checks, filter, query]);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">Check history</p>
          <h1>Every proof you have checked.</h1>
          <p className="page-lede">
            The verdict, the sale it was compared against and the signals behind
            it. Open any check to read the OCR text again.
          </p>
        </div>
        <Link className="button button-primary" to="/check">
          <Icon name="plus" size={16} />
          New check
        </Link>
      </header>

      <div className="history-stats">
        <div className="stat">
          <span className="stat-label">Total checks</span>
          <strong>{checks.length}</strong>
        </div>
        <div className="stat stat-match">
          <span className="stat-label">Match</span>
          <strong>{counts.MATCH}</strong>
        </div>
        <div className="stat stat-wait">
          <span className="stat-label">Wait</span>
          <strong>{counts.WAIT}</strong>
        </div>
        <div className="stat stat-stop">
          <span className="stat-label">Stop</span>
          <strong>{counts.STOP}</strong>
        </div>
      </div>

      <section className="card history-card">
        <div className="toolbar">
          <div className="segmented" role="group" aria-label="Filter by verdict">
            {FILTERS.map((value) => (
              <button
                key={value}
                type="button"
                className={filter === value ? "segment is-active" : "segment"}
                onClick={() => setFilter(value)}
              >
                {value === "ALL" ? "All" : value}
                <span>{value === "ALL" ? checks.length : counts[value]}</span>
              </button>
            ))}
          </div>
          <label className="search-field">
            <Icon name="search" size={16} />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search check, name or reference"
              aria-label="Search checks"
            />
          </label>
        </div>

        {loading ? (
          <div className="state-card state-inline" aria-live="polite">
            <span className="spinner" />
            <p>Loading your checks…</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="state-card state-inline">
            <span className="state-icon"><Icon name="history" size={24} /></span>
            <h2>{checks.length ? "No checks match that filter." : "No checks yet."}</h2>
            <p>
              {checks.length
                ? "Try all verdicts or clear the search."
                : "Run your first payment check and it will stay in this history."}
            </p>
            {!checks.length && (
              <Link className="button button-primary" to="/check">
                <Icon name="plus" size={16} />
                Run the first check
              </Link>
            )}
          </div>
        ) : (
          <>
            <div className="history-cards">
              {filtered.map((check) => (
                <Link
                  key={check.check_id}
                  className="history-mobile-card"
                  to={`/result/${check.check_id}`}
                >
                  <div className="hm-top">
                    <span className="mono">{check.check_id}</span>
                    <VerdictBadge verdict={check.verdict} />
                  </div>
                  <div className="hm-main">
                    <strong>{check.expected?.recipient || "Unknown recipient"}</strong>
                    <span>{money(check.expected?.amount)}</span>
                  </div>
                  <div className="hm-meta">
                    <span>Ref {check.expected?.reference || "—"}</span>
                    <span>{shortDate(check.created_at)}</span>
                    <span>{Math.round((check.ocr_confidence || 0) * 100)}% OCR</span>
                  </div>
                </Link>
              ))}
            </div>

            <div className="table-wrap history-table-view">
              <table className="table history-table">
                <thead>
                  <tr>
                    <th>Check</th>
                    <th>Expected sale</th>
                    <th>Amount</th>
                    <th>Verdict</th>
                    <th>OCR</th>
                    <th>Time</th>
                    <th aria-label="Open" />
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((check) => (
                    <tr
                      key={check.check_id}
                      onClick={() => navigate(`/result/${check.check_id}`)}
                      className="clickable-row"
                    >
                      <td data-label="Check">
                        <span className="mono strong">{check.check_id}</span>
                      </td>
                      <td data-label="Expected sale">
                        <span className="strong">
                          {check.expected?.recipient || "Unknown recipient"}
                        </span>
                        <span className="sub mono">
                          Ref {check.expected?.reference || "—"}
                        </span>
                      </td>
                      <td data-label="Amount" className="strong">
                        {money(check.expected?.amount)}
                      </td>
                      <td data-label="Verdict">
                        <VerdictBadge verdict={check.verdict} />
                      </td>
                      <td data-label="OCR">
                        <span className="confidence-inline">
                          {Math.round((check.ocr_confidence || 0) * 100)}%
                        </span>
                      </td>
                      <td data-label="Time">{shortDate(check.created_at)}</td>
                      <td className="row-arrow" aria-hidden="true">
                        <Icon name="chevron" size={16} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="table-foot">
              Showing {filtered.length} of {checks.length} checks
            </p>
          </>
        )}
      </section>
    </div>
  );
}
