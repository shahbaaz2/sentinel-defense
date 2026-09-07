"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";
const ACTOR = "demo-analyst";

export function ResponsePlanActions({ planId, status }: { planId: string; status: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");

  async function post(path: string, body: Record<string, unknown>) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/response-plans/${planId}/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      router.refresh();
    } catch {
      setError(`Failed to ${path} this plan.`);
    } finally {
      setBusy(false);
    }
  }

  if (status !== "AWAITING_APPROVAL") {
    return (
      <p className="text-sm text-zinc-500">
        This plan is {status} - no further approval action is available.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Optional note for the approval record…"
        rows={2}
        className="w-full rounded border border-zinc-300 bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
      />
      <div className="flex gap-2">
        <button
          onClick={() => post("approve", { actor: ACTOR, note: note || null })}
          disabled={busy}
          className="rounded bg-black px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
        >
          APPROVE
        </button>
        <button
          onClick={() => {
            const reason = window.prompt("Reason for rejecting this response plan:");
            if (reason) post("reject", { actor: ACTOR, reason });
          }}
          disabled={busy}
          className="rounded border border-red-300 px-3 py-1.5 text-xs font-medium text-red-600 disabled:opacity-50 dark:border-red-800 dark:text-red-400"
        >
          REJECT
        </button>
        <button
          onClick={() => post("cancel", { actor: ACTOR, note: note || null })}
          disabled={busy}
          className="rounded border border-zinc-300 px-3 py-1.5 text-xs text-zinc-600 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-400"
        >
          CANCEL
        </button>
      </div>
    </div>
  );
}
