"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const DEMO_API =
  process.env.NEXT_PUBLIC_DEMOCONTROL_API_BASE_URL ?? "http://127.0.0.1:8100";
const SENTINEL_DASHBOARD =
  process.env.NEXT_PUBLIC_SENTINEL_DASHBOARD_URL ?? "https://sentinel-defense-g6id.vercel.app";
const POLL_MS = 1200;
const STATUS_POLL_MS = 5000;
const TERMINAL = new Set(["PASSED", "FAILED", "CANCELLED"]);

type TimelineEntry = {
  timestamp: string;
  message: string;
  level?: string;
  component?: string;
  code?: string;
};

type StepResult = {
  step_id: string;
  action: string;
  target: string;
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
  step_results: StepResult[];
  timeline: TimelineEntry[];
  missionnet_event_ids: string[];
  sentinel_event_ids: string[];
  detection_ids: string[];
  incident_ids: string[];
  verification: Record<string, boolean>;
  reset_status: string | null;
};

type SystemStatus = {
  missionnet_status: string;
  sentinel_status: string;
  ai_analyst_status: string;
  ai_analyst_code: string | null;
  ai_analyst_message: string | null;
  ai_core_affected: boolean;
};

type ScenarioSummary = {
  id: string;
  name: string;
  description: string;
  expected: string;
  expectedDetections: number;
  expectedIncidents: number;
};

const SCENARIOS: ScenarioSummary[] = [
  {
    id: "SCN-010",
    name: "Multi-Signal Compromise",
    description:
      "Flagship end-to-end validation across credential pressure, service-identity misuse, critical-service degradation, telemetry anomalies, deterministic correlation, and analyst handoff.",
    expected: "5 deterministic detections · 3 incidents",
    expectedDetections: 5,
    expectedIncidents: 3,
  },
  {
    id: "SCN-001",
    name: "Credential Pressure",
    description: "Repeated authentication failures with deterministic threshold detection.",
    expected: "DET-001",
    expectedDetections: 1,
    expectedIncidents: 1,
  },
  {
    id: "SCN-002",
    name: "Service Identity Compromise",
    description: "Revoked service token followed by protected record access and cross-event correlation.",
    expected: "DET-006",
    expectedDetections: 1,
    expectedIncidents: 1,
  },
  {
    id: "SCN-003",
    name: "Critical Service Degradation",
    description: "Mission-critical service degradation with evidence-backed incident creation.",
    expected: "DET-002",
    expectedDetections: 1,
    expectedIncidents: 1,
  },
  {
    id: "SCN-004",
    name: "Data Access Burst",
    description: "Behavioral threshold detection across controlled record-access activity.",
    expected: "DET-003",
    expectedDetections: 1,
    expectedIncidents: 1,
  },
];

const SCN010_RULES = [
  ["DET-001", "Credential pressure"],
  ["DET-006", "Service identity misuse"],
  ["DET-002", "Critical service degradation"],
  ["DET-004", "Telemetry anomaly"],
  ["DET-005", "Multi-signal correlation"],
] as const;

const TECHNOLOGY_LAYERS = [
  {
    label: "Experience",
    items: [
      ["Next.js 16", "Console"],
      ["React 19", "Interactive UI"],
      ["Tailwind CSS 4", "Design system"],
      ["Vercel", "Frontend cloud"],
    ],
  },
  {
    label: "Control & API",
    items: [
      ["Demo Control", "Scenario orchestration"],
      ["FastAPI", "Service APIs"],
      ["Uvicorn", "ASGI runtime"],
      ["Pydantic", "Schema validation"],
      ["httpx", "Service transport"],
    ],
  },
  {
    label: "Security Data",
    items: [
      ["MissionNet", "Protected synthetic app"],
      ["PostgreSQL", "Persistence"],
      ["SQLAlchemy", "Async ORM"],
      ["asyncpg", "Postgres driver"],
      ["Alembic", "Migrations"],
    ],
  },
  {
    label: "Detection & Response",
    items: [
      ["Deterministic Rules", "Detection plane"],
      ["Correlation Engine", "Incident creation"],
      ["Evidence Graph", "Provenance"],
      ["Policy Engine", "Bounded response"],
      ["Verification + Rollback", "Recovery controls"],
    ],
  },
  {
    label: "Sensors & Enterprise",
    items: [
      ["Suricata", "Live sensor adapter"],
      ["Zeek", "Live sensor adapter"],
      ["Splunk", "Read-only integration"],
      ["Wazuh", "Contract-tested adapter"],
      ["Falco", "Contract-tested adapter"],
    ],
  },
  {
    label: "Advisory Intelligence",
    items: [
      ["DeepSeek", "Cloud AI advisory"],
      ["MITRE ATT&CK", "Threat context"],
      ["KEV", "Vulnerability context"],
      ["Runbooks", "Evidence-grounded guidance"],
      ["Human Approval", "Authority boundary"],
    ],
  },
] as const;

