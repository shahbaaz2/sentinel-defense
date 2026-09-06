const MISSIONNET_API_BASE = process.env.MISSIONNET_API_BASE_URL ?? "http://127.0.0.1:8090";

type Health = {
  status: string;
  classification: string;
  service: string;
  degraded_assets: string[];
  quarantined_assets: string[];
};

type Asset = {
  asset_id: string;
  name: string;
  asset_type: string;
  mission_role: string;
  criticality: number;
  status: string;
  network_state: string;
  classification: string;
};

type AuditEvent = {
  audit_id: string;
  timestamp: string;
  actor_type: string;
  actor_id: string;
  action: string;
  object_type: string;
  object_id: string;
  severity: string;
};

async function getJSON<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${MISSIONNET_API_BASE}${path}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

const ROLE_LABELS: Record<string, string> = {
  identity: "Identity",
  gateway: "API Gateway",
  data: "Mission Data",
  comms: "Communications",
  "operator-console": "Operator Console",
  edge: "Telemetry / Edge",
};

const STATUS_COLOR: Record<string, string> = {
  nominal: "bg-emerald-500",
  degraded: "bg-amber-500",
  quarantined: "bg-red-500",
  contained: "bg-red-500",
  recovering: "bg-blue-500",
};

export default async function Home() {
  const [health, assets, audit] = await Promise.all([
    getJSON<Health>("/health"),
    getJSON<Asset[]>("/assets"),
    getJSON<AuditEvent[]>("/audit"),
  ]);

  const serviceRoles = ["identity", "gateway", "data", "comms", "operator-console", "edge"];
  const assetsByRole = (role: string) => (assets ?? []).filter((a) => a.mission_role === role);

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-4xl flex-col gap-8 px-8 py-16">
        <div className="flex flex-col gap-3">
          <span className="w-fit rounded bg-amber-500/20 px-2 py-1 text-xs font-semibold tracking-wide text-amber-700 dark:text-amber-400">
            SYNTHETIC LAB — FICTIONAL DATA ONLY
          </span>
          <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
            MissionNet Operations Console
          </h1>
          <p className="text-zinc-600 dark:text-zinc-400">
            Fictional mission-information system. All assets, users, and records below are
            synthetic — nothing here represents a real operational system.
          </p>
        </div>

        <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
              Mission System Status
            </h2>
            {health && (
              <span
                className={`flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold text-white ${STATUS_COLOR[health.status] ?? "bg-zinc-500"}`}
              >
                {health.status.toUpperCase()}
              </span>
            )}
          </div>
          {!health && (
            <p className="mt-2 text-sm text-red-600 dark:text-red-400">
              MissionNet API unreachable at {MISSIONNET_API_BASE}. Run <code>make missionnet</code>.
            </p>
          )}
        </div>

        {assets && (
          <div>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
              Services
            </h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {serviceRoles.map((role) => {
                const roleAssets = assetsByRole(role);
                if (roleAssets.length === 0) return null;
                const healthy = roleAssets.every((a) => a.status === "nominal");
                return (
                  <div
                    key={role}
                    className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800"
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={`h-2 w-2 rounded-full ${healthy ? "bg-emerald-500" : "bg-amber-500"}`}
                      />
                      <span className="text-sm font-medium text-black dark:text-zinc-50">
                        {ROLE_LABELS[role] ?? role}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-zinc-500">
                      {roleAssets.length} asset{roleAssets.length !== 1 ? "s" : ""}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {assets && (
          <div>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
              Assets ({assets.length})
            </h2>
            <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-100 text-xs uppercase text-zinc-500 dark:bg-zinc-900">
                  <tr>
                    <th className="px-3 py-2">Asset</th>
                    <th className="px-3 py-2">Role</th>
                    <th className="px-3 py-2">Criticality</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Network</th>
                  </tr>
                </thead>
                <tbody>
                  {assets.map((a) => (
                    <tr key={a.asset_id} className="border-t border-zinc-200 dark:border-zinc-800">
                      <td className="px-3 py-2 font-mono">{a.asset_id}</td>
                      <td className="px-3 py-2">{ROLE_LABELS[a.mission_role] ?? a.mission_role}</td>
                      <td className="px-3 py-2">{a.criticality}</td>
                      <td className="px-3 py-2">
                        <span
                          className={`inline-block h-2 w-2 rounded-full ${STATUS_COLOR[a.status] ?? "bg-zinc-500"} mr-2`}
                        />
                        {a.status}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs">{a.network_state}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {audit && audit.length > 0 && (
          <div>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
              Recent Operations Events
            </h2>
            <ul className="flex flex-col gap-2">
              {audit.slice(0, 10).map((e) => (
                <li
                  key={e.audit_id}
                  className="rounded border border-zinc-200 px-3 py-2 text-xs dark:border-zinc-800"
                >
                  <span className="font-mono text-zinc-500">
                    {new Date(e.timestamp).toLocaleTimeString()}
                  </span>{" "}
                  <span className="font-medium">{e.action}</span> on{" "}
                  <span className="font-mono">{e.object_id}</span> by {e.actor_type}/{e.actor_id}
                </li>
              ))}
            </ul>
          </div>
        )}
      </main>
    </div>
  );
}
