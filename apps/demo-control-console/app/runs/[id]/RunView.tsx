"use client";

import { useEffect, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_DEMOCONTROL_API_BASE_URL ?? "http://127.0.0.1:8100";
const TERMINAL_STATES = new Set(["PASSED", "FAILED", "CANCELLED"]);
const POLL_MS = 1500;

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

const CHECK_LABELS: Record<string, string> = {
  missionnet_event_observed: "MissionNet event observed",
  normalized_event_observed: "Sentinel normalized event observed",
  expected_detection_observed: "Expected detection observed",
  incident_created: "Expected incident created",
  evidence_link_verified: "Evidence provenance verified",
  no_duplicate_on_replay: "Duplicate check (idempotent replay)",
};

const CHECK_ORDER = Object.keys(CHECK_LABELS);

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "PASSED"
      ? "bg-emerald-500 text-black"
      : status === "FAILED"
        ? "bg-red-500 text-black"
        : status === "CANCELLED"
          ? "bg-zinc-600 text-white"
          : "bg-amber-500 text-black animate-pulse";
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-bold uppercase ${color}`}>{status}</span>
  );
}

export function RunView({ runId }: { runId: string }) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const res = await fetch(`${API_BASE}/api/v1/runs/${runId}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`run fetch failed: ${res.status}`);
        const data: RunDetail = await res.json();
        if (cancelled) return;
        setRun(data);
        setError(null);
        if (TERMINAL_STATES.has(data.status) && intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "poll failed");
      }
    }

    poll();
    intervalRef.current = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [runId]);

  async function handleCancel() {
    await fetch(`${API_BASE}/api/v1/runs/${runId}/cancel`, { method: "POST" });
  }

  async function handleResetAfter() {
    await fetch(`${API_BASE}/api/v1/runs/${runId}/reset`, { method: "POST" });
  }

  if (error && !run) {
    return <p className="text-sm text-red-400">Demo Control API unreachable: {error}</p>;
  }
  if (!run) {
    return <p className="text-sm text-zinc-500">Loading run…</p>;
  }

  const canCancel = !TERMINAL_STATES.has(run.status);

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-mono text-xs text-zinc-500">{run.run_id}</p>
          <h1 className="text-xl font-semibold text-white">{run.scenario_id}</h1>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={run.status} />
          {canCancel && (
            <button
              onClick={handleCancel}
              className="rounded border border-red-800 px-3 py-1.5 text-xs text-red-400 hover:bg-red-950"
            >
              Cancel
            </button>
          )}
          {TERMINAL_STATES.has(run.status) && (
            <button
              onClick={handleResetAfter}
              className="rounded border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-900"
            >
              Reset Lab
            </button>
          )}
        </div>
      </div>

      {run.current_step && (
        <p className="text-sm text-cyan-400">Current step: {run.current_step}</p>
      )}
      {run.reset_status && (
        <p className="text-xs text-zinc-500">Lab reset: {run.reset_status}</p>
      )}
      {run.failure_reason && (
        <p className="rounded border border-red-900 bg-red-950/40 p-3 text-sm text-red-400">
          {run.failure_reason}
        </p>
      )}

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-zinc-500">
          Live Timeline
        </h2>
        <ul className="flex flex-col gap-1 font-mono text-xs">
          {run.timeline.map((entry, i) => (
            <li key={i} className="flex gap-3 text-zinc-400">
              <span className="text-zinc-600">
                {new Date(entry.timestamp).toLocaleTimeString()}
              </span>
              <span>{entry.message}</span>
            </li>
          ))}
          {run.timeline.length === 0 && <li className="text-zinc-600">Waiting to start…</li>}
        </ul>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-zinc-500">
          Verification
        </h2>
        <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {CHECK_ORDER.map((key) => {
            const value = run.verification[key];
            const known = key in run.verification;
            return (
              <li
                key={key}
                className="flex items-center gap-2 rounded border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs"
              >
                <span className={known ? (value ? "text-emerald-400" : "text-red-400") : "text-zinc-600"}>
                  {known ? (value ? "✓" : "✗") : "…"}
                </span>
                <span className="text-zinc-300">{CHECK_LABELS[key]}</span>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="grid grid-cols-2 gap-4 text-xs sm:grid-cols-4">
        <div>
          <p className="text-zinc-500">MissionNet events</p>
          <p className="font-mono text-zinc-200">{run.missionnet_event_ids.length}</p>
        </div>
        <div>
          <p className="text-zinc-500">Sentinel events</p>
          <p className="font-mono text-zinc-200">{run.sentinel_event_ids.length}</p>
        </div>
        <div>
          <p className="text-zinc-500">Detections</p>
          <p className="font-mono text-zinc-200">{run.detection_ids.length}</p>
        </div>
        <div>
          <p className="text-zinc-500">Incidents</p>
          <p className="font-mono text-zinc-200">{run.incident_ids.length}</p>
        </div>
      </section>

      {run.incident_ids.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-zinc-500">
            Resulting Incidents
          </h2>
          <ul className="flex flex-col gap-2">
            {run.incident_ids.map((id) => (
              <li key={id}>
                <a
                  href={`http://127.0.0.1:3000/incidents/${id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="font-mono text-xs text-cyan-400 hover:underline"
                >
                  {id} → open in Sentinel Incident Detail
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="flex flex-wrap gap-3 text-xs">
        <a
          href="http://127.0.0.1:3100"
          target="_blank"
          rel="noreferrer"
          className="rounded border border-zinc-800 px-3 py-1.5 text-zinc-400 hover:text-cyan-400"
        >
          → MissionNet Operations Console
        </a>
        <a
          href="http://127.0.0.1:3000"
          target="_blank"
          rel="noreferrer"
          className="rounded border border-zinc-800 px-3 py-1.5 text-zinc-400 hover:text-cyan-400"
        >
          → Sentinel SOC Dashboard
        </a>
      </div>
    </div>
  );
}
