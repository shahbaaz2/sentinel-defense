const MISSIONNET_API_BASE = process.env.MISSIONNET_API_BASE_URL ?? "http://127.0.0.1:8090";

type Health = {
  status: string;
  classification: string;
  service: string;
};

async function getHealth(): Promise<Health | null> {
  try {
    const res = await fetch(`${MISSIONNET_API_BASE}/health`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as Health;
  } catch {
    return null;
  }
}

export default async function Home() {
  const health = await getHealth();

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-2xl flex-col gap-6 px-8 py-20">
        <span className="w-fit rounded bg-amber-500/20 px-2 py-1 text-xs font-semibold tracking-wide text-amber-700 dark:text-amber-400">
          SYNTHETIC LAB — FICTIONAL DATA ONLY
        </span>
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          MissionNet Operations Console
        </h1>
        <p className="text-zinc-600 dark:text-zinc-400">
          Phase 0 shell. Identity, Mission Data, Telemetry Gateway, Asset Registry, and seeded
          synthetic data land in Phase 1. This page currently only proves MissionNet runs
          independently of Sentinel.
        </p>

        <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Mission System Status
          </h2>
          {health ? (
            <dl className="grid grid-cols-2 gap-y-2 text-sm">
              <dt className="text-zinc-500">Status</dt>
              <dd className="font-mono uppercase">{health.status}</dd>
              <dt className="text-zinc-500">Classification</dt>
              <dd className="font-mono">{health.classification}</dd>
              <dt className="text-zinc-500">Service</dt>
              <dd className="font-mono">{health.service}</dd>
            </dl>
          ) : (
            <p className="text-sm text-red-600 dark:text-red-400">
              MissionNet API unreachable at {MISSIONNET_API_BASE}. Run <code>make missionnet</code>.
            </p>
          )}
        </div>
      </main>
    </div>
  );
}
