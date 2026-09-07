import Link from "next/link";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type Integration = {
  adapter_id: string;
  name: string;
  version: string;
  status: "ACTIVE" | "DEGRADED" | "NOT_CONFIGURED";
  capabilities: string[];
  configuration_requirements: string[];
  supported_event_categories: string[];
  last_successful_ingest_at: string | null;
  event_count: number;
  last_error: string | null;
};

async function getIntegrations(): Promise<Integration[] | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/integrations`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as Integration[];
  } catch {
    return null;
  }
}

const STATUS_STYLE: Record<Integration["status"], string> = {
  ACTIVE: "text-emerald-600 dark:text-emerald-400",
  DEGRADED: "text-amber-600 dark:text-amber-400",
  NOT_CONFIGURED: "text-zinc-500",
};

export default async function DataSourcesPage() {
  const integrations = await getIntegrations();

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-5xl flex-col gap-6 px-8 py-16">
        <div>
          <Link href="/" className="text-sm text-zinc-500 hover:underline">
            ← Mission Cyber Posture
          </Link>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
            Data Sources
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Every adapter Sentinel can ingest from - vendor-neutral, real-checked status. Sentinel
            is not replacing any of these; it adds normalization, evidence-grounded local AI,
            human-approved response, and provenance on top of whatever an organization already
            runs. No credential or token is ever shown here.
          </p>
        </div>

        {integrations === null && (
          <p className="text-sm text-red-600 dark:text-red-400">Sentinel API unreachable.</p>
        )}

        {integrations !== null && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {integrations.map((it) => (
              <section
                key={it.adapter_id}
                className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800"
              >
                <div className="mb-2 flex items-center justify-between">
                  <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-700 dark:text-zinc-300">
                    {it.name}
                  </h2>
                  <span className={`text-xs font-bold ${STATUS_STYLE[it.status]}`}>
                    {it.status}
                  </span>
                </div>
                <dl className="grid grid-cols-2 gap-y-1 text-xs">
                  <dt className="text-zinc-500">Adapter Version</dt>
                  <dd className="font-mono">{it.version}</dd>
                  <dt className="text-zinc-500">Capabilities</dt>
                  <dd>{it.capabilities.join(", ")}</dd>
                  <dt className="text-zinc-500">Event Categories</dt>
                  <dd>{it.supported_event_categories.join(", ")}</dd>
                  <dt className="text-zinc-500">Last Successful Ingest</dt>
                  <dd>
                    {it.last_successful_ingest_at
                      ? new Date(it.last_successful_ingest_at).toLocaleString()
                      : "never"}
                  </dd>
                  <dt className="text-zinc-500">Event Count</dt>
                  <dd>{it.event_count.toLocaleString()}</dd>
                  <dt className="text-zinc-500">Last Error</dt>
                  <dd className={it.last_error ? "text-red-600 dark:text-red-400" : ""}>
                    {it.last_error ?? "none"}
                  </dd>
                </dl>
                {it.status === "NOT_CONFIGURED" && it.configuration_requirements.length > 0 && (
                  <p className="mt-2 text-xs text-zinc-500">
                    To configure: set {it.configuration_requirements.join(", ")} in .env.
                  </p>
                )}
              </section>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
