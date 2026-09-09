import Link from "next/link";
import { OverviewLive } from "./OverviewLive";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";
const DEMO_CONTROL_URL =
  process.env.NEXT_PUBLIC_DEMO_CONTROL_URL ?? "https://sentinel-defense-ov8q.vercel.app";
const LIVE_DEMO_URL = `${DEMO_CONTROL_URL.replace(/\/$/, "")}/live-demo`;

type Assurance = {
  inference_location: string;
  external_ai_api: string;
  model: string;
  ai_analyst_status: string;
};

type MetricsSummary = {
  protected_assets: number;
  normalized_events: number;
  active_detections: number;
  open_incidents: number;
  critical_high_incidents: number;
  severity_distribution: Record<string, number>;
  missionnet_reachable: boolean;
  last_ingestion_at: string | null;
  ai_analyst_status: string;
};

async function getJSON<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

const SCENARIOS = [
  { id: "SCN-010", title: "Multi-Signal Compromise", type: "End-to-end", expected: "5 detections · 3 incidents", note: "Cloud validated" },
  { id: "SCN-001", title: "Credential Pressure", type: "Identity", expected: "DET-001", note: "Controlled workflow" },
  { id: "SCN-002", title: "Service Identity Compromise", type: "Service identity", expected: "DET-006", note: "Controlled workflow" },
  { id: "SCN-003", title: "Critical Service Degradation", type: "Asset state", expected: "DET-002", note: "Controlled workflow" },
  { id: "SCN-004", title: "Data Access Burst", type: "Behavioral", expected: "DET-003", note: "Controlled workflow" },
  { id: "SCN-NET-001", title: "Network Sensor Detection", type: "Suricata + Zeek", expected: "NET-001 · NET-002 · NET-003", note: "Requires sensor runtime" },
] as const;

export default async function Home() {
  const [assurance, metrics] = await Promise.all([
    getJSON<Assurance>("/api/v1/system/assurance"),
    getJSON<MetricsSummary>("/api/v1/metrics/summary"),
  ]);

  const aiStatus = assurance?.ai_analyst_status ?? metrics?.ai_analyst_status ?? "UNKNOWN";

  return (
    <main className="min-h-screen">
      <header className="border-b border-slate-800 bg-[#091521]/90 px-5 py-4 backdrop-blur lg:px-7">
        <div className="mx-auto flex w-full max-w-[1680px] flex-col justify-between gap-4 xl:flex-row xl:items-center">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-[0.14em] text-slate-600">
              <span>Security Operations</span><span>/</span><span className="text-slate-400">Security Posture</span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight text-white">Sentinel Security Posture</h1>
              <span className="rounded border border-amber-500/25 bg-amber-500/5 px-2 py-1 text-[9px] font-semibold uppercase tracking-wider text-amber-300">Synthetic lab · defensive only</span>
            </div>
            <p className="mt-1 max-w-4xl text-xs leading-5 text-slate-400">
              Live visibility across protected assets, normalized evidence, deterministic detections, investigations, response controls, and advisory intelligence.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded border border-slate-700 bg-[#0d1b29] px-3 py-2 text-[10px] text-slate-400">AI Analyst <strong className="ml-1 text-slate-200">{aiStatus}</strong></span>
            <a href={`${LIVE_DEMO_URL}#SCN-010`} target="_blank" rel="noreferrer" className="rounded bg-sky-500 px-4 py-2 text-[11px] font-bold text-slate-950 transition hover:bg-sky-400">Launch Scenario Console ↗</a>
          </div>
        </div>
      </header>

      <div className="mx-auto w-full max-w-[1680px] space-y-5 p-5 lg:p-7">
        <OverviewLive initialMetrics={metrics} initialAssurance={assurance} />

        <section className="soc-panel rounded-lg">
          <div className="flex flex-col justify-between gap-3 border-b border-slate-800 px-5 py-4 sm:flex-row sm:items-center">
            <div>
              <p className="soc-kicker">Controlled validation library</p>
              <h2 className="mt-1 text-sm font-semibold text-white">Scenario Operations</h2>
              <p className="mt-1 text-[11px] text-slate-500">Every repository scenario opens in an enterprise security console and derives progress from persisted evidence.</p>
            </div>
            <span className="rounded border border-slate-700 bg-[#0d1b29] px-2.5 py-1 text-[10px] font-mono text-slate-400">6 controlled workflows</span>
          </div>
          <div className="grid gap-3 p-5 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
            {SCENARIOS.map((scenario) => {
              const scenarioHref = scenario.id === "SCN-NET-001" ? `${LIVE_DEMO_URL}/network` : `${LIVE_DEMO_URL}#${scenario.id}`;
              return (
                <a
                  key={scenario.id}
                  href={scenarioHref}
                  target="_blank"
                  rel="noreferrer"
                  className="group rounded-lg border border-slate-800 bg-[#0d1b29] p-4 transition hover:-translate-y-0.5 hover:border-sky-500/40 hover:bg-[#102131]"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[10px] font-bold text-sky-300">{scenario.id}</span>
                    <span className="text-[8px] uppercase tracking-wider text-slate-600">{scenario.type}</span>
                  </div>
                  <h3 className="mt-3 min-h-10 text-xs font-semibold leading-5 text-slate-200 group-hover:text-white">{scenario.title}</h3>
                  <div className="mt-3 border-t border-slate-800 pt-3">
                    <p className="text-[8px] uppercase tracking-wider text-slate-600">Expected security result</p>
                    <p className="mt-1 text-[9px] font-medium leading-4 text-slate-400">{scenario.expected}</p>
                    <p className="mt-2 text-[8px] text-slate-600">{scenario.note}</p>
                  </div>
                  <p className="mt-3 text-[10px] font-semibold text-sky-400">Open controlled run ↗</p>
                </a>
              );
            })}
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-3">
          <Link href="/incidents" className="soc-panel-soft rounded-lg p-4 transition hover:border-sky-500/30">
            <p className="soc-kicker">Investigation workflow</p>
            <h3 className="mt-2 text-sm font-semibold text-white">Evidence-backed incidents</h3>
            <p className="mt-2 text-[11px] leading-5 text-slate-500">Review correlated detections, evidence links, AI advisory output, and bounded analyst response actions.</p>
            <p className="mt-4 text-[10px] font-semibold text-sky-400">Open investigations →</p>
          </Link>
          <Link href="/detection-coverage" className="soc-panel-soft rounded-lg p-4 transition hover:border-sky-500/30">
            <p className="soc-kicker">Detection engineering</p>
            <h3 className="mt-2 text-sm font-semibold text-white">Rule & ATT&CK coverage</h3>
            <p className="mt-2 text-[11px] leading-5 text-slate-500">Inspect real rule validation status, event categories, ATT&CK mapping, and scenario coverage.</p>
            <p className="mt-4 text-[10px] font-semibold text-sky-400">View detection coverage →</p>
          </Link>
          <Link href="/data-sources" className="soc-panel-soft rounded-lg p-4 transition hover:border-sky-500/30">
            <p className="soc-kicker">Enterprise ecosystem</p>
            <h3 className="mt-2 text-sm font-semibold text-white">Sensors & integrations</h3>
            <p className="mt-2 text-[11px] leading-5 text-slate-500">See MissionNet, Suricata, Zeek, Splunk, Wazuh, Falco, and the vendor-neutral ingestion boundary.</p>
            <p className="mt-4 text-[10px] font-semibold text-sky-400">Explore data sources →</p>
          </Link>
        </section>
      </div>
    </main>
  );
}
