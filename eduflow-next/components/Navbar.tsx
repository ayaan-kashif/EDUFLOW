"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Compass,
  GraduationCap,
  BookOpen,
  GitBranch,
  Sun,
  Moon,
  LogOut,
  UserCheck,
  Activity,
  Zap,
} from "lucide-react";

export function Navbar() {
  const pathname = usePathname();
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [user, setUser] = useState<{ name: string; role: string } | null>(null);
  const [healthStatus, setHealthStatus] = useState<string>("checking");
  const [supabaseStatus, setSupabaseStatus] = useState<boolean>(false);

  useEffect(() => {
    // Initial theme
    const saved = localStorage.getItem("eduflow_theme") as "light" | "dark" | null;
    const initial = saved || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    queueMicrotask(() => setTheme(initial));
    document.documentElement.setAttribute("data-theme", initial);

    // Check health
    fetch("/api/health")
      .then((r) => r.json())
      .then((d) => {
        setHealthStatus(d.status === "healthy" ? "healthy" : "error");
        setSupabaseStatus(d.database === "connected");
      })
      .catch(() => {
        setHealthStatus("error");
        setSupabaseStatus(false);
      });

    // Check current user
    fetch("/api/classroom/me")
      .then((r) => (r.ok ? r.json() : null))
      .then((u) => setUser(u))
      .catch(() => setUser(null));
  }, [pathname]);

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    localStorage.setItem("eduflow_theme", next);
    document.documentElement.setAttribute("data-theme", next);
  };

  const handleLogout = async () => {
    await fetch("/api/classroom/logout", { method: "POST" });
    setUser(null);
    window.location.reload();
  };

  return (
    <header className="masthead">
      <Link href="/" className="brand">
        <div className="brand-icon">E</div>
        <span>EduFlow</span>
        <span className="brand-tag">Atelier OS</span>
      </Link>

      <nav className="nav-links">
        <Link
          href="/"
          className={`nav-link ${pathname === "/" ? "active" : ""}`}
        >
          <Compass size={16} />
          <span>Workspace</span>
        </Link>
        <Link
          href="/teacher"
          className={`nav-link ${pathname === "/teacher" ? "active" : ""}`}
        >
          <GraduationCap size={16} />
          <span>Teacher Portal</span>
        </Link>
        <Link
          href="/student"
          className={`nav-link ${pathname === "/student" ? "active" : ""}`}
        >
          <BookOpen size={16} />
          <span>Student Portal</span>
        </Link>
        <Link
          href="/pipeline"
          className={`nav-link ${pathname === "/pipeline" ? "active" : ""}`}
        >
          <GitBranch size={16} />
          <span>Pipeline & Audit</span>
        </Link>
      </nav>

      <div className="header-actions">
        {/* Health status badge */}
        <span
          className={`badge ${healthStatus === "healthy" ? "ok" : "warn"}`}
          title="System & Database Health"
        >
          <Activity size={12} />
          <span>{healthStatus === "healthy" ? "Live" : "Degraded"}</span>
        </span>

        {/* Supabase status badge */}
        {supabaseStatus && (
          <span
            className="badge ok"
            title="Connected to Supabase Cloud Database"
          >
            <Zap size={12} />
            <span>Supabase</span>
          </span>
        )}

        {/* Current user & logout */}
        {user ? (
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span className="badge info">
              <UserCheck size={12} />
              <span>{user.name} ({user.role})</span>
            </span>
            <button
              onClick={handleLogout}
              className="outline-btn"
              title="Sign Out"
              style={{ padding: "6px 10px", minHeight: "34px" }}
            >
              <LogOut size={14} />
            </button>
          </div>
        ) : null}

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="theme-btn outline-btn"
          aria-label="Toggle light and dark mode"
        >
          {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
        </button>
      </div>
    </header>
  );
}
