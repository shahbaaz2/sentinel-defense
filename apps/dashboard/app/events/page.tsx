import Link from "next/link";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";
const PAGE_SIZE = 25;

type Event = {
  event_id: string;
  timestamp: string;
  source: string;
  event_category: string;
  event_type: string;
  severity: string;
  asset_id: string | null;
  user_id: string | null;
  scenario_id: string | null;
  rule_id: string | null;
  src_ip: string | null;
  dst_ip: string | null;
  summary: string;
};

function str(v: string | string[] | undefined): string {
  return typeof v === "string" ? v : "";
}

async function getEvents(params: URLSearchParams): Promise<Event[] | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/events?${params.toString()}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as Event[];
  } catch {
    return null;
  }
}

const SEVERITY_COLOR: Record<string, string> = {
  info: "bg-zinc-400",
  low: "bg-zinc-400",
  medium: "bg-amber-500",
  high: "bg-orange-600",
  critical: "bg-red-600",
};

export default async function EventExplorerPage(props: PageProps<"/events">) {
  const sp = await props.searchParams;
  const filters = {
    source: str(sp.source),
    event_category: str(sp.event_category),
    event_type: str(sp.event_type),
    severity: str(sp.severity),
    asset_id: str(sp.asset_id),
    user_id: str(sp.user_id),
    scenario_id: str(sp.scenario_id),
    rule_id: str(sp.rule_id),
    src_ip: str(sp.src_ip),
    dst_ip: str(sp.dst_ip),
  };
  const page = Math.max(1, parseInt(str(sp.page)) || 1);

  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  params.set("limit", String(PAGE_SIZE));
  params.set("offset", String((page - 1) * PAGE_SIZE));

  const events = await getEvents(params);

  const nextParams = new URLSearchParams(params);
  nextParams.set("page", String(page + 1));
  const prevParams = new URLSearchParams(params);
  prevParams.set("page", String(Math.max(1, page - 1)));

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-5xl flex-col gap-6 px-8 py-16">
        <div>
          <Link href="/" className="text-sm text-zinc-500 hover:underline">
            ← Mission Cyber Posture
          </Link>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
            Event Explorer
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            A simple structured explorer over Sentinel&apos;s normalized events - not a search
            language.
          </p>
        </div>

        <form className="flex flex-wrap gap-2 text-sm" method="get">
          <input
            name="source"
            defaultValue={filters.source}
            placeholder="source"
            className="w-28 rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <input
            name="event_category"
            defaultValue={filters.event_category}
            placeholder="category"
            className="w-28 rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <input
            name="event_type"
            defaultValue={filters.event_type}
            placeholder="event_type"
            className="w-32 rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <select
            name="severity"
            defaultValue={filters.severity}
            className="rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          >
            <option value="">All severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
            <option value="info">Info</option>
          </select>
          <input
            name="asset_id"
            defaultValue={filters.asset_id}
            placeholder="asset_id"
            className="w-32 rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <input
            name="user_id"
            defaultValue={filters.user_id}
            placeholder="user_id"
            className="w-28 rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <input
            name="scenario_id"
            defaultValue={filters.scenario_id}
            placeholder="scenario_id"
            className="w-28 rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <input
            name="rule_id"
            defaultValue={filters.rule_id}
            placeholder="rule/signature (e.g. NET-001)"
            className="w-44 rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <input
            name="src_ip"
            defaultValue={filters.src_ip}
            placeholder="src IP"
            className="w-28 rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <input
            name="dst_ip"
            defaultValue={filters.dst_ip}
            placeholder="dst IP"
            className="w-28 rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <button type="submit" className="rounded bg-black px-3 py-1 text-white dark:bg-white dark:text-black">
            Filter
          </button>
          <Link href="/events" className="self-center text-xs text-zinc-500 hover:underline">
            Clear
          </Link>
        </form>

        {events === null && (
          <p className="text-sm text-red-600 dark:text-red-400">Sentinel API unreachable.</p>
        )}
        {events !== null && events.length === 0 && (
          <p className="text-sm text-zinc-500">No events match these filters.</p>
        )}
        {events !== null && events.length > 0 && (
          <>
            <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-100 text-xs uppercase text-zinc-500 dark:bg-zinc-900">
                  <tr>
                    <th className="px-3 py-2">Timestamp</th>
                    <th className="px-3 py-2">Source</th>
                    <th className="px-3 py-2">Category / Type</th>
                    <th className="px-3 py-2">Severity</th>
                    <th className="px-3 py-2">Asset</th>
                    <th className="px-3 py-2">User</th>
                    <th className="px-3 py-2">Rule</th>
                    <th className="px-3 py-2">Src → Dst</th>
                    <th className="px-3 py-2">Scenario</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((e) => (
                    <tr key={e.event_id} className="border-t border-zinc-200 dark:border-zinc-800">
                      <td className="px-3 py-2 text-xs">
                        <Link
                          href={`/events/${e.event_id}`}
                          className="text-blue-600 hover:underline dark:text-blue-400"
                        >
                          {new Date(e.timestamp).toLocaleString()}
                        </Link>
                      </td>
                      <td className="px-3 py-2 text-xs">{e.source}</td>
                      <td className="px-3 py-2 text-xs">
                        {e.event_category} / {e.event_type}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`inline-block h-2 w-2 rounded-full mr-2 ${SEVERITY_COLOR[e.severity] ?? "bg-zinc-400"}`}
                        />
                        {e.severity}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs">{e.asset_id ?? "—"}</td>
                      <td className="px-3 py-2 font-mono text-xs">{e.user_id ?? "—"}</td>
                      <td className="px-3 py-2 font-mono text-xs">{e.rule_id ?? "—"}</td>
                      <td className="px-3 py-2 font-mono text-xs">
                        {e.src_ip || e.dst_ip
                          ? `${e.src_ip ?? "?"} → ${e.dst_ip ?? "?"}`
                          : "—"}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs">{e.scenario_id ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between text-sm">
              <Link
                href={`/events?${prevParams.toString()}`}
                className="rounded border border-zinc-300 px-3 py-1 dark:border-zinc-700"
              >
                ← Previous
              </Link>
              <span className="text-xs text-zinc-500">Page {page}</span>
              <Link
                href={`/events?${nextParams.toString()}`}
                className="rounded border border-zinc-300 px-3 py-1 dark:border-zinc-700"
              >
                Next →
              </Link>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
