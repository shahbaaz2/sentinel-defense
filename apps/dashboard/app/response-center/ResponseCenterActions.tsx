"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";
const ACTOR = "demo-analyst";

export function ResponseCenterActions({ planId }: { planId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function approve() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/response-plans/${planId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor: ACTOR }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      router.refresh();
    } catch {
      setError("Approve failed.");
    } finally {
      setBusy(false);
    }
  }

  async function reject() {
    const reason = window.prompt("Reason for rejecting this response plan:");
    if (!reason) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/response-plans/${planId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor: ACTOR, reason }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      router.refresh();
    } catch {
      setError("Reject failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex gap-2">
        <button
          onClick={approve}
          disabled={busy}
          className="rounded bg-black px-2 py-1 text-xs font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
        >
          APPROVE
        </button>
        <button
          onClick={reject}
          disabled={busy}
          className="rounded border border-red-300 px-2 py-1 text-xs font-medium text-red-600 disabled:opacity-50 dark:border-red-800 dark:text-red-400"
        >
          REJECT
        </button>
      </div>
      {error && <span className="text-[10px] text-red-600 dark:text-red-400">{error}</span>}
    </div>
  );
}
