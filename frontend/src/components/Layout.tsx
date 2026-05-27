import { Outlet, useNavigate, useLocation } from "react-router-dom";

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="app-layout">
      <header className="app-header">
        <div className="header-left" onClick={() => navigate("/")}>
          <span className="logo-icon">&#x1F9E0;</span>
          <h1>AI Memory Hub</h1>
        </div>
        <nav className="header-nav">
          <button
            className={`nav-tab ${isActive("/") ? "active" : ""}`}
            onClick={() => navigate("/")}
          >
            时间线
          </button>
          <button
            className={`nav-tab ${isActive("/projects") ? "active" : ""}`}
            onClick={() => navigate("/projects")}
          >
            项目
          </button>
        </nav>
        <div className="header-right">
          <span className="subtitle">智能记忆，随时回溯</span>
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
