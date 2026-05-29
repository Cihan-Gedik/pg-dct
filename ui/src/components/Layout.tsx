import { NavLink, Outlet } from "react-router-dom";

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/live", label: "Cluster Health" },
  { to: "/backup", label: "Backup" },
  { to: "/live-logs", label: "Realtime Logs" },
  { to: "/bundles", label: "Bundle Import" },
  { to: "/bundle-logs", label: "Troubleshoot" },
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
