import Link from "next/link";
import { RunScenarioButton } from "./RunScenarioButton";

const API_BASE = process.env.DEMOCONTROL_API_BASE_URL ?? "http://127.0.0.1:8100";
const SENTINEL_DASHBOARD =
  process.env.NEXT_PUBLIC_SENTINEL_DASHBOARD_URL ?? "https://sentinel-defense-g6id.vercel.app";

type SystemStatus = {
  missionnet_status: string;
  sentinel_status: string;
  ai_analyst_status: string;
};

type Scenario = {
  id: string;
  version: string;
  name: string;
  description: string;
  risk_level: string;
  step_count: number;
};

type RunSummary = {
  run_id: string;
  scenario_id: string;
  status: string;
  current_step?: string | null;
  failure_reason?: string | null;
  started_at: string;
  completed_at?: string | null;
};

type ScenarioMeta = {
  objective: string;
  expected: string;
  scope: string;
};

const SCENARIO_META: Record<string, ScenarioMeta> = {
  "SCN-001": {
    objective: "Validate repeated authentication-failure detection from MissionNet audit evidence.",
    expected: "DET-001",
    scope: "Identity telemetry",
  },
  "SCN-002": {
    objective: "Validate deterministic correlation of token revocation and post-revocation record access.",
    expected: "DET-006",
    scope: "Service identity",
  },
  "SCN-003": {
    objective: "Validate critical-service degradation detection using MissionNet state evidence.",
    expected: "DET-002",
    scope: "Critical asset state",
  },
  "SCN-004": {
    objective: "Validate threshold detection for an abnormal burst of sensitive record access.",
    expected: "DET-003",
    scope: "Data access behavior",
  },
  "SCN-010": {
    objective: "Validate the complete multi-signal path from controlled inputs through detection, correlation, verification, and analyst handoff.",
    expected: "5 detections · 3 incidents",
    scope: "End-to-end validation",
  },
  "SCN-NET-001": {
    objective: "Validate Suricata and Zeek sensor evidence through Sentinel's standard normalization and correlation path.",
    expected: "NET-001 · NET-002 · NET-003",
    scope: "Network sensor lab",
  },
};

const CONTROL_PIPELINE = [
  ["1", "Controlled input", "Scenario actions execute only against the synthetic lab environment."],
  ["2", "Source evidence", "MissionNet or sensor runtime produces the source telemetry."],
  ["3", "Normalization", "Sentinel converts observed evidence into its standard event model."],
  ["4", "Detection", "Deterministic rules evaluate the normalized evidence."],
  ["5", "Correlation", "Evidence-backed detections are grouped into analyst incidents."],
  ["6", "AI advisory", "The configured LLM interprets existing incident evidence only."],
  ["7", "Human approval", "An analyst reviews recommendations and explicitly approves response."],
  ["8", "Bounded response", "Deterministic actions execute under policy, verification, and rollback controls."],
] as const;

async function getJSON<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

function dependencyTone(value: string) {
  const normalized = value.toUpperCase();
  if (["ONLINE", "OK", "READY", "NOMINAL"].includes(normalized)) {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (["DEGRADED", "LOADING", "UNKNOWN", "UNAVAILABLE"].includes(normalized)) {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  return "border-red-200 bg-red-50 text-red-800";
}

function runTone(value: string) {
  if (value === "PASSED") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (value === "FAILED") return "border-red-200 bg-red-50 text-red-700";
  if (value === "CANCELLED") return "border-zinc-200 bg-zinc-100 text-zinc-600";
  return "border-blue-200 bg-blue-50 text-blue-700";
}

function DependencyCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">{label}</p>
      <div className="mt-3 flex items-center justify-between gap-3">
        <span className={`rounded border px-2 py-1 text-xs font-semibold ${dependencyTone(value)}`}>{value}</span>
      </div>
      <p className="mt-3 text-xs leading-5 text-zinc-500">{detail}</p>
    </div>
  );
}

