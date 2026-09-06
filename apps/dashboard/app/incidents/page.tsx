import Link from "next/link";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type Incident = {
  incident_id: string;
  title: string;
  severity: string;
  status: string;
  category: string;
  primary_asset_id: string | null;
  detection_ids: string[];
  first_seen: string;
};

async function getIncidents(): Promise<Incident[] | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/incidents`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as Incident[];
  } catch {
    return null;
  }
}

const SEVERITY_COLOR: Record<string, string> = {
  low: "bg-zinc-400",
  medium: "bg-amber-500",
  high: "bg-orange-600",
  critical: "bg-red-600",
};

export default async function IncidentsPage() {
  const incidents = await getIncidents();

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-4xl flex-col gap-6 px-8 py-16">
        <div>
          <Link href="/" className="text-sm text-zinc-500 hover:underline">
            ← Mission Cyber Posture
          </Link>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
            Live Incidents
          </h1>
        </div>

        {incidents === null && (
          <p className="text-sm text-red-600 dark:text-red-400">Sentinel API unreachable.</p>
        )}
        {incidents !== null && incidents.length === 0 && (
          <p className="text-sm text-zinc-500">No incidents. MissionNet is nominal.</p>
        )}
        {incidents !== null && incidents.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-100 text-xs uppercase text-zinc-500 dark:bg-zinc-900">
                <tr>
                  <th className="px-3 py-2">ID</th>
                  <th className="px-3 py-2">Severity</th>
                  <th className="px-3 py-2">Title / Category</th>
                  <th className="px-3 py-2">Affected Asset</th>
                  <th className="px-3 py-2">Detections</th>
                  <th className="px-3 py-2">First Seen</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((incident) => (
                  <tr
                    key={incident.incident_id}
                    className="border-t border-zinc-200 dark:border-zinc-800"
                  >
                    <td className="px-3 py-2">
                      <Link
                        href={`/incidents/${incident.incident_id}`}
                        className="font-mono text-xs text-blue-600 hover:underline dark:text-blue-400"
                      >
                        {incident.incident_id.slice(0, 13)}…
                      </Link>
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`inline-block h-2 w-2 rounded-full ${SEVERITY_COLOR[incident.severity] ?? "bg-zinc-400"} mr-2`}
                      />
                      {incident.severity}
                    </td>
                    <td className="px-3 py-2">
                      {incident.title}
                      <div className="text-xs text-zinc-500">{incident.category}</div>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {incident.primary_asset_id ?? "—"}
                    </td>
                    <td className="px-3 py-2">{incident.detection_ids.length}</td>
                    <td className="px-3 py-2 text-xs">
                      {new Date(incident.first_seen).toLocaleString()}
                    </td>
                    <td className="px-3 py-2 uppercase text-xs">{incident.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
