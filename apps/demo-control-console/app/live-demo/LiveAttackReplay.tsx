"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const DEMO_API =
  process.env.NEXT_PUBLIC_DEMOCONTROL_API_BASE_URL ?? "http://127.0.0.1:8100";
const SENTINEL_DASHBOARD =
  process.env.NEXT_PUBLIC_SENTINEL_DASHBOARD_URL ?? "https://sentinel-defense-g6id.vercel.app";

const POLL_MS = 1200;
const REPLAY_MS = 2400;
const TERMINAL = new Set(["PASSED", "FAILED", "CANCELLED"]);

type TimelineEntry = { timestamp: string; message: string };
type RunDetail = {
  run_id: string;
  scenario_id: string;
  status: string;
  current_step: string | null;
  failure_reason: string | null;
  started_at: string;
  completed_at: string | null;
  step_results: { step_id: string; action: string; target: string }[];
  timeline: TimelineEntry[];
  missionnet_event_ids: string[];
  sentinel_event_ids: string[];
  detection_ids: string[];
  incident_ids: string[];
  verification: Record<string, boolean>;
  reset_status: string | null;
};

type Stage = {
  kicker: string;
  title: string;
  description: string;
};

const STAGES: Stage[] = [
  {
    kicker: "00 · BASELINE",
    title: "MissionNet operating normally",
    description: "Synthetic mission services are nominal. Sentinel is watching the evidence stream.",
  },
  {
    kicker: "01 · IDENTITY PRESSURE",
    title: "Rapid authentication failures begin",
    description: "The synthetic adversary repeatedly pressures u-operator-01. MissionNet emits real lab audit events.",
  },
  {
    kicker: "02 · MISSION SIGNAL ANOMALY",
    title: "A critical service degrades",
    description: "mission-data-api-01 enters a degraded state while anomalous telemetry appears in the same scenario window.",
  },
  {
    kicker: "03 · DETERMINISTIC DETECTION",
    title: "Sentinel rules fire from observed evidence",
    description: "The detection plane evaluates normalized events. The AI does not create these detections.",
  },
  {
    kicker: "04 · CORRELATION",
    title: "Multiple signals become an incident",
    description: "Related detections are joined by deterministic correlation into evidence-backed incident records.",
  },
  {
    kicker: "05 · PROVENANCE CHECK",
    title: "The evidence chain is verified",
    description: "Demo Control verifies MissionNet events, Sentinel normalization, detections, incidents, and evidence links.",
  },
  {
    kicker: "06 · HUMAN DECISION BOUNDARY",
    title: "AI assistance and bounded response are ready",
    description: "Open the resulting incident to run the configured AI Analyst, review its recommendation, and approve a bounded response.",
  },
];

function Node({
  label,
  sublabel,
  state,
}: {
  label: string;
  sublabel: string;
  state: "idle" | "danger" | "active" | "verified";
}) {
  const styles = {
    idle: "border-zinc-800 bg-zinc-950 text-zinc-500",
    danger: "border-red-500/70 bg-red-950/30 text-red-300 shadow-[0_0_30px_rgba(239,68,68,0.15)]",
    active: "border-cyan-500/70 bg-cyan-950/20 text-cyan-200 shadow-[0_0_30px_rgba(34,211,238,0.14)]",
    verified:
      "border-emerald-500/70 bg-emerald-950/20 text-emerald-200 shadow-[0_0_30px_rgba(16,185,129,0.14)]",
  }[state];

  return (
    <div className={`relative min-w-0 rounded-xl border p-4 transition-all duration-700 ${styles}`}>
      <div className="mb-3 flex items-center gap-2">
        <span
          className={`h-2 w-2 rounded-full ${
            state === "danger"
              ? "bg-red-400 animate-pulse"
              : state === "active"
                ? "bg-cyan-400 animate-pulse"
                : state === "verified"
                  ? "bg-emerald-400"
                  : "bg-zinc-700"
          }`}
        />
        <span className="text-[10px] font-semibold uppercase tracking-[0.24em] opacity-70">
          {sublabel}
        </span>
      </div>
      <p className="truncate text-sm font-semibold text-white">{label}</p>
    </div>
  );
}

function LinkBar({ active, danger = false }: { active: boolean; danger?: boolean }) {
  return (
    <div className="relative flex h-8 items-center overflow-hidden">
      <div
        className={`h-px w-full transition-all duration-700 ${
          active ? (danger ? "bg-red-500/70" : "bg-cyan-400/70") : "bg-zinc-800"
        }`}
      />
      {active && (
        <span
          className={`attack-packet absolute h-1.5 w-1.5 rounded-full ${danger ? "bg-red-300" : "bg-cyan-200"}`}
        />
      )}
    </div>
  );
}

