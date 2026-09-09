"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const DEMO_API =
  process.env.NEXT_PUBLIC_DEMOCONTROL_API_BASE_URL ?? "http://127.0.0.1:8100";
const SENTINEL_DASHBOARD =
  process.env.NEXT_PUBLIC_SENTINEL_DASHBOARD_URL ?? "https://sentinel-defense-g6id.vercel.app";

const POLL_MS = 1200;
const REPLAY_MS = 2400;
const TERMINAL = new Set(["PASSED", "FAILED", "CANCELLED"]);
const FAILURE_REASON_DISPLAY_LIMIT = 300;

type TimelineEntry = { timestamp: string; message: string };
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

type Stage = {
  kicker: string;
  title: string;
  description: string;
};

type TargetNode = {
  label: string;
  sublabel: string;
  activateAt: number;
  activeState?: "danger" | "active";
};

type ScenarioVisual = {
  id: string;
  name: string;
  shortName: string;
  summary: string;
  sourceLabel: string;
  sourceSublabel: string;
  sourceDanger?: boolean;
  targets: TargetNode[];
  stages: Stage[];
  employerStory: string;
  expectedDetection: string;
  runtimeNote?: string;
  primaryIncidentIndex?: number;
};

const SCENARIOS: ScenarioVisual[] = [
  {
    id: "SCN-001",
    name: "Repeated Authentication Failures",
    shortName: "Credential Pressure",
    summary:
      "A synthetic login burst exercises MissionNet authentication telemetry and Sentinel's deterministic repeated-failure detection path.",
    sourceLabel: "Synthetic Adversary",
    sourceSublabel: "Credential pressure",
    sourceDanger: true,
    targets: [
      { label: "j.rivera", sublabel: "MissionNet identity", activateAt: 1 },
      { label: "DET-001", sublabel: "Repeated auth rule", activateAt: 3, activeState: "active" },
    ],
    stages: [
      { kicker: "00 · BASELINE", title: "Identity telemetry is nominal", description: "MissionNet is healthy and Sentinel is waiting for authenticated audit evidence." },
      { kicker: "01 · AUTH PRESSURE", title: "Repeated login failures begin", description: "The synthetic adversary submits a bounded burst of invalid credentials against j.rivera." },
      { kicker: "02 · AUDIT EVIDENCE", title: "MissionNet records the failures", description: "Real auth.failure audit rows enter the normal Sentinel ingestion path; Demo Control never writes detections directly." },
      { kicker: "03 · DETERMINISTIC DETECTION", title: "DET-001 crosses its threshold", description: "Sentinel's rules evaluate the normalized failures and create the expected detection without LLM involvement." },
      { kicker: "04 · INCIDENT", title: "The signal becomes an incident", description: "Deterministic correlation creates an evidence-backed incident for analyst review." },
      { kicker: "05 · PROVENANCE CHECK", title: "The evidence chain is verified", description: "Demo Control verifies source event, normalization, detection, incident creation, and evidence linkage." },
      { kicker: "06 · ANALYST HANDOFF", title: "AI-assisted review is ready", description: "Open the resulting incident for evidence-grounded AI analysis and human-controlled response." },
    ],
    employerStory: "A realistic credential-abuse signal travels from application telemetry to deterministic detection and incident creation.",
    expectedDetection: "DET-001",
  },
  {
    id: "SCN-002",
    name: "Service Credential Anomaly",
    shortName: "Service Identity Compromise",
    summary:
      "A revoked service token followed by mission-record access tests Sentinel's cross-event identity-compromise correlation logic.",
    sourceLabel: "Synthetic Adversary",
    sourceSublabel: "Service credential misuse",
    sourceDanger: true,
    targets: [
      { label: "svc-mission-data-01", sublabel: "Service identity", activateAt: 1 },
      { label: "rec-000", sublabel: "Mission record", activateAt: 2 },
    ],
    stages: [
      { kicker: "00 · BASELINE", title: "Service identity is trusted", description: "MissionNet begins nominal with its service-account evidence path available to Sentinel." },
      { kicker: "01 · TOKEN REVOKED", title: "The service credential is revoked", description: "MissionNet records a real token.revoke event with scenario provenance." },
      { kicker: "02 · POST-REVOKE ACCESS", title: "The same identity accesses mission data", description: "A real record.access event follows the revocation, creating the two-signal sequence the rule expects." },
      { kicker: "03 · DETERMINISTIC CORRELATION", title: "DET-006 links the identity signals", description: "Sentinel correlates token revocation and record access for the same identity within the bounded window." },
      { kicker: "04 · INCIDENT", title: "Identity compromise indicator created", description: "The correlated evidence is promoted into a Sentinel incident for analyst review." },
      { kicker: "05 · PROVENANCE CHECK", title: "Both source events are verified", description: "The run verifies MissionNet evidence, normalized events, detection, incident, and evidence links." },
      { kicker: "06 · ANALYST HANDOFF", title: "AI-assisted triage is ready", description: "Continue to the incident for advisory AI analysis and a human-authorized response decision." },
    ],
    employerStory: "Cross-event correlation shows Sentinel can reason deterministically across a credential lifecycle instead of alerting on isolated events.",
    expectedDetection: "DET-006",
  },
  {
    id: "SCN-003",
    name: "Mission-Critical Asset Degradation",
    shortName: "Critical Service Degradation",
    summary:
      "A bounded MissionNet state change exercises critical-asset monitoring, deterministic detection, incident creation, and evidence verification.",
    sourceLabel: "Synthetic Fault",
    sourceSublabel: "Lab-controlled state change",
    sourceDanger: true,
    targets: [
      { label: "mission-data-api-01", sublabel: "Criticality 5 service", activateAt: 1 },
      { label: "DET-002", sublabel: "Critical asset rule", activateAt: 3, activeState: "active" },
    ],
    stages: [
      { kicker: "00 · BASELINE", title: "Mission service is nominal", description: "mission-data-api-01 begins healthy while Sentinel monitors MissionNet state events." },
      { kicker: "01 · SERVICE DEGRADATION", title: "The critical service degrades", description: "Demo Control uses the approved MissionNet lab API to move the service into a degraded state." },
      { kicker: "02 · STATE EVIDENCE", title: "MissionNet emits asset.degrade", description: "The real state transition becomes auditable evidence and enters Sentinel's normal ingestion pipeline." },
      { kicker: "03 · DETERMINISTIC DETECTION", title: "DET-002 identifies critical impact", description: "Sentinel evaluates the asset criticality and degradation evidence without asking the LLM to decide whether a detection exists." },
      { kicker: "04 · INCIDENT", title: "A critical-asset incident is created", description: "The deterministic signal becomes an evidence-backed incident tied to mission-data-api-01." },
      { kicker: "05 · PROVENANCE CHECK", title: "The end-to-end chain is verified", description: "Demo Control verifies the MissionNet event, normalized record, detection, incident, and evidence link." },
      { kicker: "06 · ANALYST HANDOFF", title: "Recovery decision is ready", description: "Continue into Sentinel for AI-assisted analysis and human-controlled containment or recovery." },
    ],
    employerStory: "The demo connects application state, asset criticality, deterministic detection, and analyst response in one visible chain.",
    expectedDetection: "DET-002",
  },
  {
    id: "SCN-004",
    name: "Sensitive Record Access Anomaly",
    shortName: "Data Access Burst",
    summary:
      "A bounded burst of mission-record reads by one identity exercises threshold detection and evidence-backed incident creation.",
    sourceLabel: "Synthetic Insider Pattern",
    sourceSublabel: "Abnormal data access",
    sourceDanger: true,
    targets: [
      { label: "u-analyst-01", sublabel: "Mission identity", activateAt: 1 },
      { label: "5 mission records", sublabel: "Sensitive access burst", activateAt: 2 },
    ],
    stages: [
      { kicker: "00 · BASELINE", title: "Record access is nominal", description: "MissionNet data access begins below Sentinel's bounded threshold." },
      { kicker: "01 · ACCESS BURST", title: "One identity reads multiple records", description: "u-analyst-01 accesses five seeded mission records through MissionNet's real record endpoint." },
      { kicker: "02 · THRESHOLD WINDOW", title: "The access pattern accumulates", description: "record.access evidence is normalized while the same-identity count grows inside the rule window." },
      { kicker: "03 · DETERMINISTIC DETECTION", title: "DET-003 reaches its threshold", description: "Sentinel creates the sensitive-record-access detection from the observed event count." },
      { kicker: "04 · INCIDENT", title: "The access anomaly becomes an incident", description: "The detection is represented as an evidence-backed analyst case rather than an isolated counter." },
      { kicker: "05 · PROVENANCE CHECK", title: "Five source accesses are traceable", description: "Demo Control verifies the source evidence, normalization, detection, incident, and evidence linkage." },
      { kicker: "06 · ANALYST HANDOFF", title: "Investigation is ready", description: "Open the incident to assess intent with the AI Analyst while retaining a human decision boundary." },
    ],
    employerStory: "A threshold-based insider-risk style pattern demonstrates deterministic behavioral detection over real synthetic application events.",
    expectedDetection: "DET-003",
  },
  {
    id: "SCN-010",
    name: "Multi-Signal Compromise Demonstration",
    shortName: "Multi-Signal Compromise",
    summary:
      "The flagship replay combines credential pressure, service-identity misuse, critical-service degradation, telemetry anomalies, correlation, and analyst handoff.",
    sourceLabel: "Synthetic Adversary",
    sourceSublabel: "Multi-stage pressure",
    sourceDanger: true,
    targets: [
      { label: "u-operator-01", sublabel: "Mission identity", activateAt: 1 },
      { label: "mission-data-api-01", sublabel: "Criticality 5 service", activateAt: 2 },
    ],
    stages: [
      { kicker: "00 · BASELINE", title: "MissionNet operating normally", description: "Synthetic mission services are nominal. Sentinel is watching the evidence stream." },
      { kicker: "01 · IDENTITY PRESSURE", title: "Rapid authentication failures begin", description: "The synthetic adversary repeatedly pressures u-operator-01. MissionNet emits real lab audit events." },
      { kicker: "02 · MISSION SIGNAL ANOMALY", title: "A critical service degrades", description: "mission-data-api-01 enters a degraded state while anomalous telemetry appears in the same scenario window." },
      { kicker: "03 · DETERMINISTIC DETECTION", title: "Sentinel rules fire from observed evidence", description: "The detection plane evaluates normalized events. The AI does not create these detections." },
      { kicker: "04 · CORRELATION", title: "Multiple signals become incidents", description: "Five expected detections are deterministically correlated into three evidence-backed incident records." },
      { kicker: "05 · PROVENANCE CHECK", title: "The evidence chain is verified", description: "Demo Control verifies MissionNet events, Sentinel normalization, detections, incidents, and evidence links." },
      { kicker: "06 · HUMAN DECISION BOUNDARY", title: "AI assistance and bounded response are ready", description: "Open the resulting incident to run the configured AI Analyst, review its recommendation, and approve a bounded response." },
    ],
    employerStory: "Credential, identity, service-state, and telemetry signals converge through Sentinel's full deterministic pipeline before AI enters the workflow.",
    expectedDetection: "DET-001 · DET-006 · DET-002 · DET-004 · DET-005",
    primaryIncidentIndex: 1,
  },
  {
    id: "SCN-NET-001",
    name: "Network Sensor Detection",
    shortName: "Suricata + Zeek Sensor Lab",
    summary:
      "Safe synthetic HTTP/DNS traffic is captured to PCAP and analyzed by real Suricata and Zeek sensors before entering Sentinel's standard pipeline.",
    sourceLabel: "Synthetic Traffic Generator",
    sourceSublabel: "Isolated lab network",
    sourceDanger: false,
    targets: [
      { label: "Suricata", sublabel: "Network IDS", activateAt: 2, activeState: "active" },
      { label: "Zeek", sublabel: "Network telemetry", activateAt: 2, activeState: "active" },
    ],
    stages: [
      { kicker: "00 · SENSOR BASELINE", title: "The isolated network lab is ready", description: "No MissionNet state is modified; this scenario exercises the independent network-sensor path." },
      { kicker: "01 · SYNTHETIC TRAFFIC", title: "Bounded HTTP/DNS traffic is generated", description: "Ephemeral lab containers exchange safe synthetic traffic on an isolated bridge network." },
      { kicker: "02 · SENSOR ANALYSIS", title: "PCAP is analyzed by Suricata and Zeek", description: "Real batch-mode sensor output provides alert, DNS, connection, and HTTP evidence." },
      { kicker: "03 · DETERMINISTIC DETECTION", title: "Network detections enter Sentinel", description: "Sensor adapters normalize evidence and deterministic NET rules create the expected detections." },
      { kicker: "04 · CORRELATION", title: "Sensor signals become one incident", description: "NET-001, NET-002, and NET-003 correlate through the same Sentinel incident pipeline used by MissionNet scenarios." },
      { kicker: "05 · PROVENANCE CHECK", title: "Sensor evidence is verified", description: "Demo Control verifies normalized sensor events, detections, incident creation, and evidence linkage." },
      { kicker: "06 · ANALYST HANDOFF", title: "Network investigation is ready", description: "Open the resulting incident for AI-assisted evidence review while keeping response human-controlled." },
    ],
    employerStory: "Real Suricata and Zeek outputs demonstrate that Sentinel can ingest network-sensor evidence, not just MissionNet application telemetry.",
    expectedDetection: "NET-001 · NET-002 · NET-003",
    runtimeNote: "This scenario requires the Docker/Suricata/Zeek sensor-lab runtime on the Demo Control host.",
  },
];

