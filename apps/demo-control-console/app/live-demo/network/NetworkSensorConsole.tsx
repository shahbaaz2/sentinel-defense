"use client";

import { useEffect, useRef, useState } from "react";

const DEMO_API = process.env.NEXT_PUBLIC_DEMOCONTROL_API_BASE_URL ?? "http://127.0.0.1:8100";
const POLL_MS = 1200;
const TERMINAL = new Set(["PASSED", "FAILED", "CANCELLED"]);

type TimelineEntry = { timestamp: string; message: string; level?: string; component?: string; code?: string };
type RunDetail = {
  run_id: string;
  scenario_id: string;
  status: string;
  current_step: string | null;
  failure_reason: string | null;
  started_at: string;
  completed_at: string | null;
  missionnet_event_ids: string[];
  sentinel_event_ids: string[];
  detection_ids: string[];
  incident_ids: string[];
  verification: Record<string, boolean>;
  timeline: TimelineEntry[];
};

function statusTone(status: string) {
  if (status === "PASSED") return "border-emerald-500/40 bg-emerald-500/10 text-emerald-300";
  if (status === "FAILED") return "border-red-500/40 bg-red-500/10 text-red-300";
  if (["RUNNING", "PREPARING", "VERIFYING", "WAITING_FOR_SENTINEL", "WAITING_FOR_TELEMETRY"].includes(status)) return "border-amber-500/40 bg-amber-500/10 text-amber-300";
  return "border-slate-700 bg-slate-800 text-slate-300";
}

