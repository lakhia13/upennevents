import { NavLink } from "react-router-dom";

function navClass({ isActive }: { isActive: boolean }): string {
  return isActive ? "nav-tab nav-tab-active" : "nav-tab";
}

export function Header() {
  return (
    <header className="header-row">
      <div className="wordmark">
        <span className="wm-penn">PENN</span>
        <span className="wm-events">EVENTS</span>
      </div>
      <nav className="mainnav" aria-label="Primary">
        <NavLink to="/calendar" className={navClass}>
          Calendar
        </NavLink>
        <NavLink to="/list" className={navClass}>
          List
        </NavLink>
      </nav>
    </header>
  );
}
