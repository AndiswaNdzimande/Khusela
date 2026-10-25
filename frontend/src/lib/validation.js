export const MAX_RECEIPT_BYTES = 5 * 1024 * 1024;

export const RECEIPT_TYPES = ["image/png", "image/jpeg"];

const RECEIPT_EXTENSIONS = /\.(png|jpe?g)$/i;

export function formatBytes(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function validateReceipt(file) {
  if (!file) {
    return "Choose a payment screenshot before running the check.";
  }

  const type = String(file.type || "").toLowerCase();
  const hasAllowedType = RECEIPT_TYPES.includes(type);
  const hasAllowedExtension = RECEIPT_EXTENSIONS.test(file.name || "");

  if ((type && !hasAllowedType) || (!type && !hasAllowedExtension)) {
    return "That file type is not supported. Upload a JPG or PNG screenshot.";
  }

  if (file.size === 0) {
    return "That file is empty. Choose the original screenshot instead.";
  }

  if (file.size > MAX_RECEIPT_BYTES) {
    return `That image is ${formatBytes(file.size)}. The limit is 5 MB — compress it or take a new screenshot.`;
  }

  return "";
}

export function validateSale({ amount, recipient, reference }) {
  const errors = {};
  const numericAmount = Number(String(amount).replace(/[^\d.]/g, ""));

  if (!String(amount).trim()) {
    errors.amount = "Enter the amount you expect to receive.";
  } else if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
    errors.amount = "Enter a valid amount greater than R0.";
  }

  if (!recipient.trim()) {
    errors.recipient = "Enter the name on the payment.";
  }

  if (!reference.trim()) {
    errors.reference = "Add the payment reference for this sale.";
  }

  return errors;
}
