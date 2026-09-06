import Link from "next/link";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type AuditEntry = {
  audit_id: string;
  timestamp: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor: string;
  source: string;
  scenario_id: string | null;
  detail: Record<string, unknown>;
};

function str(v: string | string[] | undefined): string {
  return typeof v === "string" ? v : "";
}

async function getAuditLog(params: URLSearchParams): Promise<AuditEntry[] | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/audit?${params.toString()}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as AuditEntry[];
  } catch {
    return null;
  }
}

function entityLink(entry: AuditEntry): string | null {
  if (entry.entity_type === "incident") return `/incidents/${entry.entity_id}`;
  return null;
}

export default async function AuditPage(props: PageProps<"/audit">) {
  const sp = await props.searchParams;
  const filters = {
    entity_type: str(sp.entity_type),
    entity_id: str(sp.entity_id),
    action: str(sp.action),
    scenario_id: str(sp.scenario_id),
  };

  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  params.set("limit", "100");

  const entries = await getAuditLog(params);

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-5xl flex-col gap-6 px-8 py-16">
        <div>
          <Link href="/" className="text-sm text-zinc-500 hover:underline">
            ← Mission Cyber Posture
          </Link>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
            Audit / Provenance
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Every ingestion cycle, detection, incident, and analyst change Sentinel has made -
            append-only, never edited or deleted.
          </p>
        </div>

        <form className="flex flex-wrap gap-2 text-sm" method="get">
          <select
            name="entity_type"
            defaultValue={filters.entity_type}
            className="rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          >
            <option value="">All entity types</option>
            <option value="ingestion">Ingestion</option>
            <option value="detection">Detection</option>
            <option value="incident">Incident</option>
          </select>
          <input
            name="entity_id"
            defaultValue={filters.entity_id}
            placeholder="entity_id"
            className="w-48 rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <input
            name="action"
            defaultValue={filters.action}
            placeholder="action"
            className="w-40 rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <input
            name="scenario_id"
            defaultValue={filters.scenario_id}
            placeholder="scenario_id"
            className="w-32 rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <button type="submit" className="rounded bg-black px-3 py-1 text-white dark:bg-white dark:text-black">
            Filter
          </button>
          <Link href="/audit" className="self-center text-xs text-zinc-500 hover:underline">
            Clear
          </Link>
        </form>

        {entries === null && (
          <p className="text-sm text-red-600 dark:text-red-400">Sentinel API unreachable.</p>
        )}
        {entries !== null && entries.length === 0 && (
          <p className="text-sm text-zinc-500">No audit entries match these filters.</p>
        )}
        {entries !== null && entries.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-100 text-xs uppercase text-zinc-500 dark:bg-zinc-900">
                <tr>
                  <th className="px-3 py-2">Timestamp</th>
                  <th className="px-3 py-2">Entity</th>
                  <th className="px-3 py-2">Action</th>
                  <th className="px-3 py-2">Actor</th>
                  <th className="px-3 py-2">Scenario</th>
                  <th className="px-3 py-2">Detail</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => {
                  const link = entityLink(entry);
                  return (
                    <tr key={entry.audit_id} className="border-t border-zinc-200 dark:border-zinc-800">
                      <td className="px-3 py-2 text-xs">
                        {new Date(entry.timestamp).toLocaleString()}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs">
                        {link ? (
                          <Link href={link} className="text-blue-600 hover:underline dark:text-blue-400">
                            {entry.entity_type}:{entry.entity_id.slice(0, 12)}…
                          </Link>
                        ) : (
                          `${entry.entity_type}:${entry.entity_id.slice(0, 20)}`
                        )}
                      </td>
                      <td className="px-3 py-2 text-xs">{entry.action}</td>
                      <td className="px-3 py-2 text-xs">{entry.actor}</td>
                      <td className="px-3 py-2 font-mono text-xs">{entry.scenario_id ?? "—"}</td>
                      <td className="px-3 py-2 font-mono text-[10px] text-zinc-500">
                        {JSON.stringify(entry.detail)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
