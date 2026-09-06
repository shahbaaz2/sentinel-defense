"use client";

import Link from "next/link";
import { useLiveData } from "./LiveDataProvider";

type Assurance = {
  inference_location: string;
  external_ai_api: string;
  model: string;
  ai_analyst_status: string;
};

type MetricsSummary = {
  protected_assets: number;
  normalized_events: number;
  active_detections: number;
  open_incidents: number;
  critical_high_incidents: number;
  severity_distribution: Record<string, number>;
  missionnet_reachable: boolean;
  last_ingestion_at: string | null;
  ai_analyst_status: string;
};

function Card({ label, value, tone }: { label: string; value: string; tone?: "warn" | "ok" }) {
  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</p>
      <p
        className={`mt-1 text-2xl font-semibold ${
          tone === "warn"
            ? "text-amber-600 dark:text-amber-400"
            : tone === "ok"
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-black dark:text-zinc-50"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

function SourceHealthRow({ label, status }: { label: string; status: "ok" | "warn" | "off" }) {
  const color =
    status === "ok" ? "bg-emerald-500" : status === "warn" ? "bg-amber-500" : "bg-zinc-400";
  const text = status === "ok" ? "ONLINE" : status === "warn" ? "DEGRADED" : "NOT CONFIGURED";
  return (
    <div className="flex items-center justify-between border-t border-zinc-200 py-2 text-sm first:border-t-0 dark:border-zinc-800">
      <span className="text-zinc-600 dark:text-zinc-400">{label}</span>
      <span className="flex items-center gap-2 font-mono text-xs">
        <span className={`h-2 w-2 rounded-full ${color}`} />
        {text}
      </span>
    </div>
  );
}

export function OverviewLive({
  initialMetrics,
  initialAssurance,
}: {
  initialMetrics: MetricsSummary | null;
  initialAssurance: Assurance | null;
}) {
  const { snapshot, connected } = useLiveData();

  const metrics: MetricsSummary | null = snapshot
    ? {
        protected_assets: snapshot.metrics.protected_assets,
        normalized_events: snapshot.metrics.normalized_events,
        active_detections: snapshot.metrics.active_detections,
        open_incidents: snapshot.metrics.open_incidents,
        critical_high_incidents:
          initialMetrics?.critical_high_incidents ?? 0, // refined further below from recent_incidents
        severity_distribution: initialMetrics?.severity_distribution ?? {},
        missionnet_reachable: snapshot.missionnet_reachable,
        last_ingestion_at: snapshot.metrics.last_ingestion_at,
        ai_analyst_status: initialMetrics?.ai_analyst_status ?? "NOT_ENABLED",
      }
    : initialMetrics;

  const recentIncidents = snapshot?.recent_incidents ?? [];
  const criticalHigh = snapshot
    ? recentIncidents.filter((i) => i.severity === "high" || i.severity === "critical").length
    : (initialMetrics?.critical_high_incidents ?? 0);

  return (
    <>
      <div className="flex items-center gap-2 text-xs">
        <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-500" : "bg-zinc-400"}`} />
        <span className="text-zinc-500">
          {connected ? "Live — updating automatically" : "Connecting to live feed…"}
        </span>
      </div>

      {metrics ? (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Card label="Mission/System Health" value={metrics.missionnet_reachable ? "NOMINAL" : "DEGRADED"} tone={metrics.missionnet_reachable ? "ok" : "warn"} />
            <Card
              label="Open Incidents"
              value={String(metrics.open_incidents)}
              tone={metrics.open_incidents > 0 ? "warn" : "ok"}
            />
            <Card
              label="Critical/High Incidents"
              value={String(criticalHigh)}
              tone={criticalHigh > 0 ? "warn" : "ok"}
            />
            <Card label="Protected Assets" value={String(metrics.protected_assets)} />
            <Card label="Active Detections" value={String(metrics.active_detections)} />
            <Card label="Events Ingested" value={String(metrics.normalized_events)} />
            <Card
              label="Last Ingestion"
              value={
                metrics.last_ingestion_at
                  ? new Date(metrics.last_ingestion_at).toLocaleTimeString()
                  : "never"
              }
            />
            <Card
              label="Ingestion Health"
              value={metrics.last_ingestion_at ? "ACTIVE" : "NO DATA YET"}
              tone={metrics.last_ingestion_at ? "ok" : "warn"}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
              <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-zinc-500">
                Sensor / Source Health
              </h2>
              <SourceHealthRow
                label="MissionNet Adapter"
                status={metrics.missionnet_reachable ? "ok" : "warn"}
              />
              <SourceHealthRow label="Sentinel Ingestion Worker" status="ok" />
              <SourceHealthRow label="Database" status="ok" />
              <SourceHealthRow label="Demo Control connectivity" status="ok" />
              <SourceHealthRow label="Wazuh" status="off" />
              <SourceHealthRow label="Splunk" status="off" />
              <SourceHealthRow label="Suricata" status="off" />
              <SourceHealthRow label="Zeek" status="off" />
              <SourceHealthRow label="Falco" status="off" />
            </div>

            <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
                AI &amp; Deployment
              </h2>
              <div className="flex flex-col gap-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-zinc-500">AI Analyst</span>
                  <span className="font-mono">{initialAssurance?.ai_analyst_status ?? "NOT ENABLED"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">External AI API</span>
                  <span className="font-mono text-emerald-600 dark:text-emerald-400">
                    {initialAssurance?.external_ai_api ?? "DISABLED"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Inference Location</span>
                  <span className="font-mono">{initialAssurance?.inference_location ?? "local"}</span>
                </div>
              </div>
            </div>
          </div>

          <div>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
              Recent Incidents
            </h2>
            {recentIncidents.length === 0 ? (
              <p className="text-sm text-zinc-500">
                No active incidents. Environment is currently nominal.
              </p>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
                <table className="w-full text-left text-sm">
                  <thead className="bg-zinc-100 text-xs uppercase text-zinc-500 dark:bg-zinc-900">
                    <tr>
                      <th className="px-3 py-2">ID</th>
                      <th className="px-3 py-2">Severity</th>
                      <th className="px-3 py-2">Title</th>
                      <th className="px-3 py-2">Asset</th>
                      <th className="px-3 py-2">First Seen</th>
                      <th className="px-3 py-2">Status</th>
                      <th className="px-3 py-2">Detections</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentIncidents.slice(0, 10).map((incident) => (
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
                        <td className="px-3 py-2 uppercase">{incident.severity}</td>
                        <td className="px-3 py-2">{incident.title}</td>
                        <td className="px-3 py-2 font-mono text-xs">
                          {incident.primary_asset_id ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-xs">
                          {new Date(incident.first_seen).toLocaleTimeString()}
                        </td>
                        <td className="px-3 py-2 uppercase">{incident.status}</td>
                        <td className="px-3 py-2">{incident.detection_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      ) : (
        <p className="text-sm text-red-600 dark:text-red-400">Sentinel API unreachable.</p>
      )}

      <Link
        href="/incidents"
        className="w-fit rounded-full bg-black px-5 py-2 text-sm font-medium text-white dark:bg-white dark:text-black"
      >
        View Live Incidents →
      </Link>
    </>
  );
}
