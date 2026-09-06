import Link from "next/link";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type EventSummary = {
  event_id: string;
  timestamp: string;
  event_type: string;
  severity: string;
};

type DetectionSummary = {
  detection_id: string;
  rule_id: string;
  rule_name: string;
  severity: string;
};

type IncidentSummary = {
  incident_id: string;
  title: string;
  severity: string;
  status: string;
};

type AssetDetail = {
  id: string;
  external_asset_id: string;
  source: string;
  name: string;
  asset_type: string;
  environment: string;
  criticality: number;
  status: string;
  first_seen_at: string;
  last_seen_at: string;
  active_incident_count: number;
  active_detection_count: number;
  recent_events: EventSummary[];
  recent_detections: DetectionSummary[];
  recent_incidents: IncidentSummary[];
  related_identity: string | null;
  vulnerability_posture: string;
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

export default async function AssetDetailPage(props: PageProps<"/assets/[id]">) {
  const { id } = await props.params;
  const asset = await getJSON<AssetDetail>(`/api/v1/assets/${id}`);

  if (!asset) {
    return (
      <div className="flex flex-1 flex-col items-center bg-zinc-50 p-16 font-sans dark:bg-black">
        <p className="text-sm text-red-600 dark:text-red-400">Asset not found.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-4xl flex-col gap-8 px-8 py-16">
        <div>
          <Link href="/assets" className="text-sm text-zinc-500 hover:underline">
            ← Asset Inventory
          </Link>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-black dark:text-zinc-50">
            {asset.name}
          </h1>
          <p className="mt-1 font-mono text-xs text-zinc-500">{asset.external_asset_id}</p>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Status</p>
            <p className="font-semibold uppercase">{asset.status}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Criticality</p>
            <p className="font-semibold">{asset.criticality}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Active Incidents</p>
            <p className="font-semibold">{asset.active_incident_count}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Active Detections</p>
            <p className="font-semibold">{asset.active_detection_count}</p>
          </div>
        </div>

        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Metadata
          </h2>
          <dl className="grid grid-cols-1 gap-y-2 text-sm sm:grid-cols-2">
            <dt className="text-zinc-500">Type</dt>
            <dd>{asset.asset_type}</dd>
            <dt className="text-zinc-500">Environment</dt>
            <dd>{asset.environment}</dd>
            <dt className="text-zinc-500">Source</dt>
            <dd className="font-mono">{asset.source}</dd>
            <dt className="text-zinc-500">Related MissionNet Identity</dt>
            <dd>{asset.related_identity ?? "N/A"}</dd>
            <dt className="text-zinc-500">First Seen</dt>
            <dd>{new Date(asset.first_seen_at).toLocaleString()}</dd>
            <dt className="text-zinc-500">Last Seen</dt>
            <dd>{new Date(asset.last_seen_at).toLocaleString()}</dd>
            <dt className="text-zinc-500">Vulnerability Posture</dt>
            <dd className="italic text-zinc-500">{asset.vulnerability_posture}</dd>
          </dl>
        </section>

        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Recent Normalized Events
          </h2>
          {asset.recent_events.length === 0 ? (
            <p className="text-sm text-zinc-500">No events recorded for this asset yet.</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {asset.recent_events.map((e) => (
                <li key={e.event_id} className="text-xs">
                  <Link href={`/events/${e.event_id}`} className="text-blue-600 hover:underline dark:text-blue-400">
                    {new Date(e.timestamp).toLocaleString()} — {e.event_type} ({e.severity})
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Detections on This Asset
          </h2>
          {asset.recent_detections.length === 0 ? (
            <p className="text-sm text-zinc-500">No open detections for this asset.</p>
          ) : (
            <ul className="flex flex-col gap-1 text-xs">
              {asset.recent_detections.map((d) => (
                <li key={d.detection_id}>
                  {d.rule_id} — {d.rule_name} ({d.severity})
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Incidents Involving This Asset
          </h2>
          {asset.recent_incidents.length === 0 ? (
            <p className="text-sm text-zinc-500">No incidents. Environment is currently nominal.</p>
          ) : (
            <ul className="flex flex-col gap-1 text-sm">
              {asset.recent_incidents.map((i) => (
                <li key={i.incident_id}>
                  <Link
                    href={`/incidents/${i.incident_id}`}
                    className="text-blue-600 hover:underline dark:text-blue-400"
                  >
                    {i.title}
                  </Link>{" "}
                  <span className="text-xs uppercase text-zinc-500">
                    ({i.severity}, {i.status})
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
