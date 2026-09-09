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
  started_at: string;
};

type ScenarioMeta = {
  eyebrow: string;
  objective: string;
  detection: string;
  tags: string[];
  accent: string;
  glow: string;
  icon: "identity" | "token" | "asset" | "records" | "multisignal" | "network";
};

const SCENARIO_META: Record<string, ScenarioMeta> = {
  "SCN-001": {
    eyebrow: "IDENTITY SIGNAL",
    objective: "Credential pressure → deterministic auth-failure detection",
    detection: "DET-001",
    tags: ["Identity", "Threshold", "Audit Evidence"],
    accent: "border-cyan-500/30 text-cyan-300",
    glow: "from-cyan-500/12 via-transparent to-transparent",
    icon: "identity",
  },
  "SCN-002": {
    eyebrow: "SERVICE IDENTITY",
    objective: "Token revocation + record access → cross-event correlation",
    detection: "DET-006",
    tags: ["Service Token", "Correlation", "Identity"],
    accent: "border-violet-500/30 text-violet-300",
    glow: "from-violet-500/12 via-transparent to-transparent",
    icon: "token",
  },
  "SCN-003": {
    eyebrow: "MISSION IMPACT",
    objective: "Critical service degradation → asset-impact detection",
    detection: "DET-002",
    tags: ["Critical Asset", "State Change", "MissionNet"],
    accent: "border-amber-500/30 text-amber-300",
    glow: "from-amber-500/12 via-transparent to-transparent",
    icon: "asset",
  },
  "SCN-004": {
    eyebrow: "DATA ACCESS",
    objective: "Sensitive-record access burst → behavioral threshold detection",
    detection: "DET-003",
    tags: ["Data Access", "Behavior", "Evidence"],
    accent: "border-fuchsia-500/30 text-fuchsia-300",
    glow: "from-fuchsia-500/12 via-transparent to-transparent",
    icon: "records",
  },
  "SCN-010": {
    eyebrow: "FLAGSHIP · MULTI-SIGNAL",
    objective: "Credential + identity + service + telemetry signals → correlated response",
    detection: "5 DETECTIONS · 3 INCIDENTS",
    tags: ["End-to-End", "AI-Assisted", "Human-Approved"],
    accent: "border-orange-400/40 text-orange-200",
    glow: "from-orange-500/20 via-amber-500/5 to-transparent",
    icon: "multisignal",
  },
  "SCN-NET-001": {
    eyebrow: "NETWORK SENSOR",
    objective: "Synthetic PCAP → Suricata + Zeek → Sentinel sensor correlation",
    detection: "NET-001 · NET-002 · NET-003",
    tags: ["Suricata", "Zeek", "PCAP"],
    accent: "border-emerald-500/30 text-emerald-300",
    glow: "from-emerald-500/12 via-transparent to-transparent",
    icon: "network",
  },
};

const PIPELINE = [
  ["01", "Trigger", "Synthetic scenario action"],
  ["02", "MissionNet", "Source telemetry"],
  ["03", "Normalize", "Parse + enrich"],
  ["04", "Detect", "Deterministic rules"],
  ["05", "Correlate", "Evidence-backed incident"],
  ["06", "AI Assist", "Advisory interpretation"],
  ["07", "Approve", "Human decision boundary"],
  ["08", "Respond", "Bounded deterministic action"],
] as const;

async function getJSON<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

