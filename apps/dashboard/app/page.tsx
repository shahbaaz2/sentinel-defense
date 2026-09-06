const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type Assurance = {
  inference_location: string;
  external_ai_api: string;
  model: string;
  knowledge_bundle: string;
  policy_bundle: string;
  synthetic_only: boolean;
};

async function getAssurance(): Promise<Assurance | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/system/assurance`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as Assurance;
  } catch {
    return null;
  }
}

export default async function Home() {
  const assurance = await getAssurance();

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-2xl flex-col gap-6 px-8 py-20">
        <span className="w-fit rounded bg-amber-500/20 px-2 py-1 text-xs font-semibold tracking-wide text-amber-700 dark:text-amber-400">
          SYNTHETIC LAB — DEFENSIVE ONLY
        </span>
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Sentinel
        </h1>
        <p className="text-zinc-600 dark:text-zinc-400">
          Phase 0 shell. Mission Cyber Posture, Live Incidents, and Incident Investigation are built
          in Phase 4. This page currently only proves the dashboard can reach the Sentinel API.
        </p>

        <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Deployment Assurance
          </h2>
          {assurance ? (
            <dl className="grid grid-cols-2 gap-y-2 text-sm">
              <dt className="text-zinc-500">Inference location</dt>
              <dd className="font-mono">{assurance.inference_location}</dd>
              <dt className="text-zinc-500">External AI API</dt>
              <dd className="font-mono">{assurance.external_ai_api}</dd>
              <dt className="text-zinc-500">Model</dt>
              <dd className="font-mono">{assurance.model}</dd>
              <dt className="text-zinc-500">Knowledge bundle</dt>
              <dd className="font-mono">{assurance.knowledge_bundle}</dd>
              <dt className="text-zinc-500">Policy bundle</dt>
              <dd className="font-mono">{assurance.policy_bundle}</dd>
              <dt className="text-zinc-500">Synthetic only</dt>
              <dd className="font-mono">{String(assurance.synthetic_only)}</dd>
            </dl>
          ) : (
            <p className="text-sm text-red-600 dark:text-red-400">
              Sentinel API unreachable at {API_BASE}. Run <code>make api</code>.
            </p>
          )}
        </div>
      </main>
    </div>
  );
}
