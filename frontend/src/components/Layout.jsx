import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "./ui";

const links = [
  ["/", "Dashboard"],
  ["/analyze", "Analyse deployment"],
  ["/incidents", "Incident history"],
  ["/memory", "Memory explorer"],
  ["/risk", "Risk prediction"],
  ["/assistant", "AI assistant"],
  ["/settings", "Settings"],
];

export default function Layout() {
  const { user, projects, projectId, selectProject, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="shell">
      <aside className="side">
        <Logo />
        {projects.length > 0 && (
          <select value={projectId || ""} onChange={(e) => selectProject(Number(e.target.value))} aria-label="Project">
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        )}
        {links.map(([to, label]) => (
          <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "active" : "")}>
            {label}
          </NavLink>
        ))}
        <div className="spacer" />
        <div className="who">{user?.full_name}<br />{user?.organization_name}</div>
        <a href="#logout" onClick={(e) => { e.preventDefault(); logout(); navigate("/login"); }}>Log out</a>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