function Glyph({ type }: { type: ScenarioMeta["icon"] }) {
  const common = "h-5 w-5";
  if (type === "identity") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.5" />
        <path d="M5.5 19c.8-4 3-6 6.5-6s5.7 2 6.5 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }
  if (type === "token") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="9" cy="12" r="4" stroke="currentColor" strokeWidth="1.5" />
        <path d="M13 12h7m-2 0v3m-3-3v2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }
  if (type === "asset") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <rect x="4" y="4" width="16" height="6" rx="2" stroke="currentColor" strokeWidth="1.5" />
        <rect x="4" y="14" width="16" height="6" rx="2" stroke="currentColor" strokeWidth="1.5" />
        <path d="M8 7h.01M8 17h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    );
  }
  if (type === "records") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M7 4h8l3 3v13H7z" stroke="currentColor" strokeWidth="1.5" />
        <path d="M10 11h5M10 15h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }
  if (type === "network") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="5" r="2" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="5" cy="18" r="2" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="19" cy="18" r="2" stroke="currentColor" strokeWidth="1.5" />
        <path d="M11 7 6 16m7-9 5 9M7 18h10" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    );
  }
  return (
    <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="6" cy="12" r="2" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="12" cy="6" r="2" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="18" cy="12" r="2" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="12" cy="18" r="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="m7.5 10.5 3-3m3 0 3 3m0 3-3 3m-3 0-3-3" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function StatusCard({
  label,
  value,
  detail,
  ok,
}: {
  label: string;
  value: string;
  detail: string;
  ok: boolean;
}) {
  return (
    <div className="sentinel-panel group relative overflow-hidden rounded-2xl p-4">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400/40 to-transparent opacity-0 transition group-hover:opacity-100" />
      <div className="flex items-center justify-between gap-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-500">{label}</p>
        <span className={`h-2 w-2 rounded-full ${ok ? "bg-emerald-400 shadow-[0_0_14px_rgba(52,211,153,.8)]" : "bg-red-400"}`} />
      </div>
      <p className={`mt-3 font-mono text-lg font-semibold ${ok ? "text-emerald-300" : "text-zinc-200"}`}>{value}</p>
      <p className="mt-1 text-[11px] leading-4 text-zinc-600">{detail}</p>
    </div>
  );
}

function TopologyNode({
  step,
  title,
  caption,
  tone = "cyan",
}: {
  step: string;
  title: string;
  caption: string;
  tone?: "red" | "amber" | "cyan" | "violet" | "emerald";
}) {
  const tones = {
    red: "border-red-500/40 bg-red-950/30 text-red-300 shadow-[0_0_35px_rgba(239,68,68,.08)]",
    amber: "border-amber-500/40 bg-amber-950/20 text-amber-300 shadow-[0_0_35px_rgba(245,158,11,.08)]",
    cyan: "border-cyan-500/35 bg-cyan-950/20 text-cyan-300 shadow-[0_0_35px_rgba(34,211,238,.08)]",
    violet: "border-violet-500/35 bg-violet-950/20 text-violet-300 shadow-[0_0_35px_rgba(139,92,246,.08)]",
    emerald: "border-emerald-500/35 bg-emerald-950/20 text-emerald-300 shadow-[0_0_35px_rgba(52,211,153,.08)]",
  };
  return (
    <div className={`relative z-10 min-w-0 rounded-xl border p-3 ${tones[tone]}`}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="rounded-md border border-current/20 bg-black/30 px-1.5 py-0.5 text-[9px] font-bold tracking-[0.16em]">{step}</span>
        <span className="topology-pulse h-1.5 w-1.5 rounded-full bg-current" />
      </div>
      <p className="text-xs font-semibold text-white">{title}</p>
      <p className="mt-1 text-[10px] leading-4 text-zinc-600">{caption}</p>
    </div>
  );
}

function ScenarioCard({ scenario }: { scenario: Scenario }) {
  const meta = SCENARIO_META[scenario.id] ?? {
    eyebrow: "SYNTHETIC SCENARIO",
    objective: scenario.description,
    detection: "DETERMINISTIC",
    tags: ["Synthetic", "Defensive", "Evidence"],
    accent: "border-cyan-500/30 text-cyan-300",
    glow: "from-cyan-500/10 via-transparent to-transparent",
    icon: "multisignal" as const,
  };

  return (
    <article className="scenario-card group relative overflow-hidden rounded-2xl border border-white/[0.07] bg-[#061018]/85 p-4 transition duration-300 hover:-translate-y-1 hover:border-cyan-400/25 hover:bg-[#07141e]">
      <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${meta.glow} opacity-0 transition duration-500 group-hover:opacity-100`} />
      <div className="relative">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[9px] font-semibold uppercase tracking-[0.22em] text-zinc-600">{meta.eyebrow}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className={`rounded-md border bg-black/30 px-2 py-1 font-mono text-[10px] font-bold ${meta.accent}`}>{scenario.id}</span>
              {scenario.id === "SCN-010" && (
                <span className="rounded-md border border-amber-400/30 bg-amber-500/10 px-2 py-1 text-[9px] font-bold uppercase tracking-wider text-amber-300">Flagship</span>
              )}
            </div>
          </div>
          <div className={`rounded-xl border bg-black/30 p-2.5 ${meta.accent}`}>
            <Glyph type={meta.icon} />
          </div>
        </div>

        <h3 className="mt-4 text-base font-semibold tracking-tight text-white">{scenario.name}</h3>
        <p className="mt-2 min-h-10 text-[11px] leading-5 text-zinc-500">{meta.objective}</p>

        <div className="mt-4 flex flex-wrap gap-1.5">
          {meta.tags.map((tag) => (
            <span key={tag} className="rounded-full border border-white/[0.07] bg-white/[0.025] px-2 py-1 text-[9px] text-zinc-500">{tag}</span>
          ))}
        </div>

        <div className="mt-4 flex items-center justify-between border-t border-white/[0.06] pt-3">
          <div>
            <p className="text-[8px] uppercase tracking-[0.18em] text-zinc-700">Expected signal</p>
            <p className="mt-1 font-mono text-[10px] text-zinc-400">{meta.detection}</p>
          </div>
          <p className="font-mono text-[9px] text-zinc-700">{scenario.step_count} STEP{scenario.step_count === 1 ? "" : "S"}</p>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2">
          <Link
            href={`/live-demo#${scenario.id}`}
            className="rounded-lg bg-cyan-400 px-3 py-2.5 text-center text-[10px] font-bold uppercase tracking-wider text-[#001016] transition hover:bg-cyan-300"
          >
            ▶ Launch Replay
          </Link>
          <RunScenarioButton scenarioId={scenario.id} />
        </div>
      </div>
    </article>
  );
}