const SCENARIO_MAP = Object.fromEntries(SCENARIOS.map((scenario) => [scenario.id, scenario])) as Record<
  string,
  ScenarioVisual
>;

function shortFailureReason(reason: string | null): string | null {
  if (!reason) return null;
  return reason.length > FAILURE_REASON_DISPLAY_LIMIT
    ? reason.slice(0, FAILURE_REASON_DISPLAY_LIMIT) + "…"
    : reason;
}

function isTransientGatewayFailure(reason: string | null): boolean {
  if (!reason) return false;
  return /\b(502|503|504)\b/.test(reason) || /transient gateway error/i.test(reason);
}

function Node({
  label,
  sublabel,
  state,
}: {
  label: string;
  sublabel: string;
  state: "idle" | "danger" | "active" | "verified";
}) {
  const styles = {
    idle: "border-zinc-800 bg-zinc-950 text-zinc-500",
    danger: "border-red-500/70 bg-red-950/30 text-red-300 shadow-[0_0_30px_rgba(239,68,68,0.15)]",
    active: "border-cyan-500/70 bg-cyan-950/20 text-cyan-200 shadow-[0_0_30px_rgba(34,211,238,0.14)]",
    verified:
      "border-emerald-500/70 bg-emerald-950/20 text-emerald-200 shadow-[0_0_30px_rgba(16,185,129,0.14)]",
  }[state];

  return (
    <div className={`relative min-w-0 rounded-xl border p-4 transition-all duration-700 ${styles}`}>
      <div className="mb-3 flex items-center gap-2">
        <span
          className={`h-2 w-2 rounded-full ${
            state === "danger"
              ? "animate-pulse bg-red-400"
              : state === "active"
                ? "animate-pulse bg-cyan-400"
                : state === "verified"
                  ? "bg-emerald-400"
                  : "bg-zinc-700"
          }`}
        />
        <span className="text-[10px] font-semibold uppercase tracking-[0.24em] opacity-70">{sublabel}</span>
      </div>
      <p className="truncate text-sm font-semibold text-white">{label}</p>
    </div>
  );
}