function statusTone(status: string) {
  const normalized = status.toUpperCase();
  if (["PASSED", "ONLINE", "NOMINAL", "HEALTHY", "AVAILABLE", "READY"].includes(normalized)) {
    return "border-emerald-500/35 bg-emerald-500/10 text-emerald-300";
  }
  if (["FAILED", "OFFLINE", "UNREACHABLE", "ERROR"].includes(normalized)) {
    return "border-red-500/35 bg-red-500/10 text-red-300";
  }
  if (["PREPARING", "RUNNING", "WAITING_FOR_TELEMETRY", "WAITING_FOR_SENTINEL", "VERIFYING", "UNKNOWN", "UNAVAILABLE"].includes(normalized)) {
    return "border-amber-500/35 bg-amber-500/10 text-amber-300";
  }
  return "border-sky-500/35 bg-sky-500/10 text-sky-300";
}

function dotTone(status: string) {
  const normalized = status.toUpperCase();
  if (["PASSED", "ONLINE", "NOMINAL", "HEALTHY", "AVAILABLE", "READY"].includes(normalized)) return "bg-emerald-400";
  if (["FAILED", "OFFLINE", "UNREACHABLE", "ERROR"].includes(normalized)) return "bg-red-400";
  if (["UNKNOWN", "UNAVAILABLE"].includes(normalized)) return "bg-amber-400";
  return "bg-sky-400";
}

function failureCode(reason: string | null) {
  return reason?.match(/\[([A-Z0-9_]+)\]/)?.[1] ?? "RUN_FAILED";
}

function readableFailure(reason: string | null) {
  const code = failureCode(reason);
  if (code === "UPSTREAM_GATEWAY_ERROR" || code === "UPSTREAM_TRANSPORT_ERROR") {
    return {
      title: "Cloud dependency interruption",
      impact: "The run stopped before downstream evidence was trusted. No security result was fabricated.",
      action: "Allow dependency warm-up to complete, review the component log, and retry the controlled run.",
    };
  }
  if (code === "UPSTREAM_INVALID_RESPONSE") {
    return {
      title: "Invalid dependency response",
      impact: "A required service returned an empty or non-JSON response and the workflow stopped safely.",
      action: "Review the affected API contract and retry after the dependency returns a valid response.",
    };
  }
  if (code === "EVIDENCE_TIMEOUT" || code === "SENTINEL_VERIFICATION_TIMEOUT") {
    return {
      title: "Evidence pipeline timeout",
      impact: "The controlled action ran, but expected evidence was not observed inside the verification window.",
      action: "Inspect the event stream and identify the missing pipeline stage before rerunning.",
    };
  }
  return {
    title: "Scenario execution stopped",
    impact: "The workflow did not advance beyond the last verified state.",
    action: "Review the operational event stream and failure code before starting another controlled run.",
  };
}

