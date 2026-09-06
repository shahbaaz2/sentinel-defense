import Link from "next/link";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type Detection = {
  detection_id: string;
  rule_id: string;
  rule_name: string;
  rule_version: string;
  severity: string;
  evidence_summary: string;
  mitre_techniques: string[];
  event_ids: string[];
};

type IncidentDetail = {
  incident_id: string;
  title: string;
  severity: string;
  status: string;
  category: string;
  summary: string;
  primary_asset_id: string | null;
  mitre_techniques: string[];
  first_seen: string;
  last_seen: string;
  detections: Detection[];
  event_ids: string[];
};

type NormalizedEvent = {
  event_id: string;
  timestamp: string;
  source: string;
  event_category: string;
  event_type: string;
  severity: string;
  summary: string;
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

export default async function IncidentDetailPage(props: PageProps<"/incidents/[id]">) {
  const { id } = await props.params;
  const incident = await getJSON<IncidentDetail>(`/api/v1/incidents/${id}`);

  if (!incident) {
    return (
      <div className="flex flex-1 flex-col items-center bg-zinc-50 p-16 font-sans dark:bg-black">
        <p className="text-sm text-red-600 dark:text-red-400">Incident not found.</p>
      </div>
    );
  }

  const events = await Promise.all(
    incident.event_ids.map((eventId) => getJSON<NormalizedEvent>(`/api/v1/events/${eventId}`)),
  );

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-4xl flex-col gap-8 px-8 py-16">
        <div>
          <Link href="/incidents" className="text-sm text-zinc-500 hover:underline">
            ← Live Incidents
          </Link>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-black dark:text-zinc-50">
            {incident.title}
          </h1>
          <p className="mt-1 font-mono text-xs text-zinc-500">{incident.incident_id}</p>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Severity</p>
            <p className="font-semibold uppercase">{incident.severity}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Status</p>
            <p className="font-semibold uppercase">{incident.status}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Category</p>
            <p className="font-semibold">{incident.category}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Primary Asset</p>
            <p className="font-mono text-sm">{incident.primary_asset_id ?? "—"}</p>
          </div>
        </div>

        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Observed Evidence
          </h2>
          <p className="mb-3 text-xs text-zinc-500">
            Facts from Sentinel&apos;s ingest pipeline — never interpreted, only recorded.
          </p>
          <ul className="flex flex-col gap-2">
            {events.map(
              (event) =>
                event && (
                  <li
                    key={event.event_id}
                    className="rounded border border-zinc-200 px-3 py-2 text-xs dark:border-zinc-800"
                  >
                    <span className="font-mono text-zinc-500">
                      {new Date(event.timestamp).toLocaleString()}
                    </span>{" "}
                    <span className="font-medium">{event.event_type}</span> (
                    {event.event_category}, {event.severity}) — {event.summary}
                  </li>
                ),
            )}
          </ul>
        </section>

        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Deterministic Detections
          </h2>
          <p className="mb-3 text-xs text-zinc-500">
            Rule-based matches — no AI involved in creating any of these.
          </p>
          <ul className="flex flex-col gap-3">
            {incident.detections.map((d) => (
              <li
                key={d.detection_id}
                className="rounded border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-zinc-500">
                    {d.rule_id} v{d.rule_version}
                  </span>
                  <span className="text-xs font-semibold uppercase">{d.severity}</span>
                </div>
                <p className="font-medium">{d.rule_name}</p>
                <p className="text-xs text-zinc-600 dark:text-zinc-400">{d.evidence_summary}</p>
                {d.mitre_techniques.length > 0 && (
                  <p className="mt-1 font-mono text-xs text-zinc-500">
                    ATT&CK: {d.mitre_techniques.join(", ")}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Incident Correlation
          </h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            {incident.detections.length} detection(s) correlated by shared asset/identity within
            the correlation window into this one incident. First seen{" "}
            {new Date(incident.first_seen).toLocaleString()}, last seen{" "}
            {new Date(incident.last_seen).toLocaleString()}.
          </p>
        </section>

        <section className="rounded-lg border border-dashed border-zinc-300 p-4 dark:border-zinc-700">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            AI Analyst
          </h2>
          <p className="text-sm text-zinc-500">NOT ENABLED — scheduled for a later phase.</p>
        </section>
      </main>
    </div>
  );
}
