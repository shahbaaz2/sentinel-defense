"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const DEMO_API =
  process.env.NEXT_PUBLIC_DEMOCONTROL_API_BASE_URL ?? "http://127.0.0.1:8100";
const SENTINEL_DASHBOARD =
  process.env.NEXT_PUBLIC_SENTINEL_DASHBOARD_URL ?? "https://sentinel-defense-g6id.vercel.app";

const POLL_MS = 1200;
const TERMINAL = new Set(["PASSED", "FAILED", "CANCELLED"]);
const FAILURE_REASON_DISPLAY_LIMIT = 500;

type TimelineEntry = {
  timestamp: string;
  message: string;
  level?: "INFO" | "WARN" | "ERROR" | string;
  component?: string;
  code?: string;
};

type RunDetail = {
  run_id: string;
  scenario_id: string;
  scenario_version?: string;
  actor?: string;
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
  label: string;
  title: string;
  description: string;
};

type ScenarioVisual = {
  id: string;
  name: string;
  shortName: string;
  summary: string;
  sourceLabel: string;
  sourceSublabel: string;
  targets: { label: string; sublabel: string }[];
  stages: Stage[];
  expectedDetection: string;
  controls: string[];
  runtimeNote?: string;
  primaryIncidentIndex?: number;
};

type FailureDiagnostic = {
  code: string;
  title: string;
  category: string;
  impact: string;
  action: string;
};

