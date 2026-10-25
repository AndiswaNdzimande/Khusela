import Icon from "./Icon";
import { BANK_REMINDER } from "../api/client";

export default function BankReminder({ compact = false }) {
  return (
    <aside className={`bank-reminder${compact ? " bank-reminder-compact" : ""}`}>
      <span className="bank-reminder-icon">
        <Icon name="bank" size={compact ? 18 : 22} />
      </span>
      <span>
        <strong>{BANK_REMINDER}</strong>
        {!compact && (
          <span>
            Khusela checks the proof, not your bank balance. A MATCH is not a
            payment.
          </span>
        )}
      </span>
    </aside>
  );
}