function RunStatus({ value }: { value: string }) {
  const style =
    value === "PASSED"
      ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
      : value === "FAILED"
        ? "border-red-500/20 bg-red-500/10 text-red-300"
        : "border-amber-500/20 bg-amber-500/10 text-amber-300";
  return <span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${style}`}>{value}</span>;
}

export default async function DemoControlHome() {
  const [status, scenarios, runs] = await Promise.all([
    getJSON<SystemStatus>("/api/v1/status"),
    getJSON<Scenario[]>("/api/v1/scenarios"),
    getJSON<RunSummary[]>("/api/v1/runs"),
  ]);

  const missionReady = status?.missionnet_status === "NOMINAL";
  const sentinelReady = status?.sentinel_status === "ONLINE";
  const aiReady = status?.ai_analyst_status === "OPERATIONAL" || status?.ai_analyst_status === "READY";
  const allReady = missionReady && sentinelReady;
  const scenarioCount = scenarios?.length ?? 0;
  const flagship = scenarios?.find((scenario) => scenario.id === "SCN-010");
  const recentRuns = runs?.slice(0, 6) ?? [];
  const passedRuns = runs?.filter((run) => run.status === "PASSED").length ?? 0;
  const failedRuns = runs?.filter((run) => run.status === "FAILED").length ?? 0;

  return (
    <div className="min-h-screen overflow-hidden bg-[#02070b] text-zinc-100">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_18%_0%,rgba(14,165,233,.11),transparent_30%),radial-gradient(circle_at_82%_12%,rgba(59,130,246,.08),transparent_24%),radial-gradient(circle_at_50%_100%,rgba(6,182,212,.05),transparent_35%)]" />
      <div className="sentinel-grid pointer-events-none fixed inset-0 opacity-35" />

      <nav className="relative z-20 border-b border-white/[0.06] bg-[#02080d]/90 backdrop-blur-xl">
        <div className="mx-auto flex h-14 w-full max-w-[1600px] items-center justify-between px-5 lg:px-8">
          <div className="flex items-center gap-8">
            <Link href="/" className="flex items-center gap-3">
              <div className="relative grid h-8 w-8 place-items-center rounded-lg border border-cyan-400/30 bg-cyan-400/10 text-cyan-300 shadow-[0_0_28px_rgba(34,211,238,.13)]">
                <span className="text-sm font-black">S</span>
                <span className="absolute inset-0 rounded-lg border border-cyan-300/20 animate-pulse" />
              </div>
              <div>
                <p className="text-sm font-bold tracking-[0.16em] text-white">SENTINEL</p>
                <p className="text-[8px] uppercase tracking-[0.22em] text-zinc-600">Demo Control</p>
              </div>
            </Link>
            <div className="hidden items-center gap-1 lg:flex">
              {[
                ["Command", "/"],
                ["Scenarios", "#scenarios"],
                ["Pipeline", "#pipeline"],
                ["Recent Runs", "#runs"],
              ].map(([label, href], index) => (
                <Link
                  key={label}
                  href={href}
                  className={`rounded-lg px-3 py-2 text-[10px] font-semibold uppercase tracking-wider transition ${index === 0 ? "bg-cyan-400/10 text-cyan-300" : "text-zinc-600 hover:bg-white/[0.03] hover:text-zinc-300"}`}
                >
                  {label}
                </Link>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-2 rounded-full border border-white/[0.07] bg-white/[0.025] px-3 py-1.5 sm:flex">
              <span className={`h-1.5 w-1.5 rounded-full ${allReady ? "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,.8)]" : "bg-amber-400"}`} />
              <span className="text-[9px] font-semibold uppercase tracking-[0.18em] text-zinc-500">{allReady ? "Systems Nominal" : "Check Systems"}</span>
            </div>
            <a
              href={SENTINEL_DASHBOARD}
              target="_blank"
              rel="noreferrer"
              className="rounded-lg border border-cyan-400/20 bg-cyan-400/5 px-3 py-2 text-[9px] font-bold uppercase tracking-wider text-cyan-300 transition hover:border-cyan-300/40 hover:bg-cyan-400/10"
            >
              Sentinel Dashboard ↗
            </a>
          </div>
        </div>
      </nav>

      <main className="relative z-10 mx-auto w-full max-w-[1600px] px-5 pb-12 pt-6 lg:px-8">
        <section className="hero-command relative overflow-hidden rounded-[28px] border border-cyan-500/15 bg-[#041019]/90 px-5 py-7 shadow-[0_30px_100px_rgba(0,0,0,.45)] sm:px-8 lg:px-10 lg:py-10">
          <div className="hero-scan pointer-events-none absolute inset-0" />
          <div className="pointer-events-none absolute -right-20 -top-28 h-[440px] w-[440px] rounded-full border border-cyan-400/10 bg-[radial-gradient(circle_at_30%_30%,rgba(34,211,238,.18),rgba(2,8,13,.25)_35%,transparent_66%)] shadow-[0_0_120px_rgba(14,165,233,.08)]" />
          <div className="pointer-events-none absolute right-0 top-0 hidden h-full w-1/2 opacity-50 lg:block">
            <div className="absolute right-20 top-14 h-64 w-64 rounded-full border border-cyan-400/10" />
            <div className="absolute right-28 top-20 h-48 w-48 rounded-full border border-cyan-400/10" />
            <div className="absolute right-[210px] top-[116px] h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_18px_rgba(34,211,238,1)]" />
            <div className="absolute right-[115px] top-[190px] h-1.5 w-1.5 rounded-full bg-amber-300 shadow-[0_0_18px_rgba(251,191,36,1)]" />
            <div className="absolute right-[275px] top-[205px] h-1.5 w-1.5 rounded-full bg-cyan-300 shadow-[0_0_18px_rgba(34,211,238,1)]" />
            <svg className="absolute right-8 top-8 h-[320px] w-[420px]" viewBox="0 0 420 320" fill="none" aria-hidden="true">
              <path d="M45 195C110 120 145 225 210 132C270 48 305 175 380 72" stroke="rgba(34,211,238,.28)" strokeWidth="1" strokeDasharray="4 8" />
              <path d="M88 85C145 145 185 85 252 170C295 226 345 190 392 222" stroke="rgba(59,130,246,.20)" strokeWidth="1" />
              <circle cx="210" cy="132" r="4" fill="rgba(34,211,238,.8)" />
              <circle cx="305" cy="175" r="3" fill="rgba(251,191,36,.8)" />
            </svg>
          </div>

          <div className="relative max-w-4xl">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-emerald-400/20 bg-emerald-400/[0.06] px-3 py-1.5 text-[9px] font-bold uppercase tracking-[0.2em] text-emerald-300">Synthetic Adversary Simulation</span>
              <span className="rounded-full border border-cyan-400/20 bg-cyan-400/[0.06] px-3 py-1.5 text-[9px] font-bold uppercase tracking-[0.2em] text-cyan-300">Real Sentinel Pipeline</span>
              <span className="rounded-full border border-violet-400/20 bg-violet-400/[0.06] px-3 py-1.5 text-[9px] font-bold uppercase tracking-[0.2em] text-violet-300">Human-Approved Response Only</span>
            </div>

            <p className="mt-8 font-mono text-[10px] font-semibold uppercase tracking-[0.34em] text-cyan-500">Defend · Detect · Understand · Strengthen</p>
            <h1 className="mt-3 max-w-4xl text-4xl font-semibold tracking-[-0.045em] text-white sm:text-5xl lg:text-6xl">
              Sentinel <span className="bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-500 bg-clip-text text-transparent">Demo Control</span>
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-zinc-400 sm:text-base">
              A synthetic cyber-range command surface that turns MissionNet and network-sensor evidence into deterministic detections, correlated incidents, AI-assisted analysis, and human-controlled response.
            </p>

            <div className="mt-7 flex flex-wrap gap-3">
              <Link
                href="/live-demo#SCN-010"
                className="group rounded-xl bg-gradient-to-r from-cyan-300 to-sky-500 px-5 py-3 text-[10px] font-black uppercase tracking-[0.15em] text-[#001018] shadow-[0_0_32px_rgba(34,211,238,.2)] transition hover:shadow-[0_0_42px_rgba(34,211,238,.35)]"
              >
                ▶ Launch Flagship Replay <span className="ml-2 inline-block transition group-hover:translate-x-1">→</span>
              </Link>
              <a
                href={SENTINEL_DASHBOARD}
                target="_blank"
                rel="noreferrer"
                className="rounded-xl border border-white/[0.09] bg-white/[0.035] px-5 py-3 text-[10px] font-bold uppercase tracking-[0.15em] text-zinc-300 transition hover:border-cyan-400/25 hover:bg-cyan-400/[0.05] hover:text-cyan-200"
              >
                View Sentinel Dashboard ↗
              </a>
            </div>
          </div>
        </section>

        <section className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <StatusCard label="MissionNet" value={status?.missionnet_status ?? "UNKNOWN"} detail="Synthetic environment state" ok={missionReady} />
          <StatusCard label="Sentinel" value={status?.sentinel_status ?? "UNKNOWN"} detail="Detection pipeline status" ok={sentinelReady} />
          <StatusCard label="AI Analyst" value={status?.ai_analyst_status ?? "NOT ENABLED"} detail="Advisory only · no autonomous execution" ok={aiReady} />
          <StatusCard label="Scenario Library" value={`${scenarioCount} SCENARIOS`} detail="GUI replay-enabled synthetic scenarios" ok={scenarioCount > 0} />
          <StatusCard label="Ingestion Mode" value="ON-DEMAND" detail="Scenario-controlled evidence ingestion" ok={true} />
        </section>

        <section className="mt-4 grid gap-4 xl:grid-cols-[1.35fr_.9fr]">
          <div className="sentinel-panel relative overflow-hidden rounded-3xl p-5 sm:p-6">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(34,211,238,.06),transparent_48%)]" />
            <div className="relative flex flex-col gap-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[9px] font-bold uppercase tracking-[0.25em] text-cyan-500">Attack-to-Defense Topology</p>
                  <h2 className="mt-2 text-xl font-semibold tracking-tight text-white">Visible defensive chain</h2>
                  <p className="mt-1 max-w-2xl text-[11px] leading-5 text-zinc-600">Informational topology preview. Live evidence and progress appear only after a scenario run starts.</p>
                </div>
                <span className="rounded-full border border-emerald-400/15 bg-emerald-400/[0.05] px-3 py-1.5 text-[9px] font-semibold uppercase tracking-wider text-emerald-400">● Visual topology · simulated</span>
              </div>

              <div className="relative">
                <div className="topology-route absolute left-[7%] right-[7%] top-[45px] hidden h-px md:block" />
                <div className="grid gap-2 md:grid-cols-6">
                  <TopologyNode step="01" title="Synthetic Adversary" caption="Scenario pressure" tone="red" />
                  <TopologyNode step="02" title="Identity / Asset" caption="MissionNet source" tone="amber" />
                  <TopologyNode step="03" title="Normalize" caption="Evidence shaping" tone="cyan" />
                  <TopologyNode step="04" title="Detection Engine" caption="Deterministic rules" tone="cyan" />
                  <TopologyNode step="05" title="Incident Correlator" caption="Multi-signal evidence" tone="violet" />
                  <TopologyNode step="06" title="AI + Human" caption="Advisory + approval" tone="emerald" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {[
                  ["Control boundary", "No direct event injection"],
                  ["Detection logic", "Deterministic first"],
                  ["AI role", "Evidence-grounded advisory"],
                  ["Response", "Policy-bounded + approved"],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-xl border border-white/[0.06] bg-black/20 p-3">
                    <p className="text-[8px] uppercase tracking-[0.18em] text-zinc-700">{label}</p>
                    <p className="mt-1 text-[10px] leading-4 text-zinc-400">{value}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="flagship-card relative overflow-hidden rounded-3xl border border-amber-400/20 bg-[#0b0c0c] p-5 sm:p-6">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_100%_0%,rgba(245,158,11,.16),transparent_42%),linear-gradient(135deg,rgba(251,146,60,.05),transparent_50%)]" />
            <div className="relative">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-lg text-amber-300">★</span>
                  <span className="font-mono text-sm font-bold text-amber-200">SCN-010</span>
                  <span className="rounded-md border border-amber-400/25 bg-amber-400/10 px-2 py-1 text-[8px] font-bold uppercase tracking-wider text-amber-300">Flagship</span>
                </div>
                <span className="text-[8px] uppercase tracking-[0.18em] text-zinc-700">Employer-ready flow</span>
              </div>
              <h2 className="mt-5 text-2xl font-semibold tracking-tight text-white">Multi-Signal Compromise Demonstration</h2>
              <p className="mt-2 text-[11px] leading-5 text-zinc-500">Credential pressure, service-identity misuse, critical-service degradation, telemetry anomaly, deterministic detection, correlation, AI-assisted analysis, and human-controlled response.</p>

              <div className="mt-5 grid grid-cols-4 gap-1.5 sm:grid-cols-8 xl:grid-cols-4 2xl:grid-cols-8">
                {["Credential", "Token", "Asset", "Telemetry", "Detect", "Correlate", "AI", "Respond"].map((step, index) => (
                  <div key={step} className="rounded-lg border border-white/[0.06] bg-black/25 px-2 py-2 text-center">
                    <div className={`mx-auto mb-1 h-1.5 w-1.5 rounded-full ${index < 4 ? "bg-orange-400" : index < 6 ? "bg-cyan-400" : "bg-emerald-400"}`} />
                    <span className="text-[8px] text-zinc-600">{step}</span>
                  </div>
                ))}
              </div>

              <div className="mt-5 flex flex-wrap gap-2">
                {["5 detections expected", "3 incidents expected", "AI-assisted", "Human-approved response"].map((chip) => (
                  <span key={chip} className="rounded-full border border-white/[0.07] bg-white/[0.03] px-2.5 py-1 text-[9px] text-zinc-400">{chip}</span>
                ))}
              </div>

              <Link href="/live-demo#SCN-010" className="mt-5 flex w-full items-center justify-between rounded-xl bg-gradient-to-r from-amber-300 to-orange-400 px-4 py-3 text-[10px] font-black uppercase tracking-[0.15em] text-black shadow-[0_0_28px_rgba(251,146,60,.14)] transition hover:shadow-[0_0_38px_rgba(251,146,60,.25)]">
                <span>▶ Launch Immersive Replay</span>
                <span>→</span>
              </Link>
              {!flagship && <p className="mt-2 text-[9px] text-amber-300/60">SCN-010 metadata is temporarily unavailable from Demo Control.</p>}
            </div>
          </div>
        </section>

        <section id="scenarios" className="mt-8 scroll-mt-20">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-[9px] font-bold uppercase tracking-[0.25em] text-cyan-500">Scenario Library</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">Choose your simulation</h2>
              <p className="mt-1 text-[11px] text-zinc-600">Each replay is paced by the real Demo Control run and cannot visually advance beyond backend evidence.</p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] px-3 py-2 font-mono text-[10px] text-zinc-500">{scenarioCount} AVAILABLE · {passedRuns} PASSED RUNS · {failedRuns} FAILED RUNS</div>
          </div>

          {!scenarios && (
            <div className="rounded-2xl border border-red-500/20 bg-red-500/[0.06] px-4 py-4 text-xs text-red-300">Demo Control API is currently unreachable at {API_BASE}. Scenario cards will return when the service is available.</div>
          )}
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {scenarios?.map((scenario) => <ScenarioCard key={scenario.id} scenario={scenario} />)}
          </div>
        </section>

        <section id="pipeline" className="mt-8 grid scroll-mt-20 gap-4 xl:grid-cols-[1.35fr_.65fr]">
          <div className="sentinel-panel rounded-3xl p-5 sm:p-6">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-[9px] font-bold uppercase tracking-[0.25em] text-cyan-500">Simulation Pipeline</p>
                <h2 className="mt-2 text-xl font-semibold text-white">From synthetic trigger to bounded response</h2>
              </div>
              <span className="hidden font-mono text-[9px] text-zinc-700 sm:inline">END-TO-END DEFENSIVE VALIDATION</span>
            </div>
            <div className="mt-6 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {PIPELINE.map(([number, title, detail], index) => (
                <div key={number} className="relative overflow-hidden rounded-xl border border-white/[0.06] bg-black/25 p-3">
                  <div className="flex items-center justify-between">
                    <span className={`grid h-7 w-7 place-items-center rounded-full border font-mono text-[9px] ${index < 3 ? "border-amber-400/25 bg-amber-400/10 text-amber-300" : index < 5 ? "border-cyan-400/25 bg-cyan-400/10 text-cyan-300" : index < 7 ? "border-violet-400/25 bg-violet-400/10 text-violet-300" : "border-emerald-400/25 bg-emerald-400/10 text-emerald-300"}`}>{number}</span>
                    {index < PIPELINE.length - 1 && <span className="text-zinc-800">→</span>}
                  </div>
                  <p className="mt-3 text-[11px] font-semibold text-white">{title}</p>
                  <p className="mt-1 text-[9px] leading-4 text-zinc-600">{detail}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="sentinel-panel relative overflow-hidden rounded-3xl p-5 sm:p-6">
            <div className="pointer-events-none absolute bottom-0 right-0 h-36 w-36 rounded-full bg-emerald-400/[0.04] blur-3xl" />
            <p className="text-[9px] font-bold uppercase tracking-[0.25em] text-emerald-500">Why this matters</p>
            <h2 className="mt-2 text-xl font-semibold text-white">Built to show engineering judgment</h2>
            <div className="mt-5 space-y-3">
              {[
                "Repeatable synthetic scenarios with traceable provenance",
                "Deterministic detections before AI enters the workflow",
                "Evidence-backed incidents instead of cosmetic alerts",
                "AI stays advisory and cannot silently execute response",
                "Human approval and deterministic response boundaries",
                "Safe defensive validation without targeting real systems",
              ].map((item) => (
                <div key={item} className="flex gap-3 text-[10px] leading-4 text-zinc-500">
                  <span className="mt-0.5 text-emerald-400">✓</span>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="runs" className="mt-8 scroll-mt-20">
          <div className="mb-4 flex items-end justify-between gap-4">
            <div>
              <p className="text-[9px] font-bold uppercase tracking-[0.25em] text-cyan-500">Run Activity</p>
              <h2 className="mt-2 text-xl font-semibold text-white">Recent evidence-backed executions</h2>
            </div>
            <span className="font-mono text-[9px] text-zinc-700">LIVE DATA FROM DEMO CONTROL</span>
          </div>
          <div className="sentinel-panel overflow-hidden rounded-3xl">
            {recentRuns.length > 0 ? (
              <div className="divide-y divide-white/[0.05]">
                {recentRuns.map((run) => (
                  <Link key={run.run_id} href={`/runs/${run.run_id}`} className="grid gap-3 px-4 py-3 transition hover:bg-white/[0.025] sm:grid-cols-[1fr_160px_110px_150px] sm:items-center sm:px-5">
                    <div className="min-w-0">
                      <p className="truncate font-mono text-[10px] text-zinc-400">{run.run_id}</p>
                      <p className="mt-1 text-[9px] text-zinc-700">Open detailed evidence timeline →</p>
                    </div>
                    <span className="font-mono text-[10px] text-cyan-400">{run.scenario_id}</span>
                    <RunStatus value={run.status} />
                    <span className="text-[9px] text-zinc-700">{new Date(run.started_at).toLocaleString()}</span>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="px-5 py-8 text-center text-[11px] text-zinc-700">No recent scenario runs are available yet.</div>
            )}
          </div>
        </section>

        <footer className="mt-8 flex flex-col justify-between gap-3 border-t border-white/[0.05] pt-5 text-[9px] uppercase tracking-[0.18em] text-zinc-700 sm:flex-row">
          <span>Sentinel · Synthetic defensive cyber range</span>
          <span>Deterministic detection · AI-assisted analysis · Human-controlled response</span>
        </footer>
      </main>
    </div>
  );
}
