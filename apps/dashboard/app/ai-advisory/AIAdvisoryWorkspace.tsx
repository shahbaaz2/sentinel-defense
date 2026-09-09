"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type Incident = {
  incident_id: string;
  title: string;
  severity: string;
  status: string;
  category: string;
  primary_asset_id: string | null;
  detection_ids: string[];
  first_seen: string;
};

type AIStatus = {
  ai_enabled: boolean;
  provider: string;
  model: string;
  status: string;
  external_ai_api?: string;
  last_latency_ms: number | null;
};

type Diagnostics = {
  status: string;
  code: string | null;
  message: string | null;
  provider: string;
  model: string;
  sentinel_core_affected: boolean;
};

type AssessmentContent = {
  classification: string;
  confidence: number;
  summary: string;
  affected_assets: string[];
  evidence_refs: { event_id: string; relevance: string }[];
  detection_refs: { detection_id: string; relevance: string }[];
  hypotheses: string[];
  recommended_investigation_steps: string[];
  attack_techniques: string[];
  recommended_playbook_id: string | null;
  limitations: string[];
};

type Assessment = {
  assessment_id: string;
  incident_id: string;
  created_at: string;
  model_name: string;
  model_provider: string;
  prompt_version: string;
  validation_status: string;
  assessment: AssessmentContent | null;
  latency_ms: number | null;
  error: string | null;
};

function statusTone(status: string) {
  const value = status.toUpperCase();
  if (["READY", "VALID", "ONLINE", "AVAILABLE"].includes(value)) return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  if (["DEGRADED", "LOADING", "UNKNOWN", "UNAVAILABLE"].includes(value)) return "border-amber-500/30 bg-amber-500/10 text-amber-300";
  if (["DISABLED", "PROVIDER_ERROR", "FAILED"].includes(value)) return "border-red-500/30 bg-red-500/10 text-red-300";
  return "border-slate-700 bg-slate-800/60 text-slate-300";
}

function severityTone(severity: string) {
  const value = severity.toLowerCase();
  if (value === "critical") return "text-red-300";
  if (value === "high") return "text-orange-300";
  if (value === "medium") return "text-amber-300";
  return "text-sky-300";
}

