"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const DEMO_API =
  process.env.NEXT_PUBLIC_DEMOCONTROL_API_BASE_URL ?? "http://127.0.0.1:8100";
const SENTINEL_DASHBOARD =
  process.env.NEXT_PUBLIC_SENTINEL_DASHBOARD_URL ?? "https://sentinel-defense-g6id.vercel.app";
const POLL_MS = 1200;
const TERMINAL = new Set(["PASSED", "FAILED", "CANCELLED"]);

type TimelineEntry = {
  timestamp: string;
  message: string;
  level?: string;
  component?: string;
  code?: string;
};

type RunDetail = {
  run_id: string;
  scenario_id: string;
  status: string;
  current_step: string | null;
  failure_reason: string | null;
  started_at: string;
  completed_at: string | null;
  step_results: { step_id: string; action: string; target: string }[];
  timeline: TimelineEntry[];
  missionnet_event_ids: string[];
  sentinel_event_ids: string[];
  detection_ids: string[];
  incident_ids: string[];
  verification: Record<string, boolean>;
  reset_status: string | null;
};

type ScenarioSummary = {
  id: string;
  name: string;
  description: string;
  expected: string;
};

const SCENARIOS: ScenarioSummary[] = [
  {
    id: "SCN-010",
    name: "Multi-Signal Compromise",
    description:
      "Flagship end-to-end validation across identity, service misuse, asset degradation, telemetry anomalies, correlation, and analyst handoff.",
    expected: "5 deterministic detections · 3 incidents",
  },
  {
    id: "SCN-001",
    name: "Credential Pressure",
    description: "Repeated authentication failures and deterministic threshold detection.",
    expected: "DET-001",
  },
  {
    id: "SCN-002",
    name: "Service Identity Compromise",
    description: "Revoked service token followed by protected record access.",
    expected: "DET-006",
  },
  {
    id: "SCN-003",
    name: "Critical Service Degradation",
    description: "Mission-critical asset degradation and evidence-backed incident creation.",
    expected: "DET-002",
  },
  {
    id: "SCN-004",
    name: "Data Access Burst",
    description: "Behavioral threshold detection across controlled record access activity.",
    expected: "DET-003",
  },
];

const DETECTION_LABELS = [
  ["DET-001", "Credential pressure"],
  ["DET-006", "Service identity misuse"],
  ["DET-002", "Critical service degradation"],
  ["DET-004", "Telemetry anomaly"],
  ["DET-005", "Multi-signal correlation"],
];

function statusClass(status: string) {
  if (status === "PASSED") return "border-emerald-500/40 bg-emerald-500/10 text-emerald-300";
  if (status === "FAILED") return "border-red-500/40 bg-red-500/10 text-red-300";
  if (status === "CANCELLED") return "border-zinc-500/40 bg-zinc-500/10 text-zinc-300";
  if (status === "READY") return "border-slate-600 bg-slate-800 text-slate-300";
  return "border-sky-500/40 bg-sky-500/10 text-sky-300";
}

function failureCode(reason: string | null) {
  return reason?.match(/\[([A-Z0-9_]+)\]/)?.[1] ?? "RUN_FAILED";
}

function readableFailure(reason: string | null) {
  const code = failureCode(reason);
  if (code === "UPSTREAM_GATEWAY_ERROR") {
    return {
      title: "Cloud dependency temporarily unavailable",
      impact: "The run stopped before evidence generation. Sentinel did not fabricate downstream results.",
      action: "The service will be revalidated on the next run. Review the dependency log if the condition persists.",
    };
  }
  if (code === "UPSTREAM_INVALID_RESPONSE") {
    return {
      title: "Invalid dependency response",
      impact: "A required service returned an empty or non-JSON response, so the run stopped safely.",
      action: "Review the affected component and retry after its API contract is healthy.",
    };
  }
  return {
    title: "Scenario execution stopped",
    impact: "The workflow did not advance beyond the last verified stage.",
    action: "Review the operational event stream below before starting a new controlled run.",
  };
}

function MiniBars({ values }: { values: number[] }) {
  const max = Math.max(...values, 1);
  return (
    <div className="flex h-10 items-end gap-1">
      {values.map((value, index) => (
        <div
          key={index}
          className="w-full rounded-sm bg-sky-400/70"
          style={{ height: `${Math.max(10, (value / max) * 100)}%` }}
        />
      ))}
    </div>
  );
}

