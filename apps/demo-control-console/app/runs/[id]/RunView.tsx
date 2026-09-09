"use client";

import { useEffect, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_DEMOCONTROL_API_BASE_URL ?? "http://127.0.0.1:8100";
const SENTINEL_DASHBOARD =
  process.env.NEXT_PUBLIC_SENTINEL_DASHBOARD_URL ?? "https://sentinel-defense-g6id.vercel.app";
const MISSIONNET_CONSOLE = process.env.NEXT_PUBLIC_MISSIONNET_CONSOLE_URL ?? null;
const TERMINAL_STATES = new Set(["PASSED", "FAILED", "CANCELLED"]);
const POLL_MS = 1500;

type TimelineEntry = {
  timestamp: string;
  message: string;
  level?: string;
  component?: string;
  code?: string;
};

type RunDetail = {
  run_id: string;
  scenario_id: string;
  scenario_version?: string;
  actor?: string;
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
  missionnet_event_observed: "Source evidence observed",
  normalized_event_observed: "Normalized event observed",
  expected_detection_observed: "Expected detection observed",
  incident_created: "Expected incident created",
  evidence_link_verified: "Evidence provenance verified",
  no_duplicate_on_replay: "Replay idempotency verified",
};

const CHECK_ORDER = Object.keys(CHECK_LABELS);

function statusClass(status: string) {
  if (status === "PASSED") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (status === "FAILED") return "border-red-200 bg-red-50 text-red-700";
  if (status === "CANCELLED") return "border-zinc-200 bg-zinc-100 text-zinc-600";
  return "border-blue-200 bg-blue-50 text-blue-700";
}

function failureCode(reason: string | null): string | null {
  return reason?.match(/\[([A-Z0-9_]+)\]/)?.[1] ?? null;
}

function failureSummary(reason: string | null): { title: string; action: string } {
  const code = failureCode(reason);
  if (code === "UPSTREAM_INVALID_RESPONSE") {
    return {
      title: "An upstream API returned an invalid response format.",
      action: "Review the component and operation in the log. The run stopped because the required JSON contract was not satisfied.",
    };
  }
  if (code === "UPSTREAM_GATEWAY_ERROR" || code === "UPSTREAM_TRANSPORT_ERROR") {
    return {
      title: "An upstream service was temporarily unavailable.",
      action: "Confirm MissionNet and Sentinel service health, then start a new controlled run.",
    };
  }
  if (code === "EVIDENCE_TIMEOUT" || code === "SENTINEL_VERIFICATION_TIMEOUT") {
    return {
      title: "Expected pipeline evidence was not observed within the validation window.",
      action: "Review source telemetry and Sentinel ingestion logs to identify the missing stage.",
    };
  }
  return {
    title: "The run stopped before all verification controls completed.",
    action: "Review the failure detail and operational log before rerunning the scenario.",
  };
}

export function RunView({ runId }: { runId: string }) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState<"cancel" | "reset" | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const response = await fetch(`${API_BASE}/api/v1/runs/${runId}`, { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = (await response.json()) as RunDetail;
        if (cancelled) return;
        setRun(data);
        setError(null);
        if (TERMINAL_STATES.has(data.status) && intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      } catch (err) {
        if (!cancelled) {
          setError(`Unable to retrieve run state${err instanceof Error ? ` (${err.message})` : ""}.`);
        }
      }
    }

    void poll();
    intervalRef.current = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [runId]);

  async function handleCancel() {
    setActionBusy("cancel");
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/v1/runs/${runId}/cancel`, { method: "POST" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setRun((await response.json()) as RunDetail);
    } catch (err) {
      setError(`Cancel request failed${err instanceof Error ? ` (${err.message})` : ""}.`);
    } finally {
      setActionBusy(null);
    }
  }

  async function handleResetAfter() {
    setActionBusy("reset");
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/v1/runs/${runId}/reset`, { method: "POST" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setRun((await response.json()) as RunDetail);
    } catch (err) {
      setError(`Lab reset failed${err instanceof Error ? ` (${err.message})` : ""}.`);
    } finally {
      setActionBusy(null);
    }
  }

  if (error && !run) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
        <p className="font-semibold">Demo Control API unavailable</p>
        <p className="mt-1">{error}</p>
      </div>
    );
  }

  if (!run) {
    return <p className="text-sm text-zinc-500">Loading run state…</p>;
  }

  const canCancel = !TERMINAL_STATES.has(run.status);
  const failed = run.status === "FAILED";
  const failure = failed ? failureSummary(run.failure_reason) : null;
  const code = failureCode(run.failure_reason);

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs font-semibold text-blue-700">{run.scenario_id}</span>
              <span className={`rounded border px-2 py-1 text-[10px] font-semibold ${statusClass(run.status)}`}>{run.status}</span>
            </div>
            <h1 className="mt-3 text-xl font-semibold text-zinc-950">Scenario run detail</h1>
            <p className="mt-2 break-all font-mono text-xs text-zinc-500">{run.run_id}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {canCancel && (
              <button
                onClick={handleCancel}
                disabled={actionBusy !== null}
                className="rounded-md border border-red-300 bg-white px-3 py-2 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"
              >
                {actionBusy === "cancel" ? "Cancelling…" : "Cancel run"}
              </button>
            )}
            {TERMINAL_STATES.has(run.status) && (
              <button
                onClick={handleResetAfter}
                disabled={actionBusy !== null}
                className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
              >
                {actionBusy === "reset" ? "Resetting…" : "Reset synthetic lab"}
              </button>
            )}
          </div>
        </div>

        <dl className="mt-5 grid gap-4 border-t border-zinc-100 pt-4 text-xs sm:grid-cols-2 lg:grid-cols-4">
          <div><dt className="text-zinc-500">Current step</dt><dd className="mt-1 font-mono text-zinc-800">{run.current_step ?? "—"}</dd></div>
          <div><dt className="text-zinc-500">Started</dt><dd className="mt-1 text-zinc-800">{new Date(run.started_at).toLocaleString()}</dd></div>
          <div><dt className="text-zinc-500">Completed</dt><dd className="mt-1 text-zinc-800">{run.completed_at ? new Date(run.completed_at).toLocaleString() : "—"}</dd></div>
          <div><dt className="text-zinc-500">Lab reset</dt><dd className="mt-1 font-mono text-zinc-800">{run.reset_status ?? "Not requested"}</dd></div>
        </dl>
      </section>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
      )}

      {failed && failure && (
        <section className="rounded-lg border border-red-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-red-100 bg-red-50 px-5 py-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-red-700">Execution failure</p>
              <p className="mt-1 text-sm font-semibold text-red-950">{failure.title}</p>
            </div>
            {code && <span className="rounded border border-red-200 bg-white px-2 py-1 font-mono text-[10px] text-red-700">{code}</span>}
          </div>
          <div className="grid gap-4 p-5 md:grid-cols-2">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">Failure detail</p>
              <p className="mt-2 break-words font-mono text-xs leading-5 text-zinc-700">{run.failure_reason ?? "No detail available"}</p>
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">Recommended action</p>
              <p className="mt-2 text-xs leading-5 text-zinc-700">{failure.action}</p>
              <p className="mt-2 text-xs font-semibold text-zinc-600">No downstream stage is represented as successful after this failure.</p>
            </div>
          </div>
        </section>
      )}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Source events", run.missionnet_event_ids.length],
          ["Normalized events", run.sentinel_event_ids.length],
          ["Detections", run.detection_ids.length],
          ["Incidents", run.incident_ids.length],
        ].map(([label, value]) => (
          <div key={String(label)} className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">{label}</p>
            <p className="mt-2 text-2xl font-semibold text-zinc-950">{value}</p>
          </div>
        ))}
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="border-b border-zinc-200 px-5 py-4">
          <h2 className="text-sm font-semibold text-zinc-950">Verification controls</h2>
          <p className="mt-1 text-xs text-zinc-500">Checks are derived from observed MissionNet and Sentinel evidence.</p>
        </div>
        <div className="grid gap-0 sm:grid-cols-2 lg:grid-cols-3">
          {CHECK_ORDER.map((key) => {
            const known = key in run.verification;
            const value = run.verification[key];
            return (
              <div key={key} className="border-b border-r border-zinc-100 p-4">
                <p className="text-xs text-zinc-600">{CHECK_LABELS[key]}</p>
                <p className={`mt-2 text-xs font-semibold ${!known ? "text-zinc-400" : value ? "text-emerald-700" : "text-red-700"}`}>
                  {!known ? "PENDING" : value ? "PASS" : "FAIL"}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="border-b border-zinc-200 px-5 py-4">
          <h2 className="text-sm font-semibold text-zinc-950">Operational log</h2>
          <p className="mt-1 text-xs text-zinc-500">Structured timeline of execution and upstream service activity.</p>
        </div>
        <div className="max-h-[460px] overflow-auto">
          <table className="w-full min-w-[760px] border-collapse text-left text-xs">
            <thead className="sticky top-0 bg-zinc-50 text-[10px] uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="border-b border-zinc-200 px-4 py-3 font-semibold">Time</th>
                <th className="border-b border-zinc-200 px-4 py-3 font-semibold">Level</th>
                <th className="border-b border-zinc-200 px-4 py-3 font-semibold">Component</th>
                <th className="border-b border-zinc-200 px-4 py-3 font-semibold">Code</th>
                <th className="border-b border-zinc-200 px-4 py-3 font-semibold">Message</th>
              </tr>
            </thead>
            <tbody>
              {run.timeline.map((entry, index) => (
                <tr key={`${entry.timestamp}-${index}`} className="border-b border-zinc-100 last:border-0">
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-zinc-500">{new Date(entry.timestamp).toLocaleTimeString()}</td>
                  <td className={`px-4 py-3 font-semibold ${entry.level === "ERROR" ? "text-red-700" : entry.level === "WARN" ? "text-amber-700" : "text-zinc-600"}`}>{entry.level ?? "INFO"}</td>
                  <td className="px-4 py-3 text-zinc-600">{entry.component ?? "Demo Control"}</td>
                  <td className="px-4 py-3 font-mono text-zinc-500">{entry.code ?? "—"}</td>
                  <td className="px-4 py-3 leading-5 text-zinc-700">{entry.message}</td>
                </tr>
              ))}
              {run.timeline.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-zinc-400">No operational events recorded.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {run.incident_ids.length > 0 && (
        <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-zinc-950">Resulting incidents</h2>
          <div className="mt-3 space-y-2">
            {run.incident_ids.map((id) => (
              <a
                key={id}
                href={`${SENTINEL_DASHBOARD}/incidents/${id}`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between rounded border border-zinc-200 px-3 py-2.5 text-xs text-zinc-700 hover:border-blue-300 hover:bg-blue-50"
              >
                <span className="font-mono">{id}</span>
                <span className="text-blue-700">Open incident ↗</span>
              </a>
            ))}
          </div>
        </section>
      )}

      <div className="flex flex-wrap gap-2">
        <a
          href={SENTINEL_DASHBOARD}
          target="_blank"
          rel="noreferrer"
          className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
        >
          Open Sentinel dashboard ↗
        </a>
        {MISSIONNET_CONSOLE && (
          <a
            href={MISSIONNET_CONSOLE}
            target="_blank"
            rel="noreferrer"
            className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
          >
            Open MissionNet console ↗
          </a>
        )}
      </div>
    </div>
  );
}