export function NetworkSensorConsole() {
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    async function poll() {
      try {
        const response = await fetch(`${DEMO_API}/api/v1/runs/${runId}`, { cache: "no-store" });
        if (!response.ok) throw new Error(`Run status request failed (HTTP ${response.status})`);
        const data = (await response.json()) as RunDetail;
        if (cancelled) return;
        setRun(data);
        setError(null);
        if (TERMINAL.has(data.status) && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to retrieve run status");
      }
    }
    void poll();
    pollRef.current = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [runId]);

  async function startRun() {
    setStarting(true);
    setError(null);
    setRun(null);
    try {
      const response = await fetch(`${DEMO_API}/api/v1/scenarios/SCN-NET-001/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor: "portfolio-demo" }),
      });
      if (!response.ok) throw new Error(`Scenario start failed (HTTP ${response.status})`);
      const data = (await response.json()) as { run_id: string };
      setRunId(data.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start network sensor scenario");
    } finally {
      setStarting(false);
    }
  }

  const status = run?.status ?? "READY";
  const verificationPassed = run ? Object.values(run.verification).filter(Boolean).length : 0;
  const pipeline = [
    ["Traffic", "Synthetic HTTP/DNS", Boolean(runId)],
    ["PCAP", "Isolated capture", Boolean(run?.sentinel_event_ids.length || run?.detection_ids.length)],
    ["Suricata", "IDS evidence", Boolean(run?.detection_ids.length)],
    ["Zeek", "DNS telemetry", Boolean(run?.detection_ids.length)],
    ["Normalize", "Sentinel event model", Boolean(run?.sentinel_event_ids.length)],
    ["Detect", "NET-001/002/003", Boolean(run?.detection_ids.length)],
    ["Correlate", "Evidence-backed incident", Boolean(run?.incident_ids.length)],
    ["Verify", "Provenance controls", verificationPassed > 0 || status === "PASSED"],
  ] as const;

  return (
    <div className="min-h-screen bg-[#071019] text-slate-100">
      <div className="grid min-h-screen lg:grid-cols-[228px_minmax(0,1fr)]">
        <aside className="hidden border-r border-slate-800 bg-[#08131e] lg:flex lg:flex-col">
          <div className="border-b border-slate-800 px-5 py-5">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-400">Sentinel</p>
            <h1 className="mt-1 text-base font-semibold text-white">Enterprise Security</h1>
            <p className="mt-1 text-[11px] text-slate-500">Network Sensor Operations</p>
          </div>
          <nav className="flex-1 px-3 py-4 text-sm">
            {["Security Posture", "Scenario Control", "Sensor Telemetry", "Detections", "Incidents", "Evidence", "System Health"].map((label, index) => (
              <div key={label} className={`mb-1 rounded px-3 py-2.5 ${index === 1 ? "bg-sky-500/10 font-medium text-sky-300" : "text-slate-400"}`}>{label}</div>
            ))}
          </nav>
          <div className="border-t border-slate-800 p-4 text-[10px] leading-5 text-slate-500">Synthetic network lab only<br />No production target traffic</div>
        </aside>

        <main className="min-w-0">
          <header className="border-b border-slate-800 bg-[#0a1622] px-5 py-4 lg:px-7">
            <div className="flex flex-col justify-between gap-4 xl:flex-row xl:items-center">
              <div>
                <p className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Security Operations / Sensor Lab / SCN-NET-001</p>
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <h2 className="text-xl font-semibold text-white">Network Sensor Detection</h2>
                  <span className={`rounded border px-2.5 py-1 text-[10px] font-semibold ${statusTone(status)}`}>{status}</span>
                </div>
                <p className="mt-1 max-w-4xl text-xs leading-5 text-slate-400">Real Suricata and Zeek batch analysis over safe synthetic HTTP/DNS traffic, normalized into Sentinel's standard evidence, detection, and incident pipeline.</p>
              </div>
              <button onClick={startRun} disabled={starting || Boolean(run && !TERMINAL.has(run.status))} className="rounded bg-sky-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-sky-400 disabled:bg-slate-700 disabled:text-slate-400">
                {starting ? "Starting…" : run && !TERMINAL.has(run.status) ? "Run in progress" : "Start controlled run"}
              </button>
            </div>
          </header>

          <div className="space-y-5 p-5 lg:p-7">
            <section className="rounded border border-amber-500/25 bg-amber-500/5 px-4 py-3 text-[11px] leading-5 text-amber-200">
              <strong>Runtime requirement:</strong> this scenario needs Docker, Suricata, and Zeek on the Demo Control host. The cloud UI is available everywhere, but execution can fail safely when those sensor runtimes are not installed.
            </section>
            {error && <section className="rounded border border-red-500/30 bg-red-500/5 px-4 py-3 text-xs text-red-200">{error}</section>}
            {run?.failure_reason && <section className="rounded border border-red-500/30 bg-[#12151c] p-4"><p className="text-[10px] uppercase tracking-wider text-red-400">Execution detail</p><p className="mt-2 break-words font-mono text-[10px] leading-5 text-slate-400">{run.failure_reason}</p></section>}

            <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              {[
                ["Sensor events", run?.sentinel_event_ids.length ?? 0, "Normalized network evidence"],
                ["Detections", run?.detection_ids.length ?? 0, "Expected 3"],
                ["Incidents", run?.incident_ids.length ?? 0, "Expected minimum 1"],
                ["Verification", `${verificationPassed}/6`, "Evidence controls"],
                ["Run ID", runId ? runId.slice(4, 12) : "—", "Current execution"],
              ].map(([label, value, detail]) => <div key={String(label)} className="rounded border border-slate-800 bg-[#0b1723] p-4"><p className="text-[9px] uppercase tracking-wider text-slate-500">{label}</p><p className="mt-2 text-xl font-semibold text-white">{value}</p><p className="mt-1 text-[9px] text-slate-600">{detail}</p></div>)}
            </section>

            <section className="rounded border border-slate-800 bg-[#0b1723]">
              <div className="border-b border-slate-800 px-5 py-4"><h3 className="text-sm font-semibold text-white">Network security signal pipeline</h3><p className="mt-1 text-[10px] text-slate-500">Technology stages reflect real scenario evidence, not simulated progress.</p></div>
              <div className="overflow-x-auto p-5"><div className="flex min-w-[1100px] items-center">{pipeline.map(([label, detail, complete], index) => <div key={label} className="contents"><div className={`w-[118px] rounded border p-3 ${complete ? "border-emerald-500/35 bg-emerald-500/5" : "border-slate-700 bg-[#0d1b29]"}`}><div className="flex items-center gap-2"><span className={`h-2 w-2 rounded-full ${complete ? "bg-emerald-400" : "bg-slate-600"}`} /><p className="text-xs font-semibold text-slate-100">{label}</p></div><p className="mt-2 text-[9px] leading-4 text-slate-500">{detail}</p></div>{index < pipeline.length - 1 && <div className={`mx-2 h-px w-6 ${complete ? "bg-emerald-500/50" : "bg-slate-700"}`} />}</div>)}</div></div>
            </section>

            <div className="grid gap-5 xl:grid-cols-2">
              <section className="rounded border border-slate-800 bg-[#0b1723]"><div className="border-b border-slate-800 px-5 py-4"><h3 className="text-sm font-semibold text-white">Expected network analytics</h3></div><div className="divide-y divide-slate-800">{[["NET-001","Suricata alert evidence"],["NET-002","Zeek DNS evidence"],["NET-003","Cross-sensor correlation"]].map(([id,label],index)=><div key={id} className="grid grid-cols-[90px_1fr_80px] gap-3 px-4 py-3 text-[10px]"><span className="font-mono text-sky-300">{id}</span><span className="text-slate-300">{label}</span><span className={`text-right font-semibold ${index < (run?.detection_ids.length ?? 0) ? "text-emerald-300" : "text-slate-600"}`}>{index < (run?.detection_ids.length ?? 0) ? "OBSERVED" : "PENDING"}</span></div>)}</div></section>
              <section className="rounded border border-slate-800 bg-[#0b1723]"><div className="border-b border-slate-800 px-5 py-4"><h3 className="text-sm font-semibold text-white">Technology fabric</h3></div><div className="grid grid-cols-2 gap-2 p-4 text-[10px]">{[["Docker","Isolated bridge runtime"],["tcpdump/PCAP","Packet capture"],["Suricata","IDS analysis"],["Zeek","Network telemetry"],["FastAPI","Control/API plane"],["PostgreSQL","Evidence persistence"],["Sentinel","Detection + correlation"],["Vercel","Operator GUI"]].map(([name,detail])=><div key={name} className="rounded border border-slate-800 bg-[#0d1b29] p-3"><p className="font-semibold text-slate-200">{name}</p><p className="mt-1 text-[9px] text-slate-600">{detail}</p></div>)}</div></section>
            </div>

            <section className="rounded border border-slate-800 bg-[#0b1723]"><div className="border-b border-slate-800 px-5 py-4"><h3 className="text-sm font-semibold text-white">Operational event stream</h3></div><div className="max-h-[360px] overflow-auto"><table className="w-full min-w-[760px] text-left text-[10px]"><thead className="sticky top-0 bg-[#0d1b29] uppercase tracking-wider text-slate-600"><tr><th className="px-4 py-3">Time</th><th className="px-4 py-3">Level</th><th className="px-4 py-3">Component</th><th className="px-4 py-3">Code</th><th className="px-4 py-3">Event</th></tr></thead><tbody>{(run?.timeline ?? []).map((entry,index)=><tr key={`${entry.timestamp}-${index}`} className="border-t border-slate-800"><td className="px-4 py-3 font-mono text-slate-500">{new Date(entry.timestamp).toLocaleTimeString()}</td><td className="px-4 py-3 text-slate-400">{entry.level ?? "INFO"}</td><td className="px-4 py-3 text-slate-400">{entry.component ?? "Demo Control"}</td><td className="px-4 py-3 font-mono text-slate-600">{entry.code ?? "—"}</td><td className="px-4 py-3 text-slate-300">{entry.message}</td></tr>)}{!run?.timeline.length && <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-600">No network scenario events recorded yet.</td></tr>}</tbody></table></div></section>
          </div>
        </main>
      </div>
    </div>
  );
}
