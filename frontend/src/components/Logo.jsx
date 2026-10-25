import { Link } from "react-router-dom";

export default function Logo({ to = "/check", variant = "compact", className = "" }) {
  const src =
    variant === "full"
      ? "/brand/khusela-logo.png"
      : "/brand/khusela-logo-compact.png";

  return (
    <Link
      className={["brand", className].filter(Boolean).join(" ")}
      to={to}
      aria-label="Khusela home"
    >
      <img
        className={`brand-logo brand-logo-${variant}`}
        src={src}
        alt="Khusela"
      />
    </Link>
  );
}
