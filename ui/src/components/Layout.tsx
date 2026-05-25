import { NavLink, Outlet } from "react-router-dom";

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/live", label: "Live Monitor" },
  { to: "/backup", label: "Backup" },
  { to: "/logs", label: "Lets Check Logs" },
  { to: "/bundles", label: "Bundles" },
  { to: "/settings", label: "Settings" },
];

export default function Layout() {
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">PG-DCT</div>
        <nav className="nav">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.to === "/"}>
              {l.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
