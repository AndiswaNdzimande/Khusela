import { Link } from "react-router-dom";
import Icon from "../components/Icon";
import Logo from "../components/Logo";

export default function NotFoundPage() {
  return (
    <div className="not-found">
      <Logo to="/check" />
      <span className="state-icon"><Icon name="search" size={26} /></span>
      <p className="eyebrow">404</p>
      <h1>That page is not part of the console.</h1>
      <p>The link may be old. Head back to a new payment check.</p>
      <Link className="button button-primary" to="/check">
        <Icon name="arrowRight" size={16} />
        Go to a new check
      </Link>
    </div>
  );
}
