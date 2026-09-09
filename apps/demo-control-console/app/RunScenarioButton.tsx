"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_DEMOCONTROL_API_BASE_URL ?? "http://127.0.0.1:8100";

export function RunScenarioButton({ scenarioId }: { scenarioId: string }) {
  const router = useRouter();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setStarting(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/scenarios/${scenarioId}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor: "demo-operator" }),
      });
      if (!res.ok) throw new Error(`start failed: ${res.status}`);
      const run = await res.json();
      router.push(`/runs/${run.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed to start run");
      setStarting(false);
    }
  }

  return (
    <div className="flex min-w-0 flex-col gap-1">
      <button
        onClick={handleRun}
        disabled={starting}
        className="w-full rounded-lg border border-white/[0.09] bg-white/[0.035] px-3 py-2.5 text-[10px] font-bold uppercase tracking-wider text-zinc-300 transition hover:border-cyan-400/30 hover:bg-cyan-400/[0.07] hover:text-cyan-200 disabled:cursor-wait disabled:opacity-50"
      >
        {starting ? "Starting…" : "Run Scenario"}
      </button>
      {error && <span className="break-words text-[9px] leading-4 text-red-400">{error}</span>}
    </div>
  );
}