export function LiveAttackReplay() {
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visualStage, setVisualStage] = useState(0);
  const [paused, setPaused] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const actualGate = useMemo(() => {
    if (!run) return runId ? 1 : 0;
    let gate = 0;
    if (run.step_results.length > 0 || run.timeline.length > 1) gate = 1;
    if (run.step_results.length >= 2 || run.missionnet_event_ids.length >= 2) gate = 2;
    if (run.detection_ids.length > 0) gate = 3;
    if (run.incident_ids.length > 0) gate = 4;
    if (Object.values(run.verification).some(Boolean)) gate = 5;
    if (run.status === "PASSED") gate = 6;
    return gate;
  }, [run, runId]);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;

    async function poll() {
      try {
        const res = await fetch(`${DEMO_API}/api/v1/runs/${runId}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`run fetch failed: ${res.status}`);
        const data: RunDetail = await res.json();
        if (cancelled) return;
        setRun(data);
        setError(null);
        if (TERMINAL.has(data.status) && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "run poll failed");
      }
    }

    poll();
    pollRef.current = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [runId]);

  useEffect(() => {
    if (!runId || paused) return;
    const timer = setInterval(() => {
      setVisualStage((current) => (current < actualGate ? current + 1 : current));
    }, REPLAY_MS);
    return () => clearInterval(timer);
  }, [runId, paused, actualGate]);

  async function startReplay() {
    setStarting(true);
    setError(null);
    setRun(null);
    setRunId(null);
    setVisualStage(0);
    setPaused(false);
    try {
      const res = await fetch(`${DEMO_API}/api/v1/scenarios/SCN-010/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor: "portfolio-demo" }),
      });
      if (!res.ok) throw new Error(`scenario start failed: ${res.status}`);
      const started = await res.json();
      setRunId(started.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed to start SCN-010");
    } finally {
      setStarting(false);
    }
  }

  async function resetLab() {
    if (!runId) return;
    await fetch(`${DEMO_API}/api/v1/runs/${runId}/reset`, { method: "POST" });
  }

  const stage = STAGES[visualStage];
  const primaryIncident = run?.incident_ids[1] ?? run?.incident_ids[0] ?? null;
  const runFinished = run ? TERMINAL.has(run.status) : false;

  return (
    <div className="min-h-screen bg-[#020406] font-mono text-zinc-100">
      <style>{`
        @keyframes packetMove { 0% { left: 0%; opacity: 0; } 12% { opacity: 1; } 88% { opacity: 1; } 100% { left: calc(100% - 6px); opacity: 0; } }
        .attack-packet { animation: packetMove 1.35s linear infinite; }
        @keyframes scan { 0% { transform: translateY(-10%); opacity: 0; } 20% { opacity: .7; } 80% { opacity: .7; } 100% { transform: translateY(410px); opacity: 0; } }
        .scanline { animation: scan 4s linear infinite; }
      `}</style>

      <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-5 py-8 lg:px-8">
        <header className="flex flex-col justify-between gap-4 border-b border-zinc-900 pb-5 lg:flex-row lg:items-end">
          <div>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className="rounded border border-red-900 bg-red-950/40 px-2 py-1 text-[10px] font-semibold tracking-[0.2em] text-red-300">
                SYNTHETIC ADVERSARY SIMULATION
              </span>
              <span className="rounded border border-cyan-900 bg-cyan-950/30 px-2 py-1 text-[10px] font-semibold tracking-[0.2em] text-cyan-300">
                REAL SENTINEL PIPELINE
              </span>
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
              SCN-010 · LIVE ATTACK REPLAY
            </h1>
            <p className="mt-2 max-w-3xl text-xs leading-5 text-zinc-500">
              A paced GUI replay of a constrained MissionNet adversary scenario. The visualization is synthetic;
              the resulting MissionNet events, Sentinel detections, incident IDs, and verification results come from
              the running cloud prototype.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {!runId ? (
              <button
                onClick={startReplay}
                disabled={starting}
                className="rounded-lg bg-cyan-400 px-5 py-2.5 text-xs font-bold uppercase tracking-wider text-black hover:bg-cyan-300 disabled:opacity-50"
              >
                {starting ? "Starting…" : "▶ Start Immersive Demo"}
              </button>
            ) : (
              <>
                <button
                  onClick={() => setPaused((v) => !v)}
                  className="rounded-lg border border-zinc-700 px-4 py-2 text-xs text-zinc-300 hover:border-cyan-700 hover:text-cyan-300"
                >
                  {paused ? "▶ Resume" : "Ⅱ Pause"}
                </button>
                <button
                  onClick={() => setVisualStage((v) => Math.min(actualGate, v + 1))}
                  disabled={visualStage >= actualGate}
                  className="rounded-lg border border-zinc-700 px-4 py-2 text-xs text-zinc-300 hover:border-cyan-700 hover:text-cyan-300 disabled:opacity-30"
                >
                  Next →
                </button>
              </>
            )}
          </div>
        </header>

        {error && (
          <div className="rounded-lg border border-red-900 bg-red-950/30 px-4 py-3 text-xs text-red-300">
            {error}
          </div>
        )}

        <section className="grid gap-4 lg:grid-cols-[1fr_310px]">
          <div className="relative overflow-hidden rounded-2xl border border-zinc-900 bg-zinc-950/40 p-5 sm:p-7">
            <div className="scanline pointer-events-none absolute left-0 top-0 h-px w-full bg-gradient-to-r from-transparent via-cyan-400/40 to-transparent" />
            <div className="mb-6 flex items-center justify-between gap-4">
              <div>
                <p className="text-[10px] font-semibold tracking-[0.26em] text-cyan-400">{stage.kicker}</p>
                <h2 className="mt-1 text-lg font-semibold text-white">{stage.title}</h2>
                <p className="mt-1 max-w-2xl text-xs leading-5 text-zinc-500">{stage.description}</p>
              </div>
              <div className="text-right">
                <p className="text-[10px] uppercase tracking-widest text-zinc-600">Replay</p>
                <p className="text-xl font-semibold text-white">{String(visualStage + 1).padStart(2, "0")}/{String(STAGES.length).padStart(2, "0")}</p>
              </div>
            </div>

            <div className="mb-6 grid grid-cols-7 gap-1">
              {STAGES.map((item, index) => (
                <button
                  key={item.kicker}
                  onClick={() => index <= actualGate && setVisualStage(index)}
                  className={`h-1.5 rounded-full transition-all ${
                    index <= visualStage
                      ? index <= actualGate
                        ? "bg-cyan-400"
                        : "bg-zinc-800"
                      : "bg-zinc-900"
                  }`}
                  title={item.title}
                />
              ))}
            </div>

            <div className="grid items-center gap-3 md:grid-cols-[1fr_70px_1fr_70px_1fr]">
              <Node
                label="Synthetic Adversary"
                sublabel="External actor"
                state={visualStage >= 1 ? "danger" : "idle"}
              />
              <LinkBar active={visualStage >= 1} danger />
              <div className="flex flex-col gap-3">
                <Node
                  label="u-operator-01"
                  sublabel="Mission identity"
                  state={visualStage >= 1 ? "danger" : "idle"}
                />
                <Node
                  label="mission-data-api-01"
                  sublabel="Criticality 5 service"
                  state={visualStage >= 2 ? "danger" : "idle"}
                />
              </div>
              <LinkBar active={visualStage >= 3} />
              <div className="flex flex-col gap-3">
                <Node
                  label="Detection Engine"
                  sublabel="Deterministic rules"
                  state={visualStage >= 3 ? "active" : "idle"}
                />
                <Node
                  label="Incident Correlator"
                  sublabel="Evidence graph"
                  state={visualStage >= 4 ? "active" : "idle"}
                />
                <Node
                  label="AI + Response Guardrail"
                  sublabel="Human-approved only"
                  state={visualStage >= 6 ? "verified" : "idle"}
                />
              </div>
            </div>

            <div className="mt-7 grid gap-3 sm:grid-cols-4">
              {[
                ["MissionNet events", run?.missionnet_event_ids.length ?? 0],
                ["Sentinel events", run?.sentinel_event_ids.length ?? 0],
                ["Detections", run?.detection_ids.length ?? 0],
                ["Incidents", run?.incident_ids.length ?? 0],
              ].map(([label, value]) => (
                <div key={String(label)} className="rounded-lg border border-zinc-900 bg-black/40 p-3">
                  <p className="text-[10px] uppercase tracking-widest text-zinc-600">{label}</p>
                  <p className="mt-1 text-2xl font-semibold text-white">{value}</p>
                </div>
              ))}
            </div>
          </div>

          <aside className="flex flex-col gap-4">
            <div className="rounded-2xl border border-zinc-900 bg-zinc-950/50 p-4">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-500">Run status</p>
                <span
                  className={`rounded-full px-2 py-1 text-[10px] font-bold ${
                    run?.status === "PASSED"
                      ? "bg-emerald-500 text-black"
                      : run?.status === "FAILED"
                        ? "bg-red-500 text-black"
                        : runId
                          ? "bg-amber-400 text-black animate-pulse"
                          : "bg-zinc-800 text-zinc-500"
                  }`}
                >
                  {run?.status ?? (runId ? "RUNNING" : "READY")}
                </span>
              </div>
              <p className="break-all text-[11px] text-zinc-600">{runId ?? "No run started"}</p>
              {run?.current_step && <p className="mt-2 text-xs text-cyan-300">{run.current_step}</p>}
            </div>

            <div className="rounded-2xl border border-zinc-900 bg-zinc-950/50 p-4">
              <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-500">Evidence verification</p>
              <div className="space-y-2 text-xs">
                {[
                  ["Mission event", run?.verification.missionnet_event_observed],
                  ["Normalized", run?.verification.normalized_event_observed],
                  ["Detection", run?.verification.expected_detection_observed],
                  ["Incident", run?.verification.incident_created],
                  ["Evidence link", run?.verification.evidence_link_verified],
                ].map(([label, value]) => (
                  <div key={String(label)} className="flex items-center justify-between border-b border-zinc-900 pb-2 last:border-0 last:pb-0">
                    <span className="text-zinc-500">{label}</span>
                    <span className={value ? "text-emerald-400" : "text-zinc-700"}>{value ? "VERIFIED" : "WAITING"}</span>
                  </div>
                ))}
              </div>
            </div>

            {runFinished && primaryIncident && (
              <div className="rounded-2xl border border-emerald-900 bg-emerald-950/20 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-emerald-400">Analyst handoff</p>
                <p className="mt-2 text-xs leading-5 text-zinc-400">
                  The attack replay has produced real Sentinel incident evidence. Continue into the SOC workflow for AI analysis and human-approved response.
                </p>
                <a
                  href={`${SENTINEL_DASHBOARD}/incidents/${primaryIncident}`}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-4 block rounded-lg bg-emerald-400 px-3 py-2 text-center text-[11px] font-bold uppercase tracking-wider text-black hover:bg-emerald-300"
                >
                  Continue to AI + Response ↗
                </a>
                <button
                  onClick={resetLab}
                  className="mt-2 w-full rounded-lg border border-zinc-800 px-3 py-2 text-[11px] text-zinc-500 hover:text-zinc-300"
                >
                  Reset synthetic lab
                </button>
              </div>
            )}
          </aside>
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-zinc-900 bg-black p-4">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-500">Live evidence stream</p>
              <span className="text-[10px] text-zinc-700">Demo Control telemetry</span>
            </div>
            <div className="max-h-64 space-y-2 overflow-auto text-[11px] leading-5">
              {(run?.timeline ?? []).slice(-12).map((entry, index) => (
                <div key={`${entry.timestamp}-${index}`} className="grid grid-cols-[82px_1fr] gap-3 border-b border-zinc-950 pb-2">
                  <span className="text-zinc-700">{new Date(entry.timestamp).toLocaleTimeString()}</span>
                  <span className="text-zinc-400">{entry.message}</span>
                </div>
              ))}
              {!run?.timeline.length && <p className="text-zinc-700">Awaiting scenario start…</p>}
            </div>
          </div>

          <div className="rounded-2xl border border-zinc-900 bg-zinc-950/40 p-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-500">What an employer is seeing</p>
            <div className="mt-4 grid gap-3 text-xs text-zinc-400 sm:grid-cols-2">
              <div className="rounded-lg border border-zinc-900 p-3">
                <p className="font-semibold text-white">Attack realism</p>
                <p className="mt-1 leading-5 text-zinc-600">Credential pressure plus a mission-service telemetry anomaly in a constrained synthetic environment.</p>
              </div>
              <div className="rounded-lg border border-zinc-900 p-3">
                <p className="font-semibold text-white">Detection integrity</p>
                <p className="mt-1 leading-5 text-zinc-600">Detections and incidents come from deterministic Sentinel logic, not from the LLM.</p>
              </div>
              <div className="rounded-lg border border-zinc-900 p-3">
                <p className="font-semibold text-white">AI guardrail</p>
                <p className="mt-1 leading-5 text-zinc-600">AI is advisory and evidence-grounded. It cannot silently create detections or execute response actions.</p>
              </div>
              <div className="rounded-lg border border-zinc-900 p-3">
                <p className="font-semibold text-white">Response control</p>
                <p className="mt-1 leading-5 text-zinc-600">Containment actions remain policy-bounded and require explicit human approval.</p>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
