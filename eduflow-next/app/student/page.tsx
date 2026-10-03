"use client";

import { useEffect, useState } from "react";
import {
  BookOpen,
  UserCheck,
  CheckCircle,
  Circle,
  Calendar,
  Clock,
  ShieldCheck,
  GraduationCap,
  Sparkles,
  Search,
} from "lucide-react";
import { ClassOutline, PortalUser } from "@/lib/types";

export default function StudentPage() {
  const [user, setUser] = useState<PortalUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authForm, setAuthForm] = useState({ name: "", email: "", password: "" });
  const [enrollCode, setEnrollCode] = useState("");
  const [enrolling, setEnrolling] = useState(false);

  const [teachers, setTeachers] = useState<{ id: string; name: string }[]>([]);
  const [outlines, setOutlines] = useState<(ClassOutline & { teacher_name: string })[]>([]);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Track completed study tasks in localStorage
  const [completedTasks, setCompletedTasks] = useState<Record<string, boolean>>({});

  useEffect(() => {
    loadUser();
  }, []);

  async function loadUser() {
    setLoading(true);
    try {
      const res = await fetch("/api/classroom/me");
      if (res.ok) {
        const u = await res.json();
        if (u.role === "student") {
          setUser(u);
          const saved = localStorage.getItem(`eduflow_completed_tasks_${u.id}`);
          try {
            setCompletedTasks(saved ? JSON.parse(saved) : {});
          } catch {
            setCompletedTasks({});
          }
          loadStudentData();
        } else {
          setErrorMsg("You are signed in as a teacher. Sign out to access the student portal.");
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function loadStudentData() {
    try {
      const [teachersRes, outlinesRes] = await Promise.all([
        fetch("/api/classroom/student/teachers"),
        fetch("/api/classroom/student/outlines"),
      ]);
      if (teachersRes.ok) setTeachers(await teachersRes.json());
      if (outlinesRes.ok) setOutlines(await outlinesRes.json());
    } catch (err) {
      console.error(err);
    }
  }

  async function handleAuth(e: React.FormEvent) {
    e.preventDefault();
    setErrorMsg("");
    setSuccessMsg("");

    const endpoint = authMode === "login" ? "/api/classroom/login" : "/api/classroom/register";
    const body =
      authMode === "login"
        ? { email: authForm.email, password: authForm.password }
        : { name: authForm.name, email: authForm.email, password: authForm.password, role: "student" };

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.error || "Authentication failed");
        return;
      }

      setUser(data);
      loadStudentData();
    } catch (err: any) {
      setErrorMsg(err.message || "Network error");
    }
  }

  async function handleEnroll(e: React.FormEvent) {
    e.preventDefault();
    if (!enrollCode) return;

    setEnrolling(true);
    setErrorMsg("");
    setSuccessMsg("");

    try {
      const res = await fetch("/api/classroom/student/enroll", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: enrollCode.trim().toUpperCase() }),
      });

      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.error || "Enrollment failed");
        return;
      }

      setSuccessMsg(`Successfully joined ${data.name}'s class!`);
      setEnrollCode("");
      loadStudentData();
    } catch (err: any) {
      setErrorMsg(err.message || "Enrollment error");
    } finally {
      setEnrolling(false);
    }
  }

  const toggleTask = (taskId: string) => {
    if (!user) return;
    const next = { ...completedTasks, [taskId]: !completedTasks[taskId] };
    setCompletedTasks(next);
    localStorage.setItem(`eduflow_completed_tasks_${user.id}`, JSON.stringify(next));
  };

  if (loading) {
    return (
      <div className="page-container" style={{ textAlign: "center", padding: "100px 0" }}>
        <p className="badge info">Loading Student Portal...</p>
      </div>
    );
  }

  // Not signed in as student: Auth Screen
  if (!user) {
    return (
      <div className="page-container" style={{ maxWidth: "520px" }}>
        <div className="card" style={{ marginTop: "40px" }}>
          <div style={{ textAlign: "center", marginBottom: "24px" }}>
            <span className="badge info" style={{ marginBottom: "12px" }}>
              Student Portal
            </span>
            <h1 style={{ fontSize: "28px", fontWeight: "800", letterSpacing: "-0.03em" }}>
              {authMode === "login" ? "Welcome Back, Student" : "Create Student Account"}
            </h1>
            <p style={{ color: "var(--soft)", fontSize: "14px", marginTop: "6px" }}>
              Access teacher-curated notes, AI-reviewed revision guides, and structured 7-day study plans.
            </p>
          </div>

          {errorMsg && <div className="alert error">{errorMsg}</div>}
          {successMsg && <div className="alert success">{successMsg}</div>}

          <form onSubmit={handleAuth}>
            {authMode === "register" && (
              <div className="form-group">
                <label className="form-label">Full Name</label>
                <input
                  type="text"
                  placeholder="e.g. Alex Johnson"
                  value={authForm.name}
                  onChange={(e) => setAuthForm({ ...authForm, name: e.target.value })}
                  required
                />
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Student Email</label>
              <input
                type="email"
                placeholder="student@school.edu"
                value={authForm.email}
                onChange={(e) => setAuthForm({ ...authForm, email: e.target.value })}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Password (min 8 chars)</label>
              <input
                type="password"
                placeholder="••••••••"
                value={authForm.password}
                onChange={(e) => setAuthForm({ ...authForm, password: e.target.value })}
                required
              />
            </div>

            <button type="submit" className="primary" style={{ width: "100%", marginTop: "10px" }}>
              {authMode === "login" ? "Sign In to Student Portal" : "Register as Student"}
            </button>
          </form>

          <div style={{ textAlign: "center", marginTop: "20px", fontSize: "13px", color: "var(--soft)" }}>
            {authMode === "login" ? "Need a student account?" : "Already have an account?"}{" "}
            <button
              type="button"
              className="text-btn"
              style={{
                background: "none",
                border: "none",
                color: "var(--accent)",
                cursor: "pointer",
                fontWeight: "700",
                padding: "0",
              }}
              onClick={() => {
                setErrorMsg("");
                setAuthMode(authMode === "login" ? "register" : "login");
              }}
            >
              {authMode === "login" ? "Create one now" : "Sign in here"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Signed in Student Dashboard
  return (
    <div className="page-container">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "20px",
          marginBottom: "30px",
        }}
      >
        <div>
          <span className="badge info" style={{ marginBottom: "8px" }}>
            Student Workspace
          </span>
          <h1 style={{ fontSize: "32px", fontWeight: "800", letterSpacing: "-0.03em" }}>
            Hello, {user.name}
          </h1>
          <p style={{ color: "var(--soft)", fontSize: "14px" }}>
            Your personalized study hub with teacher-published revision notes and daily goals.
          </p>
        </div>

        {/* Enroll in Class Card */}
        <div className="card" style={{ padding: "16px 20px" }}>
          <form
            onSubmit={handleEnroll}
            style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}
          >
            <div>
              <span style={{ fontSize: "11px", fontWeight: "700", color: "var(--soft)", textTransform: "uppercase", display: "block" }}>
                Join Teacher&apos;s Class
              </span>
              <input
                type="text"
                placeholder="6-DIGIT CODE"
                value={enrollCode}
                onChange={(e) => setEnrollCode(e.target.value)}
                style={{
                  minHeight: "38px",
                  padding: "6px 12px",
                  fontFamily: "var(--mono)",
                  textTransform: "uppercase",
                  fontWeight: "700",
                  letterSpacing: "0.1em",
                  width: "140px",
                }}
                required
              />
            </div>
            <button
              type="submit"
              className="primary"
              disabled={enrolling || !enrollCode}
              style={{ marginTop: "18px", padding: "8px 16px", minHeight: "38px" }}
            >
              <span>{enrolling ? "Joining..." : "Join Class"}</span>
            </button>
          </form>
        </div>
      </div>

      {errorMsg && <div className="alert error">{errorMsg}</div>}
      {successMsg && <div className="alert success">{successMsg}</div>}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.4fr) minmax(280px, 0.6fr)",
          gap: "28px",
          alignItems: "start",
        }}
      >
        {/* Left Column: Published Study Outlines */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <h2 style={{ fontSize: "20px", fontWeight: "700" }}>
              Assigned Materials ({outlines.length})
            </h2>
          </div>

          {outlines.length === 0 ? (
            <div className="card" style={{ textAlign: "center", padding: "40px 20px" }}>
              <GraduationCap size={40} color="var(--soft)" style={{ margin: "0 auto 12px" }} />
              <h3 style={{ fontSize: "17px", fontWeight: "700" }}>No Materials Yet</h3>
              <p style={{ color: "var(--soft)", fontSize: "13px", maxWidth: "400px", margin: "6px auto 0" }}>
                Ask your teacher for their enrollment code to join their classroom and receive notes and 7-day study plans.
              </p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
              {outlines.map((outline) => (
                <div key={outline.id} className="card" style={{ padding: "24px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "10px", marginBottom: "12px" }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                        <span className="badge info">{outline.subject}</span>
                        <span className="badge ok">
                          <UserCheck size={12} />
                          Teacher: {outline.teacher_name}
                        </span>
                        {outline.notes && (
                          <span className="badge ok">
                            <ShieldCheck size={12} />
                            Factual Verification Passed
                          </span>
                        )}
                      </div>
                      <h3 style={{ fontSize: "22px", fontWeight: "800", letterSpacing: "-0.02em" }}>
                        {outline.title}
                      </h3>
                    </div>
                  </div>

                  {/* Outline summary */}
                  <div
                    style={{
                      background: "var(--sunken)",
                      padding: "14px 18px",
                      borderRadius: "var(--radius)",
                      fontSize: "13px",
                      whiteSpace: "pre-wrap",
                      marginBottom: "20px",
                    }}
                  >
                    {outline.content}
                  </div>

                  {/* Verified Revision Notes */}
                  {outline.notes && (
                    <div style={{ marginBottom: "24px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                        <h4
                          style={{
                            fontSize: "16px",
                            fontWeight: "700",
                            color: "var(--ok)",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <ShieldCheck size={18} />
                          Verified Study Notes
                        </h4>
                        {outline.generated_by && (
                          <span style={{ fontSize: "11px", color: "var(--soft)", fontFamily: "var(--mono)" }}>
                            Audited by {outline.generated_by}
                          </span>
                        )}
                      </div>
                      <div
                        className="markdown-body"
                        style={{
                          background: "var(--surface)",
                          border: "1px solid var(--line)",
                          borderRadius: "var(--radius)",
                          padding: "20px 24px",
                          fontSize: "14px",
                          lineHeight: "1.75",
                          whiteSpace: "pre-wrap",
                        }}
                      >
                        {outline.notes}
                      </div>
                    </div>
                  )}

                  {/* 7-Day Interactive Revision Roadmap */}
                  {outline.study_plan?.days && (
                    <div>
                      <h4
                        style={{
                          fontSize: "16px",
                          fontWeight: "700",
                          marginBottom: "14px",
                          display: "flex",
                          alignItems: "center",
                          gap: "6px",
                        }}
                      >
                        <Calendar size={18} color="var(--accent)" />
                        7-Day Revision Roadmap & Task Checklist
                      </h4>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "14px" }}>
                        {outline.study_plan.days.map((d: any) => {
                          const dayKey = `${outline.id}-day-${d.day}`;
                          return (
                            <div
                              key={d.day}
                              style={{
                                background: "var(--surface)",
                                border: "1px solid var(--line)",
                                borderRadius: "var(--radius)",
                                padding: "16px",
                                display: "flex",
                                flexDirection: "column",
                                justifyContent: "space-between",
                              }}
                            >
                              <div>
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                                  <span style={{ fontWeight: "800", color: "var(--accent)", fontSize: "14px" }}>
                                    Day {d.day}
                                  </span>
                                  <span style={{ fontSize: "11px", color: "var(--soft)", display: "flex", alignItems: "center", gap: "4px" }}>
                                    <Clock size={12} />
                                    {d.minutes} mins
                                  </span>
                                </div>
                                <strong style={{ display: "block", fontSize: "14px", marginBottom: "12px" }}>
                                  {d.focus}
                                </strong>

                                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                                  {d.tasks?.map((task: string, taskIdx: number) => {
                                    const taskId = `${dayKey}-task-${taskIdx}`;
                                    const isDone = Boolean(completedTasks[taskId]);
                                    return (
                                      <div
                                        key={taskIdx}
                                        onClick={() => toggleTask(taskId)}
                                        style={{
                                          display: "flex",
                                          alignItems: "flex-start",
                                          gap: "8px",
                                          cursor: "pointer",
                                          padding: "4px 0",
                                          userSelect: "none",
                                        }}
                                      >
                                        <span style={{ marginTop: "2px", color: isDone ? "var(--ok)" : "var(--soft)" }}>
                                          {isDone ? <CheckCircle size={15} /> : <Circle size={15} />}
                                        </span>
                                        <span
                                          style={{
                                            fontSize: "12px",
                                            lineHeight: "1.4",
                                            textDecoration: isDone ? "line-through" : "none",
                                            color: isDone ? "var(--soft)" : "var(--ink)",
                                          }}
                                        >
                                          {task}
                                        </span>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Column: Enrolled Teachers list */}
        <div>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title" style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "18px" }}>
                <UserCheck size={18} color="var(--accent)" />
                Your Teachers ({teachers.length})
              </h3>
            </div>

            {teachers.length === 0 ? (
              <div
                style={{
                  background: "var(--sunken)",
                  padding: "18px",
                  borderRadius: "var(--radius)",
                  textAlign: "center",
                  fontSize: "13px",
                  color: "var(--soft)",
                }}
              >
                You haven&apos;t joined any classes yet. Enter a teacher code above to join!
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {teachers.map((teacher) => (
                  <div
                    key={teacher.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                      padding: "12px 14px",
                      borderRadius: "var(--radius)",
                      background: "var(--sunken)",
                    }}
                  >
                    <div
                      style={{
                        width: "36px",
                        height: "36px",
                        borderRadius: "50%",
                        background: "var(--accent)",
                        color: "white",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontWeight: "800",
                        fontSize: "14px",
                      }}
                    >
                      {teacher.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div style={{ fontWeight: "700", fontSize: "14px" }}>{teacher.name}</div>
                      <div style={{ fontSize: "11px", color: "var(--soft)" }}>Teacher</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
