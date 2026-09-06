"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useLiveData } from "../LiveDataProvider";

type Incident = {
  incident_id: string;
  title: string;
  severity: string;
  status: string;
  category: string;
  primary_asset_id: string | null;
  assigned_to: string | null;
  detection_ids: string[];
  first_seen: string;
};

const SEVERITY_COLOR: Record<string, string> = {
  low: "bg-zinc-400",
  medium: "bg-amber-500",
  high: "bg-orange-600",
  critical: "bg-red-600",
};

export function IncidentsLive({ initialIncidents }: { initialIncidents: Incident[] | null }) {
  const { snapshot, connected } = useLiveData();
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  const incidents: Incident[] | null = useMemo(() => {
    if (connected && snapshot) {
      return snapshot.recent_incidents.map((i) => ({
        incident_id: i.incident_id,
        title: i.title,
        severity: i.severity,
        status: i.status,
        category: "",
        primary_asset_id: i.primary_asset_id,
        assigned_to: null,
        detection_ids: Array.from({ length: i.detection_count }),
        first_seen: i.first_seen,
      }));
    }
    return initialIncidents;
  }, [connected, snapshot, initialIncidents]);

  const filtered = (incidents ?? []).filter(
    (i) =>
      (!severityFilter || i.severity === severityFilter) &&
      (!statusFilter || i.status === statusFilter)
  );

  return (
    <>
      <div className="flex items-center gap-3 text-xs">
        <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-500" : "bg-zinc-400"}`} />
        <span className="text-zinc-500">{connected ? "Live" : "Static (connecting…)"}</span>

        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="ml-4 rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
        >
          <option value="">All severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
        >
          <option value="">All statuses</option>
          <option value="OPEN">Open</option>
          <option value="INVESTIGATING">Investigating</option>
          <option value="MONITORING">Monitoring</option>
          <option value="RESOLVED">Resolved</option>
          <option value="DISMISSED">Dismissed</option>
        </select>
      </div>

      {incidents === null && (
        <p className="text-sm text-red-600 dark:text-red-400">Sentinel API unreachable.</p>
      )}
      {incidents !== null && filtered.length === 0 && (
        <p className="text-sm text-zinc-500">
          No active incidents. Environment is currently nominal.
        </p>
      )}
      {incidents !== null && filtered.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-zinc-100 text-xs uppercase text-zinc-500 dark:bg-zinc-900">
              <tr>
                <th className="px-3 py-2">ID</th>
                <th className="px-3 py-2">Severity</th>
                <th className="px-3 py-2">Title</th>
                <th className="px-3 py-2">Affected Asset</th>
                <th className="px-3 py-2">Detections</th>
                <th className="px-3 py-2">First Seen</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Assigned</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((incident) => (
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
                    {incident.severity.toUpperCase()}
                  </td>
                  <td className="px-3 py-2">
                    {incident.title}
                    {incident.category && (
                      <div className="text-xs text-zinc-500">{incident.category}</div>
                    )}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {incident.primary_asset_id ?? "—"}
                  </td>
                  <td className="px-3 py-2">{incident.detection_ids.length}</td>
                  <td className="px-3 py-2 text-xs">
                    {new Date(incident.first_seen).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 uppercase text-xs">{incident.status}</td>
                  <td className="px-3 py-2 text-xs">{incident.assigned_to ?? "unassigned"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
