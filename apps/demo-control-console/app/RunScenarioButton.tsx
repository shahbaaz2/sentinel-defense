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
      const response = await fetch(`${API_BASE}/api/v1/scenarios/${scenarioId}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor: "demo-operator" }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const run = await response.json();
      router.push(`/runs/${run.run_id}`);
    } catch (err) {
      setError(
        `Unable to start run${err instanceof Error ? ` (${err.message})` : ""}. Review Demo Control service health.`,
      );
      setStarting(false);
    }
  }

  return (
    <div className="flex min-w-0 flex-col gap-1">
      <button
        onClick={handleRun}
        disabled={starting}
        className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2.5 text-xs font-semibold text-zinc-700 transition hover:bg-zinc-50 disabled:cursor-wait disabled:opacity-50"
      >
        {starting ? "Starting…" : "Run directly"}
      </button>
      {error && <span className="break-words text-[10px] leading-4 text-red-700">{error}</span>}
    </div>
  );
}
