import { Link } from "react-router-dom";

export default function Logo({ to = "/check" }) {
  return (
    <Link className="brand" to={to} aria-label="Khusela home">
      <span className="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 32 32" width="32" height="32">
          <rect width="32" height="32" rx="8" fill="#03080a" />
          <path
            d="M10 7c4.2 0 6.2 2.6 6.2 5.6 0 2.8-2.2 4.4-4.4 4.7 3.4.3 5.6 2.6 5.6 5.3 0 3.2-2.5 5.4-7.4 5.4V7Z"
            fill="#c8ff00"
          />
          <path
            d="M18 7h4.2v7.4L28 7h4.3l-6.5 8.7L32.2 28h-4.5l-5.5-8.2-2 2.7V28H18V7Z"
            fill="#fff"
            transform="translate(-3 0)"
          />
        </svg>
      </span>
      <span className="brand-name">
        khusela<span>.</span>
      </span>
    </Link>
  );
}