function Panel({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`overflow-hidden border border-[#263442] bg-[#101923] shadow-[0_8px_24px_rgba(0,0,0,0.12)] ${className}`}>
      <div className="flex items-start justify-between gap-4 border-b border-[#263442] bg-[#131e29] px-4 py-3">
        <div>
          <h3 className="text-[13px] font-semibold text-slate-100">{title}</h3>
          {subtitle && <p className="mt-0.5 text-[10px] leading-4 text-slate-500">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function KpiCard({
  label,
  value,
  detail,
  target,
  tone = "sky",
}: {
  label: string;
  value: string | number;
  detail: string;
  target?: string;
  tone?: "sky" | "emerald" | "amber" | "violet" | "slate";
}) {
  const line = {
    sky: "bg-sky-400",
    emerald: "bg-emerald-400",
    amber: "bg-amber-400",
    violet: "bg-violet-400",
    slate: "bg-slate-400",
  }[tone];
  return (
    <div className="relative overflow-hidden border border-[#263442] bg-[#101923] px-4 py-3.5">
      <div className={`absolute left-0 top-0 h-full w-[3px] ${line}`} />
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[9px] font-semibold uppercase tracking-[0.15em] text-slate-500">{label}</p>
          <p className="mt-1.5 text-[26px] font-semibold leading-none tracking-tight text-white">{value}</p>
        </div>
        {target && <span className="mt-0.5 rounded-sm border border-[#314151] bg-[#0b141d] px-2 py-1 font-mono text-[9px] text-slate-500">{target}</span>}
      </div>
      <p className="mt-2 text-[10px] text-slate-500">{detail}</p>
    </div>
  );
}

function SignalVolumeChart({ values }: { values: { label: string; value: number }[] }) {
  const max = Math.max(...values.map((item) => item.value), 1);
  return (
    <div className="px-5 pb-5 pt-4">
      <div className="grid h-[210px] grid-cols-[36px_minmax(0,1fr)] gap-3">
        <div className="flex flex-col justify-between pb-7 text-right font-mono text-[9px] text-slate-600">
          {[max, Math.round(max * 0.75), Math.round(max * 0.5), Math.round(max * 0.25), 0].map((value, index) => (
            <span key={`${value}-${index}`}>{value}</span>
          ))}
        </div>
        <div className="relative border-b border-l border-[#2a3948]">
          {[0, 1, 2, 3].map((row) => (
            <div key={row} className="absolute left-0 right-0 border-t border-dashed border-[#24313e]" style={{ top: `${row * 25}%` }} />
          ))}
          <div className="absolute inset-x-3 bottom-0 top-2 flex items-end justify-around gap-4">
            {values.map((item) => {
              const height = item.value === 0 ? 2 : Math.max(8, (item.value / max) * 100);
              return (
                <div key={item.label} className="flex h-full min-w-0 flex-1 flex-col justify-end">
                  <div className="group relative mx-auto flex h-full w-full max-w-[86px] items-end justify-center">
                    <div
                      className="w-full border border-sky-400/40 bg-gradient-to-t from-sky-500/60 to-cyan-300/70 transition hover:from-sky-400/70 hover:to-cyan-200/80"
                      style={{ height: `${height}%` }}
                    />
                    <span className="absolute bottom-[calc(100%+5px)] hidden rounded bg-black/80 px-1.5 py-0.5 text-[9px] text-white group-hover:block">
                      {item.value}
                    </span>
                  </div>
                  <p className="mt-2 truncate text-center text-[9px] text-slate-500">{item.label}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function VerificationGauge({ passed, total }: { passed: number; total: number }) {
  const safeTotal = Math.max(total, 6);
  const percent = Math.min(100, Math.round((passed / safeTotal) * 100));
  return (
    <div className="flex items-center gap-5 p-5">
      <div
        className="relative grid h-28 w-28 shrink-0 place-items-center rounded-full"
        style={{ background: `conic-gradient(#34d399 ${percent * 3.6}deg, #23303d 0deg)` }}
      >
        <div className="grid h-[84px] w-[84px] place-items-center rounded-full bg-[#101923] text-center">
          <div>
            <p className="text-xl font-semibold text-white">{percent}%</p>
            <p className="text-[8px] uppercase tracking-wider text-slate-600">verified</p>
          </div>
        </div>
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-semibold uppercase tracking-[0.13em] text-slate-500">Evidence integrity</p>
        <p className="mt-2 text-sm font-medium text-slate-200">{passed} of {safeTotal} controls passed</p>
        <div className="mt-3 h-1.5 overflow-hidden bg-[#263442]">
          <div className="h-full bg-emerald-400" style={{ width: `${percent}%` }} />
        </div>
        <p className="mt-2 text-[10px] leading-4 text-slate-500">Source evidence, normalization, detection, incident linkage, replay idempotency, and run verification.</p>
      </div>
    </div>
  );
}

function TechLayer({
  label,
  items,
}: {
  label: string;
  items: readonly (readonly [string, string])[];
}) {
  return (
    <div className="grid gap-2 border-b border-[#263442] px-4 py-3 last:border-0 xl:grid-cols-[150px_minmax(0,1fr)] xl:items-start">
      <div>
        <p className="text-[9px] font-semibold uppercase tracking-[0.15em] text-slate-500">{label}</p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map(([name, role]) => (
          <div key={`${label}-${name}`} className="group relative border border-[#314151] bg-[#0b141d] px-2.5 py-1.5">
            <span className="text-[10px] font-semibold text-slate-200">{name}</span>
            <span className="ml-2 text-[9px] text-slate-600">{role}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function SplunkSecurityDashboard() {
  const [scenarioId, setScenarioId] = useState("SCN-010");
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logQuery, setLogQuery] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const scenario = SCENARIOS.find((item) => item.id === scenarioId) ?? SCENARIOS[0];

  useEffect(() => {
    const hash = window.location.hash.replace(/^#/, "").toUpperCase();
    if (SCENARIOS.some((item) => item.id === hash)) setScenarioId(hash);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function readStatus() {
      try {
        const res = await fetch(`${DEMO_API}/api/v1/status`, { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as SystemStatus;
        if (!cancelled) setSystemStatus(data);
      } catch {
        // The dashboard remains usable even if the status probe is briefly unavailable.
      }
    }
    void readStatus();
    const timer = setInterval(readStatus, STATUS_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
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
      const started = (await res.json()) as RunDetail;
      setRunId(started.run_id);
      setRun(started);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start scenario");
    } finally {
      setStarting(false);
    }
  }

  async function cancelRun() {
    if (!runId) return;
    setCancelling(true);
    setError(null);
    try {
      const res = await fetch(`${DEMO_API}/api/v1/runs/${runId}/cancel`, { method: "POST" });
      if (!res.ok) throw new Error(`Cancel request failed (HTTP ${res.status})`);
      setRun((await res.json()) as RunDetail);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to cancel run");
    } finally {
      setCancelling(false);
    }
  }

  async function resetLab() {
    if (!runId) return;
    setResetting(true);
    setError(null);
    try {
      const res = await fetch(`${DEMO_API}/api/v1/runs/${runId}/reset`, { method: "POST" });
      if (!res.ok) throw new Error(`Lab reset failed (HTTP ${res.status})`);
      setRun((await res.json()) as RunDetail);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lab reset failed");
    } finally {
      setResetting(false);
    }
  }

  const status = run?.status ?? "READY";
  const runActive = Boolean(run && !TERMINAL.has(run.status));
  const verificationPassed = run ? Object.values(run.verification).filter(Boolean).length : 0;
  const verificationTotal = run ? Object.keys(run.verification).length : 0;
  const detectionCount = run?.detection_ids.length ?? 0;
  const incidentCount = run?.incident_ids.length ?? 0;
  const detectionCoverage = scenario.expectedDetections
    ? Math.min(100, Math.round((detectionCount / scenario.expectedDetections) * 100))
    : 0;
  const incidentCoverage = scenario.expectedIncidents
    ? Math.min(100, Math.round((incidentCount / scenario.expectedIncidents) * 100))
    : 0;
  const runPassed = status === "PASSED";
  const failure = status === "FAILED" ? readableFailure(run?.failure_reason ?? null) : null;

  const filteredTimeline = useMemo(() => {
    const query = logQuery.trim().toLowerCase();
    if (!query) return run?.timeline ?? [];
    return (run?.timeline ?? []).filter((entry) =>
      [entry.message, entry.level, entry.component, entry.code]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query)),
    );
  }, [run?.timeline, logQuery]);

  const pipeline = useMemo(() => {
    const hasSteps = Boolean(run?.step_results.length);
    const hasSource = Boolean(run?.missionnet_event_ids.length);
    const hasNormalized = Boolean(run?.sentinel_event_ids.length);
    const hasDetection = Boolean(run?.detection_ids.length);
    const hasIncident = Boolean(run?.incident_ids.length);
    const hasVerification = Boolean(run && Object.values(run.verification).some(Boolean));
    return [
      ["MissionNet", "Controlled inputs", hasSteps || runPassed],
      ["Evidence", "Audit + telemetry", hasSource || runPassed],
      ["Normalize", "Vendor-neutral ingest", hasNormalized || runPassed],
      ["Detect", "Deterministic rules", hasDetection || runPassed],
      ["Correlate", "Incident graph", hasIncident || runPassed],
      ["Verify", "Evidence integrity", hasVerification || runPassed],
      ["Analyst", "AI advisory + approval", runPassed],
    ] as const;
  }, [run, runPassed]);

  const currentStage = Math.max(0, pipeline.findIndex((item) => !item[2]));
  const uniqueTargets = Array.from(new Set((run?.step_results ?? []).map((step) => step.target).filter(Boolean))).slice(0, 8);
  const volumeValues = [
    { label: "Source", value: run?.missionnet_event_ids.length ?? 0 },
    { label: "Normalized", value: run?.sentinel_event_ids.length ?? 0 },
    { label: "Detections", value: detectionCount },
    { label: "Incidents", value: incidentCount },
    { label: "Verified", value: verificationPassed },
  ];

  const aiStatus = systemStatus?.ai_analyst_status ?? "UNKNOWN";
  const aiBillingIssue = systemStatus?.ai_analyst_code === "AI_PROVIDER_BILLING";

  return (
    <div className="min-h-screen bg-[#081018] text-slate-200">
      <div className="sticky top-0 z-40 flex h-11 items-center border-b border-[#2b3947] bg-[#050a0f] px-3 shadow-md">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid h-7 w-7 place-items-center bg-gradient-to-br from-emerald-400 to-cyan-500 text-[11px] font-black text-[#041014]">S</div>
          <div className="hidden sm:block">
            <span className="text-[12px] font-semibold text-white">Sentinel</span>
            <span className="ml-2 text-[10px] text-slate-600">Enterprise Security</span>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <div className="hidden items-center gap-2 border border-[#2c3a48] bg-[#101923] px-2.5 py-1.5 text-[9px] text-slate-500 lg:flex">
            <span className={`h-1.5 w-1.5 rounded-full ${dotTone(systemStatus?.sentinel_status ?? "UNKNOWN")}`} />
            Sentinel Core {systemStatus?.sentinel_status ?? "checking"}
          </div>
          <div className="hidden border border-[#2c3a48] bg-[#101923] px-2.5 py-1.5 text-[9px] text-slate-500 md:block">Current run</div>
          <a href={SENTINEL_DASHBOARD} target="_blank" rel="noreferrer" className="border border-[#2c3a48] bg-[#101923] px-2.5 py-1.5 text-[9px] text-slate-300 hover:border-sky-500/50 hover:text-sky-300">Open Sentinel ↗</a>
        </div>
      </div>

      <div className="grid min-h-[calc(100vh-44px)] lg:grid-cols-[218px_minmax(0,1fr)]">
        <aside className="hidden border-r border-[#253340] bg-[#0b131b] lg:flex lg:flex-col">
          <div className="border-b border-[#253340] px-4 py-4">
            <p className="text-[9px] font-semibold uppercase tracking-[0.17em] text-slate-600">Security Operations</p>
            <p className="mt-1 text-sm font-semibold text-slate-100">Analyst Workspace</p>
          </div>
          <nav className="flex-1 py-3 text-[11px]">
            <p className="px-4 pb-1.5 pt-2 text-[8px] font-semibold uppercase tracking-[0.18em] text-slate-700">Monitor</p>
            {[
              ["▦", "Security Posture", true],
              ["◫", "Mission Control", false],
              ["◆", "Findings", false],
              ["◎", "Investigations", false],
              ["⌁", "Detections", false],
            ].map(([icon, label, active]) => (
              <button key={String(label)} className={`flex w-full items-center gap-3 border-l-2 px-4 py-2.5 text-left ${active ? "border-cyan-400 bg-[#122331] text-cyan-300" : "border-transparent text-slate-500 hover:bg-[#101b25] hover:text-slate-300"}`}>
                <span className="w-4 text-center text-[12px]">{icon}</span><span>{label}</span>
              </button>
            ))}
            <p className="px-4 pb-1.5 pt-5 text-[8px] font-semibold uppercase tracking-[0.18em] text-slate-700">Intelligence</p>
            {[["⌘", "Evidence"], ["◈", "AI Advisory"], ["▤", "Runbooks"]].map(([icon, label]) => (
              <button key={label} className="flex w-full items-center gap-3 border-l-2 border-transparent px-4 py-2.5 text-left text-slate-500 hover:bg-[#101b25] hover:text-slate-300"><span className="w-4 text-center text-[12px]">{icon}</span><span>{label}</span></button>
            ))}
            <p className="px-4 pb-1.5 pt-5 text-[8px] font-semibold uppercase tracking-[0.18em] text-slate-700">Platform</p>
            {[["◉", "Technology Fabric"], ["⌬", "Integrations"], ["◌", "System Health"]].map(([icon, label]) => (
              <button key={label} className="flex w-full items-center gap-3 border-l-2 border-transparent px-4 py-2.5 text-left text-slate-500 hover:bg-[#101b25] hover:text-slate-300"><span className="w-4 text-center text-[12px]">{icon}</span><span>{label}</span></button>
            ))}
          </nav>
          <div className="border-t border-[#253340] px-4 py-3 text-[9px] leading-4 text-slate-600">
            Synthetic defensive environment<br />Human authority retained
          </div>
        </aside>

        <main className="min-w-0">
          <header className="border-b border-[#263442] bg-[#0d1620] px-4 py-4 lg:px-6">
            <div className="flex flex-col justify-between gap-4 xl:flex-row xl:items-center">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2 text-[9px] text-slate-600"><span>Security Operations</span><span>›</span><span>Security Posture</span><span>›</span><span className="text-slate-400">{scenario.id}</span></div>
                <div className="mt-1.5 flex flex-wrap items-center gap-2.5">
                  <h1 className="text-[20px] font-semibold tracking-tight text-white">Security Posture</h1>
                  <span className={`border px-2 py-1 text-[9px] font-semibold ${statusTone(status)}`}>{status.replaceAll("_", " ")}</span>
                  {runId && <span className="font-mono text-[9px] text-slate-600">{runId}</span>}
                </div>
                <p className="mt-1 max-w-5xl text-[10px] leading-4 text-slate-500">{scenario.name} — {scenario.description}</p>
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
                  className="h-8 border border-[#344453] bg-[#111d28] px-2.5 text-[10px] text-slate-300 outline-none focus:border-cyan-500 disabled:opacity-50"
                >
                  {SCENARIOS.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.name}</option>)}
                </select>
                {runActive ? (
                  <button onClick={cancelRun} disabled={cancelling} className="h-8 border border-red-500/40 bg-red-500/10 px-3 text-[10px] font-semibold text-red-300 hover:bg-red-500/20 disabled:opacity-50">{cancelling ? "Cancelling…" : "Cancel run"}</button>
                ) : (
                  <button onClick={startRun} disabled={starting} className="h-8 bg-cyan-400 px-3.5 text-[10px] font-bold text-[#041015] hover:bg-cyan-300 disabled:bg-slate-700 disabled:text-slate-500">{starting ? "Starting…" : "▶ Start controlled run"}</button>
                )}
                {run && TERMINAL.has(run.status) && (
                  <button onClick={resetLab} disabled={resetting} className="h-8 border border-[#344453] bg-[#111d28] px-3 text-[10px] font-semibold text-slate-300 hover:border-emerald-500/40 hover:text-emerald-300 disabled:opacity-50">{resetting ? "Resetting…" : "Reset lab"}</button>
                )}
              </div>
            </div>
          </header>

          <div className="space-y-4 p-4 lg:p-5 xl:p-6">
            {error && <div className="border border-red-500/35 bg-red-500/10 px-4 py-2.5 text-[10px] text-red-200"><span className="font-semibold">Console request error:</span> {error}</div>}

            {run?.status === "PREPARING" && <div className="border border-amber-500/35 bg-amber-500/10 px-4 py-2.5 text-[10px] text-amber-200"><span className="font-semibold">Dependency warm-up:</span> MissionNet and Sentinel are being health-checked before execution. The workflow remains in PREPARING until both dependencies are trustworthy.</div>}

            {failure && (
              <div className="grid gap-3 border border-red-500/30 bg-[#171619] p-4 md:grid-cols-3">
                <div><p className="text-[8px] font-semibold uppercase tracking-[0.16em] text-red-400">Execution exception</p><p className="mt-1 text-sm font-semibold text-white">{failure.title}</p><p className="mt-1 font-mono text-[9px] text-red-300">{failureCode(run?.failure_reason ?? null)}</p></div>
                <div><p className="text-[8px] font-semibold uppercase tracking-[0.16em] text-slate-600">Operational impact</p><p className="mt-1 text-[10px] leading-4 text-slate-400">{failure.impact}</p></div>
                <div><p className="text-[8px] font-semibold uppercase tracking-[0.16em] text-slate-600">Recommended action</p><p className="mt-1 text-[10px] leading-4 text-slate-400">{failure.action}</p></div>
              </div>
            )}

            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-6">
              <KpiCard label="Source Events" value={run?.missionnet_event_ids.length ?? 0} detail="MissionNet audit + telemetry" tone="sky" />
              <KpiCard label="Normalized" value={run?.sentinel_event_ids.length ?? 0} detail="Vendor-neutral Sentinel events" tone="violet" />
              <KpiCard label="Detections" value={detectionCount} detail={`${detectionCoverage}% expected coverage`} target={`${scenario.expectedDetections} exp`} tone="emerald" />
              <KpiCard label="Incidents" value={incidentCount} detail={`${incidentCoverage}% expected coverage`} target={`${scenario.expectedIncidents} exp`} tone="amber" />
              <KpiCard label="Verification" value={`${verificationPassed}/${Math.max(verificationTotal, 6)}`} detail="Evidence-integrity controls" tone="emerald" />
              <KpiCard label="Security Decision" value={runPassed ? "PASS" : runActive ? "LIVE" : status === "FAILED" ? "STOP" : "—"} detail="Deterministic pipeline state" tone={runPassed ? "emerald" : runActive ? "sky" : "slate"} />
            </div>

            <div className="grid gap-4 2xl:grid-cols-[minmax(0,1.55fr)_minmax(360px,0.75fr)]">
              <Panel title="Security Signal Activity" subtitle="Observed security-object volume from the current persisted run; no fabricated telemetry.">
                <SignalVolumeChart values={volumeValues} />
              </Panel>
              <Panel title="Verification Coverage" subtitle="Control-plane proof for source evidence through incident linkage.">
                <VerificationGauge passed={verificationPassed} total={verificationTotal} />
              </Panel>
            </div>

            <Panel title="Live Security Pipeline" subtitle="MissionNet → evidence → normalization → deterministic detection → correlation → verification → analyst handoff." action={<span className="font-mono text-[9px] text-slate-600">{run?.current_step ?? "idle"}</span>}>
              <div className="overflow-x-auto px-5 py-5">
                <div className="flex min-w-[1040px] items-center justify-center">
                  {pipeline.map(([label, detail, complete], index) => {
                    const active = runActive && index === currentStage;
                    return (
                      <div key={label} className="contents">
                        <div className={`relative w-[128px] border px-3 py-3 ${complete ? "border-emerald-500/35 bg-emerald-500/[0.06]" : active ? "border-cyan-400/50 bg-cyan-400/[0.07]" : "border-[#334251] bg-[#0c151e]"}`}>
                          <div className="flex items-center gap-2"><span className={`h-2 w-2 rounded-full ${complete ? "bg-emerald-400" : active ? "bg-cyan-300" : "bg-slate-700"}`} /><span className="text-[10px] font-semibold text-slate-200">{label}</span></div>
                          <p className="mt-2 text-[9px] leading-4 text-slate-600">{detail}</p>
                          <p className={`mt-2 text-[8px] font-semibold uppercase tracking-wider ${complete ? "text-emerald-400" : active ? "text-cyan-300" : "text-slate-700"}`}>{complete ? "verified" : active ? "active" : "pending"}</p>
                        </div>
                        {index < pipeline.length - 1 && <div className={`relative mx-2 h-px w-9 ${complete ? "bg-emerald-500/60" : "bg-[#334251]"}`}><span className={`absolute -right-1 -top-[3px] h-2 w-2 rotate-45 border-r border-t ${complete ? "border-emerald-500/60" : "border-[#334251]"}`} /></div>}
                      </div>
                    );
                  })}
                </div>
              </div>
            </Panel>

            <div className="grid gap-4 2xl:grid-cols-[minmax(0,1.3fr)_minmax(420px,0.9fr)]">
              <Panel title="Detection Analytics" subtitle="Deterministic rule coverage and concrete detection objects from the current run." action={<span className="text-[9px] text-slate-600">{scenario.expected}</span>}>
                <div className="grid gap-4 p-4 xl:grid-cols-[minmax(300px,0.85fr)_minmax(0,1.15fr)]">
                  <div className="border border-[#263442] bg-[#0b141d]">
                    <div className="border-b border-[#263442] px-3 py-2 text-[8px] font-semibold uppercase tracking-[0.15em] text-slate-600">Expected analytic coverage</div>
                    {scenario.id === "SCN-010" ? SCN010_RULES.map(([id, label]) => (
                      <div key={id} className="grid grid-cols-[70px_minmax(0,1fr)_72px] items-center gap-2 border-b border-[#21303d] px-3 py-2.5 last:border-0">
                        <span className="font-mono text-[9px] text-cyan-300">{id}</span>
                        <span className="text-[10px] text-slate-400">{label}</span>
                        <span className={`text-right text-[8px] font-semibold ${runPassed ? "text-emerald-300" : "text-slate-700"}`}>{runPassed ? "VERIFIED" : "EXPECTED"}</span>
                      </div>
                    )) : <div className="px-3 py-5 text-[10px] text-slate-500">Expected rule: <span className="font-mono text-cyan-300">{scenario.expected}</span></div>}
                  </div>
                  <div>
                    <div className="grid grid-cols-[minmax(0,1fr)_92px] border border-[#263442] bg-[#0b141d] px-3 py-2 text-[8px] font-semibold uppercase tracking-[0.15em] text-slate-600"><span>Detection object</span><span className="text-right">State</span></div>
                    {(run?.detection_ids ?? []).slice(0, 8).map((id) => (
                      <div key={id} className="grid grid-cols-[minmax(0,1fr)_92px] border-x border-b border-[#263442] px-3 py-2.5"><div><p className="truncate font-mono text-[9px] text-slate-300">{id}</p><p className="mt-1 text-[8px] text-slate-600">Deterministic Sentinel detection</p></div><span className="self-center text-right text-[8px] font-semibold text-emerald-300">CONFIRMED</span></div>
                    ))}
                    {!detectionCount && <div className="border-x border-b border-dashed border-[#334251] px-3 py-7 text-center text-[10px] text-slate-600">No detection objects observed yet.</div>}
                  </div>
                </div>
              </Panel>

              <Panel title="Investigation Queue" subtitle="Evidence-backed Sentinel incidents generated by deterministic correlation." action={<span className="text-[9px] text-slate-600">{incidentCount} cases</span>}>
                <div className="max-h-[360px] overflow-auto">
                  {(run?.incident_ids ?? []).map((id, index) => (
                    <a key={id} href={`${SENTINEL_DASHBOARD}/incidents/${id}`} target="_blank" rel="noreferrer" className="grid grid-cols-[36px_minmax(0,1fr)_86px] items-center gap-3 border-b border-[#263442] px-4 py-3 hover:bg-[#14202b]">
                      <div className="grid h-7 w-7 place-items-center border border-amber-500/35 bg-amber-500/10 text-[9px] font-semibold text-amber-300">{String(index + 1).padStart(2, "0")}</div>
                      <div className="min-w-0"><p className="truncate font-mono text-[9px] text-cyan-300">{id}</p><p className="mt-1 text-[9px] text-slate-500">{scenario.id} evidence-backed investigation</p></div>
                      <div className="text-right"><span className="border border-amber-500/30 bg-amber-500/[0.06] px-2 py-1 text-[8px] font-semibold text-amber-300">INVESTIGATE</span><p className="mt-1 text-[8px] text-slate-700">open ↗</p></div>
                    </a>
                  ))}
                  {!incidentCount && <div className="px-4 py-10 text-center text-[10px] text-slate-600">No incidents created yet.</div>}
                </div>
              </Panel>
            </div>

            <Panel title="Security Technology Fabric" subtitle="Actual technologies and platform layers represented in the Sentinel repository and deployed demo — grouped by operational role." action={<span className="border border-emerald-500/30 bg-emerald-500/[0.05] px-2 py-1 text-[8px] font-semibold text-emerald-300">EMPLOYER VIEW</span>}>
              <div>{TECHNOLOGY_LAYERS.map((layer) => <TechLayer key={layer.label} label={layer.label} items={layer.items} />)}</div>
            </Panel>

            <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(340px,0.6fr)]">
              <Panel title="System & Provider Health" subtitle="Live dependency status from Demo Control. AI status is advisory and cannot change deterministic security results.">
                <div className="grid gap-px bg-[#263442] sm:grid-cols-3">
                  {[
                    ["MissionNet", systemStatus?.missionnet_status ?? "UNKNOWN", "Protected synthetic environment"],
                    ["Sentinel Core", systemStatus?.sentinel_status ?? "UNKNOWN", "Detection + correlation pipeline"],
                    ["AI Advisory", aiStatus, "DeepSeek advisory integration"],
                  ].map(([name, state, detail]) => (
                    <div key={name} className="bg-[#101923] p-4"><div className="flex items-center justify-between gap-3"><span className="text-[10px] font-semibold text-slate-300">{name}</span><span className={`flex items-center gap-1.5 border px-2 py-1 text-[8px] font-semibold ${statusTone(state)}`}><span className={`h-1.5 w-1.5 rounded-full ${dotTone(state)}`} />{state}</span></div><p className="mt-2 text-[9px] leading-4 text-slate-600">{detail}</p></div>
                  ))}
                </div>
                {(systemStatus?.ai_analyst_message || aiBillingIssue) && <div className="border-t border-[#263442] bg-[#0b141d] px-4 py-3 text-[9px] leading-4 text-slate-500"><span className="font-semibold text-slate-400">AI advisory:</span> {systemStatus?.ai_analyst_message ?? "Provider billing condition detected."} <span className="text-emerald-400">Sentinel Core remains unaffected.</span></div>}
              </Panel>

              <Panel title="Observed Entities" subtitle="Targets surfaced from the current scenario action results.">
                <div className="flex min-h-[128px] flex-wrap content-start gap-2 p-4">
                  {uniqueTargets.map((target) => <span key={target} className="border border-[#344453] bg-[#0b141d] px-2.5 py-2 font-mono text-[9px] text-slate-400">{target}</span>)}
                  {!uniqueTargets.length && <p className="w-full py-7 text-center text-[10px] text-slate-600">Entities appear as controlled actions execute.</p>}
                </div>
              </Panel>
            </div>

            <Panel title="Operational Event Stream" subtitle="Structured Demo Control, MissionNet, and Sentinel execution events." action={<div className="flex items-center gap-2"><input value={logQuery} onChange={(event) => setLogQuery(event.target.value)} placeholder="Filter events…" className="h-7 w-44 border border-[#344453] bg-[#0b141d] px-2 text-[9px] text-slate-300 outline-none placeholder:text-slate-700 focus:border-cyan-500" /><span className="text-[8px] uppercase tracking-wider text-slate-700">{filteredTimeline.length} rows</span></div>}>
              <div className="max-h-[430px] overflow-auto">
                <table className="w-full min-w-[880px] border-collapse text-left">
                  <thead className="sticky top-0 bg-[#121e29] text-[8px] uppercase tracking-[0.13em] text-slate-600"><tr><th className="px-3 py-2.5 font-semibold">Time</th><th className="px-3 py-2.5 font-semibold">Level</th><th className="px-3 py-2.5 font-semibold">Component</th><th className="px-3 py-2.5 font-semibold">Code</th><th className="px-3 py-2.5 font-semibold">Event</th></tr></thead>
                  <tbody className="text-[9px]">
                    {filteredTimeline.map((entry, index) => (
                      <tr key={`${entry.timestamp}-${index}`} className="border-t border-[#22303d] hover:bg-[#14202b]"><td className="whitespace-nowrap px-3 py-2.5 font-mono text-slate-600">{new Date(entry.timestamp).toLocaleTimeString()}</td><td className={`px-3 py-2.5 font-semibold ${entry.level === "ERROR" ? "text-red-300" : entry.level === "WARN" ? "text-amber-300" : "text-slate-500"}`}>{entry.level ?? "INFO"}</td><td className="px-3 py-2.5 text-slate-500">{entry.component ?? "Demo Control"}</td><td className="px-3 py-2.5 font-mono text-slate-600">{entry.code ?? "—"}</td><td className="px-3 py-2.5 leading-4 text-slate-400">{entry.message}</td></tr>
                    ))}
                    {!filteredTimeline.length && <tr><td colSpan={5} className="px-3 py-9 text-center text-[10px] text-slate-600">No matching operational events.</td></tr>}
                  </tbody>
                </table>
              </div>
            </Panel>

            <div className="grid gap-4 xl:grid-cols-2">
              <Panel title="Verification Controls" subtitle="Evidence-backed gates used to determine whether the run can be marked PASSED.">
                <div className="grid gap-px bg-[#263442] sm:grid-cols-2">
                  {[
                    ["Source evidence observed", run?.verification.missionnet_event_observed],
                    ["Normalized event observed", run?.verification.normalized_event_observed],
                    ["Expected detection observed", run?.verification.expected_detection_observed],
                    ["Incident created", run?.verification.incident_created],
                    ["Evidence link verified", run?.verification.evidence_link_verified],
                    ["Replay idempotency", run?.verification.no_duplicate_on_replay],
                  ].map(([label, value]) => (
                    <div key={String(label)} className="flex items-center justify-between gap-4 bg-[#101923] px-4 py-3"><span className="text-[9px] text-slate-500">{label}</span><span className={`text-[8px] font-semibold ${value ? "text-emerald-300" : "text-slate-700"}`}>{value ? "PASS" : "PENDING"}</span></div>
                  ))}
                </div>
              </Panel>

              <Panel title="Control Boundaries" subtitle="What the prototype deliberately allows — and what it does not.">
                <div className="grid gap-px bg-[#263442] sm:grid-cols-2">
                  {[
                    ["Detections", "Deterministic rules", "AUTHORIZED"],
                    ["Correlation", "Evidence-backed incidents", "AUTHORIZED"],
                    ["AI", "Read-only advisory", "NON-AUTHORITATIVE"],
                    ["Response", "Policy + human approval", "CONTROLLED"],
                    ["Execution", "Pre-approved playbooks only", "BOUNDED"],
                    ["Recovery", "Verification + rollback", "AUDITABLE"],
                  ].map(([name, detail, state]) => (
                    <div key={name} className="bg-[#101923] px-4 py-3"><div className="flex items-center justify-between gap-3"><span className="text-[9px] font-semibold text-slate-400">{name}</span><span className="text-[7px] font-semibold text-cyan-400">{state}</span></div><p className="mt-1 text-[9px] text-slate-600">{detail}</p></div>
                  ))}
                </div>
              </Panel>
            </div>

            <footer className="flex flex-col justify-between gap-2 border-t border-[#253340] pt-3 text-[8px] text-slate-700 sm:flex-row"><span>Sentinel · synthetic defensive cyber-range prototype</span><span>Deterministic core · AI advisory · human-controlled response</span></footer>
          </div>
        </main>
      </div>
    </div>
  );
}