function ScenarioCard({ scenario }: { scenario: Scenario }) {
  const meta = SCENARIO_META[scenario.id] ?? {
    objective: scenario.description,
    expected: "Deterministic validation",
    scope: "Synthetic scenario",
  };

  return (
    <article className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-xs font-semibold text-blue-700">{scenario.id}</p>
          <p className="mt-1 text-[11px] uppercase tracking-wide text-zinc-500">{meta.scope}</p>
        </div>
        <span className="rounded border border-zinc-200 bg-zinc-50 px-2 py-1 text-[10px] text-zinc-500">
          {scenario.step_count} step{scenario.step_count === 1 ? "" : "s"}
        </span>
      </div>

      <h3 className="mt-4 text-base font-semibold text-zinc-950">{scenario.name}</h3>
      <p className="mt-2 min-h-12 text-xs leading-5 text-zinc-600">{meta.objective}</p>

      <dl className="mt-4 grid gap-3 border-t border-zinc-100 pt-4 text-xs sm:grid-cols-2">
        <div>
          <dt className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">Expected result</dt>
          <dd className="mt-1 font-mono text-zinc-700">{meta.expected}</dd>
        </div>
        <div>
          <dt className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">Risk level</dt>
          <dd className="mt-1 text-zinc-700">{scenario.risk_level}</dd>
        </div>
      </dl>

      <div className="mt-5 grid grid-cols-2 gap-2">
        <Link
          href={`/live-demo#${scenario.id}`}
          className="rounded-md bg-blue-700 px-3 py-2.5 text-center text-xs font-semibold text-white hover:bg-blue-800"
        >
          Open execution console
        </Link>
        <RunScenarioButton scenarioId={scenario.id} />
      </div>
    </article>
  );
}

