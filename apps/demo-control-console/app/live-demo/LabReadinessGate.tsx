"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const DEMO_API =
  process.env.NEXT_PUBLIC_DEMOCONTROL_API_BASE_URL ?? "http://127.0.0.1:8100";
const SENTINEL_DASHBOARD =
  process.env.NEXT_PUBLIC_SENTINEL_DASHBOARD_URL ?? "https://sentinel-defense-g6id.vercel.app";
const MISSIONNET_WAKE_URL =
  process.env.NEXT_PUBLIC_MISSIONNET_WAKE_URL ?? "https://sentinel-defense-hes7.onrender.com/health";
const SENTINEL_WAKE_URL =
  process.env.NEXT_PUBLIC_SENTINEL_API_WAKE_URL ?? "https://sentinel-api-ie2z.onrender.com/api/v1/health";

type Probe = {
  ready: boolean;
  status: string;
  detail: string;
  code?: string;
};

type WarmupState = {
  ready: boolean;
  phase: string;
  message: string;
  missionnet: Probe;
  sentinel: Probe;
};

function tone(status: string) {
  const normalized = status.toUpperCase();
  if (["ONLINE", "READY", "HEALTHY", "NOMINAL", "OPERATIONAL"].includes(normalized)) {
    return "border-emerald-500/30 bg-emerald-500/5 text-emerald-300";
  }
  if (["UNAVAILABLE", "FAILED", "OFFLINE", "ERROR"].includes(normalized)) {
    return "border-red-500/30 bg-red-500/5 text-red-300";
  }
  return "border-amber-500/30 bg-amber-500/5 text-amber-300";
}

function wakeBackendServices() {
  // These no-cors GETs are intentionally fire-and-forget. Their purpose is only to trigger the
  // public Render services to spin up in parallel while Demo Control itself is waking. Readiness is
  // still determined by Demo Control's /warmup endpoint before run controls are shown.
  void fetch(MISSIONNET_WAKE_URL, { mode: "no-cors", cache: "no-store" }).catch(() => undefined);
  void fetch(SENTINEL_WAKE_URL, { mode: "no-cors", cache: "no-store" }).catch(() => undefined);
}

export function LabReadinessGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<WarmupState | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [controlPlaneStatus, setControlPlaneStatus] = useState("WARMING");
  const [manualRetry, setManualRetry] = useState(false);
  const mounted = useRef(true);

  const probe = useCallback(async () => {
    wakeBackendServices();
    try {
      const response = await fetch(`${DEMO_API}/api/v1/warmup`, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = (await response.json()) as WarmupState;
      if (!mounted.current) return;
      setControlPlaneStatus("ONLINE");
      setState(data);
    } catch {
      if (!mounted.current) return;
      setControlPlaneStatus("WARMING");
    } finally {
      if (mounted.current) setManualRetry(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    // Start all three cloud wake-ups immediately instead of waiting for Demo Control to wake first.
    wakeBackendServices();
    void probe();
    const poller = window.setInterval(() => void probe(), 3000);
    const clock = window.setInterval(() => setElapsed((seconds) => seconds + 1), 1000);
    return () => {
      mounted.current = false;
      window.clearInterval(poller);
      window.clearInterval(clock);
    };
  }, [probe]);

  if (state?.ready) return <>{children}</>;

  const missionnetStatus = state?.missionnet.status ?? "WARMING";
  const sentinelStatus = state?.sentinel.status ?? "WARMING";
  const longWait = elapsed >= 60;

  return (
    <main className="min-h-[calc(100vh-38px)] bg-[#071019] px-4 py-8 text-slate-200 lg:px-8">
      <div className="mx-auto max-w-5xl">
        <div className="border border-[#263442] bg-[#0d1721] shadow-[0_24px_70px_rgba(0,0,0,.25)]">
          <div className="border-b border-[#263442] bg-[#101c28] px-5 py-4">
            <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
              <div>
                <p className="text-[9px] font-bold uppercase tracking-[0.18em] text-sky-400">Sentinel controlled validation</p>
                <h1 className="mt-1 text-xl font-semibold text-white">Preparing the security lab</h1>
                <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">
                  MissionNet, Sentinel API, and Demo Control are being woken in parallel and verified before the Run control is exposed. No scenario is created until the lab is genuinely ready.
                </p>
              </div>
              <div className="shrink-0 border border-amber-500/25 bg-amber-500/5 px-3 py-2 text-center">
                <p className="text-[9px] uppercase tracking-wider text-slate-600">Warm-up elapsed</p>
                <p className="mt-1 font-mono text-sm font-semibold text-amber-300">{elapsed}s</p>
              </div>
            </div>
          </div>

          <div className="grid gap-px bg-[#263442] md:grid-cols-3">
            {[
              ["Demo Control", controlPlaneStatus, "Scenario orchestration API"],
              ["MissionNet", missionnetStatus, state?.missionnet.detail ?? "Waking protected synthetic environment"],
              ["Sentinel API", sentinelStatus, state?.sentinel.detail ?? "Verifying detection and incident pipeline"],
            ].map(([name, status, detail]) => (
              <div key={name} className="bg-[#0b151f] p-5">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold text-white">{name}</p>
                  <span className={`border px-2 py-1 font-mono text-[9px] font-semibold ${tone(status)}`}>{status}</span>
                </div>
                <p className="mt-3 text-[10px] leading-4 text-slate-500">{detail}</p>
              </div>
            ))}
          </div>

          <div className="p-5">
            <div className="h-1.5 overflow-hidden bg-[#1a2734]">
              <div className="h-full w-1/2 animate-pulse bg-gradient-to-r from-sky-500 via-cyan-300 to-sky-500" />
            </div>
            <div className="mt-4 flex flex-col justify-between gap-4 md:flex-row md:items-center">
              <div>
                <p className="text-xs font-medium text-slate-300">
                  {longWait
                    ? "Cloud startup is taking longer than usual, but the services are still being retried automatically in parallel."
                    : "The scenario console will open automatically as soon as the backend is ready."}
                </p>
                <p className="mt-1 text-[10px] text-slate-600">
                  This startup gate prevents a cold cloud service from becoming a failed security scenario.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={manualRetry}
                  onClick={() => {
                    setManualRetry(true);
                    wakeBackendServices();
                    void probe();
                  }}
                  className="border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-[10px] font-semibold text-sky-200 transition hover:border-sky-400/60 disabled:opacity-50"
                >
                  {manualRetry ? "Checking…" : "Check now"}
                </button>
                <a
                  href={SENTINEL_DASHBOARD}
                  target="_blank"
                  rel="noreferrer"
                  className="border border-slate-700 bg-[#101c28] px-3 py-2 text-[10px] font-semibold text-slate-300 hover:border-slate-500 hover:text-white"
                >
                  Open read-only dashboard ↗
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
