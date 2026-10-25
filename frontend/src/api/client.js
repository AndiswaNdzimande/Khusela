export const API_MODE =
  import.meta.env.VITE_API_MODE === "live" ? "live" : "mock";

const MOCK_URL = (
  import.meta.env.VITE_MOCK_API_URL || "http://localhost:3001"
).replace(/\/$/, "");

const LIVE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/$/, "");

const API_URL = API_MODE === "live" ? LIVE_URL : MOCK_URL;
const HISTORY_KEY = "khusela.checks.v1";
const MAX_HISTORY = 60;

export const BANK_REMINDER =
  "Confirm the money in your banking app before you release goods.";

export const MODE_LABEL =
  API_MODE === "live" ? "Live API" : "Offline mock";

export class ApiError extends Error {
  constructor(code, message, status = 0) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

function readHistory() {
  try {
    const raw = window.localStorage.getItem(HISTORY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeHistory(checks) {
  try {
    window.localStorage.setItem(
      HISTORY_KEY,
      JSON.stringify(checks.slice(0, MAX_HISTORY)),
    );
  } catch {
    // Storage can be unavailable in private mode. The current session still works.
  }
}

export function saveCheck(check) {
  const existing = readHistory().filter((item) => item.check_id !== check.check_id);
  writeHistory([check, ...existing]);
}

function normaliseAmount(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(String(value).replace(/[^\d.-]/g, ""));
  return Number.isFinite(number) ? number : null;
}

function normaliseCheck(raw, fallback = {}) {
  const extracted = raw.extracted ||
    raw.extracted_text || {
      amount: fallback.extractedAmount ?? null,
      recipient: fallback.extractedRecipient ?? null,
      reference: fallback.extractedReference ?? null,
    };

  const expected = raw.expected || {
    amount: fallback.amount ?? null,
    recipient: fallback.recipient ?? "",
    reference: fallback.reference ?? "",
  };

  const duplicate = raw.duplicate || {
    found: Boolean(raw.is_duplicate),
    same_seller: false,
  };

  const ocrConfidence =
    typeof raw.ocr_confidence === "number"
      ? raw.ocr_confidence
      : typeof raw.confidence === "number"
        ? raw.confidence
        : 0;

  const extractedAmount = normaliseAmount(extracted.amount);
  const extractedRecipient = extracted.recipient ?? null;
  const extractedReference = extracted.reference ?? null;

  return {
    check_id: raw.check_id || raw.id || `chk_${Date.now()}`,
    verdict: String(raw.verdict || "WAIT").toUpperCase(),
    reasons: Array.isArray(raw.reasons) ? raw.reasons : [],
    explanation:
      raw.explanation ||
      "Khusela could not produce an explanation. Confirm the money in your banking app before releasing goods.",
    explanation_source: raw.explanation_source || "template",
    extracted: {
      amount: extractedAmount,
      recipient: extractedRecipient,
      reference: extractedReference,
    },
    expected: {
      amount: normaliseAmount(expected.amount),
      recipient: expected.recipient ?? "",
      reference: expected.reference ?? "",
    },
    ocr_confidence: Math.max(0, Math.min(1, ocrConfidence)),
    duplicate: {
      found: Boolean(duplicate.found),
      same_seller: Boolean(duplicate.same_seller),
    },
    raw_ocr_text:
      raw.raw_ocr_text ||
      [
        "DEMO BANK",
        "Payment successful",
        extractedAmount !== null ? `R${extractedAmount.toFixed(2)}` : "Amount unreadable",
        "Recipient",
        extractedRecipient || "Recipient unreadable",
        "Reference",
        extractedReference || "Reference unreadable",
      ].join("\n"),
    bank_reminder: raw.bank_reminder || BANK_REMINDER,
    seller_id: raw.seller_id || fallback.sellerId || null,
    created_at: raw.created_at || new Date().toISOString(),
  };
}

async function readFailure(response) {
  let body = {};
  try {
    body = await response.json();
  } catch {
    // Some failures have no JSON body.
  }
  return new ApiError(
    body.error || `http_${response.status}`,
    body.message || "Khusela could not complete that request. Please try again.",
    response.status,
  );
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, options);
  } catch {
    throw new ApiError(
      "network_error",
      API_MODE === "live"
        ? "The Khusela API is not reachable. Start the FastAPI backend on localhost:8000 and try again."
        : "The local mock API is not reachable. Run the app with “npm run dev” so json-server starts on port 3001.",
    );
  }
  if (!response.ok) throw await readFailure(response);
  if (response.status === 204) return null;
  return response.json();
}

export async function login(token) {
  const cleaned = token.trim();
  if (!cleaned) {
    throw new ApiError("missing_token", "Enter your seller API token.");
  }

  if (API_MODE === "mock") {
    return request("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: cleaned }),
    });
  }

  return {
    token: cleaned,
    seller_id: "live_seller",
    business_name: "Khusela seller",
  };
}

export async function register({ businessName, password }) {
  if (!businessName.trim()) {
    throw new ApiError("missing_business_name", "Enter your business name.");
  }
  if (password.length < 6) {
    throw new ApiError(
      "weak_password",
      "Use at least 6 characters for your password.",
    );
  }

  if (API_MODE === "mock") {
    return request("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ business_name: businessName.trim(), password }),
    });
  }

  return {
    token: `khs_local_${Date.now().toString(36)}`,
    seller_id: `local_${Date.now().toString(36)}`,
    business_name: businessName.trim(),
  };
}

export async function runCheck({
  file,
  amount,
  recipient,
  reference,
  token,
  sellerId,
}) {
  const form = new FormData();
  form.append("image", file, file.name);
  form.append("expected_amount", String(amount));
  form.append("expected_recipient", recipient);
  form.append("expected_reference", reference);

  const payload = await request("/api/check", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });

  const check = normaliseCheck(payload, {
    amount,
    recipient,
    reference,
    sellerId,
  });
  saveCheck(check);
  return check;
}

export async function getHistory({ token } = {}) {
  const local = readHistory();

  if (API_MODE === "live") {
    return local;
  }

  try {
    const response = await fetch(`${API_URL}/checks`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) return local;
    const remote = await response.json();
    const merged = new Map();
    remote.forEach((item) => {
      const check = normaliseCheck(item);
      merged.set(check.check_id, check);
    });
    local.forEach((item) => merged.set(item.check_id, item));
    return [...merged.values()].sort(
      (a, b) => new Date(b.created_at) - new Date(a.created_at),
    );
  } catch {
    return local;
  }
}

export async function getCheck(checkId, { token } = {}) {
  const local = readHistory().find((item) => item.check_id === checkId);
  if (local) return local;

  if (API_MODE === "live") return null;

  try {
    const response = await fetch(
      `${API_URL}/checks?check_id=${encodeURIComponent(checkId)}`,
      { headers: token ? { Authorization: `Bearer ${token}` } : {} },
    );
    if (!response.ok) return null;
    const matches = await response.json();
    return Array.isArray(matches) && matches[0] ? normaliseCheck(matches[0]) : null;
  } catch {
    return null;
  }
}

export function clearLocalHistory() {
  writeHistory([]);
}
