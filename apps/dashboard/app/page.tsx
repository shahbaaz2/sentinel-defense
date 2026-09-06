import Link from "next/link";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type Assurance = {
  inference_location: string;
  external_ai_api: string;
  model: string;
  knowledge_bundle: string;
  policy_bundle: string;
  synthetic_only: boolean;
};

type MetricsSummary = {
  protected_assets: number;
  normalized_events: number;
  active_detections: number;
  open_incidents: number;
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

function Card({ label, value, tone }: { label: string; value: string; tone?: "warn" | "ok" }) {
  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</p>
      <p
        className={`mt-1 text-2xl font-semibold ${
          tone === "warn"
            ? "text-amber-600 dark:text-amber-400"
            : tone === "ok"
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-black dark:text-zinc-50"
        }`}
      >
        {value}
      </p>
    </div>
  );
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

        {metrics ? (
          <>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Card label="Protected Assets" value={String(metrics.protected_assets)} />
              <Card label="Normalized Events" value={String(metrics.normalized_events)} />
              <Card label="Active Detections" value={String(metrics.active_detections)} />
              <Card
                label="Open Incidents"
                value={String(metrics.open_incidents)}
                tone={metrics.open_incidents > 0 ? "warn" : "ok"}
              />
              <Card
                label="MissionNet Connectivity"
                value={metrics.missionnet_reachable ? "REACHABLE" : "UNREACHABLE"}
                tone={metrics.missionnet_reachable ? "ok" : "warn"}
              />
              <Card
                label="Last Ingestion"
                value={
                  metrics.last_ingestion_at
                    ? new Date(metrics.last_ingestion_at).toLocaleTimeString()
                    : "never"
                }
              />
              <Card label="AI Analyst" value={metrics.ai_analyst_status} />
              <Card
                label="External AI API"
                value={assurance?.external_ai_api ?? "unknown"}
                tone={assurance?.external_ai_api === "disabled" ? "ok" : "warn"}
              />
            </div>

            <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
                Severity Distribution (open incidents)
              </h2>
              {Object.keys(metrics.severity_distribution).length > 0 ? (
                <div className="flex gap-4 text-sm">
                  {Object.entries(metrics.severity_distribution).map(([sev, count]) => (
                    <span key={sev} className="font-mono">
                      {sev}: {count}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-zinc-500">No open incidents.</p>
              )}
            </div>
          </>
        ) : (
          <p className="text-sm text-red-600 dark:text-red-400">
            Sentinel API unreachable at {API_BASE}. Run <code>make api</code>.
          </p>
        )}

        <Link
          href="/incidents"
          className="w-fit rounded-full bg-black px-5 py-2 text-sm font-medium text-white dark:bg-white dark:text-black"
        >
          View Live Incidents →
        </Link>
      </main>
    </div>
  );
}