export default async function Home() {
  const [status, scenarios, runs] = await Promise.all([
    getJSON<SystemStatus>("/api/v1/status"),
    getJSON<Scenario[]>("/api/v1/scenarios"),
    getJSON<RunSummary[]>("/api/v1/runs"),
  ]);

  const missionnet = status?.missionnet_status ?? "UNAVAILABLE";
  const sentinel = status?.sentinel_status ?? "UNAVAILABLE";
  const ai = status?.ai_analyst_status ?? "UNKNOWN";
  const scenarioList = scenarios ?? [];
  const recentRuns = (runs ?? []).slice(0, 8);

  return (
    <main className="min-h-screen bg-[#f5f7fa] text-zinc-900">
      <div className="mx-auto w-full max-w-[1500px] px-5 py-8 lg:px-8">
        <header className="border-b border-zinc-200 pb-6">
          <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-start">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">Sentinel</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-950">Demo Control & Validation</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-600">
                Enterprise-style operational experience for validating Sentinel's deterministic detection,
                evidence correlation, advisory AI, and human-controlled response workflow against a synthetic protected environment.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link
                href="/live-demo#SCN-010"
                className="rounded-md bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-800"
              >
                Open end-to-end validation
              </Link>
              <a
                href={SENTINEL_DASHBOARD}
                target="_blank"
                rel="noreferrer"
                className="rounded-md border border-zinc-300 bg-white px-4 py-2.5 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
              >
                Open Sentinel dashboard ↗
              </a>
            </div>
          </div>
        </header>

        <section className="mt-6">
          <div className="mb-3 flex items-end justify-between gap-4">
            <div>
              <h2 className="text-sm font-semibold text-zinc-950">Service dependencies</h2>
              <p className="mt-1 text-xs text-zinc-500">Operational health is reported independently for core services and the external AI advisory dependency.</p>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <DependencyCard label="MissionNet" value={missionnet} detail="Synthetic protected environment and source telemetry provider." />
            <DependencyCard label="Sentinel Core" value={sentinel} detail="Deterministic normalization, detection, correlation, evidence, and response APIs." />
            <DependencyCard label="AI Advisory" value={ai} detail="External advisory layer. A degraded AI provider does not invalidate Sentinel Core detections or incidents." />
          </div>
        </section>

        <section className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
          <div>
            <div className="mb-4">
              <h2 className="text-sm font-semibold text-zinc-950">Controlled validation scenarios</h2>
              <p className="mt-1 text-xs text-zinc-500">Each run uses the real Demo Control → source evidence → Sentinel verification path. Scenario success is not fabricated by the UI.</p>
            </div>
            {scenarioList.length > 0 ? (
              <div className="grid gap-4 lg:grid-cols-2">
                {scenarioList.map((scenario) => <ScenarioCard key={scenario.id} scenario={scenario} />)}
              </div>
            ) : (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-5 text-sm text-amber-800">
                Scenario catalog is currently unavailable. Review Demo Control service health before starting a run.
              </div>
            )}
          </div>

          <aside className="space-y-6">
            <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
              <div className="border-b border-zinc-200 px-5 py-4">
                <h2 className="text-sm font-semibold text-zinc-950">Recent runs</h2>
                <p className="mt-1 text-xs text-zinc-500">Latest persisted scenario executions.</p>
              </div>
              <div className="divide-y divide-zinc-100">
                {recentRuns.map((run) => (
                  <div key={run.run_id} className="px-5 py-4">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-mono text-xs font-semibold text-zinc-700">{run.scenario_id}</span>
                      <span className={`rounded border px-2 py-1 text-[10px] font-semibold ${runTone(run.status)}`}>{run.status}</span>
                    </div>
                    <p className="mt-2 break-all font-mono text-[10px] text-zinc-400">{run.run_id}</p>
                    <p className="mt-1 text-[11px] text-zinc-500">{new Date(run.started_at).toLocaleString()}</p>
                    {run.status === "FAILED" && run.failure_reason && (
                      <p className="mt-2 line-clamp-2 text-[11px] leading-4 text-red-700">{run.failure_reason}</p>
                    )}
                  </div>
                ))}
                {recentRuns.length === 0 && <p className="px-5 py-8 text-center text-sm text-zinc-400">No runs recorded.</p>}
              </div>
            </section>

            <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-zinc-950">Product boundaries</h2>
              <dl className="mt-4 space-y-4 text-xs">
                <div>
                  <dt className="font-semibold text-zinc-700">Detection authority</dt>
                  <dd className="mt-1 leading-5 text-zinc-500">Deterministic Sentinel rules and correlation logic create detections and incidents.</dd>
                </div>
                <div>
                  <dt className="font-semibold text-zinc-700">AI authority</dt>
                  <dd className="mt-1 leading-5 text-zinc-500">Advisory only. Provider failure, billing, or rate limits are reported separately from Sentinel Core.</dd>
                </div>
                <div>
                  <dt className="font-semibold text-zinc-700">Response authority</dt>
                  <dd className="mt-1 leading-5 text-zinc-500">Policy-bounded deterministic actions require explicit human approval and supported verification.</dd>
                </div>
              </dl>
            </section>
          </aside>
        </section>

        <section className="mt-8 rounded-lg border border-zinc-200 bg-white shadow-sm">
          <div className="border-b border-zinc-200 px-5 py-4">
            <h2 className="text-sm font-semibold text-zinc-950">Validated control path</h2>
            <p className="mt-1 text-xs text-zinc-500">The product experience separates source evidence, deterministic security decisions, advisory AI, and human response authority.</p>
          </div>
          <div className="grid gap-0 md:grid-cols-2 xl:grid-cols-4">
            {CONTROL_PIPELINE.map(([step, title, detail]) => (
              <div key={step} className="border-b border-zinc-100 p-5 last:border-0 md:border-r xl:border-b-0">
                <p className="font-mono text-xs font-semibold text-blue-700">{step.padStart(2, "0")}</p>
                <h3 className="mt-2 text-sm font-semibold text-zinc-900">{title}</h3>
                <p className="mt-2 text-xs leading-5 text-zinc-500">{detail}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
