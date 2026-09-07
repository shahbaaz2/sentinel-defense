"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";
const ACTOR = "demo-analyst";

async function post(path: string, body: Record<string, unknown>) {
  return fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function ApprovalActions({ planId }: { planId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: "approve" | "reject") {
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = { actor: ACTOR };
      if (action === "reject") {
        const reason = window.prompt("Reason for rejecting this response plan:");
        if (!reason) {
          setBusy(false);
          return;
        }
        body.reason = reason;
      }
      const res = await post(`/api/v1/response-plans/${planId}/${action}`, body);
      if (!res.ok) throw new Error(`${res.status}`);
      router.refresh();
    } catch {
      setError(`${action === "approve" ? "Approve" : "Reject"} failed.`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex gap-2">
        <button
          onClick={() => run("approve")}
          disabled={busy}
          className="rounded bg-black px-2 py-1 text-xs font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
        >
          APPROVE
        </button>
        <button
          onClick={() => run("reject")}
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

export function ExecuteAction({ planId }: { planId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (
      !window.confirm(
        "Execute this approved response plan against the SYNTHETIC MISSIONNET LAB ONLY?",
      )
    ) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await post(`/api/v1/response-plans/${planId}/execute`, { actor: ACTOR });
      if (!res.ok) throw new Error(`${res.status}`);
      router.refresh();
    } catch {
      setError("Execute failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        onClick={run}
        disabled={busy}
        className="rounded bg-amber-600 px-2 py-1 text-xs font-medium text-white disabled:opacity-50"
      >
        {busy ? "EXECUTING…" : "EXECUTE APPROVED PLAN"}
      </button>
      {error && <span className="text-[10px] text-red-600 dark:text-red-400">{error}</span>}
    </div>
  );
}

export function RollbackAction({ planId }: { planId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!window.confirm("Roll back this response plan's actions in the synthetic lab?")) return;
    setBusy(true);
    setError(null);
    try {
      const res = await post(`/api/v1/response-plans/${planId}/rollback`, { actor: ACTOR });
      if (!res.ok) throw new Error(`${res.status}`);
      router.refresh();
    } catch {
      setError("Rollback failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        onClick={run}
        disabled={busy}
        className="rounded border border-zinc-400 px-2 py-1 text-xs font-medium text-zinc-700 disabled:opacity-50 dark:border-zinc-600 dark:text-zinc-300"
      >
        {busy ? "ROLLING BACK…" : "ROLLBACK"}
      </button>
      {error && <span className="text-[10px] text-red-600 dark:text-red-400">{error}</span>}
    </div>
  );
}
