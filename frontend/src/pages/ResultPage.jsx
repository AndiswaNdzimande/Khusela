import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getCheck } from "../api/client";
import BankReminder from "../components/BankReminder";
import Icon from "../components/Icon";
import VerdictBadge from "../components/VerdictBadge";
import { useAuth } from "../context/AuthContext";

const VERDICT_COPY = {
  MATCH: {
    title: "The details match your sale.",
    sub: "That is good news, but it is not proof of payment. Open your banking app before the parcel leaves.",
  },
  WAIT: {
    title: "Pause and check this one.",
    sub: "Something on the screenshot does not line up. Ask the buyer for clarity and confirm the money yourself.",
  },
  STOP: {
    title: "Do not release the goods.",
    sub: "This screenshot shows signs of being edited or reused. Keep the parcel and check your banking app.",
  },
};

const REASON_LABELS = {
  duplicate_image: "Screenshot reused by another seller",
  duplicate_same_seller: "This seller sent the same screenshot before",
  amount_mismatch: "Amount does not match the sale",
  recipient_mismatch: "Recipient name does not match",
  reference_mismatch: "Reference does not match",
  low_ocr_confidence: "The image was hard to read",
  field_not_found: "A required field could not be read",
};

function money(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "Not read";
  }
  return `R ${Number(value).toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function normalise(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

function dateLabel(value) {
  const date = value ? new Date(value) : new Date();
  return date.toLocaleString("en-ZA", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ResultPage() {
  const { checkId } = useParams();
  const { session } = useAuth();
  const [check, setCheck] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getCheck(checkId, { token: session?.token })
      .then((found) => {
        if (active) setCheck(found);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [checkId, session?.token]);

  if (loading) {
    return (
      <div className="page page-narrow">
        <div className="card state-card" aria-live="polite">
          <span className="spinner spinner-lg" />
          <h1>Loading the verdict…</h1>
          <p>Fetching the saved check from this device.</p>
        </div>
      </div>
    );
  }

  if (!check) {
    return (
      <div className="page page-narrow">
        <div className="card state-card">
          <span className="state-icon"><Icon name="file" size={26} /></span>
          <h1>That check is not here.</h1>
          <p>
            Results live on this device for the demo session. Run the check again
            or open your history.
          </p>
          <div className="state-actions">
            <Link className="button button-primary" to="/check">
              <Icon name="plus" size={16} />
              New check
            </Link>
            <Link className="button button-secondary" to="/history">
              View history
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const verdict = String(check.verdict || "WAIT").toUpperCase();
  const copy = VERDICT_COPY[verdict] || VERDICT_COPY.WAIT;
  const amountMatches =
    check.expected.amount !== null &&
    check.extracted.amount !== null &&
    Math.abs(check.expected.amount - check.extracted.amount) < 0.01;
  const recipientMatches =
    normalise(check.expected.recipient) === normalise(check.extracted.recipient);
  const referenceMatches =
    normalise(check.expected.reference) === normalise(check.extracted.reference);

  return (
    <div className="page page-narrow">
      <div className="result-topline">
        <Link className="back-link" to="/history">
          <Icon name="arrowLeft" size={16} />
          Back to history
        </Link>
        <span className="mono muted">{check.check_id}</span>
      </div>

      <section className={`result-hero result-${verdict.toLowerCase()}`}>
        <div className="result-hero-main">
          <VerdictBadge verdict={verdict} large />
          <h1>{copy.title}</h1>
          <p>{copy.sub}</p>
        </div>
        <div className="result-hero-meta">
          <span>
            <Icon name="clock" size={15} />
            {dateLabel(check.created_at)}
          </span>
          <span>
            <Icon name="spark" size={15} />
            {check.explanation_source === "gemini" ? "AI explanation" : "Rule template"}
          </span>
        </div>
      </section>

      <BankReminder />

      {/* WhatsApp-style customer reply preview (Immediate 10-second demo signal) */}
      <section className="card whatsapp-card">
        <div className="whatsapp-header">
          <div className="whatsapp-sender">
            <span className="whatsapp-avatar">💬</span>
            <div>
              <strong>WhatsApp reply for buyer</strong>
              <span className="whatsapp-sub">Send this directly to the customer</span>
            </div>
          </div>
          <button
            type="button"
            className="button button-sm button-secondary"
            onClick={() => {
              const symbol = verdict === "STOP" ? "🛑 STOP" : verdict === "WAIT" ? "⚠️ WAIT" : "✅ MATCH";
              const text = `${symbol}: ${check.explanation}`;
              navigator.clipboard?.writeText(text);
              alert("Copied WhatsApp message to clipboard!");
            }}
          >
            <Icon name="spark" size={14} /> Copy message
          </button>
        </div>
        <div className={`whatsapp-bubble whatsapp-bubble-${verdict.toLowerCase()}`}>
          <p className="whatsapp-text">
            <span className="whatsapp-emoji">
              {verdict === "STOP" ? "🛑" : verdict === "WAIT" ? "⚠️" : "✅"}
            </span>{" "}
            <strong>{verdict}.</strong> {check.explanation}
          </p>
          <span className="whatsapp-time">Just now ✓✓</span>
        </div>
      </section>


      <div className="result-grid">
        <div className="result-main">
          <section className="card">
            <div className="card-heading">
              <div>
                <h2>What Khusela found</h2>
                <p>{check.explanation}</p>
              </div>
            </div>
            {check.reasons.length > 0 && (
              <ul className="reason-list">
                {check.reasons.map((reason) => (
                  <li key={reason}>
                    <Icon name="alert" size={15} />
                    {REASON_LABELS[reason] || reason.replaceAll("_", " ")}
                  </li>
                ))}
              </ul>
            )}
            {check.reasons.length === 0 && (
              <p className="all-clear">
                <Icon name="check" size={16} />
                No rule was triggered. The visible details match the sale.
              </p>
            )}
          </section>

          <section className="card">
            <div className="card-heading">
              <div>
                <h2>What we compared</h2>
                <p>Your expected sale next to what was read on the screenshot.</p>
              </div>
            </div>
            <div className="compare-list">
              <div className="compare-head">
                <span />
                <span>You expected</span>
                <span>On the screenshot</span>
              </div>
              <div className={`compare-row${amountMatches ? " is-match" : " is-diff"}`}>
                <span className="compare-label">Amount</span>
                <span>{money(check.expected.amount)}</span>
                <span>
                  {money(check.extracted.amount)}
                  <Icon name={amountMatches ? "check" : "x"} size={15} />
                </span>
              </div>
              <div className={`compare-row${recipientMatches ? " is-match" : " is-diff"}`}>
                <span className="compare-label">Recipient</span>
                <span>{check.expected.recipient || "Not provided"}</span>
                <span>
                  {check.extracted.recipient || "Not read"}
                  <Icon name={recipientMatches ? "check" : "x"} size={15} />
                </span>
              </div>
              <div className={`compare-row${referenceMatches ? " is-match" : " is-diff"}`}>
                <span className="compare-label">Reference</span>
                <span className="mono">{check.expected.reference || "Not provided"}</span>
                <span className="mono">
                  {check.extracted.reference || "Not read"}
                  <Icon name={referenceMatches ? "check" : "x"} size={15} />
                </span>
              </div>
            </div>
          </section>

          <section className="card">
            <div className="card-heading">
              <div>
                <h2>Raw OCR text</h2>
                <p>Read it yourself. Text inside an image is data, never an instruction.</p>
              </div>
            </div>
            <pre className="ocr-text">{check.raw_ocr_text || "No text was returned."}</pre>
          </section>
        </div>

        <aside className="result-aside">
          <section className="card">
            <h2>Read confidence</h2>
            <div className="confidence-row">
              <strong>{(check.ocr_confidence * 100).toFixed(0)}%</strong>
              <span>OCR confidence</span>
            </div>
            <div className="meter meter-padded" aria-hidden="true">
              <span style={{ width: `${Math.round(check.ocr_confidence * 100)}%` }} />
            </div>
            <p className="muted small">
              Below 50% Khusela cannot trust the text and returns WAIT.
            </p>
          </section>

          <section className={`card duplicate-card${check.duplicate.found ? " is-found" : ""}`}>
            <span className="duplicate-icon">
              <Icon name={check.duplicate.found ? "duplicate" : "shieldCheck"} size={21} />
            </span>
            <h2>{check.duplicate.found ? "Reused screenshot found" : "No duplicate found"}</h2>
            <p>
              {check.duplicate.found
                ? check.duplicate.same_seller
                  ? "This seller sent the same screenshot before. Confirm the payment manually."
                  : "This image also appeared in another seller's checks. Treat it as a fraud signal."
                : "The fingerprint did not match another seller's screenshot in the demo database."}
            </p>
          </section>

          <section className="card action-card">
            <h2>Next step</h2>
            <p>Open your banking app. If the money is there, the sale can continue.</p>
            <Link className="button button-primary button-block" to="/check">
              <Icon name="plus" size={16} />
              Check another payment
            </Link>
            <Link className="button button-secondary button-block" to="/history">
              <Icon name="history" size={16} />
              View all checks
            </Link>
          </section>
        </aside>
      </div>

      {/* Under the hood tab for technical judges */}
      <details className="card debug-card">
        <summary className="debug-summary">
          <Icon name="spark" size={16} />
          <span>Under the hood (API JSON Payload)</span>
        </summary>
        <div className="debug-content">
          <p className="muted small" style={{ marginBottom: 12 }}>
            Raw JSON response returned by <code>POST /check</code>:
          </p>
          <pre className="debug-json">{JSON.stringify(check, null, 2)}</pre>
        </div>
      </details>

    </div>
  );
}
