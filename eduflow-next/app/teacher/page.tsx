"use client";

import { useEffect, useState } from "react";
import {
  Sparkles,
  Send,
  Copy,
  Check,
  Plus,
  Users,
  BookOpen,
  Calendar,
  Clock,
  ShieldCheck,
  AlertCircle,
  FileText,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { ClassOutline, PortalUser } from "@/lib/types";

export default function TeacherPage() {
  const [user, setUser] = useState<PortalUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authForm, setAuthForm] = useState({ name: "", email: "", password: "" });
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  const [outlines, setOutlines] = useState<ClassOutline[]>([]);
  const [students, setStudents] = useState<{ id: string; name: string }[]>([]);
  const [copiedCode, setCopiedCode] = useState(false);

  // New outline form
  const [newTitle, setNewTitle] = useState("");
  const [newSubject, setNewSubject] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newSource, setNewSource] = useState("");
  const [submittingOutline, setSubmittingOutline] = useState(false);
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [expandedOutlineId, setExpandedOutlineId] = useState<string | null>(null);

  useEffect(() => {
    loadUser();
  }, []);

  async function loadUser() {
    setLoading(true);
    try {
      const res = await fetch("/api/classroom/me");
      if (res.ok) {
        const u = await res.json();
        if (u.role === "teacher") {
          setUser(u);
          loadTeacherData();
        } else {
          setErrorMsg("You are signed in as a student. Sign out to access the teacher portal.");
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function loadTeacherData() {
    try {
      const [outlinesRes, studentsRes] = await Promise.all([
        fetch("/api/classroom/teacher/outlines"),
        fetch("/api/classroom/teacher/students"),
      ]);
      if (outlinesRes.ok) setOutlines(await outlinesRes.json());
      if (studentsRes.ok) setStudents(await studentsRes.json());
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
        : { name: authForm.name, email: authForm.email, password: authForm.password, role: "teacher" };

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
      loadTeacherData();
    } catch (err: any) {
      setErrorMsg(err.message || "Network error");
    }
  }

  async function handleCreateOutline(e: React.FormEvent) {
    e.preventDefault();
    if (!newTitle || !newSubject || !newContent) return;

    setSubmittingOutline(true);
    setErrorMsg("");
    try {
      const res = await fetch("/api/classroom/teacher/outlines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: newTitle,
          subject: newSubject,
          content: newContent,
          source_text: newSource,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.error || "Failed to create outline");
        return;
      }

      setOutlines([data, ...outlines]);
      setNewTitle("");
      setNewSubject("");
      setNewContent("");
      setNewSource("");
      setSuccessMsg("Outline created successfully!");
      setExpandedOutlineId(data.id);
    } catch (err: any) {
      setErrorMsg(err.message || "Error creating outline");
    } finally {
      setSubmittingOutline(false);
    }
  }

  async function handleGenerate(outlineId: string) {
    setGeneratingId(outlineId);
    setErrorMsg("");
    setSuccessMsg("");

    try {
      const res = await fetch(`/api/classroom/teacher/outlines/${outlineId}/generate`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.error || "Generation failed");
        return;
      }

      setOutlines(outlines.map((o) => (o.id === outlineId ? data : o)));
      setSuccessMsg("Study notes & 7-day revision plan generated and verified!");
      setExpandedOutlineId(outlineId);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to generate material");
    } finally {
      setGeneratingId(null);
    }
  }

  async function handlePublish(outlineId: string) {
    try {
      const res = await fetch(`/api/classroom/teacher/outlines/${outlineId}/publish`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.error || "Failed to publish");
        return;
      }
      setOutlines(outlines.map((o) => (o.id === outlineId ? data : o)));
      setSuccessMsg("Outline published to enrolled students!");
    } catch (err: any) {
      setErrorMsg(err.message || "Error publishing");
    }
  }

  const copyCode = () => {
    if (user?.enrollment_code) {
      navigator.clipboard.writeText(user.enrollment_code);
      setCopiedCode(true);
      setTimeout(() => setCopiedCode(false), 2000);
    }
  };

  if (loading) {
    return (
      <div className="page-container" style={{ textAlign: "center", padding: "100px 0" }}>
        <p className="badge info">Loading Teacher Portal...</p>
      </div>
    );
  }

  // Not signed in as teacher: Auth Screen
  if (!user) {
    return (
      <div className="page-container" style={{ maxWidth: "520px" }}>
        <div className="card" style={{ marginTop: "40px" }}>
          <div style={{ textAlign: "center", marginBottom: "24px" }}>
            <span className="badge info" style={{ marginBottom: "12px" }}>
              Teacher Portal
            </span>
            <h1 style={{ fontSize: "28px", fontWeight: "800", letterSpacing: "-0.03em" }}>
              {authMode === "login" ? "Welcome Back, Educator" : "Create Teacher Account"}
            </h1>
            <p style={{ color: "var(--soft)", fontSize: "14px", marginTop: "6px" }}>
              Curate lesson outlines, generate grounded notes, and distribute 7-day study plans.
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
                  placeholder="e.g. Dr. Jane Smith"
                  value={authForm.name}
                  onChange={(e) => setAuthForm({ ...authForm, name: e.target.value })}
                  required
                />
              </div>
            )}

            <div className="form-group">
              <label className="form-label">School Email</label>
              <input
                type="email"
                placeholder="teacher@institution.edu"
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
              {authMode === "login" ? "Sign In to Teacher Portal" : "Register as Teacher"}
            </button>
          </form>

          <div style={{ textAlign: "center", marginTop: "20px", fontSize: "13px", color: "var(--soft)" }}>
            {authMode === "login" ? "Need a teacher account?" : "Already registered?"}{" "}
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

  // Signed in Teacher Dashboard
  return (
    <div className="page-container">
      {/* Header and Enrollment Code banner */}
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
            Educator Workspace
          </span>
          <h1 style={{ fontSize: "32px", fontWeight: "800", letterSpacing: "-0.03em" }}>
            Hello, {user.name}
          </h1>
          <p style={{ color: "var(--soft)", fontSize: "14px" }}>
            Share verified lesson materials and track enrolled students.
          </p>
        </div>

        {/* Enrollment code card */}
        <div
          className="card"
          style={{
            padding: "16px 24px",
            background: "linear-gradient(135deg, var(--surface), var(--accent-bg))",
            display: "flex",
            alignItems: "center",
            gap: "20px",
          }}
        >
          <div>
            <span style={{ fontSize: "11px", fontWeight: "700", color: "var(--soft)", textTransform: "uppercase" }}>
              Student Enrollment Code
            </span>
            <div
              style={{
                fontFamily: "var(--mono)",
                fontSize: "26px",
                fontWeight: "800",
                color: "var(--accent)",
                letterSpacing: "0.15em",
              }}
            >
              {user.enrollment_code}
            </div>
          </div>
          <button onClick={copyCode} className="primary" style={{ padding: "8px 14px" }}>
            {copiedCode ? <Check size={16} /> : <Copy size={16} />}
            <span>{copiedCode ? "Copied" : "Copy"}</span>
          </button>
        </div>
      </div>

      {errorMsg && <div className="alert error">{errorMsg}</div>}
      {successMsg && <div className="alert success">{successMsg}</div>}

      {/* Main Grid: Outlines (left) & Enrolled Students (right) */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.4fr) minmax(300px, 0.6fr)",
          gap: "28px",
          alignItems: "start",
        }}
      >
        {/* Left Column: Create Outline + Outline List */}
        <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
          {/* New Outline Creation Form */}
          <div className="card">
            <div className="card-header">
              <h2 className="card-title" style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <Plus size={20} color="var(--accent)" />
                Create New Class Outline
              </h2>
            </div>

            <form onSubmit={handleCreateOutline}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <div className="form-group">
                  <label className="form-label">Subject</label>
                  <input
                    type="text"
                    placeholder="e.g. Biology, AP Chemistry"
                    value={newSubject}
                    onChange={(e) => setNewSubject(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Unit / Topic Title</label>
                  <input
                    type="text"
                    placeholder="e.g. Cellular Respiration & ATP"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Curriculum Objectives & Outline</label>
                <textarea
                  placeholder="Outline key concepts, required competencies, or lesson breakdown (min 20 chars)..."
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  style={{ minHeight: "100px" }}
                  required
                />
              </div>

              <div className="form-group">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <label className="form-label">Teacher-Approved Source Text (for AI Grounding)</label>
                  <span style={{ fontSize: "11px", color: newSource.length >= 200 ? "var(--ok)" : "var(--warn)" }}>
                    {newSource.length} / 200 characters min for AI generation
                  </span>
                </div>
                <textarea
                  placeholder="Paste verified textbook paragraphs, official syllabus specs, or lecture excerpts here. The verify-then-render pipeline uses ONLY this text to generate notes."
                  value={newSource}
                  onChange={(e) => setNewSource(e.target.value)}
                  style={{ minHeight: "120px" }}
                />
              </div>

              <button type="submit" className="primary" disabled={submittingOutline}>
                <Plus size={16} />
                <span>{submittingOutline ? "Saving..." : "Create Outline"}</span>
              </button>
            </form>
          </div>

          {/* Outlines List */}
          <div>
            <h2 style={{ fontSize: "20px", fontWeight: "700", marginBottom: "16px" }}>
              Your Outlines ({outlines.length})
            </h2>

            {outlines.length === 0 ? (
              <div className="card" style={{ textAlign: "center", padding: "40px 20px" }}>
                <BookOpen size={36} color="var(--soft)" style={{ margin: "0 auto 12px" }} />
                <p style={{ color: "var(--soft)" }}>No class outlines created yet. Create your first outline above!</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                {outlines.map((outline) => {
                  const isExpanded = expandedOutlineId === outline.id;
                  const hasSource = Boolean(outline.source_text && outline.source_text.length >= 200);

                  return (
                    <div key={outline.id} className="card" style={{ padding: "20px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "12px" }}>
                        <div>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                            <span className="badge info">{outline.subject}</span>
                            <span className={`badge ${outline.published ? "ok" : "warn"}`}>
                              {outline.published ? "Published to Students" : "Draft"}
                            </span>
                            {outline.notes && (
                              <span className="badge ok">
                                <ShieldCheck size={12} />
                                Notes Verified
                              </span>
                            )}
                          </div>
                          <h3 style={{ fontSize: "18px", fontWeight: "700" }}>{outline.title}</h3>
                          <p style={{ fontSize: "12px", color: "var(--soft)", marginTop: "4px" }}>
                            Created on {new Date(outline.created_at).toLocaleDateString()}
                          </p>
                        </div>

                        <div style={{ display: "flex", gap: "8px" }}>
                          {/* AI Generation button */}
                          <button
                            className="primary"
                            onClick={() => handleGenerate(outline.id)}
                            disabled={generatingId === outline.id || !hasSource}
                            title={!hasSource ? "Needs 200+ chars of source text" : "Generate verified notes"}
                            style={{ padding: "8px 14px", fontSize: "12px" }}
                          >
                            <Sparkles size={14} />
                            <span>
                              {generatingId === outline.id
                                ? "Verifying & Generating..."
                                : outline.notes
                                ? "Regenerate"
                                : "Generate AI Study Plan"}
                            </span>
                          </button>

                          {/* Publish button */}
                          {!outline.published && (
                            <button
                              onClick={() => handlePublish(outline.id)}
                              className="outline-btn"
                              style={{ padding: "8px 14px", fontSize: "12px" }}
                            >
                              <Send size={14} />
                              <span>Publish</span>
                            </button>
                          )}

                          {/* Toggle Expand */}
                          <button
                            onClick={() => setExpandedOutlineId(isExpanded ? null : outline.id)}
                            className="outline-btn"
                            style={{ padding: "8px", minWidth: "36px" }}
                          >
                            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                          </button>
                        </div>
                      </div>

                      {/* Expanded View */}
                      {isExpanded && (
                        <div style={{ marginTop: "20px", paddingTop: "20px", borderTop: "1px solid var(--line)" }}>
                          <h4 style={{ fontSize: "14px", fontWeight: "700", marginBottom: "8px" }}>
                            Outline Requirements
                          </h4>
                          <div
                            style={{
                              background: "var(--sunken)",
                              padding: "12px 16px",
                              borderRadius: "var(--radius)",
                              fontSize: "13px",
                              whiteSpace: "pre-wrap",
                              marginBottom: "16px",
                            }}
                          >
                            {outline.content}
                          </div>

                          {outline.source_text && (
                            <div style={{ marginBottom: "16px" }}>
                              <h4 style={{ fontSize: "14px", fontWeight: "700", marginBottom: "8px" }}>
                                Grounding Source Material ({outline.source_text.length} chars)
                              </h4>
                              <div
                                style={{
                                  background: "var(--sunken)",
                                  padding: "12px 16px",
                                  borderRadius: "var(--radius)",
                                  fontSize: "12px",
                                  color: "var(--soft)",
                                  maxHeight: "120px",
                                  overflowY: "auto",
                                  whiteSpace: "pre-wrap",
                                }}
                              >
                                {outline.source_text}
                              </div>
                            </div>
                          )}

                          {/* Generated Revision Notes */}
                          {outline.notes && (
                            <div style={{ marginBottom: "20px" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                                <h4 style={{ fontSize: "15px", fontWeight: "700", color: "var(--ok)", display: "flex", alignItems: "center", gap: "6px" }}>
                                  <ShieldCheck size={16} />
                                  Verified Revision Notes
                                </h4>
                                {outline.generated_by && (
                                  <span style={{ fontSize: "11px", color: "var(--soft)", fontFamily: "var(--mono)" }}>
                                    {outline.generated_by}
                                  </span>
                                )}
                              </div>
                              <div
                                className="markdown-body"
                                style={{
                                  background: "var(--surface)",
                                  border: "1px solid var(--line)",
                                  borderRadius: "var(--radius)",
                                  padding: "18px 22px",
                                  fontSize: "14px",
                                  whiteSpace: "pre-wrap",
                                }}
                              >
                                {outline.notes}
                              </div>
                            </div>
                          )}

                          {/* 7-Day Study Plan */}
                          {outline.study_plan?.days && (
                            <div>
                              <h4 style={{ fontSize: "15px", fontWeight: "700", marginBottom: "12px", display: "flex", alignItems: "center", gap: "6px" }}>
                                <Calendar size={16} color="var(--accent)" />
                                7-Day Structured Study Plan
                              </h4>
                              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "12px" }}>
                                {outline.study_plan.days.map((d: any) => (
                                  <div
                                    key={d.day}
                                    style={{
                                      background: "var(--surface)",
                                      border: "1px solid var(--line)",
                                      borderRadius: "var(--radius)",
                                      padding: "14px",
                                    }}
                                  >
                                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                                      <span style={{ fontWeight: "800", color: "var(--accent)", fontSize: "13px" }}>
                                        Day {d.day}
                                      </span>
                                      <span style={{ fontSize: "11px", color: "var(--soft)", display: "flex", alignItems: "center", gap: "3px" }}>
                                        <Clock size={12} />
                                        {d.minutes}m
                                      </span>
                                    </div>
                                    <strong style={{ display: "block", fontSize: "13px", marginBottom: "8px" }}>
                                      {d.focus}
                                    </strong>
                                    <ul style={{ paddingLeft: "16px", margin: 0, fontSize: "12px", color: "var(--soft)" }}>
                                      {d.tasks?.map((t: string, idx: number) => (
                                        <li key={idx} style={{ marginBottom: "4px" }}>
                                          {t}
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Enrolled Students List */}
        <div>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title" style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "18px" }}>
                <Users size={18} color="var(--accent)" />
                Enrolled Students ({students.length})
              </h3>
            </div>

            <p style={{ fontSize: "13px", color: "var(--soft)", marginBottom: "16px" }}>
              Students who have registered with your enrollment code{" "}
              <strong style={{ color: "var(--accent)" }}>{user.enrollment_code}</strong>.
            </p>

            {students.length === 0 ? (
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
                No students enrolled yet. Share your code above with your class!
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {students.map((student) => (
                  <div
                    key={student.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                      padding: "10px 14px",
                      borderRadius: "var(--radius)",
                      background: "var(--sunken)",
                    }}
                  >
                    <div
                      style={{
                        width: "30px",
                        height: "30px",
                        borderRadius: "50%",
                        background: "var(--accent)",
                        color: "white",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontWeight: "700",
                        fontSize: "12px",
                      }}
                    >
                      {student.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div style={{ fontWeight: "700", fontSize: "13px" }}>{student.name}</div>
                      <div style={{ fontSize: "11px", color: "var(--soft)" }}>Active Learner</div>
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