const SCENARIOS: ScenarioVisual[] = [
  {
    id: "SCN-001",
    name: "Repeated Authentication Failures",
    shortName: "Credential Pressure",
    summary:
      "Controlled authentication failures validate MissionNet audit telemetry, deterministic threshold detection, incident creation, and evidence linkage.",
    sourceLabel: "MissionNet Identity API",
    sourceSublabel: "Synthetic failed authentication",
    targets: [
      { label: "j.rivera", sublabel: "Identity under test" },
      { label: "DET-001", sublabel: "Expected detection rule" },
    ],
    stages: [
      { label: "01", title: "Validate baseline", description: "Confirm MissionNet and Sentinel dependencies are healthy and reset the lab state." },
      { label: "02", title: "Execute controlled input", description: "Submit a bounded sequence of invalid authentication attempts through MissionNet." },
      { label: "03", title: "Observe source evidence", description: "Confirm MissionNet audit records exist for the controlled input." },
      { label: "04", title: "Evaluate detection", description: "Sentinel evaluates normalized events using deterministic detection logic." },
      { label: "05", title: "Create incident", description: "The resulting signal is correlated into an evidence-backed incident." },
      { label: "06", title: "Verify evidence chain", description: "Validate source events, normalized events, detections, incidents, and evidence links." },
      { label: "07", title: "Analyst handoff", description: "Continue to the incident workflow for advisory AI analysis and human-controlled response." },
    ],
    expectedDetection: "DET-001",
    controls: ["Deterministic detection", "Evidence verification", "Human-controlled response"],
  },
  {
    id: "SCN-002",
    name: "Service Credential Anomaly",
    shortName: "Service Identity Compromise",
    summary:
      "A controlled token revocation followed by record access validates deterministic cross-event service-identity correlation.",
    sourceLabel: "MissionNet Service Identity",
    sourceSublabel: "Revoked token + record access",
    targets: [
      { label: "svc-mission-data-01", sublabel: "Service identity" },
      { label: "rec-000", sublabel: "Controlled record access" },
    ],
    stages: [
      { label: "01", title: "Validate baseline", description: "Confirm service health and reset the synthetic environment." },
      { label: "02", title: "Revoke service token", description: "Record a controlled credential revocation in MissionNet." },
      { label: "03", title: "Access protected record", description: "Use the same service identity to generate a post-revocation record-access event." },
      { label: "04", title: "Correlate evidence", description: "Sentinel deterministically links the two identity events in the configured window." },
      { label: "05", title: "Create incident", description: "The correlated condition becomes an evidence-backed incident." },
      { label: "06", title: "Verify provenance", description: "Validate source evidence, normalization, detection, incident, and evidence linkage." },
      { label: "07", title: "Analyst handoff", description: "Continue to the incident workflow for investigation and bounded response." },
    ],
    expectedDetection: "DET-006",
    controls: ["Cross-event correlation", "Scenario provenance", "Human-controlled response"],
  },
  {
    id: "SCN-003",
    name: "Mission-Critical Asset Degradation",
    shortName: "Critical Service Degradation",
    summary:
      "A controlled service-state transition validates critical-asset monitoring, deterministic detection, and incident evidence.",
    sourceLabel: "MissionNet Asset State",
    sourceSublabel: "Controlled degradation",
    targets: [
      { label: "mission-data-api-01", sublabel: "Criticality 5 service" },
      { label: "DET-002", sublabel: "Expected detection rule" },
    ],
    stages: [
      { label: "01", title: "Validate baseline", description: "Confirm the service is nominal and dependencies are healthy." },
      { label: "02", title: "Change service state", description: "Use the approved lab API to move the critical service into a degraded state." },
      { label: "03", title: "Observe state evidence", description: "Confirm the MissionNet state transition is present in the audit stream." },
      { label: "04", title: "Evaluate detection", description: "Sentinel evaluates asset criticality and degradation evidence deterministically." },
      { label: "05", title: "Create incident", description: "The critical-asset signal becomes an analyst incident." },
      { label: "06", title: "Verify evidence chain", description: "Validate state evidence, normalization, detection, incident, and linkage." },
      { label: "07", title: "Analyst handoff", description: "Continue to recovery planning with advisory AI and explicit approval boundaries." },
    ],
    expectedDetection: "DET-002",
    controls: ["Critical asset context", "Deterministic detection", "Verified recovery workflow"],
  },
  {
    id: "SCN-004",
    name: "Sensitive Record Access Anomaly",
    shortName: "Data Access Burst",
    summary:
      "A bounded sequence of record reads validates behavioral threshold detection over synthetic application evidence.",
    sourceLabel: "MissionNet Data API",
    sourceSublabel: "Controlled access sequence",
    targets: [
      { label: "u-analyst-01", sublabel: "Identity under test" },
      { label: "5 mission records", sublabel: "Threshold input" },
    ],
    stages: [
      { label: "01", title: "Validate baseline", description: "Confirm record access starts below the configured threshold." },
      { label: "02", title: "Execute access sequence", description: "Read five seeded records through the real MissionNet record endpoint." },
      { label: "03", title: "Observe access evidence", description: "Confirm record.access events accumulate for the same identity." },
      { label: "04", title: "Evaluate threshold", description: "Sentinel deterministically evaluates the access count inside the rule window." },
      { label: "05", title: "Create incident", description: "The access anomaly becomes an evidence-backed analyst case." },
      { label: "06", title: "Verify provenance", description: "Validate all source accesses, normalization, detection, incident, and evidence links." },
      { label: "07", title: "Analyst handoff", description: "Continue to investigation and human-controlled response decisions." },
    ],
    expectedDetection: "DET-003",
    controls: ["Behavior threshold", "Evidence provenance", "Analyst review"],
  },
  {
    id: "SCN-010",
    name: "Multi-Signal Compromise Demonstration",
    shortName: "Multi-Signal Compromise",
    summary:
      "End-to-end controlled validation of credential pressure, service-identity misuse, critical-service degradation, telemetry anomalies, deterministic correlation, and analyst handoff.",
    sourceLabel: "Controlled Scenario Inputs",
    sourceSublabel: "Identity + service + telemetry",
    targets: [
      { label: "MissionNet", sublabel: "Synthetic protected environment" },
      { label: "Sentinel", sublabel: "Detection and correlation pipeline" },
    ],
    stages: [
      { label: "01", title: "Validate baseline", description: "Verify dependencies and reset MissionNet and Sentinel to a deterministic baseline." },
      { label: "02", title: "Execute scenario inputs", description: "Run the approved identity, service, state, and telemetry actions through MissionNet." },
      { label: "03", title: "Observe source evidence", description: "Confirm MissionNet audit and telemetry records exist for the scenario." },
      { label: "04", title: "Evaluate detections", description: "Sentinel applies deterministic rules to normalized evidence. AI does not create detections." },
      { label: "05", title: "Correlate incidents", description: "Expected detections are correlated into evidence-backed incidents." },
      { label: "06", title: "Verify end-to-end evidence", description: "Validate source events, normalized events, detections, incidents, evidence links, and replay idempotency." },
      { label: "07", title: "Analyst handoff", description: "Open the resulting incident for advisory AI interpretation and explicit human-approved response." },
    ],
    expectedDetection: "DET-001 · DET-006 · DET-002 · DET-004 · DET-005",
    controls: ["5 deterministic detections", "3 expected incidents", "AI advisory only", "Human approval required"],
    primaryIncidentIndex: 1,
  },
  {
    id: "SCN-NET-001",
    name: "Network Sensor Detection",
    shortName: "Suricata + Zeek Sensor Lab",
    summary:
      "Controlled synthetic HTTP/DNS traffic is captured to PCAP and analyzed by Suricata and Zeek before entering Sentinel's standard evidence pipeline.",
    sourceLabel: "Isolated Sensor Lab",
    sourceSublabel: "Synthetic HTTP/DNS traffic",
    targets: [
      { label: "Suricata", sublabel: "Network IDS evidence" },
      { label: "Zeek", sublabel: "Network telemetry evidence" },
    ],
    stages: [
      { label: "01", title: "Validate sensor runtime", description: "Confirm the isolated network-sensor runtime is available." },
      { label: "02", title: "Generate synthetic traffic", description: "Produce bounded HTTP/DNS traffic in the isolated lab network." },
      { label: "03", title: "Analyze PCAP", description: "Run Suricata and Zeek against the captured traffic." },
      { label: "04", title: "Normalize sensor evidence", description: "Convert sensor output into Sentinel's standard event model." },
      { label: "05", title: "Correlate incident", description: "Apply deterministic NET rules and correlate resulting evidence." },
      { label: "06", title: "Verify provenance", description: "Validate sensor events, detections, incident creation, and evidence linkage." },
      { label: "07", title: "Analyst handoff", description: "Continue to the incident workflow for evidence review." },
    ],
    expectedDetection: "NET-001 · NET-002 · NET-003",
    controls: ["Real sensor output", "Isolated runtime", "Deterministic correlation"],
    runtimeNote: "Requires Docker, Suricata, and Zeek on the Demo Control host. Cloud execution is environment-dependent.",
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

function failureCode(reason: string | null): string {
  return reason?.match(/\[([A-Z0-9_]+)\]/)?.[1] ?? "RUN_FAILED";
}

function classifyFailure(reason: string | null): FailureDiagnostic {
  const code = failureCode(reason);
  if (code === "UPSTREAM_GATEWAY_ERROR" || code === "UPSTREAM_TRANSPORT_ERROR") {
    return {
      code,
      title: "Upstream service interruption",
      category: "Cloud integration",
      impact: "The current run stopped. Sentinel did not advance the scenario or fabricate evidence.",
      action: "Retry after the affected MissionNet or Sentinel service is reachable. Review the operational log for the component and operation.",
    };
  }
  if (code === "UPSTREAM_INVALID_RESPONSE") {
    return {
      code,
      title: "Invalid upstream service response",
      category: "Integration contract",
      impact: "A required service returned an empty or non-JSON response. The run stopped safely rather than interpreting unknown data.",
      action: "Review the affected service logs and the operation shown below, then retry once the API is returning its documented response format.",
    };
  }
  if (code === "UPSTREAM_HTTP_ERROR" || code === "UPSTREAM_HEALTH_ERROR") {
    return {
      code,
      title: "Upstream application error",
      category: "Service dependency",
      impact: "A MissionNet or Sentinel API operation returned an application-level failure and the run was terminated.",
      action: "Review the component, HTTP operation, and upstream service logs before retrying.",
    };
  }
  if (code === "SCENARIO_PRECONDITION_FAILED") {
    return {
      code,
      title: "Scenario precondition not satisfied",
      category: "Environment state",
      impact: "The controlled run did not start because the synthetic environment was not in the required baseline state.",
      action: "Reset the lab to the expected baseline and start a new run.",
    };
  }
  if (code === "EVIDENCE_TIMEOUT" || code === "SENTINEL_VERIFICATION_TIMEOUT") {
    return {
      code,
      title: "Expected evidence not observed",
      category: "Pipeline verification",
      impact: "The run executed, but the expected evidence or downstream security result was not observed inside the configured validation window.",
      action: "Review the source-event and Sentinel ingestion logs to identify the missing pipeline stage before rerunning.",
    };
  }
  if (code === "VERIFICATION_FAILED") {
    return {
      code,
      title: "Verification control failed",
      category: "Evidence validation",
      impact: "One or more evidence-integrity checks did not pass. The run is correctly marked failed.",
      action: "Review the verification checklist and operational log to identify which control did not pass.",
    };
  }
  return {
    code,
    title: "Scenario execution failed",
    category: "Runtime",
    impact: "The run stopped at the reported point. No later stage is presented as completed.",
    action: "Review the failure detail and operational log before starting another controlled run.",
  };
}

function statusTone(status: string): string {
  if (status === "PASSED") return "border-emerald-300 bg-emerald-50 text-emerald-800";
  if (status === "FAILED") return "border-red-300 bg-red-50 text-red-800";
  if (status === "CANCELLED") return "border-zinc-300 bg-zinc-100 text-zinc-700";
  return "border-blue-300 bg-blue-50 text-blue-800";
}

function stageStatus(index: number, gate: number, terminalStatus?: string): "COMPLETE" | "ACTIVE" | "PENDING" | "BLOCKED" {
  if (terminalStatus === "PASSED") return "COMPLETE";
  if (terminalStatus === "FAILED") {
    if (index < gate) return "COMPLETE";
    if (index === gate) return "BLOCKED";
    return "PENDING";
  }
  if (index < gate) return "COMPLETE";
  if (index === gate) return "ACTIVE";
  return "PENDING";
}

function StageBadge({ value }: { value: "COMPLETE" | "ACTIVE" | "PENDING" | "BLOCKED" }) {
  const classes = {
    COMPLETE: "border-emerald-200 bg-emerald-50 text-emerald-700",
    ACTIVE: "border-blue-200 bg-blue-50 text-blue-700",
    PENDING: "border-zinc-200 bg-zinc-50 text-zinc-500",
    BLOCKED: "border-red-200 bg-red-50 text-red-700",
  }[value];
  return <span className={`rounded border px-2 py-1 text-[10px] font-semibold ${classes}`}>{value}</span>;
}

export function LiveAttackReplay() {
  const [scenarioId, setScenarioId] = useState("SCN-010");
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const scenario = SCENARIO_MAP[scenarioId] ?? SCENARIO_MAP["SCN-010"];

  useEffect(() => {
    const fromHash = window.location.hash.replace(/^#/, "").toUpperCase();
    if (SCENARIO_MAP[fromHash]) setScenarioId(fromHash);
  }, []);

  const actualGate = useMemo(() => {
    if (!run) return 0;
    let gate = 0;
    if (run.step_results.length > 0 || run.timeline.length > 2) gate = 1;
    if (run.missionnet_event_ids.length > 0) gate = 2;
    if (run.sentinel_event_ids.length > 0 || run.detection_ids.length > 0) gate = 3;
    if (run.incident_ids.length > 0) gate = 4;
    if (Object.values(run.verification).some(Boolean)) gate = 5;
    if (run.status === "PASSED") gate = 6;
    return Math.min(gate, scenario.stages.length - 1);
  }, [run, scenario.stages.length]);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;

    async function poll() {
      try {
        const res = await fetch(`${DEMO_API}/api/v1/runs/${runId}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`Unable to retrieve run status (HTTP ${res.status})`);
        const data = (await res.json()) as RunDetail;
        if (cancelled) return;
        setRun(data);
        setError(null);
        if (TERMINAL.has(data.status) && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to retrieve run status");
      }
    }

    poll();
    pollRef.current = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [runId]);

  function chooseScenario(nextScenarioId: string) {
    if (runId && run && !TERMINAL.has(run.status)) return;
    setScenarioId(nextScenarioId);
    window.history.replaceState(null, "", `#${nextScenarioId}`);
    setRunId(null);
    setRun(null);
    setError(null);
  }

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
      if (!res.ok) throw new Error(`Unable to start scenario (HTTP ${res.status})`);
      const started = await res.json();
      setRunId(started.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Unable to start ${scenario.id}`);
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

  const preferredIncidentIndex = scenario.primaryIncidentIndex ?? 0;
  const primaryIncident = run?.incident_ids[preferredIncidentIndex] ?? run?.incident_ids[0] ?? null;
  const runFinished = run ? TERMINAL.has(run.status) : false;
  const diagnostic = run?.status === "FAILED" ? classifyFailure(run.failure_reason) : null;

  return (
    <div className="min-h-screen bg-[#f5f7fa] text-zinc-900">
      <main className="mx-auto w-full max-w-[1500px] px-5 py-6 lg:px-8">
        <header className="mb-6 border-b border-zinc-200 pb-5">
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">Sentinel Demo Control</p>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-950">Scenario Execution Console</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-600">
                Professional operational interface for controlled cyber-range execution, deterministic detection validation,
                evidence verification, and analyst handoff.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded border border-zinc-300 bg-white px-3 py-2 text-xs font-medium text-zinc-600">Synthetic environment</span>
              <span className="rounded border border-zinc-300 bg-white px-3 py-2 text-xs font-medium text-zinc-600">No autonomous response</span>
            </div>
          </div>
        </header>

        <section className="mb-6 rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-start">
            <div className="max-w-4xl">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded border border-zinc-300 bg-zinc-50 px-2 py-1 font-mono text-xs font-semibold text-zinc-700">{scenario.id}</span>
                <span className="text-xs text-zinc-500">Controlled validation scenario</span>
              </div>
              <h2 className="mt-3 text-xl font-semibold text-zinc-950">{scenario.name}</h2>
              <p className="mt-2 text-sm leading-6 text-zinc-600">{scenario.summary}</p>
              {scenario.runtimeNote && (
                <p className="mt-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">{scenario.runtimeNote}</p>
              )}
            </div>
            <button
              onClick={startRun}
              disabled={starting || Boolean(run && !runFinished)}
              className="rounded-md bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
            >
              {starting ? "Starting controlled run…" : "Start controlled run"}
            </button>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-3">
            <div className="rounded border border-zinc-200 bg-zinc-50 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Input source</p>
              <p className="mt-1 text-sm font-medium text-zinc-900">{scenario.sourceLabel}</p>
              <p className="mt-1 text-xs text-zinc-500">{scenario.sourceSublabel}</p>
            </div>
            <div className="rounded border border-zinc-200 bg-zinc-50 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Expected detection</p>
              <p className="mt-1 break-words font-mono text-xs font-medium text-zinc-900">{scenario.expectedDetection}</p>
            </div>
            <div className="rounded border border-zinc-200 bg-zinc-50 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Control model</p>
              <p className="mt-1 text-xs leading-5 text-zinc-600">Deterministic security decisions; AI advisory only; human approval for response.</p>
            </div>
          </div>
        </section>

        <section className="mb-6 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-zinc-950">Scenario catalog</h2>
              <p className="mt-1 text-xs text-zinc-500">Select a controlled validation workflow. Active runs cannot be switched mid-execution.</p>
            </div>
            <span className="text-xs text-zinc-400">{SCENARIOS.length} scenarios</span>
          </div>
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {SCENARIOS.map((item) => {
              const selected = item.id === scenario.id;
              return (
                <button
                  key={item.id}
                  onClick={() => chooseScenario(item.id)}
                  disabled={Boolean(run && !runFinished)}
                  className={`rounded border p-3 text-left transition ${
                    selected
                      ? "border-blue-500 bg-blue-50"
                      : "border-zinc-200 bg-white hover:border-zinc-300 hover:bg-zinc-50"
                  } disabled:cursor-not-allowed disabled:opacity-50`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-mono text-xs font-semibold text-zinc-800">{item.id}</span>
                    {item.id === "SCN-010" && <span className="text-[10px] font-medium text-zinc-500">End-to-end</span>}
                  </div>
                  <p className="mt-1 text-xs text-zinc-600">{item.shortName}</p>
                </button>
              );
            })}
          </div>
        </section>

        {error && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            <span className="font-semibold">Console request error:</span> {error}
          </div>
        )}

        {diagnostic && (
          <section className="mb-6 rounded-lg border border-red-200 bg-white shadow-sm">
            <div className="border-b border-red-100 bg-red-50 px-5 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-red-700">Run failure</p>
                  <h2 className="mt-1 text-base font-semibold text-red-950">{diagnostic.title}</h2>
                </div>
                <span className="rounded border border-red-200 bg-white px-2 py-1 font-mono text-xs text-red-700">{diagnostic.code}</span>
              </div>
            </div>
            <div className="grid gap-4 p-5 md:grid-cols-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Category</p>
                <p className="mt-1 text-sm text-zinc-800">{diagnostic.category}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Operational impact</p>
                <p className="mt-1 text-sm leading-5 text-zinc-700">{diagnostic.impact}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Recommended action</p>
                <p className="mt-1 text-sm leading-5 text-zinc-700">{diagnostic.action}</p>
              </div>
            </div>
            {shortFailureReason(run?.failure_reason ?? null) && (
              <div className="border-t border-zinc-100 bg-zinc-50 px-5 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Failure detail</p>
                <p className="mt-1 break-words font-mono text-xs leading-5 text-zinc-700">{shortFailureReason(run?.failure_reason ?? null)}</p>
              </div>
            )}
          </section>
        )}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-6">
            <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
              <div className="flex flex-col justify-between gap-3 border-b border-zinc-200 px-5 py-4 sm:flex-row sm:items-center">
                <div>
                  <h2 className="text-sm font-semibold text-zinc-950">Execution stages</h2>
                  <p className="mt-1 text-xs text-zinc-500">Progress is derived from the actual backend run state; no simulated success states are displayed.</p>
                </div>
                <span className={`rounded border px-3 py-1.5 text-xs font-semibold ${statusTone(run?.status ?? "READY")}`}>
                  {run?.status ?? "READY"}
                </span>
              </div>
              <div className="divide-y divide-zinc-100">
                {scenario.stages.map((stage, index) => {
                  const value = run ? stageStatus(index, actualGate, run.status) : index === 0 ? "ACTIVE" : "PENDING";
                  return (
                    <div key={`${scenario.id}-${stage.label}`} className="grid gap-3 px-5 py-4 sm:grid-cols-[44px_minmax(0,1fr)_90px] sm:items-start">
                      <span className="font-mono text-xs font-semibold text-zinc-400">{stage.label}</span>
                      <div>
                        <p className="text-sm font-medium text-zinc-900">{stage.title}</p>
                        <p className="mt-1 text-xs leading-5 text-zinc-500">{stage.description}</p>
                      </div>
                      <div className="sm:text-right"><StageBadge value={value} /></div>
                    </div>
                  );
                })}
              </div>
            </section>

            <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
              <div className="border-b border-zinc-200 px-5 py-4">
                <h2 className="text-sm font-semibold text-zinc-950">Operational log</h2>
                <p className="mt-1 text-xs text-zinc-500">Structured execution events from Demo Control and upstream components.</p>
              </div>
              <div className="max-h-[420px] overflow-auto">
                <table className="w-full min-w-[760px] border-collapse text-left text-xs">
                  <thead className="sticky top-0 bg-zinc-50 text-[10px] uppercase tracking-wide text-zinc-500">
                    <tr>
                      <th className="border-b border-zinc-200 px-4 py-3 font-semibold">Time</th>
                      <th className="border-b border-zinc-200 px-4 py-3 font-semibold">Level</th>
                      <th className="border-b border-zinc-200 px-4 py-3 font-semibold">Component</th>
                      <th className="border-b border-zinc-200 px-4 py-3 font-semibold">Code</th>
                      <th className="border-b border-zinc-200 px-4 py-3 font-semibold">Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(run?.timeline ?? []).map((entry, index) => (
                      <tr key={`${entry.timestamp}-${index}`} className="border-b border-zinc-100 last:border-0">
                        <td className="whitespace-nowrap px-4 py-3 font-mono text-zinc-500">{new Date(entry.timestamp).toLocaleTimeString()}</td>
                        <td className={`px-4 py-3 font-semibold ${entry.level === "ERROR" ? "text-red-700" : entry.level === "WARN" ? "text-amber-700" : "text-zinc-600"}`}>{entry.level ?? "INFO"}</td>
                        <td className="px-4 py-3 text-zinc-600">{entry.component ?? "Demo Control"}</td>
                        <td className="px-4 py-3 font-mono text-zinc-500">{entry.code ?? "—"}</td>
                        <td className="px-4 py-3 leading-5 text-zinc-700">{entry.message}</td>
                      </tr>
                    ))}
                    {!run?.timeline.length && (
                      <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-zinc-400">No run events recorded.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </div>

          <aside className="space-y-6">
            <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-zinc-950">Run summary</h2>
              <dl className="mt-4 space-y-3 text-xs">
                <div className="flex items-start justify-between gap-4"><dt className="text-zinc-500">Status</dt><dd className="font-semibold text-zinc-900">{run?.status ?? "READY"}</dd></div>
                <div className="flex items-start justify-between gap-4"><dt className="text-zinc-500">Scenario</dt><dd className="font-mono text-zinc-800">{scenario.id}</dd></div>
                <div className="flex items-start justify-between gap-4"><dt className="text-zinc-500">Run ID</dt><dd className="max-w-[210px] break-all text-right font-mono text-zinc-700">{runId ?? "Not started"}</dd></div>
                <div className="flex items-start justify-between gap-4"><dt className="text-zinc-500">Current step</dt><dd className="max-w-[210px] text-right font-mono text-zinc-700">{run?.current_step ?? "—"}</dd></div>
                <div className="flex items-start justify-between gap-4"><dt className="text-zinc-500">Started</dt><dd className="text-right text-zinc-700">{run?.started_at ? new Date(run.started_at).toLocaleString() : "—"}</dd></div>
                <div className="flex items-start justify-between gap-4"><dt className="text-zinc-500">Completed</dt><dd className="text-right text-zinc-700">{run?.completed_at ? new Date(run.completed_at).toLocaleString() : "—"}</dd></div>
              </dl>
            </section>

            <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-zinc-950">Observed results</h2>
              <div className="mt-4 grid grid-cols-2 gap-3">
                {[
                  ["Source events", run?.missionnet_event_ids.length ?? 0],
                  ["Normalized events", run?.sentinel_event_ids.length ?? 0],
                  ["Detections", run?.detection_ids.length ?? 0],
                  ["Incidents", run?.incident_ids.length ?? 0],
                ].map(([label, value]) => (
                  <div key={String(label)} className="rounded border border-zinc-200 bg-zinc-50 p-3">
                    <p className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</p>
                    <p className="mt-1 text-xl font-semibold text-zinc-950">{value}</p>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-zinc-950">Verification controls</h2>
              <div className="mt-4 space-y-3 text-xs">
                {[
                  ["Source evidence observed", run?.verification.missionnet_event_observed],
                  ["Normalized event observed", run?.verification.normalized_event_observed],
                  ["Expected detection observed", run?.verification.expected_detection_observed],
                  ["Incident created", run?.verification.incident_created],
                  ["Evidence link verified", run?.verification.evidence_link_verified],
                  ["Replay idempotency", run?.verification.no_duplicate_on_replay],
                ].map(([label, value]) => (
                  <div key={String(label)} className="flex items-center justify-between gap-4 border-b border-zinc-100 pb-2 last:border-0 last:pb-0">
                    <span className="text-zinc-600">{label}</span>
                    <span className={`font-semibold ${value ? "text-emerald-700" : "text-zinc-400"}`}>{value ? "PASS" : "PENDING"}</span>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-zinc-950">Control boundaries</h2>
              <ul className="mt-3 space-y-2 text-xs leading-5 text-zinc-600">
                {scenario.controls.map((control) => <li key={control}>• {control}</li>)}
              </ul>
            </section>

            {runFinished && primaryIncident && (
              <section className="rounded-lg border border-emerald-200 bg-emerald-50 p-5">
                <h2 className="text-sm font-semibold text-emerald-950">Analyst workflow available</h2>
                <p className="mt-2 text-xs leading-5 text-emerald-900/80">
                  This run produced a Sentinel incident. Continue to evidence review, AI advisory analysis, and the human-approved response workflow.
                </p>
                <a
                  href={`${SENTINEL_DASHBOARD}/incidents/${primaryIncident}`}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-4 block rounded-md bg-emerald-700 px-3 py-2.5 text-center text-xs font-semibold text-white hover:bg-emerald-800"
                >
                  Open incident workflow ↗
                </a>
                <button
                  onClick={resetLab}
                  disabled={resetting}
                  className="mt-2 w-full rounded-md border border-emerald-300 bg-white px-3 py-2.5 text-xs font-semibold text-emerald-800 hover:bg-emerald-100 disabled:opacity-50"
                >
                  {resetting ? "Resetting…" : "Reset synthetic lab"}
                </button>
              </section>
            )}
          </aside>
        </div>
      </main>
    </div>
  );
}
