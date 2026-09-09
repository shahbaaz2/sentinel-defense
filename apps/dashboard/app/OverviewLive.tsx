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

function tone(value: string) {
  const v = value.toUpperCase();
  if (["ONLINE", "ACTIVE", "NOMINAL", "READY", "AVAILABLE", "OPERATIONAL"].includes(v)) return "text-emerald-300";
  if (["DEGRADED", "UNKNOWN", "UNAVAILABLE"].includes(v)) return "text-amber-300";
  return "text-slate-300";
}

function MetricCard({ label, value, detail, accent }: { label: string; value: string; detail: string; accent?: "sky" | "amber" | "emerald" }) {
  const accentClass = accent === "amber" ? "bg-amber-400" : accent === "emerald" ? "bg-emerald-400" : "bg-sky-400";
  return (
    <div className="soc-panel rounded-lg p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="soc-kicker">{label}</p>
        <span className={`mt-1 h-1.5 w-1.5 rounded-full ${accentClass}`} />
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-white">{value}</p>
      <p className="mt-1 text-[10px] text-slate-500">{detail}</p>
    </div>
  );
}

function HealthRow({ label, status, detail }: { label: string; status: string; detail: string }) {
  const statusUpper = status.toUpperCase();
  const dot = ["ONLINE", "ACTIVE", "NOMINAL", "READY", "OPERATIONAL"].includes(statusUpper)
    ? "bg-emerald-400"
    : ["DEGRADED", "UNKNOWN", "UNAVAILABLE"].includes(statusUpper)
      ? "bg-amber-400"
      : "bg-slate-500";
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-slate-800 py-3 first:border-t-0">
      <div className="min-w-0">
        <p className="text-[11px] font-medium text-slate-300">{label}</p>
        <p className="mt-0.5 truncate text-[9px] text-slate-600">{detail}</p>
      </div>
      <span className={`flex items-center gap-2 font-mono text-[9px] font-semibold ${tone(status)}`}>
        <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />{statusUpper}
      </span>
    </div>
  );
}

const TECHNOLOGY_FABRIC = [
  ["Next.js 16", "Experience", "Runtime"],
  ["React 19", "Interactive UI", "Runtime"],
  ["Tailwind CSS 4", "Design system", "Runtime"],
  ["Vercel", "Frontend cloud", "Cloud"],
  ["FastAPI", "API services", "Runtime"],
  ["Uvicorn", "ASGI runtime", "Runtime"],
  ["Pydantic", "Schema validation", "Runtime"],
  ["httpx", "Service transport", "Runtime"],
  ["PostgreSQL", "Persistence", "Runtime"],
  ["SQLAlchemy", "Async data layer", "Runtime"],
  ["Alembic", "Migrations", "Runtime"],
  ["Suricata", "Network IDS adapter", "Live adapter"],
  ["Zeek", "Network telemetry", "Live adapter"],
  ["Splunk", "Read-only SIEM target", "Integration"],
  ["Wazuh", "Endpoint/SIEM adapter", "Contract-tested"],
  ["Falco", "Runtime sensor adapter", "Contract-tested"],
  ["DeepSeek", "AI advisory", "Provider"],
  ["MITRE ATT&CK", "Threat mapping", "Knowledge"],
  ["KEV", "Vulnerability context", "Knowledge"],
  ["Policy Engine", "Bounded response", "Control"],
] as const;

