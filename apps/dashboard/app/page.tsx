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

export default async function Home() {
  const [assurance, metrics] = await Promise.all([
    getJSON<Assurance>("/api/v1/system/assurance"),
    getJSON<MetricsSummary>("/api/v1/metrics/summary"),
  ]);

  const aiStatus = assurance?.ai_analyst_status ?? metrics?.ai_analyst_status ?? "UNKNOWN";

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-4xl flex-col gap-8 px-8 py-16">
        <div className="flex flex-col gap-4">
          <span className="w-fit rounded bg-amber-500/20 px-2 py-1 text-xs font-semibold tracking-wide text-amber-700 dark:text-amber-400">
            SYNTHETIC LAB — DEFENSIVE ONLY
          </span>
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
              Mission Cyber Posture
            </h1>
            <p className="mt-2 text-zinc-600 dark:text-zinc-400">
              Deterministic detection and correlation with an evidence-grounded AI Analyst.
              <span className="font-medium"> AI Analyst: {aiStatus}</span>
              {assurance?.inference_location ? ` · ${assurance.inference_location}` : ""}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <a
              href={LIVE_DEMO_URL}
              target="_blank"
              rel="noreferrer"
              className="rounded-md bg-black px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-zinc-800 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
            >
              LAUNCH IMMERSIVE LIVE DEMO ↗
            </a>
            <Link
              href="/incidents"
              className="rounded-md border border-zinc-300 px-5 py-2.5 text-sm font-medium text-zinc-700 transition hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
            >
              View Incidents
            </Link>
          </div>
          <p className="max-w-2xl text-xs text-zinc-500">
            Launch the flagship SCN-010 GUI replay to watch synthetic credential pressure and mission-service
            degradation produce real Sentinel detections, correlated incidents, evidence verification, and a
            guided handoff into AI-assisted, human-approved response.
          </p>
        </div>

        <OverviewLive initialMetrics={metrics} initialAssurance={assurance} />
      </main>
    </div>
  );
}