export function AIAdvisoryWorkspace({
  incidents,
  initialStatus,
  initialDiagnostics,
  initialAssessments,
}: {
  incidents: Incident[];
  initialStatus: AIStatus | null;
  initialDiagnostics: Diagnostics | null;
  initialAssessments: Record<string, Assessment | null>;
}) {
  const [status, setStatus] = useState(initialStatus);
  const [diagnostics, setDiagnostics] = useState(initialDiagnostics);
  const [assessments, setAssessments] = useState(initialAssessments);
  const [busyIncident, setBusyIncident] = useState<string | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [selectedIncident, setSelectedIncident] = useState<string | null>(incidents[0]?.incident_id ?? null);

  const selected = selectedIncident ? incidents.find((item) => item.incident_id === selectedIncident) ?? null : null;
  const assessment = selectedIncident ? assessments[selectedIncident] ?? null : null;
  const validCount = useMemo(() => Object.values(assessments).filter((item) => item?.validation_status === "VALID").length, [assessments]);

  async function refreshProvider() {
    try {
      const [statusRes, diagnosticRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/ai/status`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/v1/ai/provider-diagnostics`, { cache: "no-store" }),
      ]);
      if (statusRes.ok) setStatus((await statusRes.json()) as AIStatus);
      if (diagnosticRes.ok) setDiagnostics((await diagnosticRes.json()) as Diagnostics);
    } catch {
      // Keep last trusted provider state visible.
    }
  }

  async function analyze(incidentId: string) {
    setBusyIncident(incidentId);
    setRequestError(null);
    setSelectedIncident(incidentId);
    try {
      const res = await fetch(`${API_BASE}/api/v1/incidents/${incidentId}/ai/analyze`, { method: "POST" });
      if (!res.ok) {
        throw new Error(`AI advisory request failed (HTTP ${res.status})`);
      }
      const result = (await res.json()) as Assessment;
      setAssessments((current) => ({ ...current, [incidentId]: result }));
      await refreshProvider();
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : "AI advisory request failed");
      await refreshProvider();
    } finally {
      setBusyIncident(null);
    }
  }

  return (
    <div className="space-y-5">
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <div className="soc-panel rounded-lg p-4">
          <p className="soc-kicker">Provider state</p>
          <div className="mt-2 flex items-center justify-between gap-3">
            <p className="text-xl font-semibold text-white">{status?.status ?? diagnostics?.status ?? "UNKNOWN"}</p>
            <span className={`rounded border px-2 py-1 font-mono text-[9px] font-semibold ${statusTone(status?.status ?? diagnostics?.status ?? "UNKNOWN")}`}>{status?.provider ?? diagnostics?.provider ?? "provider"}</span>
          </div>
          <p className="mt-2 text-[10px] text-slate-500">External advisory dependency</p>
        </div>
        <div className="soc-panel rounded-lg p-4">
          <p className="soc-kicker">Model</p>
          <p className="mt-2 truncate text-lg font-semibold text-white">{status?.model ?? diagnostics?.model ?? "Unavailable"}</p>
          <p className="mt-2 text-[10px] text-slate-500">Schema-validated advisory output</p>
        </div>
        <div className="soc-panel rounded-lg p-4">
          <p className="soc-kicker">Investigations</p>
          <p className="mt-2 text-2xl font-semibold text-white">{incidents.length}</p>
          <p className="mt-2 text-[10px] text-slate-500">Existing deterministic incidents</p>
        </div>
        <div className="soc-panel rounded-lg p-4">
          <p className="soc-kicker">Accepted assessments</p>
          <p className="mt-2 text-2xl font-semibold text-white">{validCount}</p>
          <p className="mt-2 text-[10px] text-slate-500">Validation status = VALID</p>
        </div>
        <div className="soc-panel rounded-lg p-4">
          <p className="soc-kicker">Authority boundary</p>
          <p className="mt-2 text-sm font-semibold text-amber-300">ADVISORY ONLY</p>
          <p className="mt-2 text-[10px] leading-4 text-slate-500">AI cannot create detections, incidents, approvals, or containment actions.</p>
        </div>
      </section>

      {diagnostics && diagnostics.status !== "READY" && (
        <section className="rounded-lg border border-amber-500/25 bg-amber-500/5 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-amber-400">AI provider diagnostic</p>
              <p className="mt-1 text-xs text-amber-100">{diagnostics.message ?? "The advisory provider is currently unavailable."}</p>
            </div>
            {diagnostics.code && <span className="rounded border border-amber-500/30 bg-[#0d1b29] px-2 py-1 font-mono text-[9px] text-amber-300">{diagnostics.code}</span>}
          </div>
          {!diagnostics.sentinel_core_affected && <p className="mt-2 text-[10px] font-semibold text-emerald-300">Sentinel Core remains operational. Detection and incident truth are unaffected.</p>}
        </section>
      )}

      {requestError && (
        <section className="rounded-lg border border-red-500/25 bg-red-500/5 px-4 py-3 text-xs text-red-300">{requestError}</section>
      )}

      <section className="grid gap-5 2xl:grid-cols-[minmax(0,1.05fr)_minmax(420px,0.95fr)]">
        <div className="soc-panel overflow-hidden rounded-lg">
          <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
            <div>
              <p className="soc-kicker">Analyst work queue</p>
              <h2 className="mt-1 text-sm font-semibold text-white">Incident Advisory Queue</h2>
            </div>
            <span className="rounded border border-slate-700 bg-[#0d1b29] px-2 py-1 font-mono text-[9px] text-slate-500">{incidents.length} incidents</span>
          </div>
          <div className="max-h-[620px] overflow-auto">
            {incidents.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">No incidents are available for advisory analysis.</div>
            ) : incidents.map((incident) => {
              const itemAssessment = assessments[incident.incident_id];
              const active = selectedIncident === incident.incident_id;
              return (
                <button
                  key={incident.incident_id}
                  onClick={() => setSelectedIncident(incident.incident_id)}
                  className={`grid w-full grid-cols-[minmax(0,1fr)_auto] gap-4 border-b border-slate-800 px-5 py-4 text-left transition last:border-b-0 ${active ? "bg-sky-500/7" : "hover:bg-slate-800/35"}`}
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`text-[9px] font-bold uppercase ${severityTone(incident.severity)}`}>{incident.severity}</span>
                      <span className="font-mono text-[9px] text-slate-600">{incident.incident_id}</span>
                    </div>
                    <p className="mt-1.5 truncate text-xs font-semibold text-slate-200">{incident.title}</p>
                    <p className="mt-1 text-[9px] text-slate-600">{incident.detection_ids.length} detections · {incident.primary_asset_id ?? "no primary asset"} · {new Date(incident.first_seen).toLocaleString()}</p>
                  </div>
                  <span className={`self-center rounded border px-2 py-1 font-mono text-[8px] ${statusTone(itemAssessment?.validation_status ?? "NOT_ANALYZED")}`}>{itemAssessment?.validation_status ?? "NOT ANALYZED"}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="soc-panel overflow-hidden rounded-lg">
          <div className="border-b border-slate-800 px-5 py-4">
            <p className="soc-kicker">Evidence-grounded analysis</p>
            <h2 className="mt-1 text-sm font-semibold text-white">AI Analyst Workbench</h2>
          </div>
          {!selected ? (
            <div className="p-8 text-center text-xs text-slate-500">Select an incident to review advisory analysis.</div>
          ) : (
            <div className="p-5">
              <div className="flex flex-col justify-between gap-4 border-b border-slate-800 pb-4 sm:flex-row sm:items-start">
                <div>
                  <p className={`text-[9px] font-bold uppercase ${severityTone(selected.severity)}`}>{selected.severity} · {selected.category}</p>
                  <h3 className="mt-1.5 text-base font-semibold text-white">{selected.title}</h3>
                  <p className="mt-1 font-mono text-[9px] text-slate-600">{selected.incident_id}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => analyze(selected.incident_id)}
                    disabled={busyIncident === selected.incident_id || !status?.ai_enabled}
                    className="rounded bg-indigo-500 px-3 py-2 text-[10px] font-bold text-white transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-500"
                  >
                    {busyIncident === selected.incident_id ? "Analyzing…" : assessment ? "Run new advisory" : "Analyze with AI"}
                  </button>
                  <Link href={`/incidents/${selected.incident_id}`} className="rounded border border-slate-700 bg-[#0d1b29] px-3 py-2 text-[10px] font-semibold text-slate-300 hover:border-sky-500/40 hover:text-white">Full investigation →</Link>
                </div>
              </div>

              {!assessment ? (
                <div className="mt-5 rounded border border-dashed border-slate-700 bg-[#0b141d] p-6 text-center">
                  <p className="text-xs font-semibold text-slate-300">No advisory assessment recorded yet.</p>
                  <p className="mt-2 text-[10px] leading-5 text-slate-600">The incident already exists because deterministic rules and correlation created it. AI is an optional second opinion over that evidence.</p>
                </div>
              ) : (
                <div className="mt-5 space-y-4">
                  <div className="grid gap-3 sm:grid-cols-3">
                    <div className="rounded border border-slate-800 bg-[#0d1b29] p-3"><p className="soc-kicker">Validation</p><p className={`mt-2 text-xs font-semibold ${assessment.validation_status === "VALID" ? "text-emerald-300" : "text-amber-300"}`}>{assessment.validation_status}</p></div>
                    <div className="rounded border border-slate-800 bg-[#0d1b29] p-3"><p className="soc-kicker">Provider / model</p><p className="mt-2 truncate font-mono text-[10px] text-slate-300">{assessment.model_provider} · {assessment.model_name}</p></div>
                    <div className="rounded border border-slate-800 bg-[#0d1b29] p-3"><p className="soc-kicker">Latency</p><p className="mt-2 font-mono text-xs text-slate-300">{assessment.latency_ms == null ? "n/a" : `${assessment.latency_ms} ms`}</p></div>
                  </div>

                  {assessment.validation_status !== "VALID" || !assessment.assessment ? (
                    <div className="rounded border border-amber-500/25 bg-amber-500/5 p-4 text-xs leading-5 text-amber-200">
                      <p className="font-semibold">This advisory attempt was not accepted as a valid assessment.</p>
                      <p className="mt-1 text-amber-300/80">{assessment.error ?? assessment.validation_status}</p>
                    </div>
                  ) : (
                    <>
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded border border-indigo-500/30 bg-indigo-500/10 px-2 py-1 text-[9px] font-bold uppercase text-indigo-300">{assessment.assessment.classification}</span>
                          <span className="text-[10px] text-slate-500">confidence {(assessment.assessment.confidence * 100).toFixed(0)}%</span>
                        </div>
                        <p className="mt-3 text-sm leading-6 text-slate-200">{assessment.assessment.summary}</p>
                      </div>

                      {assessment.assessment.hypotheses.length > 0 && <div><p className="soc-kicker">Hypotheses</p><ul className="mt-2 space-y-1.5 text-[11px] leading-5 text-slate-400">{assessment.assessment.hypotheses.map((item, index) => <li key={index}>• {item}</li>)}</ul></div>}

                      {assessment.assessment.recommended_investigation_steps.length > 0 && <div><p className="soc-kicker">Recommended analyst steps</p><ol className="mt-2 space-y-1.5 text-[11px] leading-5 text-slate-400">{assessment.assessment.recommended_investigation_steps.map((item, index) => <li key={index}><span className="mr-2 font-mono text-sky-400">{String(index + 1).padStart(2, "0")}</span>{item}</li>)}</ol></div>}

                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="rounded border border-slate-800 bg-[#0d1b29] p-3"><p className="soc-kicker">ATT&CK candidates</p><p className="mt-2 font-mono text-[10px] leading-5 text-slate-300">{assessment.assessment.attack_techniques.join(", ") || "None returned"}</p></div>
                        <div className="rounded border border-slate-800 bg-[#0d1b29] p-3"><p className="soc-kicker">Evidence citations</p><p className="mt-2 text-xs text-slate-300">{assessment.assessment.evidence_refs.length} events · {assessment.assessment.detection_refs.length} detections</p></div>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