export function OverviewLive({ initialMetrics, initialAssurance }: { initialMetrics: MetricsSummary | null; initialAssurance: Assurance | null }) {
  const { snapshot, connected } = useLiveData();

  const metrics: MetricsSummary | null = snapshot
    ? {
        protected_assets: snapshot.metrics.protected_assets,
        normalized_events: snapshot.metrics.normalized_events,
        active_detections: snapshot.metrics.active_detections,
        open_incidents: snapshot.metrics.open_incidents,
        critical_high_incidents: initialMetrics?.critical_high_incidents ?? 0,
        severity_distribution: initialMetrics?.severity_distribution ?? {},
        missionnet_reachable: snapshot.missionnet_reachable,
        last_ingestion_at: snapshot.metrics.last_ingestion_at,
        ai_analyst_status: initialMetrics?.ai_analyst_status ?? "UNKNOWN",
      }
    : initialMetrics;

  const recentIncidents = snapshot?.recent_incidents ?? [];
  const criticalHigh = snapshot
    ? recentIncidents.filter((incident) => ["high", "critical"].includes(incident.severity.toLowerCase())).length
    : (initialMetrics?.critical_high_incidents ?? 0);

  const severity = metrics?.severity_distribution ?? {};
  const severityRows = ["critical", "high", "medium", "low"].map((key) => [key, Number(severity[key] ?? 0)] as const);
  const severityMax = Math.max(...severityRows.map(([, value]) => value), 1);
  const objectValues = [
    metrics?.protected_assets ?? 0,
    metrics?.normalized_events ?? 0,
    metrics?.active_detections ?? 0,
    metrics?.open_incidents ?? 0,
  ];
  const objectMax = Math.max(...objectValues, 1);

  if (!metrics) {
    return (
      <section className="soc-panel rounded-lg p-6">
        <p className="soc-kicker">Live platform state</p>
        <h2 className="mt-2 text-sm font-semibold text-white">Sentinel API is currently unreachable</h2>
        <p className="mt-2 text-xs text-slate-500">The interface remains available, but live posture metrics cannot be trusted until the API reconnects.</p>
      </section>
    );
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3 rounded border border-slate-800 bg-[#0b1723]/80 px-4 py-2.5">
        <div className="flex items-center gap-2 text-[10px] text-slate-500">
          <span className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-400" : "bg-amber-400"}`} />
          <span className={connected ? "text-emerald-300" : "text-amber-300"}>{connected ? "LIVE EVENT STREAM CONNECTED" : "RECONNECTING LIVE EVENT STREAM"}</span>
          <span className="text-slate-700">|</span>
          <span>SSE telemetry</span>
        </div>
        <div className="flex flex-wrap items-center gap-3 font-mono text-[9px] text-slate-600">
          <span>MissionNet: <strong className={metrics.missionnet_reachable ? "text-emerald-300" : "text-amber-300"}>{metrics.missionnet_reachable ? "NOMINAL" : "DEGRADED"}</strong></span>
          <span>AI: <strong className="text-slate-300">{initialAssurance?.ai_analyst_status ?? metrics.ai_analyst_status}</strong></span>
          <span>Last ingest: <strong className="text-slate-300">{metrics.last_ingestion_at ? new Date(metrics.last_ingestion_at).toLocaleTimeString() : "none"}</strong></span>
        </div>
      </div>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="Mission health" value={metrics.missionnet_reachable ? "NOMINAL" : "DEGRADED"} detail="Protected synthetic environment" accent={metrics.missionnet_reachable ? "emerald" : "amber"} />
        <MetricCard label="Protected assets" value={String(metrics.protected_assets)} detail="Asset inventory under observation" />
        <MetricCard label="Normalized events" value={metrics.normalized_events.toLocaleString()} detail="Vendor-neutral security evidence" />
        <MetricCard label="Active detections" value={String(metrics.active_detections)} detail="Deterministic rule results" accent={metrics.active_detections ? "amber" : "emerald"} />
        <MetricCard label="Open investigations" value={String(metrics.open_incidents)} detail={`${criticalHigh} critical/high in recent view`} accent={metrics.open_incidents ? "amber" : "emerald"} />
      </section>

      <section className="grid gap-5 2xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.55fr)]">
        <div className="soc-panel rounded-lg">
          <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
            <div>
              <p className="soc-kicker">Security analytics</p>
              <h2 className="mt-1 text-sm font-semibold text-white">Current Security Object Distribution</h2>
              <p className="mt-1 text-[10px] text-slate-600">Current persisted counts only — no fabricated historical trend.</p>
            </div>
            <span className="rounded border border-slate-700 bg-[#0d1b29] px-2 py-1 text-[9px] text-slate-500">LIVE SNAPSHOT</span>
          </div>
          <div className="grid gap-5 p-5 xl:grid-cols-[minmax(0,1.2fr)_280px]">
            <div>
              <div className="flex h-52 items-end gap-4 rounded border border-slate-800 bg-[#08131e] px-5 pb-5 pt-7">
                {[
                  ["Assets", metrics.protected_assets],
                  ["Events", metrics.normalized_events],
                  ["Detections", metrics.active_detections],
                  ["Incidents", metrics.open_incidents],
                ].map(([label, raw]) => {
                  const value = Number(raw);
                  return (
                    <div key={String(label)} className="flex h-full flex-1 flex-col justify-end gap-2">
                      <div className="flex flex-1 items-end justify-center">
                        <div className="relative w-full max-w-[88px] rounded-t bg-gradient-to-t from-sky-500/20 to-sky-400/80" style={{ height: `${Math.max(8, (value / objectMax) * 100)}%` }}>
                          <span className="absolute -top-5 left-1/2 -translate-x-1/2 font-mono text-[9px] text-slate-400">{value}</span>
                        </div>
                      </div>
                      <p className="text-center text-[9px] uppercase tracking-wider text-slate-600">{label}</p>
                    </div>
                  );
                })}
              </div>
              <div className="mt-4 grid grid-cols-4 gap-2 text-center">
                {["Collect", "Normalize", "Detect", "Investigate"].map((stage, index) => (
                  <div key={stage} className="relative rounded border border-slate-800 bg-[#0d1b29] px-2 py-3">
                    <div className="mx-auto mb-2 h-2 w-2 rounded-full bg-emerald-400" />
                    <p className="text-[9px] font-semibold text-slate-300">{stage}</p>
                    {index < 3 && <span className="absolute -right-[10px] top-1/2 hidden h-px w-5 bg-slate-700 xl:block" />}
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded border border-slate-800 bg-[#0d1b29] p-4">
              <p className="soc-kicker">Incident severity</p>
              <div className="mt-4 space-y-4">
                {severityRows.map(([label, value]) => {
                  const width = `${Math.max(value > 0 ? 8 : 0, (value / severityMax) * 100)}%`;
                  return (
                    <div key={label}>
                      <div className="mb-1.5 flex items-center justify-between text-[10px]">
                        <span className="capitalize text-slate-400">{label}</span>
                        <span className="font-mono text-slate-300">{value}</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-slate-800"><div className="h-full rounded-full bg-sky-400/70" style={{ width }} /></div>
                    </div>
                  );
                })}
              </div>
              <div className="mt-5 border-t border-slate-800 pt-4">
                <p className="text-[9px] uppercase tracking-wider text-slate-600">Detection authority</p>
                <p className="mt-1 text-[10px] font-semibold text-emerald-300">DETERMINISTIC RULE ENGINE</p>
                <p className="mt-2 text-[9px] leading-4 text-slate-600">AI may interpret evidence and recommend actions. It does not create the security findings shown here.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="soc-panel rounded-lg">
          <div className="border-b border-slate-800 px-5 py-4">
            <p className="soc-kicker">Service health</p>
            <h2 className="mt-1 text-sm font-semibold text-white">Operational Dependencies</h2>
          </div>
          <div className="px-5 py-2">
            <HealthRow label="MissionNet" status={metrics.missionnet_reachable ? "NOMINAL" : "DEGRADED"} detail="Protected synthetic application" />
            <HealthRow label="Sentinel API" status="ONLINE" detail="FastAPI security services" />
            <HealthRow label="Ingestion pipeline" status={metrics.last_ingestion_at ? "ACTIVE" : "UNKNOWN"} detail="Normalization and detection path" />
            <HealthRow label="PostgreSQL" status="ONLINE" detail="Security state persistence" />
            <HealthRow label="AI Analyst" status={initialAssurance?.ai_analyst_status ?? metrics.ai_analyst_status} detail={initialAssurance?.model ?? "Advisory intelligence"} />
          </div>
          <div className="border-t border-slate-800 px-5 py-4">
            <Link href="/assurance" className="text-[10px] font-semibold text-sky-400 hover:text-sky-300">Open system assurance →</Link>
          </div>
        </div>
      </section>

      <section className="soc-panel rounded-lg">
        <div className="flex flex-col justify-between gap-3 border-b border-slate-800 px-5 py-4 sm:flex-row sm:items-center">
          <div>
            <p className="soc-kicker">Platform architecture</p>
            <h2 className="mt-1 text-sm font-semibold text-white">Technology Fabric</h2>
            <p className="mt-1 text-[10px] text-slate-600">Technologies represented by the repository and supported integration boundary. Capability labels do not imply every adapter is enabled in this cloud deployment.</p>
          </div>
          <Link href="/data-sources" className="text-[10px] font-semibold text-sky-400 hover:text-sky-300">Inspect integration status →</Link>
        </div>
        <div className="grid gap-2 p-5 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5">
          {TECHNOLOGY_FABRIC.map(([name, purpose, capability]) => (
            <div key={name} className="rounded border border-slate-800 bg-[#0d1b29] p-3">
              <div className="flex items-start justify-between gap-2">
                <p className="text-[11px] font-semibold text-slate-200">{name}</p>
                <span className="rounded border border-slate-700 px-1.5 py-0.5 text-[7px] uppercase tracking-wider text-slate-600">{capability}</span>
              </div>
              <p className="mt-2 text-[9px] leading-4 text-slate-600">{purpose}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="soc-panel rounded-lg">
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <div>
            <p className="soc-kicker">Investigation queue</p>
            <h2 className="mt-1 text-sm font-semibold text-white">Recent Incidents</h2>
          </div>
          <Link href="/incidents" className="text-[10px] font-semibold text-sky-400 hover:text-sky-300">View all investigations →</Link>
        </div>
        {recentIncidents.length === 0 ? (
          <div className="p-8 text-center">
            <div className="mx-auto h-2 w-2 rounded-full bg-emerald-400" />
            <p className="mt-3 text-xs font-medium text-slate-300">No active incidents in the live feed</p>
            <p className="mt-1 text-[10px] text-slate-600">Run a controlled scenario to populate this investigation queue.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] border-collapse text-left">
              <thead className="bg-[#0d1b29] text-[9px] uppercase tracking-wider text-slate-600">
                <tr><th className="px-4 py-3">Incident</th><th className="px-4 py-3">Severity</th><th className="px-4 py-3">Title</th><th className="px-4 py-3">Primary asset</th><th className="px-4 py-3">First seen</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Detections</th></tr>
              </thead>
              <tbody className="text-[10px]">
                {recentIncidents.slice(0, 8).map((incident) => (
                  <tr key={incident.incident_id} className="border-t border-slate-800 hover:bg-slate-800/20">
                    <td className="px-4 py-3"><Link href={`/incidents/${incident.incident_id}`} className="font-mono text-sky-300 hover:text-sky-200">{incident.incident_id.slice(0, 16)}…</Link></td>
                    <td className="px-4 py-3"><span className={`rounded border px-2 py-1 text-[8px] font-semibold uppercase ${["critical", "high"].includes(incident.severity.toLowerCase()) ? "border-amber-500/30 bg-amber-500/5 text-amber-300" : "border-slate-700 text-slate-400"}`}>{incident.severity}</span></td>
                    <td className="max-w-[320px] truncate px-4 py-3 text-slate-300">{incident.title}</td>
                    <td className="px-4 py-3 font-mono text-slate-500">{incident.primary_asset_id ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-500">{new Date(incident.first_seen).toLocaleTimeString()}</td>
                    <td className="px-4 py-3 uppercase text-slate-400">{incident.status}</td>
                    <td className="px-4 py-3 text-right font-mono text-slate-300">{incident.detection_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
