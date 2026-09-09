import Link from "next/link";
import { RunScenarioButton } from "./RunScenarioButton";

const API_BASE = process.env.DEMOCONTROL_API_BASE_URL ?? "http://127.0.0.1:8100";

type SystemStatus = {
  missionnet_status: string;
  sentinel_status: string;
  ai_analyst_status: string;
};

type Scenario = {
  id: string;
  version: string;
  name: string;
  description: string;
  risk_level: string;
  step_count: number;
};

type RunSummary = {
  run_id: string;
  scenario_id: string;
  status: string;
  started_at: string;
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

function StatusPill({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-2 rounded border border-zinc-800 bg-zinc-950 px-3 py-2">
      <span className={`h-2 w-2 rounded-full ${ok ? "bg-emerald-400" : "bg-red-500"}`} />
      <span className="text-xs uppercase tracking-wide text-zinc-500">{label}</span>
      <span className="ml-auto font-mono text-sm text-zinc-100">{value}</span>
    </div>
  );
}

export default async function DemoControlHome() {
  const [status, scenarios, runs] = await Promise.all([
    getJSON<SystemStatus>("/api/v1/status"),
    getJSON<Scenario[]>("/api/v1/scenarios"),
    getJSON<RunSummary[]>("/api/v1/runs"),
  ]);

  return (
    <div className="flex flex-1 flex-col items-center bg-black font-mono text-zinc-100">
      <main className="flex w-full max-w-4xl flex-col gap-8 px-8 py-16">
        <div>
          <span className="w-fit rounded bg-cyan-500/10 px-2 py-1 text-xs font-semibold tracking-widest text-cyan-400">
            SYNTHETIC LAB — DEFENSIVE ONLY
          </span>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight text-white">
            SENTINEL CYBER RANGE — DEMO CONTROL
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            Orchestrates MissionNet through approved lab APIs. Never writes to Sentinel directly.
          </p>
        </div>

        <Link
          href="/live-demo"
          className="group overflow-hidden rounded-xl border border-cyan-900/70 bg-gradient-to-r from-cyan-950/30 via-zinc-950 to-red-950/20 p-5 transition hover:border-cyan-500/70"
        >
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <div className="flex items-center gap-2">
                <span className="rounded bg-amber-500/20 px-2 py-1 text-[10px] font-bold uppercase tracking-widest text-amber-300">
                  Flagship experience
                </span>
                <span className="text-[10px] uppercase tracking-widest text-cyan-500">SCN-010</span>
              </div>
              <h2 className="mt-3 text-lg font-semibold text-white">Immersive Live Attack Replay</h2>
              <p className="mt-1 max-w-2xl text-xs leading-5 text-zinc-500">
                Watch credential pressure, mission-service degradation, deterministic Sentinel detections,
                incident correlation, evidence verification, and the handoff into AI-assisted human-approved response.
              </p>
            </div>
            <span className="whitespace-nowrap rounded-lg bg-cyan-400 px-4 py-2.5 text-xs font-bold uppercase tracking-wide text-black group-hover:bg-cyan-300">
              Launch GUI Demo →
            </span>
          </div>
        </Link>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <StatusPill
            label="MissionNet"
            value={status?.missionnet_status ?? "UNKNOWN"}
            ok={status?.missionnet_status === "NOMINAL"}
          />
          <StatusPill
            label="Sentinel"
            value={status?.sentinel_status ?? "UNKNOWN"}
            ok={status?.sentinel_status === "ONLINE"}
          />
          <StatusPill label="Ingestion" value="ON-DEMAND" ok={true} />
          <StatusPill
            label="AI Analyst"
            value={status?.ai_analyst_status ?? "NOT_ENABLED"}
            ok={status?.ai_analyst_status === "OPERATIONAL" || status?.ai_analyst_status === "READY"}
          />
        </div>

        <div>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-zinc-500">
            Available Scenarios
          </h2>
          {!scenarios && (
            <p className="text-sm text-red-400">Demo Control API unreachable at {API_BASE}.</p>
          )}
          <div className="flex flex-col gap-3">
            {scenarios?.map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between gap-4 rounded border border-zinc-800 bg-zinc-950 p-4"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm text-cyan-400">{s.id}</span>
                    <span className="font-medium text-white">{s.name}</span>
                    {s.id === "SCN-010" && (
                      <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-amber-400">
                        Flagship
                      </span>
                    )}
                  </div>
                  <p className="mt-1 max-w-xl text-xs text-zinc-500">{s.description}</p>
                  <p className="mt-1 text-xs text-zinc-600">
                    {s.step_count} step(s) · {s.risk_level}
                  </p>
                </div>
                {s.id === "SCN-010" ? (
                  <Link
                    href="/live-demo"
                    className="whitespace-nowrap rounded bg-cyan-500 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-black hover:bg-cyan-400"
                  >
                    Launch Replay
                  </Link>
                ) : (
                  <RunScenarioButton scenarioId={s.id} />
                )}
              </div>
            ))}
          </div>
        </div>

        {runs && runs.length > 0 && (
          <div>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-zinc-500">
              Recent Runs
            </h2>
            <ul className="flex flex-col gap-2">
              {runs.slice(0, 10).map((r) => (
                <li key={r.run_id}>
                  <Link
                    href={`/runs/${r.run_id}`}
                    className="flex items-center justify-between rounded border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs hover:border-cyan-800"
                  >
                    <span className="font-mono text-zinc-400">{r.run_id.slice(0, 13)}…</span>
                    <span className="text-zinc-500">{r.scenario_id}</span>
                    <span
                      className={
                        r.status === "PASSED"
                          ? "text-emerald-400"
                          : r.status === "FAILED"
                            ? "text-red-400"
                            : "text-amber-400"
                      }
                    >
                      {r.status}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </main>
    </div>
  );
}
