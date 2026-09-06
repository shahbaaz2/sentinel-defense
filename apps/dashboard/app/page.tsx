import { OverviewLive } from "./OverviewLive";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

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

export default async function Home() {
  const [assurance, metrics] = await Promise.all([
    getJSON<Assurance>("/api/v1/system/assurance"),
    getJSON<MetricsSummary>("/api/v1/metrics/summary"),
  ]);

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-4xl flex-col gap-8 px-8 py-16">
        <div className="flex flex-col gap-3">
          <span className="w-fit rounded bg-amber-500/20 px-2 py-1 text-xs font-semibold tracking-wide text-amber-700 dark:text-amber-400">
            SYNTHETIC LAB — DEFENSIVE ONLY
          </span>
          <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
            Mission Cyber Posture
          </h1>
          <p className="text-zinc-600 dark:text-zinc-400">
            Deterministic detection and correlation only.{" "}
            <span className="font-medium">AI Analyst: NOT ENABLED</span> — scheduled for a later
            phase.
          </p>
        </div>

        <OverviewLive initialMetrics={metrics} initialAssurance={assurance} />
      </main>
    </div>
  );
}
