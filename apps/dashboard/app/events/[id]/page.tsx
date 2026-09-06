import Link from "next/link";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type EventDetail = {
  event_id: string;
  timestamp: string;
  ingestion_timestamp: string;
  source: string;
  source_event_id: string;
  asset_id: string | null;
  user_id: string | null;
  event_category: string;
  event_type: string;
  severity: string;
  summary: string;
  raw_event_ref: string;
  scenario_id: string | null;
  raw_payload: Record<string, unknown>;
  raw_sha256: string | null;
  detection_ids: string[];
  incident_ids: string[];
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

export default async function EventDetailPage(props: PageProps<"/events/[id]">) {
  const { id } = await props.params;
  const event = await getJSON<EventDetail>(`/api/v1/events/${id}`);

  if (!event) {
    return (
      <div className="flex flex-1 flex-col items-center bg-zinc-50 p-16 font-sans dark:bg-black">
        <p className="text-sm text-red-600 dark:text-red-400">Event not found.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-4xl flex-col gap-8 px-8 py-16">
        <div>
          <Link href="/events" className="text-sm text-zinc-500 hover:underline">
            ← Event Explorer
          </Link>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-black dark:text-zinc-50">
            {event.event_type}
          </h1>
          <p className="mt-1 font-mono text-xs text-zinc-500">{event.event_id}</p>
        </div>

        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Normalized Fields
          </h2>
          <dl className="grid grid-cols-1 gap-y-2 text-sm sm:grid-cols-2">
            <dt className="text-zinc-500">Timestamp</dt>
            <dd>{new Date(event.timestamp).toLocaleString()}</dd>
            <dt className="text-zinc-500">Ingested at</dt>
            <dd>{new Date(event.ingestion_timestamp).toLocaleString()}</dd>
            <dt className="text-zinc-500">Source</dt>
            <dd>{event.source}</dd>
            <dt className="text-zinc-500">Source Event ID</dt>
            <dd className="font-mono">{event.source_event_id}</dd>
            <dt className="text-zinc-500">Category / Type</dt>
            <dd>
              {event.event_category} / {event.event_type}
            </dd>
            <dt className="text-zinc-500">Severity</dt>
            <dd className="uppercase">{event.severity}</dd>
            <dt className="text-zinc-500">Asset</dt>
            <dd className="font-mono">{event.asset_id ?? "—"}</dd>
            <dt className="text-zinc-500">User</dt>
            <dd className="font-mono">{event.user_id ?? "—"}</dd>
            <dt className="text-zinc-500">Scenario</dt>
            <dd className="font-mono">{event.scenario_id ?? "—"}</dd>
          </dl>
          <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">{event.summary}</p>
        </section>

        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Raw Source Payload
          </h2>
          <p className="mb-2 text-xs text-zinc-500">
            Untouched, as received from {event.source} - never treated as instructions, even if it
            contains text that looks like one.
          </p>
          <pre className="overflow-x-auto rounded bg-zinc-100 p-3 text-xs dark:bg-zinc-900">
            {JSON.stringify(event.raw_payload, null, 2)}
          </pre>
          <p className="mt-2 font-mono text-xs text-zinc-500">
            raw_event_ref: {event.raw_event_ref} · sha256: {event.raw_sha256}
          </p>
        </section>

        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Used By
          </h2>
          <div className="flex flex-col gap-2 text-sm">
            <div>
              <span className="text-zinc-500">Detections: </span>
              {event.detection_ids.length === 0 ? (
                <span className="text-zinc-500">none</span>
              ) : (
                <span className="font-mono text-xs">{event.detection_ids.join(", ")}</span>
              )}
            </div>
            <div>
              <span className="text-zinc-500">Incidents: </span>
              {event.incident_ids.length === 0 ? (
                <span className="text-zinc-500">none</span>
              ) : (
                event.incident_ids.map((id) => (
                  <Link
                    key={id}
                    href={`/incidents/${id}`}
                    className="mr-2 font-mono text-xs text-blue-600 hover:underline dark:text-blue-400"
                  >
                    {id}
                  </Link>
                ))
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
