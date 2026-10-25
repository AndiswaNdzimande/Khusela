import Icon from "./Icon";

const ICONS = {
  MATCH: "check",
  WAIT: "clock",
  STOP: "x",
};

export default function VerdictBadge({ verdict, large = false }) {
  const value = String(verdict || "WAIT").toUpperCase();
  return (
    <span className={`verdict verdict-${value.toLowerCase()}${large ? " verdict-large" : ""}`}>
      <Icon name={ICONS[value] || "shield"} size={large ? 22 : 14} strokeWidth={2.2} />
      {value}
    </span>
  );
}
