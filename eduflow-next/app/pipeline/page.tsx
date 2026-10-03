"use client";

import { useEffect, useState } from "react";
import {
  GitBranch,
  ShieldCheck,
  Cpu,
  Activity,
  Layers,
  CheckCircle,
  Clock,
  Zap,
  FileCheck,
  AlertOctagon,
  ArrowRight,
} from "lucide-react";

export default function PipelinePage() {
  const [resilienceData, setResilienceData] = useState<any>(null);

  useEffect(() => {
    fetch("/api/studio/resilience")
      .then((r) => r.json())
      .then((d) => setResilienceData(d))
      .catch((e) => console.error(e));
  }, []);

  const stages = [
    {
      num: 1,
      title: "Document Ingestion",
      desc: "Multi-format parsing (PDF, DOCX, Syllabi) into structural elements with SHA-256 provenance.",
      category: "Ingestion",
      status: "Ready",
    },
    {
      num: 2,
      title: "Structural Span Extraction",
      desc: "Deconstructs documents into page-bounded bounding-box spans with reading-order preservation.",
      category: "Parsing",
      status: "Active",
    },
    {
      num: 3,
      title: "Curriculum Decomposition",
      desc: "Identifies atomic syllabus objectives, Bloom cognitive levels, and official competency codes.",
      category: "Graph",
      status: "Active",
    },
    {
      num: 4,
      title: "DAG Prerequisite Assembly",
      desc: "Constructs dependency edges with topological sorting and cycle prevention guarantees.",
      category: "Graph",
      status: "Active",
    },
    {
      num: 5,
      title: "Exam Question Mapping",
      desc: "Ensemble mapping combining vector embeddings, lexical BM25, and LLM consensus scoring.",
      category: "Assessment",
      status: "Active",
    },
    {
      num: 6,
      title: "Class Mastery Feedback",
      desc: "Ingests student mastery signals to trigger automated reteach windows for struggling concepts.",
      category: "Mastery",
      status: "Active",
    },
    {
      num: 7,
      title: "Assessment Emphasis Scoring",
      desc: "Calculates historic past paper mark weights to prioritize high-yield curriculum objectives.",
      category: "Optimization",
      status: "Active",
    },
    {
      num: 8,
      title: "Constraint-Based Scheduling",
      desc: "Solves optimal academic calendar allocations adhering to hard window and holiday constraints.",
      category: "Scheduling",
      status: "Active",
    },
    {
      num: 9,
      title: "Grounded Content Generation",
      desc: "Generates student revision notes strictly conditioned on teacher-approved source material.",
      category: "AI Generation",
      status: "Dual-Engine",
    },
    {
      num: 10,
      title: "Factual Verification & Audit",
      desc: "Secondary independent LLM audits every claim against raw source spans before publishing.",
      category: "Verification",
      status: "Guaranteed",
    },
  ];

  return (
    <div className="page-container">
      {/* Header */}
      <div style={{ marginBottom: "32px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
          <span className="badge info">Architecture & Telemetry</span>
          <span className="badge ok">10-Stage Verification Engine</span>
        </div>
        <h1 style={{ fontSize: "36px", fontWeight: "800", letterSpacing: "-0.03em" }}>
          Pipeline Architecture & Resilience Audit
        </h1>
        <p style={{ color: "var(--soft)", fontSize: "15px", maxWidth: "750px" }}>
          EduFlow implements an end-to-end verified curriculum delivery pipeline. Every generated
          sentence is factually bounded against source material, with automated failover and circuit breaker protection.
        </p>
      </div>

      {/* Resilience & Provider Failover Telemetry */}
      <div className="card" style={{ marginBottom: "36px" }}>
        <div className="card-header">
          <div>
            <h2 className="card-title" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <Cpu size={20} color="var(--accent)" />
              LLM Provider Health & Circuit Breakers
            </h2>
            <p style={{ color: "var(--soft)", fontSize: "13px", marginTop: "4px" }}>
              Dynamic fallback chain with per-provider failure thresholds and automatic cooldown recovery.
            </p>
          </div>
          <span className="badge ok">
            <Activity size={12} />
            Telemetry Active
          </span>
        </div>

        {/* Provider status cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "14px", marginBottom: "24px" }}>
          {(resilienceData?.providers || []).map((prov: any) => (
            <div
              key={prov.name}
              style={{
                background: "var(--sunken)",
                border: "1px solid var(--line)",
                borderRadius: "var(--radius)",
                padding: "16px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <div>
                  <span style={{ fontWeight: "800", textTransform: "capitalize", fontSize: "16px" }}>
                    {prov.name}
                  </span>
                  <span style={{ fontSize: "11px", color: "var(--soft)", textTransform: "uppercase", marginLeft: "8px", fontWeight: "700" }}>
                    ({prov.role})
                  </span>
                </div>
                <span className={`badge ${prov.configured ? "ok" : "warn"}`}>
                  {prov.configured ? "API Key Set" : "Missing Key"}
                </span>
              </div>
              <div style={{ fontSize: "12px", fontFamily: "var(--mono)", color: "var(--soft)", marginBottom: "4px" }}>
                Model: {prov.model}
              </div>
              <div style={{ fontSize: "11px", color: "var(--soft)" }}>
                Circuit: <strong style={{ color: prov.configured ? "var(--ok)" : "var(--warn)" }}>
                  {prov.configured ? "Active" : "Unconfigured"}
                </strong>
              </div>
            </div>
          ))}
        </div>

        {/* Recent Audit events */}
        <h3 style={{ fontSize: "15px", fontWeight: "700", marginBottom: "12px" }}>
          Recent Provider Event Telemetry
        </h3>
        {resilienceData?.recentEvents?.length ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {resilienceData.recentEvents.map((evt: any, i: number) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "10px 14px",
                  borderRadius: "var(--radius)",
                  background: "var(--surface)",
                  border: "1px solid var(--line)",
                  fontSize: "12px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span className={`badge ${evt.status === "success" ? "ok" : "warn"}`}>
                    {evt.status}
                  </span>
                  <strong>{evt.provider}</strong>
                  <span style={{ color: "var(--soft)", fontFamily: "var(--mono)" }}>{evt.model}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "14px", color: "var(--soft)", fontFamily: "var(--mono)" }}>
                  <span>{evt.latencyMs}ms</span>
                  <span>{new Date(evt.timestamp).toLocaleTimeString()}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div
            style={{
              background: "var(--sunken)",
              padding: "14px",
              borderRadius: "var(--radius)",
              fontSize: "12px",
              color: "var(--soft)",
            }}
          >
            No provider events logged in this session yet. Events will appear here during AI generation and verification calls.
          </div>
        )}
      </div>

      {/* 10-Stage Pipeline Overview */}
      <h2 style={{ fontSize: "24px", fontWeight: "800", letterSpacing: "-0.03em", marginBottom: "18px" }}>
        The 10-Stage Educational Pipeline
      </h2>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "18px" }}>
        {stages.map((stage) => (
          <div
            key={stage.num}
            className="card"
            style={{
              padding: "20px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
            }}
          >
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                <span
                  style={{
                    fontFamily: "var(--mono)",
                    fontSize: "12px",
                    fontWeight: "800",
                    color: "var(--accent)",
                    background: "var(--accent-bg)",
                    padding: "4px 8px",
                    borderRadius: "6px",
                  }}
                >
                  STAGE {stage.num.toString().padStart(2, "0")}
                </span>
                <span className="badge ok">{stage.status}</span>
              </div>
              <h3 style={{ fontSize: "17px", fontWeight: "700", marginBottom: "6px" }}>
                {stage.title}
              </h3>
              <p style={{ fontSize: "13px", color: "var(--soft)", lineHeight: "1.5" }}>
                {stage.desc}
              </p>
            </div>

            <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "11px", fontWeight: "700", color: "var(--soft)", textTransform: "uppercase" }}>
                {stage.category}
              </span>
              <CheckCircle size={15} color="var(--ok)" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
