import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { API_MODE, runCheck } from "../api/client";
import BankReminder from "../components/BankReminder";
import Icon from "../components/Icon";
import UploadField from "../components/UploadField";
import VerdictBadge from "../components/VerdictBadge";
import { useAuth } from "../context/AuthContext";
import { validateReceipt, validateSale } from "../lib/validation";

const DEMOS = [
  {
    key: "match",
    label: "MATCH",
    amount: "1800.00",
    recipient: "Thabo Sneakers",
    reference: "SNK1800",
  },
  {
    key: "wait",
    label: "WAIT",
    amount: "1500.00",
    recipient: "Thabo Sneakers",
    reference: "SNK1800",
  },
  {
    key: "stop",
    label: "STOP",
    amount: "1800.00",
    recipient: "Thabo Sneakers",
    reference: "SNK-DUP",
  },
];

const PROCESS_STEPS = [
  "Checking the image header and file safety",
  "Reading the amount, recipient and reference",
  "Comparing the claim with your expected sale",
  "Looking for a reused screenshot",
  "Choosing STOP, WAIT or MATCH",
];

export default function NewCheckPage() {
  const { session } = useAuth();
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [uploadError, setUploadError] = useState("");
  const [amount, setAmount] = useState("");
  const [recipient, setRecipient] = useState("");
  const [reference, setReference] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [submitError, setSubmitError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sampleBusy, setSampleBusy] = useState(false);

  function applyDemo(demo) {
    setAmount(demo.amount);
    setRecipient(demo.recipient);
    setReference(demo.reference);
    setFieldErrors({});
    setSubmitError("");
  }

  async function loadSample() {
    setSampleBusy(true);
    setSubmitError("");
    try {
      const response = await fetch("/sample-receipt.png");
      if (!response.ok) throw new Error("Sample receipt unavailable.");
      const blob = await response.blob();
      setFile(new File([blob], "sample-receipt.png", { type: "image/png" }));
      setUploadError("");
    } catch {
      setUploadError("The sample receipt could not be loaded. Choose a screenshot from your device.");
    } finally {
      setSampleBusy(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const saleErrors = validateSale({ amount, recipient, reference });
    const receiptError = validateReceipt(file);
    setFieldErrors(saleErrors);
    setUploadError(receiptError);
    setSubmitError("");

    if (Object.keys(saleErrors).length || receiptError) {
      return;
    }

    setSubmitting(true);
    try {
      const check = await runCheck({
        file,
        amount,
        recipient,
        reference,
        token: session.token,
        sellerId: session.seller_id,
      });
      navigate(`/result/${check.check_id}`, { replace: true });
    } catch (error) {
      setSubmitError(error.message || "The check could not be completed. Please try again.");
      setSubmitting(false);
    }
  }

  return (
    <div className="page page-narrow">
      <header className="page-head">
        <div>
          <p className="eyebrow">New check</p>
          <h1>Check the proof before the parcel leaves.</h1>
          <p className="page-lede">
            Add the payment screenshot and the sale you expected. Khusela returns
            one clear next step in seconds.
          </p>
        </div>
        <div className="page-meta">
          <span><Icon name="shield" size={15} /> 5 MB limit</span>
          <span><Icon name="clock" size={15} /> 24h retention</span>
        </div>
      </header>

      <BankReminder compact />

      <div className="check-grid">
        <section className="card check-card">
          {submitting ? (
            <div className="processing" aria-live="polite">
              <span className="processing-mark">
                <Icon name="shieldCheck" size={30} />
              </span>
              <p className="eyebrow">Running the check</p>
              <h2>Reading the screenshot…</h2>
              <p>
                Keep this tab open. The image is checked in memory and the raw
                file is never published.
              </p>
              <ol className="processing-steps">
                {PROCESS_STEPS.map((step, index) => (
                  <li key={step} style={{ animationDelay: `${index * 180}ms` }}>
                    <span className="processing-dot" />
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          ) : (
            <form className="form-stack" onSubmit={handleSubmit} noValidate>
              <div className="card-heading">
                <div>
                  <h2>Payment screenshot</h2>
                  <p>The document the buyer sent you on WhatsApp.</p>
                </div>
                <span className="step-pill">01</span>
              </div>

              <UploadField
                file={file}
                onFile={setFile}
                error={uploadError}
                onError={setUploadError}
              />

              <div className="divider" />

              <div className="card-heading">
                <div>
                  <h2>What did you expect?</h2>
                  <p>Use the details from the order, not the screenshot.</p>
                </div>
                <span className="step-pill">02</span>
              </div>

              <div className="form-grid">
                <label className="field">
                  <span className="field-label">Expected amount</span>
                  <span className={`input-prefix${fieldErrors.amount ? " has-error" : ""}`}>
                    <span>R</span>
                    <input
                      className="input"
                      inputMode="decimal"
                      value={amount}
                      onChange={(event) => setAmount(event.target.value)}
                      placeholder="1 800.00"
                      aria-invalid={Boolean(fieldErrors.amount)}
                      required
                    />
                  </span>
                  {fieldErrors.amount && <span className="field-error">{fieldErrors.amount}</span>}
                </label>

                <label className="field">
                  <span className="field-label">Recipient name</span>
                  <input
                    className={`input${fieldErrors.recipient ? " has-error" : ""}`}
                    value={recipient}
                    onChange={(event) => setRecipient(event.target.value)}
                    placeholder="Thabo Sneakers"
                    aria-invalid={Boolean(fieldErrors.recipient)}
                    required
                  />
                  {fieldErrors.recipient && <span className="field-error">{fieldErrors.recipient}</span>}
                </label>
              </div>

              <label className="field">
                <span className="field-label">Payment reference</span>
                <input
                  className={`input mono${fieldErrors.reference ? " has-error" : ""}`}
                  value={reference}
                  onChange={(event) => setReference(event.target.value)}
                  placeholder="SNK1800"
                  aria-invalid={Boolean(fieldErrors.reference)}
                  spellCheck="false"
                  required
                />
                <span className="field-hint">
                  The reference on the order, e.g. the order number or buyer name.
                </span>
                {fieldErrors.reference && <span className="field-error">{fieldErrors.reference}</span>}
              </label>

              {API_MODE === "mock" && (
                <div className="demo-box">
                  <div className="demo-box-head">
                    <span>
                      <Icon name="spark" size={16} />
                      Demo scenarios
                    </span>
                    <button
                      type="button"
                      className="link-button"
                      onClick={loadSample}
                      disabled={sampleBusy}
                    >
                      {sampleBusy ? "Loading…" : "Load sample receipt"}
                    </button>
                  </div>
                  <div className="demo-actions">
                    {DEMOS.map((demo) => (
                      <button
                        type="button"
                        key={demo.key}
                        className={`demo-chip demo-${demo.key}`}
                        onClick={() => applyDemo(demo)}
                      >
                        <VerdictBadge verdict={demo.key.toUpperCase()} />
                      </button>
                    ))}
                  </div>
                  <p>
                    Load the sample receipt, then pick a scenario to see each
                    verdict. The sample values are safe demo data.
                  </p>
                </div>
              )}

              {submitError && (
                <div className="alert alert-error" role="alert">
                  <Icon name="alert" size={18} />
                  <span>
                    <strong>The check did not complete.</strong>
                    {submitError}
                  </span>
                  <button type="button" className="alert-action" onClick={handleSubmit}>
                    Retry
                  </button>
                </div>
              )}

              <button className="button button-primary button-block button-lg" type="submit">
                <Icon name="shieldCheck" size={18} />
                Run the check
              </button>
              <p className="form-footnote">
                <Icon name="bank" size={15} />
                Khusela never says PAID. Confirm the money in your banking app.
              </p>
            </form>
          )}
        </section>

        <aside className="check-aside">
          <section className="card">
            <div className="card-heading">
              <div>
                <h2>How the verdict is decided</h2>
                <p>Rules first. The AI only explains.</p>
              </div>
            </div>
            <ol className="mini-steps">
              <li>
                <span>1</span>
                <div>
                  <strong>Document check</strong>
                  <p>File type, size, image headers and editing traces.</p>
                </div>
              </li>
              <li>
                <span>2</span>
                <div>
                  <strong>Payment claim</strong>
                  <p>Amount, recipient and reference against your order.</p>
                </div>
              </li>
              <li>
                <span>3</span>
                <div>
                  <strong>Containment</strong>
                  <p>Reused screenshots from other sellers trigger a STOP.</p>
                </div>
              </li>
            </ol>
          </section>

          <section className="card verdict-key">
            <h2>What each verdict means</h2>
            <div className="verdict-row">
              <VerdictBadge verdict="MATCH" />
              <p>The details line up. Still confirm the money in your bank app.</p>
            </div>
            <div className="verdict-row">
              <VerdictBadge verdict="WAIT" />
              <p>Something needs a human check before you release anything.</p>
            </div>
            <div className="verdict-row">
              <VerdictBadge verdict="STOP" />
              <p>Do not release. This looks edited or reused.</p>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