export function EnterpriseSecurityConsole() {
  const [scenarioId, setScenarioId] = useState("SCN-010");
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [starting, setStarting] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const scenario = SCENARIOS.find((item) => item.id === scenarioId) ?? SCENARIOS[0];

  useEffect(() => {
    const hash = window.location.hash.replace(/^#/, "").toUpperCase();
    if (SCENARIOS.some((item) => item.id === hash)) setScenarioId(hash);
  }, []);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;

    async function poll() {
      try {
        const res = await fetch(`${DEMO_API}/api/v1/runs/${runId}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`Run status request failed (HTTP ${res.status})`);
        const data = (await res.json()) as RunDetail;
        if (cancelled) return;
        setRun(data);
        setError(null);
        if (TERMINAL.has(data.status) && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to retrieve run state");
      }
    }

    void poll();
    pollRef.current = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [runId]);

  async function startRun() {
    setStarting(true);
    setError(null);
    setRun(null);
    setRunId(null);
    try {
      const res = await fetch(`${DEMO_API}/api/v1/scenarios/${scenario.id}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor: "portfolio-demo" }),
      });
      if (!res.ok) throw new Error(`Scenario start failed (HTTP ${res.status})`);
      const started = (await res.json()) as { run_id: string };
      setRunId(started.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start scenario");
    } finally {
      setStarting(false);
    }
  }

  async function resetLab() {
    if (!runId) return;
    setResetting(true);
    setError(null);
    try {
      const res = await fetch(`${DEMO_API}/api/v1/runs/${runId}/reset`, { method: "POST" });
      if (!res.ok) throw new Error(`Lab reset failed (HTTP ${res.status})`);
      const updated = (await res.json()) as RunDetail;
      setRun(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lab reset failed");
    } finally {
      setResetting(false);
    }
  }

  const status = run?.status ?? "READY";
  const runActive = Boolean(run && !TERMINAL.has(run.status));
  const failed = run?.status === "FAILED";
  const failure = failed ? readableFailure(run?.failure_reason ?? null) : null;
  const verificationPassed = run ? Object.values(run.verification).filter(Boolean).length : 0;
  const verificationTotal = run ? Object.keys(run.verification).length : 0;

  const pipeline = useMemo(() => {
    const hasSteps = Boolean(run?.step_results.length);
    const hasSource = Boolean(run?.missionnet_event_ids.length);
    const hasNormalized = Boolean(run?.sentinel_event_ids.length);
    const hasDetection = Boolean(run?.detection_ids.length);
    const hasIncident = Boolean(run?.incident_ids.length);
    const hasVerification = Boolean(run && Object.values(run.verification).some(Boolean));
    return [
      { label: "MissionNet", detail: "Controlled input", complete: hasSteps || status === "PASSED" },
      { label: "Evidence", detail: "Audit + telemetry", complete: hasSource || status === "PASSED" },
      { label: "Normalize", detail: "Sentinel ingest", complete: hasNormalized || status === "PASSED" },
      { label: "Detect", detail: "Deterministic rules", complete: hasDetection || status === "PASSED" },
      { label: "Correlate", detail: "Incident graph", complete: hasIncident || status === "PASSED" },
      { label: "Verify", detail: "Evidence integrity", complete: hasVerification || status === "PASSED" },
      { label: "Analyst", detail: "AI advisory + approval", complete: status === "PASSED" },
    ];
  }, [run, status]);

  const trendValues = [
    run?.missionnet_event_ids.length ?? 0,
    run?.sentinel_event_ids.length ?? 0,
    run?.detection_ids.length ?? 0,
    run?.incident_ids.length ?? 0,
    verificationPassed,
  ];

  const currentStageIndex = Math.max(
    0,
    pipeline.findIndex((item) => !item.complete),
  );

  return (
    <div className="min-h-screen bg-[#071019] text-slate-100">
      <div className="grid min-h-screen lg:grid-cols-[228px_minmax(0,1fr)]">
        <aside className="hidden border-r border-slate-800 bg-[#08131e] lg:flex lg:flex-col">
          <div className="border-b border-slate-800 px-5 py-5">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-400">Sentinel</p>
            <h1 className="mt-1 text-base font-semibold text-white">Enterprise Security</h1>
            <p className="mt-1 text-[11px] text-slate-500">Security Operations Console</p>
          </div>
          <nav className="flex-1 px-3 py-4 text-sm">
            {[
              ["Security Posture", true],
              ["Scenario Control", false],
              ["Findings", false],
              ["Incidents", false],
              ["Detections", false],
              ["Evidence", false],
              ["AI Advisory", false],
              ["System Health", false],
            ].map(([label, active]) => (
              <div
                key={String(label)}
                className={`mb-1 rounded px-3 py-2.5 ${
                  active ? "bg-sky-500/10 font-medium text-sky-300" : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                }`}
              >
                {label}
              </div>
            ))}
          </nav>
          <div className="border-t border-slate-800 p-4 text-[11px] leading-5 text-slate-500">
            Deterministic security decisions<br />AI advisory is non-authoritative
          </div>
        </aside>

        <main className="min-w-0">
          <header className="border-b border-slate-800 bg-[#0a1622] px-5 py-4 lg:px-7">
            <div className="flex flex-col justify-between gap-4 xl:flex-row xl:items-center">
              <div>
                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <span>Security Operations</span><span>/</span><span>Security Posture</span><span>/</span><span className="text-slate-300">{scenario.id}</span>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <h2 className="text-xl font-semibold text-white">{scenario.name}</h2>
                  <span className={`rounded border px-2.5 py-1 text-[11px] font-semibold ${statusClass(status)}`}>{status}</span>
                </div>
                <p className="mt-1 max-w-4xl text-xs leading-5 text-slate-400">{scenario.description}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={scenarioId}
                  onChange={(event) => {
                    const next = event.target.value;
                    setScenarioId(next);
                    window.history.replaceState(null, "", `#${next}`);
                    setRun(null);
                    setRunId(null);
                  }}
                  disabled={runActive}
                  className="rounded border border-slate-700 bg-[#0d1b29] px-3 py-2 text-xs text-slate-200 outline-none focus:border-sky-500 disabled:opacity-50"
                >
                  {SCENARIOS.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.name}</option>)}
                </select>
                <button
                  onClick={startRun}
                  disabled={starting || runActive}
                  className="rounded bg-sky-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-sky-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
                >
                  {starting ? "Starting…" : runActive ? "Run in progress" : "Start controlled run"}
                </button>
              </div>
            </div>
          </header>

          <div className="space-y-5 p-5 lg:p-7">
            {run?.status === "PREPARING" && (
              <section className="rounded border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-xs text-amber-200">
                <span className="font-semibold">Dependency readiness:</span> MissionNet and Sentinel are being validated before execution. Cloud cold starts can take up to roughly 75 seconds; the scenario will not advance until the dependencies are healthy.
              </section>
            )}

            {error && (
              <section className="rounded border border-red-500/30 bg-red-500/5 px-4 py-3 text-xs text-red-200">
                <span className="font-semibold">Console request error:</span> {error}
              </section>
            )}

            {failure && (
              <section className="grid gap-4 rounded border border-red-500/30 bg-[#12151c] p-4 md:grid-cols-[1.1fr_1fr_1fr]">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-red-400">Execution exception</p>
                  <h3 className="mt-1 text-sm font-semibold text-white">{failure.title}</h3>
                  <p className="mt-1 font-mono text-[11px] text-red-300">{failureCode(run?.failure_reason ?? null)}</p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Operational impact</p>
                  <p className="mt-1 text-xs leading-5 text-slate-300">{failure.impact}</p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Recommended action</p>
                  <p className="mt-1 text-xs leading-5 text-slate-300">{failure.action}</p>
                </div>
              </section>
            )}

            <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              {[
                ["Source Events", run?.missionnet_event_ids.length ?? 0, "MissionNet evidence"],
                ["Normalized Events", run?.sentinel_event_ids.length ?? 0, "Sentinel pipeline"],
                ["Detections", run?.detection_ids.length ?? 0, scenario.id === "SCN-010" ? "Expected 5" : "Deterministic"],
                ["Incidents", run?.incident_ids.length ?? 0, scenario.id === "SCN-010" ? "Expected 3" : "Correlated cases"],
                ["Verification", verificationTotal ? `${verificationPassed}/${verificationTotal}` : "0/6", "Evidence controls"],
              ].map(([label, value, sub]) => (
                <div key={String(label)} className="rounded border border-slate-800 bg-[#0b1723] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">{label}</p>
                      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
                    </div>
                    <div className="h-8 w-14"><MiniBars values={trendValues} /></div>
                  </div>
                  <p className="mt-2 text-[11px] text-slate-500">{sub}</p>
                </div>
              ))}
            </section>

            <section className="rounded border border-slate-800 bg-[#0b1723]">
              <div className="flex flex-col justify-between gap-3 border-b border-slate-800 px-5 py-4 sm:flex-row sm:items-center">
                <div>
                  <h3 className="text-sm font-semibold text-white">Security signal pipeline</h3>
                  <p className="mt-1 text-[11px] text-slate-500">Live workflow state derived from persisted run evidence — not a scripted animation.</p>
                </div>
                <p className="font-mono text-[11px] text-slate-500">{runId ?? "No active run"}</p>
              </div>
              <div className="overflow-x-auto p-5">
                <div className="flex min-w-[980px] items-center">
                  {pipeline.map((item, index) => {
                    const active = runActive && index === currentStageIndex;
                    return (
                      <div key={item.label} className="contents">
                        <div className={`w-[118px] rounded border p-3 ${item.complete ? "border-emerald-500/35 bg-emerald-500/5" : active ? "border-sky-400/50 bg-sky-500/10" : "border-slate-700 bg-[#0d1b29]"}`}>
                          <div className="flex items-center gap-2">
                            <span className={`h-2 w-2 rounded-full ${item.complete ? "bg-emerald-400" : active ? "bg-sky-400" : "bg-slate-600"}`} />
                            <p className="text-xs font-semibold text-slate-100">{item.label}</p>
                          </div>
                          <p className="mt-2 text-[10px] leading-4 text-slate-500">{item.detail}</p>
                        </div>
                        {index < pipeline.length - 1 && (
                          <div className={`mx-2 h-px w-8 ${item.complete ? "bg-emerald-500/50" : "bg-slate-700"}`} />
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </section>

            <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.45fr)_minmax(360px,0.75fr)]">
              <section className="rounded border border-slate-800 bg-[#0b1723]">
                <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
                  <div>
                    <h3 className="text-sm font-semibold text-white">Detection & investigation overview</h3>
                    <p className="mt-1 text-[11px] text-slate-500">Expected analytic coverage and live observed security objects.</p>
                  </div>
                  <span className="text-[11px] text-slate-500">{scenario.expected}</span>
                </div>
                <div className="grid gap-5 p-5 xl:grid-cols-2">
                  <div>
                    <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">Expected analytics</p>
                    <div className="overflow-hidden rounded border border-slate-800">
                      {scenario.id === "SCN-010" ? DETECTION_LABELS.map(([id, label], index) => (
                        <div key={id} className="grid grid-cols-[82px_minmax(0,1fr)_70px] items-center gap-3 border-b border-slate-800 px-3 py-2.5 last:border-0">
                          <span className="font-mono text-[11px] text-sky-300">{id}</span>
                          <span className="text-xs text-slate-300">{label}</span>
                          <span className={`text-right text-[10px] font-semibold ${index < (run?.detection_ids.length ?? 0) ? "text-emerald-300" : "text-slate-600"}`}>{index < (run?.detection_ids.length ?? 0) ? "OBSERVED" : "PENDING"}</span>
                        </div>
                      )) : (
                        <div className="px-3 py-4 text-xs text-slate-400">Expected detection coverage: <span className="font-mono text-sky-300">{scenario.expected}</span></div>
                      )}
                    </div>
                  </div>
                  <div>
                    <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">Observed objects</p>
                    <div className="space-y-2">
                      {(run?.detection_ids ?? []).slice(0, 5).map((id) => (
                        <div key={id} className="flex items-center justify-between gap-4 rounded border border-slate-800 bg-[#0d1b29] px-3 py-2.5">
                          <div><p className="font-mono text-[11px] text-slate-200">{id}</p><p className="mt-1 text-[10px] text-slate-500">Deterministic detection object</p></div>
                          <span className="text-[10px] font-semibold text-emerald-300">CONFIRMED</span>
                        </div>
                      ))}
                      {!run?.detection_ids.length && <div className="rounded border border-dashed border-slate-700 px-3 py-6 text-center text-xs text-slate-500">No detections observed yet.</div>}
                    </div>
                  </div>
                </div>
              </section>

              <section className="rounded border border-slate-800 bg-[#0b1723]">
                <div className="border-b border-slate-800 px-5 py-4">
                  <h3 className="text-sm font-semibold text-white">Investigation queue</h3>
                  <p className="mt-1 text-[11px] text-slate-500">Evidence-backed Sentinel incidents created by the deterministic pipeline.</p>
                </div>
                <div className="p-4">
                  {(run?.incident_ids ?? []).map((id, index) => (
                    <a
                      key={id}
                      href={`${SENTINEL_DASHBOARD}/incidents/${id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="mb-2 block rounded border border-slate-800 bg-[#0d1b29] p-3 hover:border-sky-500/40"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-mono text-[11px] text-sky-300">{id}</span>
                        <span className="rounded border border-amber-500/30 bg-amber-500/5 px-2 py-0.5 text-[9px] font-semibold text-amber-300">INVESTIGATION</span>
                      </div>
                      <p className="mt-2 text-xs text-slate-300">Incident {index + 1} from {scenario.id}</p>
                      <p className="mt-1 text-[10px] text-slate-500">Open evidence, AI advisory, and human-controlled response workflow ↗</p>
                    </a>
                  ))}
                  {!run?.incident_ids.length && <div className="rounded border border-dashed border-slate-700 px-3 py-8 text-center text-xs text-slate-500">No incidents created yet.</div>}
                </div>
              </section>
            </div>

            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
              <section className="rounded border border-slate-800 bg-[#0b1723]">
                <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
                  <div>
                    <h3 className="text-sm font-semibold text-white">Operational event stream</h3>
                    <p className="mt-1 text-[11px] text-slate-500">Structured events from Demo Control and upstream components.</p>
                  </div>
                  <span className="text-[10px] uppercase tracking-wider text-slate-600">live log</span>
                </div>
                <div className="max-h-[430px] overflow-auto">
                  <table className="w-full min-w-[820px] border-collapse text-left">
                    <thead className="sticky top-0 bg-[#0d1b29] text-[10px] uppercase tracking-wider text-slate-500">
                      <tr><th className="px-4 py-3">Time</th><th className="px-4 py-3">Level</th><th className="px-4 py-3">Component</th><th className="px-4 py-3">Code</th><th className="px-4 py-3">Event</th></tr>
                    </thead>
                    <tbody className="text-[11px]">
                      {(run?.timeline ?? []).map((entry, index) => (
                        <tr key={`${entry.timestamp}-${index}`} className="border-t border-slate-800/80">
                          <td className="whitespace-nowrap px-4 py-3 font-mono text-slate-500">{new Date(entry.timestamp).toLocaleTimeString()}</td>
                          <td className={`px-4 py-3 font-semibold ${entry.level === "ERROR" ? "text-red-300" : entry.level === "WARN" ? "text-amber-300" : "text-slate-400"}`}>{entry.level ?? "INFO"}</td>
                          <td className="px-4 py-3 text-slate-400">{entry.component ?? "Demo Control"}</td>
                          <td className="px-4 py-3 font-mono text-slate-500">{entry.code ?? "—"}</td>
                          <td className="px-4 py-3 leading-5 text-slate-300">{entry.message}</td>
                        </tr>
                      ))}
                      {!run?.timeline.length && <tr><td colSpan={5} className="px-4 py-10 text-center text-xs text-slate-600">Start a controlled run to populate the event stream.</td></tr>}
                    </tbody>
                  </table>
                </div>
              </section>

              <aside className="space-y-5">
                <section className="rounded border border-slate-800 bg-[#0b1723] p-4">
                  <h3 className="text-sm font-semibold text-white">Verification controls</h3>
                  <div className="mt-4 space-y-2.5">
                    {[
                      ["Source evidence", run?.verification.missionnet_event_observed],
                      ["Normalized event", run?.verification.normalized_event_observed],
                      ["Expected detection", run?.verification.expected_detection_observed],
                      ["Incident created", run?.verification.incident_created],
                      ["Evidence linkage", run?.verification.evidence_link_verified],
                      ["Replay idempotency", run?.verification.no_duplicate_on_replay],
                    ].map(([label, value]) => (
                      <div key={String(label)} className="flex items-center justify-between gap-4 border-b border-slate-800 pb-2.5 last:border-0 last:pb-0">
                        <span className="text-[11px] text-slate-400">{label}</span>
                        <span className={`text-[10px] font-semibold ${value ? "text-emerald-300" : "text-slate-600"}`}>{value ? "PASS" : "PENDING"}</span>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="rounded border border-slate-800 bg-[#0b1723] p-4">
                  <h3 className="text-sm font-semibold text-white">Control boundaries</h3>
                  <div className="mt-3 space-y-2 text-[11px] leading-5 text-slate-400">
                    <p>• Detection decisions are deterministic.</p>
                    <p>• AI cannot create detections or incidents.</p>
                    <p>• AI advisory is evidence-grounded and non-authoritative.</p>
                    <p>• Response actions require explicit human approval.</p>
                    <p>• No hack-back or autonomous offensive action.</p>
                  </div>
                </section>

                {run && TERMINAL.has(run.status) && (
                  <button
                    onClick={resetLab}
                    disabled={resetting}
                    className="w-full rounded border border-slate-700 bg-[#0d1b29] px-4 py-2.5 text-xs font-semibold text-slate-300 hover:border-sky-500/40 hover:text-white disabled:opacity-50"
                  >
                    {resetting ? "Resetting synthetic lab…" : "Reset synthetic lab"}
                  </button>
                )}
              </aside>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
