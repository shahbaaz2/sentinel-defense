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
    <div className="flex flex-col items-end gap-1">
      <button
        onClick={handleRun}
        disabled={starting}
        className="whitespace-nowrap rounded bg-cyan-500 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-black hover:bg-cyan-400 disabled:opacity-50"
      >
        {starting ? "Starting…" : "Run Scenario"}
      </button>
      {error && <span className="text-xs text-red-400">{error}</span>}
    </div>
  );
}