function LinkBar({ active, danger = false }: { active: boolean; danger?: boolean }) {
  return (
    <div className="relative flex h-8 items-center overflow-hidden">
      <div
        className={`h-px w-full transition-all duration-700 ${
          active ? (danger ? "bg-red-500/70" : "bg-cyan-400/70") : "bg-zinc-800"
        }`}
      />
      {active && (
        <span
          className={`attack-packet absolute h-1.5 w-1.5 rounded-full ${danger ? "bg-red-300" : "bg-cyan-200"}`}
        />
      )}
    </div>
  );
}

export function LiveAttackReplay() {
  const [scenarioId, setScenarioId] = useState("SCN-010");
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visualStage, setVisualStage] = useState(0);
  const [paused, setPaused] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const scenario = SCENARIO_MAP[scenarioId] ?? SCENARIO_MAP["SCN-010"];
  const stages = scenario.stages;

  useEffect(() => {
    const fromHash = window.location.hash.replace(/^#/, "").toUpperCase();
    if (SCENARIO_MAP[fromHash]) setScenarioId(fromHash);
  }, []);

  const actualGate = useMemo(() => {
    if (!run) return runId ? 1 : 0;
    let gate = 0;
    if (run.step_results.length > 0 || run.timeline.length > 1) gate = 1;
    if (
      run.step_results.length >= 2 ||
      run.missionnet_event_ids.length >= 2 ||
      run.sentinel_event_ids.length >= 2
    )
      gate = 2;
    if (run.detection_ids.length > 0) gate = 3;
    if (run.incident_ids.length > 0) gate = 4;
    if (Object.values(run.verification).some(Boolean)) gate = 5;
    if (run.status === "PASSED") gate = 6;
    return gate;
  }, [run, runId]);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;

    async function poll() {
      try {
        const res = await fetch(`${DEMO_API}/api/v1/runs/${runId}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`run fetch failed: ${res.status}`);
        const data: RunDetail = await res.json();
        if (cancelled) return;
        setRun(data);
        setError(null);
        if (TERMINAL.has(data.status) && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "run poll failed");
      }
    }

    poll();
    pollRef.current = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [runId]);

  useEffect(() => {
    if (!runId || paused) return;
    const timer = setInterval(() => {
      setVisualStage((current) => (current < actualGate ? current + 1 : current));
    }, REPLAY_MS);
    return () => clearInterval(timer);
  }, [runId, paused, actualGate]);

  function chooseScenario(nextScenarioId: string) {
    if (runId && !run?.status) return;
    setScenarioId(nextScenarioId);
    window.history.replaceState(null, "", `#${nextScenarioId}`);
    setRunId(null);
    setRun(null);
    setVisualStage(0);
    setPaused(false);
    setError(null);
  }

  async function startReplay() {
    setStarting(true);
    setError(null);
    setRun(null);
    setRunId(null);
    setVisualStage(0);
    setPaused(false);
    try {
      const res = await fetch(`${DEMO_API}/api/v1/scenarios/${scenario.id}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor: "portfolio-demo" }),
      });
      if (!res.ok) throw new Error(`scenario start failed: ${res.status}`);
      const started = await res.json();
      setRunId(started.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : `failed to start ${scenario.id}`);
    } finally {
      setStarting(false);
    }
  }

  async function resetLab() {
    if (!runId) return;
    await fetch(`${DEMO_API}/api/v1/runs/${runId}/reset`, { method: "POST" });
  }

  const stage = stages[visualStage];
  const preferredIncidentIndex = scenario.primaryIncidentIndex ?? 0;
  const primaryIncident =
    run?.incident_ids[preferredIncidentIndex] ?? run?.incident_ids[0] ?? null;
  const runFinished = run ? TERMINAL.has(run.status) : false;

  return (
    <div className="min-h-screen bg-[#020406] font-mono text-zinc-100">
      <style>{`
        @keyframes packetMove { 0% { left: 0%; opacity: 0; } 12% { opacity: 1; } 88% { opacity: 1; } 100% { left: calc(100% - 6px); opacity: 0; } }
        .attack-packet { animation: packetMove 1.35s linear infinite; }
        @keyframes scan { 0% { transform: translateY(-10%); opacity: 0; } 20% { opacity: .7; } 80% { opacity: .7; } 100% { transform: translateY(410px); opacity: 0; } }
        .scanline { animation: scan 4s linear infinite; }
      `}</style>

      <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-5 py-8 lg:px-8">
        <header className="flex flex-col justify-between gap-4 border-b border-zinc-900 pb-5 lg:flex-row lg:items-end">
          <div>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className="rounded border border-red-900 bg-red-950/40 px-2 py-1 text-[10px] font-semibold tracking-[0.2em] text-red-300">
                SYNTHETIC ADVERSARY SIMULATION
              </span>
              <span className="rounded border border-cyan-900 bg-cyan-950/30 px-2 py-1 text-[10px] font-semibold tracking-[0.2em] text-cyan-300">
                REAL SENTINEL PIPELINE
              </span>
              {scenario.id === "SCN-010" && (
                <span className="rounded border border-amber-900 bg-amber-950/30 px-2 py-1 text-[10px] font-semibold tracking-[0.2em] text-amber-300">
                  FLAGSHIP
                </span>
              )}
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
              {scenario.id} · {scenario.name.toUpperCase()}
            </h1>
            <p className="mt-2 max-w-3xl text-xs leading-5 text-zinc-500">{scenario.summary}</p>
            {scenario.runtimeNote && (
              <p className="mt-2 max-w-3xl text-[10px] leading-4 text-amber-500/80">{scenario.runtimeNote}</p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {!runId ? (
              <button
                onClick={startReplay}
                disabled={starting}
                className="rounded-lg bg-cyan-400 px-5 py-2.5 text-xs font-bold uppercase tracking-wider text-black hover:bg-cyan-300 disabled:opacity-50"
              >
                {starting ? "Starting…" : "▶ Start Immersive Demo"}
              </button>
            ) : (
              <>
                <button
                  onClick={() => setPaused((value) => !value)}
                  className="rounded-lg border border-zinc-700 px-4 py-2 text-xs text-zinc-300 hover:border-cyan-700 hover:text-cyan-300"
                >
                  {paused ? "▶ Resume" : "Ⅱ Pause"}
                </button>
                <button
                  onClick={() => setVisualStage((value) => Math.min(actualGate, value + 1))}
                  disabled={visualStage >= actualGate}
                  className="rounded-lg border border-zinc-700 px-4 py-2 text-xs text-zinc-300 hover:border-cyan-700 hover:text-cyan-300 disabled:opacity-30"
                >
                  Next →
                </button>
              </>
            )}
          </div>
        </header>

        <section className="rounded-2xl border border-zinc-900 bg-zinc-950/30 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-500">Immersive scenario library</p>
              <p className="mt-1 text-[11px] text-zinc-700">Every cyber-range scenario now has a live GUI replay driven by its real run state.</p>
            </div>
            <span className="text-[10px] text-zinc-700">{SCENARIOS.length} scenarios</span>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {SCENARIOS.map((item) => {
              const selected = item.id === scenario.id;
              return (
                <button
                  key={item.id}
                  onClick={() => chooseScenario(item.id)}
                  disabled={Boolean(runId && !runFinished)}
                  className={`rounded-lg border p-3 text-left transition disabled:cursor-not-allowed disabled:opacity-35 ${
                    selected
                      ? "border-cyan-500/70 bg-cyan-950/20"
                      : "border-zinc-900 bg-black/30 hover:border-zinc-700"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className={selected ? "text-xs font-semibold text-cyan-300" : "text-xs font-semibold text-zinc-400"}>{item.id}</span>
                    {item.id === "SCN-010" && <span className="text-[9px] font-semibold uppercase tracking-widest text-amber-400">Flagship</span>}
                  </div>
                  <p className="mt-1 text-[11px] text-zinc-500">{item.shortName}</p>
                </button>
              );
            })}
          </div>
        </section>

        {error && (
          <div className="rounded-lg border border-red-900 bg-red-950/30 px-4 py-3 text-xs text-red-300">{error}</div>
        )}

        {run?.status === "FAILED" && (
          <div className="rounded-lg border border-amber-900 bg-amber-950/20 px-4 py-3 text-xs text-amber-200">
            <p className="font-semibold uppercase tracking-wide">
              {isTransientGatewayFailure(run.failure_reason) ? "Cloud service interruption" : "Scenario run failed"}
            </p>
            <p className="mt-1 text-amber-200/80">
              {isTransientGatewayFailure(run.failure_reason)
                ? "A temporary gateway failure stopped this real run. Sentinel has not fabricated or advanced the scenario."
                : "The scenario stopped before completing. Sentinel has not fabricated or advanced past this point."}
            </p>
            {shortFailureReason(run.failure_reason) && (
              <p className="mt-2 break-words font-mono text-[10px] text-amber-200/50">{shortFailureReason(run.failure_reason)}</p>
            )}
          </div>
        )}

        <section className="grid gap-4 lg:grid-cols-[1fr_310px]">
          <div className="relative overflow-hidden rounded-2xl border border-zinc-900 bg-zinc-950/40 p-5 sm:p-7">
            <div className="scanline pointer-events-none absolute left-0 top-0 h-px w-full bg-gradient-to-r from-transparent via-cyan-400/40 to-transparent" />
            <div className="mb-6 flex items-center justify-between gap-4">
              <div>
                <p className="text-[10px] font-semibold tracking-[0.26em] text-cyan-400">{stage.kicker}</p>
                <h2 className="mt-1 text-lg font-semibold text-white">{stage.title}</h2>
                <p className="mt-1 max-w-2xl text-xs leading-5 text-zinc-500">{stage.description}</p>
              </div>
              <div className="text-right">
                <p className="text-[10px] uppercase tracking-widest text-zinc-600">Replay</p>
                <p className="text-xl font-semibold text-white">
                  {String(visualStage + 1).padStart(2, "0")}/{String(stages.length).padStart(2, "0")}
                </p>
              </div>
            </div>

            <div className="mb-6 grid grid-cols-7 gap-1">
              {stages.map((item, index) => (
                <button
                  key={item.kicker}
                  onClick={() => index <= actualGate && setVisualStage(index)}
                  className={`h-1.5 rounded-full transition-all ${
                    index <= visualStage
                      ? index <= actualGate
                        ? "bg-cyan-400"
                        : "bg-zinc-800"
                      : "bg-zinc-900"
                  }`}
                  title={item.title}
                />
              ))}
            </div>

            <div className="grid items-center gap-3 md:grid-cols-[1fr_70px_1fr_70px_1fr]">
              <Node
                label={scenario.sourceLabel}
                sublabel={scenario.sourceSublabel}
                state={visualStage >= 1 ? (scenario.sourceDanger ? "danger" : "active") : "idle"}
              />
              <LinkBar active={visualStage >= 1} danger={Boolean(scenario.sourceDanger)} />
              <div className="flex flex-col gap-3">
                {scenario.targets.map((target) => (
                  <Node
                    key={`${scenario.id}-${target.label}`}
                    label={target.label}
                    sublabel={target.sublabel}
                    state={visualStage >= target.activateAt ? (target.activeState ?? "danger") : "idle"}
                  />
                ))}
              </div>
              <LinkBar active={visualStage >= 3} />
              <div className="flex flex-col gap-3">
                <Node label="Detection Engine" sublabel={scenario.expectedDetection} state={visualStage >= 3 ? "active" : "idle"} />
                <Node label="Incident Correlator" sublabel="Evidence graph" state={visualStage >= 4 ? "active" : "idle"} />
                <Node label="AI + Response Guardrail" sublabel="Human-approved only" state={visualStage >= 6 ? "verified" : "idle"} />
              </div>
            </div>

            <div className="mt-7 grid gap-3 sm:grid-cols-4">
              {[
                ["MissionNet events", run?.missionnet_event_ids.length ?? 0],
                ["Sentinel events", run?.sentinel_event_ids.length ?? 0],
                ["Detections", run?.detection_ids.length ?? 0],
                ["Incidents", run?.incident_ids.length ?? 0],
              ].map(([label, value]) => (
                <div key={String(label)} className="rounded-lg border border-zinc-900 bg-black/40 p-3">
                  <p className="text-[10px] uppercase tracking-widest text-zinc-600">{label}</p>
                  <p className="mt-1 text-2xl font-semibold text-white">{value}</p>
                </div>
              ))}
            </div>
          </div>

          <aside className="flex flex-col gap-4">
            <div className="rounded-2xl border border-zinc-900 bg-zinc-950/50 p-4">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-500">Run status</p>
                <span
                  className={`rounded-full px-2 py-1 text-[10px] font-bold ${
                    run?.status === "PASSED"
                      ? "bg-emerald-500 text-black"
                      : run?.status === "FAILED"
                        ? "bg-red-500 text-black"
                        : runId
                          ? "animate-pulse bg-amber-400 text-black"
                          : "bg-zinc-800 text-zinc-500"
                  }`}
                >
                  {run?.status ?? (runId ? "RUNNING" : "READY")}
                </span>
              </div>
              <p className="text-[11px] text-cyan-500">{scenario.id}</p>
              <p className="mt-1 break-all text-[11px] text-zinc-600">{runId ?? "No run started"}</p>
              {run?.current_step && <p className="mt-2 text-xs text-cyan-300">{run.current_step}</p>}
            </div>

            <div className="rounded-2xl border border-zinc-900 bg-zinc-950/50 p-4">
              <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-500">Evidence verification</p>
              <div className="space-y-2 text-xs">
                {[
                  ["Mission / sensor event", run?.verification.missionnet_event_observed],
                  ["Normalized", run?.verification.normalized_event_observed],
                  ["Detection", run?.verification.expected_detection_observed],
                  ["Incident", run?.verification.incident_created],
                  ["Evidence link", run?.verification.evidence_link_verified],
                ].map(([label, value]) => (
                  <div key={String(label)} className="flex items-center justify-between border-b border-zinc-900 pb-2 last:border-0 last:pb-0">
                    <span className="text-zinc-500">{label}</span>
                    <span className={value ? "text-emerald-400" : "text-zinc-700"}>{value ? "VERIFIED" : "WAITING"}</span>
                  </div>
                ))}
              </div>
            </div>

            {runFinished && primaryIncident && (
              <div className="rounded-2xl border border-emerald-900 bg-emerald-950/20 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-emerald-400">Analyst handoff</p>
                <p className="mt-2 text-xs leading-5 text-zinc-400">
                  This replay produced real Sentinel incident evidence. Continue into the SOC workflow for AI analysis and human-approved response.
                </p>
                <a
                  href={`${SENTINEL_DASHBOARD}/incidents/${primaryIncident}`}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-4 block rounded-lg bg-emerald-400 px-3 py-2 text-center text-[11px] font-bold uppercase tracking-wider text-black hover:bg-emerald-300"
                >
                  Continue to AI + Response ↗
                </a>
                <button
                  onClick={resetLab}
                  className="mt-2 w-full rounded-lg border border-zinc-800 px-3 py-2 text-[11px] text-zinc-500 hover:text-zinc-300"
                >
                  Reset synthetic lab
                </button>
              </div>
            )}
          </aside>
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-zinc-900 bg-black p-4">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-500">Live evidence stream</p>
              <span className="text-[10px] text-zinc-700">Demo Control telemetry</span>
            </div>
            <div className="max-h-64 space-y-2 overflow-auto text-[11px] leading-5">
              {(run?.timeline ?? []).slice(-12).map((entry, index) => (
                <div key={`${entry.timestamp}-${index}`} className="grid grid-cols-[82px_1fr] gap-3 border-b border-zinc-950 pb-2">
                  <span className="text-zinc-700">{new Date(entry.timestamp).toLocaleTimeString()}</span>
                  <span className="text-zinc-400">{entry.message}</span>
                </div>
              ))}
              {!run?.timeline.length && <p className="text-zinc-700">Awaiting scenario start…</p>}
            </div>
          </div>

          <div className="rounded-2xl border border-zinc-900 bg-zinc-950/40 p-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-500">What an employer is seeing</p>
            <div className="mt-4 grid gap-3 text-xs text-zinc-400 sm:grid-cols-2">
              <div className="rounded-lg border border-zinc-900 p-3">
                <p className="font-semibold text-white">Scenario story</p>
                <p className="mt-1 leading-5 text-zinc-600">{scenario.employerStory}</p>
              </div>
              <div className="rounded-lg border border-zinc-900 p-3">
                <p className="font-semibold text-white">Detection integrity</p>
                <p className="mt-1 leading-5 text-zinc-600">Detections and incidents come from deterministic Sentinel logic, not from the LLM.</p>
              </div>
              <div className="rounded-lg border border-zinc-900 p-3">
                <p className="font-semibold text-white">AI guardrail</p>
                <p className="mt-1 leading-5 text-zinc-600">AI is advisory and evidence-grounded. It cannot silently create detections or execute response actions.</p>
              </div>
              <div className="rounded-lg border border-zinc-900 p-3">
                <p className="font-semibold text-white">Response control</p>
                <p className="mt-1 leading-5 text-zinc-600">Containment actions remain policy-bounded and require explicit human approval.</p>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
