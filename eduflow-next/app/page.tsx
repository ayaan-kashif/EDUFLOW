"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Compass,
  FileText,
  Network,
  Calendar,
  ShieldCheck,
  Zap,
  ArrowRight,
  Sparkles,
  Layers,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Plus,
} from "lucide-react";

export default function WorkspacePage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"graph" | "schedule" | "evidence">("graph");
  const [simulationScenario, setSimulationScenario] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/studio/workspace")
      .then((r) => r.json())
      .then((d) => setData(d))
      .catch((e) => {
        console.error(e);
        setData({ error: "Workspace unavailable" });
      })
      .finally(() => setLoading(false));
  }, []);

  const stats = data?.stats || {
    nodeCount: 0,
    edgeCount: 0,
    docCount: 0,
    planCount: 0,
    claimCount: 0,
  };

  const nodes = data?.nodes || [];
  const units = data?.scheduledUnits || [];
  const claims = data?.claims || [];

  if (!loading && data?.error) {
    return (
      <div className="page-container">
        <section className="card" style={{ padding: "clamp(28px, 5vw, 56px)", maxWidth: "900px", margin: "36px auto" }}>
          <span className="badge info">EduFlow Classroom</span>
          <h1 style={{ fontFamily: "var(--display)", fontSize: "clamp(32px, 5vw, 56px)", margin: "18px 0" }}>
            From lesson outline to a focused study plan.
          </h1>
          <p style={{ color: "var(--soft)", fontSize: "17px", lineHeight: 1.6 }}>
            Teachers add an outline and approved source material. EduFlow drafts notes and a seven-day plan,
            checks the draft with a second AI provider, then shares it with enrolled students after publishing.
          </p>
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", marginTop: "26px" }}>
            <Link href="/teacher" className="primary">Open Teacher Portal</Link>
            <Link href="/student" className="outline-btn">Open Student Portal</Link>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="page-container">
      {/* Hero Studio Banner */}
      <div
        className="card"
        style={{
          background: "linear-gradient(135deg, var(--surface) 30%, var(--accent-bg))",
          border: "1px solid var(--line)",
          padding: "36px 40px",
          marginBottom: "32px",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div style={{ maxWidth: "760px", position: "relative", zIndex: 2 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
            <span className="badge info">EduFlow Atelier 2.0</span>
            <span className="badge info">Teacher Workspace</span>
          </div>
          <h1
            style={{
              fontFamily: "var(--display)",
              fontSize: "clamp(32px, 3.5vw, 48px)",
              fontWeight: 800,
              letterSpacing: "-0.04em",
              lineHeight: 1.15,
              marginBottom: "14px",
            }}
          >
            Your Classroom Workspace
          </h1>
          <p style={{ color: "var(--soft)", fontSize: "16px", lineHeight: "1.6", marginBottom: "24px" }}>
            Review curriculum records and classroom planning data stored in the shared database.
            Create and publish source-guided student materials in the Teacher Portal.
          </p>

          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
            <Link href="/teacher" className="primary" style={{ padding: "11px 20px" }}>
              <Sparkles size={16} />
              <span>Launch Teacher Studio</span>
            </Link>
            <Link href="/pipeline" className="outline-btn" style={{ padding: "11px 20px" }}>
              <Network size={16} />
              <span>View Classroom Workflow</span>
            </Link>
          </div>
        </div>
      </div>

      {/* KPI Stats Bar */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "16px",
          marginBottom: "32px",
        }}
      >
        <div className="card" style={{ padding: "18px 22px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", color: "var(--soft)", fontSize: "12px", fontWeight: "700" }}>
            <span>CURRICULUM NODES</span>
            <Layers size={16} color="var(--accent)" />
          </div>
          <div style={{ fontSize: "32px", fontWeight: "800", marginTop: "6px" }}>
            {stats.nodeCount}
          </div>
          <span style={{ fontSize: "11px", color: "var(--ok)", fontWeight: "600" }}>
            {stats.nodeCount > 0 ? "Stored in workspace" : "Awaiting Data"}
          </span>
        </div>

        <div className="card" style={{ padding: "18px 22px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", color: "var(--soft)", fontSize: "12px", fontWeight: "700" }}>
            <span>DEPENDENCY EDGES</span>
            <Network size={16} color="var(--orange)" />
          </div>
          <div style={{ fontSize: "32px", fontWeight: "800", marginTop: "6px" }}>
            {stats.edgeCount}
          </div>
          <span style={{ fontSize: "11px", color: "var(--soft)" }}>Prerequisites & Coverage</span>
        </div>

        <div className="card" style={{ padding: "18px 22px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", color: "var(--soft)", fontSize: "12px", fontWeight: "700" }}>
            <span>SCHEDULED UNITS</span>
            <Calendar size={16} color="var(--ok)" />
          </div>
          <div style={{ fontSize: "32px", fontWeight: "800", marginTop: "6px" }}>
            {units.length}
          </div>
          <span style={{ fontSize: "11px", color: "var(--soft)" }}>Stored schedule records</span>
        </div>

        <div className="card" style={{ padding: "18px 22px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", color: "var(--soft)", fontSize: "12px", fontWeight: "700" }}>
            <span>VERIFIED CLAIMS</span>
            <ShieldCheck size={16} color="var(--accent)" />
          </div>
          <div style={{ fontSize: "32px", fontWeight: "800", marginTop: "6px" }}>
            {claims.filter((c: any) => c.verification_status === "verified").length} / {claims.length}
          </div>
          <span style={{ fontSize: "11px", color: "var(--soft)" }}>Recorded claim status</span>
        </div>
      </div>

      {/* Tabs Control */}
      <div style={{ display: "flex", gap: "10px", borderBottom: "1px solid var(--line)", paddingBottom: "12px", marginBottom: "24px" }}>
        <button
          onClick={() => setActiveTab("graph")}
          className={activeTab === "graph" ? "primary" : "outline-btn"}
          style={{ padding: "8px 16px" }}
        >
          <Network size={15} />
          <span>Curriculum Graph ({nodes.length})</span>
        </button>
        <button
          onClick={() => setActiveTab("schedule")}
          className={activeTab === "schedule" ? "primary" : "outline-btn"}
          style={{ padding: "8px 16px" }}
        >
          <Calendar size={15} />
          <span>Calendar & Scheduler ({units.length})</span>
        </button>
        <button
          onClick={() => setActiveTab("evidence")}
          className={activeTab === "evidence" ? "primary" : "outline-btn"}
          style={{ padding: "8px 16px" }}
        >
          <ShieldCheck size={15} />
          <span>Claims & Evidence ({claims.length})</span>
        </button>
      </div>

      {/* TAB 1: Curriculum Graph */}
      {activeTab === "graph" && (
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Curriculum Hierarchy & Dependency Graph</h2>
              <p style={{ color: "var(--soft)", fontSize: "13px", marginTop: "4px" }}>
                Deconstructed atomic units mapped with confidence and provenance tracing.
              </p>
            </div>
          </div>

          {nodes.length === 0 ? (
            <div style={{ textAlign: "center", padding: "48px 20px", color: "var(--soft)" }}>
              <Layers size={36} style={{ margin: "0 auto 12px", opacity: 0.6 }} />
              <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--ink)", marginBottom: "6px" }}>
                No Curriculum Nodes Ingested
              </h3>
              <p style={{ fontSize: "13px", maxWidth: "440px", margin: "0 auto 16px" }}>
                The curriculum database currently has 0 nodes. Ingest syllabus documents or create class outlines in the Teacher Portal to populate the hierarchy.
              </p>
              <Link href="/teacher" className="primary" style={{ padding: "8px 16px", fontSize: "12px", display: "inline-flex" }}>
                <Plus size={14} />
                <span>Create Outline in Teacher Portal</span>
              </Link>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {nodes.map((n: any) => (
                <div
                  key={n.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "14px 18px",
                    borderRadius: "var(--radius)",
                    background: "var(--sunken)",
                    border: "1px solid var(--line)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <span
                      className="badge"
                      style={{
                        background:
                          n.node_type === "topic"
                            ? "var(--accent-bg)"
                            : n.node_type === "subtopic"
                            ? "var(--ok-bg)"
                            : "var(--warn-bg)",
                        color:
                          n.node_type === "topic"
                            ? "var(--accent)"
                            : n.node_type === "subtopic"
                            ? "var(--ok)"
                            : "var(--warn)",
                      }}
                    >
                      {n.node_type}
                    </span>
                    <div>
                      <span style={{ fontWeight: "700", fontSize: "14px" }}>{n.label}</span>
                      {n.syllabus_ref && (
                        <span style={{ fontFamily: "var(--mono)", fontSize: "11px", color: "var(--soft)", marginLeft: "10px" }}>
                          [{n.syllabus_ref}]
                        </span>
                      )}
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <span className="badge info" style={{ fontSize: "10px" }}>
                      Origin: {n.origin}
                    </span>
                    <span style={{ fontSize: "12px", fontFamily: "var(--mono)", fontWeight: "700", color: "var(--ok)" }}>
                      {(n.confidence * 100).toFixed(0)}% Conf
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: Calendar & Constraint Scheduler */}
      {activeTab === "schedule" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          {/* Schedule list */}
          <div className="card">
            <h2 className="card-title" style={{ marginBottom: "16px" }}>
              Allocated Teaching Units ({units.length})
            </h2>

            {units.length === 0 ? (
              <div style={{ textAlign: "center", padding: "48px 20px", color: "var(--soft)" }}>
                <Calendar size={36} style={{ margin: "0 auto 12px", opacity: 0.6 }} />
                <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--ink)", marginBottom: "6px" }}>
                  No Teaching Units Scheduled
                </h3>
                <p style={{ fontSize: "13px", maxWidth: "440px", margin: "0 auto" }}>
                  No teaching units are currently stored in the academic schedule.
                </p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {units.map((u: any, idx: number) => (
                  <div
                    key={u.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "14px 18px",
                      borderRadius: "var(--radius)",
                      background: "var(--sunken)",
                      border: "1px solid var(--line)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                      <span style={{ fontFamily: "var(--mono)", fontSize: "12px", fontWeight: "700", color: "var(--accent)" }}>
                        Slot #{idx + 1}
                      </span>
                      <div>
                        <div style={{ fontWeight: "700", fontSize: "14px" }}>{u.unit_title}</div>
                        <span style={{ fontSize: "11px", color: "var(--soft)" }}>Date: {u.calendar_date}</span>
                      </div>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                      <span className="badge info">{u.duration_minutes} mins</span>
                      <span className="badge ok">{u.status}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: Evidence & Claims Ledger */}
      {activeTab === "evidence" && (
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Instructional Claims & Factual Verification Ledger</h2>
              <p style={{ color: "var(--soft)", fontSize: "13px", marginTop: "4px" }}>
                This ledger shows any claim records stored in the database. AI notes are reviewed separately before saving.
              </p>
            </div>
          </div>

          {claims.length === 0 ? (
            <div style={{ textAlign: "center", padding: "48px 20px", color: "var(--soft)" }}>
              <ShieldCheck size={36} style={{ margin: "0 auto 12px", opacity: 0.6 }} />
              <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--ink)", marginBottom: "6px" }}>
                No Claims Recorded Yet
              </h3>
              <p style={{ fontSize: "13px", maxWidth: "440px", margin: "0 auto 16px" }}>
                No claim records are stored here. Classroom notes and study plans are available in the Teacher Portal.
              </p>
              <Link href="/teacher" className="primary" style={{ padding: "8px 16px", fontSize: "12px", display: "inline-flex" }}>
                <Sparkles size={14} />
                <span>Go to Teacher Portal</span>
              </Link>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {claims.map((claim: any) => {
                const isVerified = claim.verification_status === "verified";
                return (
                  <div
                    key={claim.id}
                    style={{
                      padding: "16px 20px",
                      borderRadius: "var(--radius)",
                      background: isVerified ? "var(--surface)" : "var(--bad-bg)",
                      border: `1px solid ${isVerified ? "var(--line)" : "var(--bad)"}`,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span className={`badge ${isVerified ? "ok" : "bad"}`}>
                          {isVerified ? "Verified Grounded" : "Unsupported / Flagged"}
                        </span>
                        {claim.source_page && (
                          <span style={{ fontSize: "11px", color: "var(--soft)", fontFamily: "var(--mono)" }}>
                            Source Page {claim.source_page}
                          </span>
                        )}
                      </div>
                      <span style={{ fontSize: "12px", fontFamily: "var(--mono)", fontWeight: "700" }}>
                        Confidence: {(claim.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p style={{ fontSize: "14px", lineHeight: "1.5", margin: 0 }}>
                      &ldquo;{claim.claim_text}&rdquo;
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
