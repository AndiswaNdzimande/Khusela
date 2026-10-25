const path = require("path");
const jsonServer = require("json-server");
const multer = require("multer");

const server = jsonServer.create();
const router = jsonServer.router(path.join(__dirname, "db.json"));
const middlewares = jsonServer.defaults();

const MAX_BYTES = 5 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/png", "image/jpeg"]);
const DELAY_MS = 700;

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: MAX_BYTES, files: 1 },
}).single("image");

server.use(middlewares);
server.use(jsonServer.bodyParser);

function sellerFor(req) {
  const header = req.headers.authorization || "";
  const token = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  if (!token) return null;
  return router.db.get("sellers").find({ auth_token: token }).value() || null;
}

function normaliseName(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

function expectedFrom(body) {
  return {
    amount: Number(String(body.expected_amount || "").replace(/[^\d.-]/g, "")),
    recipient: String(body.expected_recipient || "").trim(),
    reference: String(body.expected_reference || "").trim(),
  };
}

function makeExplanation(verdict, reasons) {
  if (verdict === "MATCH") {
    return "The amount, recipient name and reference match your sale. Check your banking app to confirm the money has arrived before you release the goods.";
  }
  if (verdict === "STOP") {
    return "This screenshot has already been submitted by another seller, so it may be a reused fake. Do not release the goods; check your banking app.";
  }
  if (reasons.includes("low_ocr_confidence")) {
    return "The screenshot is too blurry to read reliably. Ask the buyer for a clear, original screenshot and verify the money in your banking app.";
  }
  if (reasons.includes("amount_mismatch")) {
    return "The amount on the screenshot does not match the sale you entered. Do not release the goods; check your banking app first.";
  }
  if (reasons.includes("recipient_mismatch")) {
    return "The recipient name on the screenshot does not match your sale. Do not release the goods; check your banking app first.";
  }
  return "The reference on the screenshot does not match the sale you entered. Do not release the goods; check your banking app first.";
}

function buildVerdict(req) {
  const expected = expectedFrom(req.body);
  const extracted = {
    amount: 1800,
    recipient: "Thabo Sneakers",
    reference: "SNK1800",
  };

  const isDuplicate =
    /dup/i.test(expected.reference) || /dup/i.test(req.file.originalname);
  const isBlurry = /blur/i.test(req.file.originalname);

  if (isDuplicate) {
    return {
      verdict: "STOP",
      reasons: ["duplicate_image"],
      duplicate: { found: true, same_seller: false },
      ocr_confidence: 0.93,
    };
  }

  if (isBlurry) {
    return {
      verdict: "WAIT",
      reasons: ["low_ocr_confidence"],
      duplicate: { found: false, same_seller: false },
      ocr_confidence: 0.42,
    };
  }

  const reasons = [];
  if (Math.abs(expected.amount - extracted.amount) > 0.009) {
    reasons.push("amount_mismatch");
  }
  if (
    expected.recipient &&
    normaliseName(expected.recipient) !== normaliseName(extracted.recipient)
  ) {
    reasons.push("recipient_mismatch");
  }
  if (
    expected.reference &&
    normaliseName(expected.reference) !== normaliseName(extracted.reference)
  ) {
    reasons.push("reference_mismatch");
  }

  return {
    verdict: reasons.length ? "WAIT" : "MATCH",
    reasons,
    duplicate: { found: false, same_seller: false },
    ocr_confidence: reasons.length ? 0.71 : 0.94,
  };
}

server.post("/api/auth/login", (req, res) => {
  const businessName = String(req.body.business_name || "").trim();
  const password = String(req.body.password || "");
  const seller = router.db
    .get("sellers")
    .find(
      (item) =>
        item.business_name.toLowerCase() === businessName.toLowerCase() &&
        item.password === password,
    )
    .value();

  if (!seller) {
    return res.status(401).json({
      error: "invalid_credentials",
      message: "That business name or password is not correct.",
    });
  }
  return res.json({
    token: seller.auth_token,
    seller_id: seller.id,
    business_name: seller.business_name,
  });
});

server.post("/api/auth/register", (req, res) => {
  const businessName = String(req.body.business_name || "").trim();
  const password = String(req.body.password || "");

  if (!businessName) {
    return res.status(400).json({
      error: "missing_business_name",
      message: "Enter your business name.",
    });
  }
  if (password.length < 8) {
    return res.status(400).json({
      error: "weak_password",
      message: "Use at least 8 characters for your password.",
    });
  }

  const existing = router.db
    .get("sellers")
    .find((seller) => seller.business_name.toLowerCase() === businessName.toLowerCase())
    .value();

  if (existing) {
    return res.status(409).json({
      error: "business_exists",
      message: "That business already has a workspace. Sign in with its password instead.",
    });
  }

  const seller = {
    id: `sel_${Date.now().toString(36)}`,
    business_name: businessName,
    auth_token: `khs_live_${Math.random().toString(36).slice(2, 10)}`,
    password,
    created_at: new Date().toISOString(),
  };
  router.db.get("sellers").push(seller).write();

  return res.status(201).json({
    token: seller.auth_token,
    seller_id: seller.id,
    business_name: seller.business_name,
  });
});

server.get("/api/health", (_req, res) => {
  res.json({ status: "ok", mode: "mock", time: new Date().toISOString() });
});

server.post("/api/check", (req, res) => {
  upload(req, res, (uploadError) => {
    if (uploadError) {
      const tooLarge = uploadError.code === "LIMIT_FILE_SIZE";
      return res.status(400).json({
        error: tooLarge ? "file_too_large" : "unsupported_type",
        message: tooLarge
          ? "Images must be 5 MB or smaller."
          : "Upload a JPG or PNG screenshot.",
      });
    }

    const seller = sellerFor(req);
    if (!seller) {
      return res.status(401).json({
        error: "unauthorized",
        message: "Sign in again before running a check.",
      });
    }

    if (!req.file) {
      return res.status(400).json({
        error: "missing_file",
        message: "Choose a payment screenshot to upload.",
      });
    }

    if (!ALLOWED_TYPES.has(req.file.mimetype)) {
      return res.status(400).json({
        error: "unsupported_type",
        message: "Upload a JPG or PNG screenshot.",
      });
    }

    const expected = expectedFrom(req.body);
    if (!Number.isFinite(expected.amount) || !expected.recipient) {
      return res.status(400).json({
        error: "missing_fields",
        message: "Add the expected amount and recipient before running a check.",
      });
    }

    const result = buildVerdict(req);
    const check = {
      check_id: `chk_${Date.now().toString(36)}`,
      seller_id: seller.id,
      verdict: result.verdict,
      reasons: result.reasons,
      explanation: makeExplanation(result.verdict, result.reasons),
      explanation_source: "template",
      extracted: {
        amount: 1800,
        recipient: "Thabo Sneakers",
        reference: "SNK1800",
      },
      expected,
      ocr_confidence: result.ocr_confidence,
      duplicate: result.duplicate,
      raw_ocr_text: [
        "DEMO BANK",
        "Payment successful",
        "R1,800.00",
        "Recipient",
        "Thabo Sneakers",
        "Reference",
        "SNK1800",
      ].join("\n"),
      bank_reminder:
        "Confirm the money in your banking app before you release goods.",
      created_at: new Date().toISOString(),
    };

    router.db.get("checks").unshift(check).write();

    setTimeout(() => res.status(200).json(check), DELAY_MS);
  });
});

server.use(router);

const port = Number(process.env.MOCK_PORT || 3001);
server.listen(port, () => {
  console.log(`Khusela mock API listening on http://localhost:${port}`);
});
