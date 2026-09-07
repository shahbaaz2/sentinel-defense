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

export function ExecutionControls({
  planId,
  planStatus,
  executionStatus,
  reversible,
  playbookName,
}: {
  planId: string;
  planStatus: string;
  executionStatus: string;
  reversible: boolean;
  playbookName: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function execute() {
    const confirmed = window.confirm(
      `EXECUTE APPROVED PLAN\n\n` +
        `Playbook: ${playbookName}\n` +
        `Actor: ${ACTOR}\n\n` +
        `This will perform the plan's actions against the SYNTHETIC MISSIONNET LAB ONLY. ` +
        `Every target, action, and expected outcome is already shown above on this page - review ` +
        `it before confirming.\n\n` +
        `Proceed?`,
    );
    if (!confirmed) return;
    setBusy(true);
    setError(null);
    try {
      const res = await post(`/api/v1/response-plans/${planId}/execute`, { actor: ACTOR });
      if (res.status === 422) {
        const body = await res.json();
        setError(`Blocked: ${body.detail}`);
        return;
      }
      if (!res.ok) throw new Error(`${res.status}`);
      router.refresh();
    } catch {
      setError("Execute failed.");
    } finally {
      setBusy(false);
    }
  }

  async function rollback() {
    if (
      !window.confirm(
        `Roll back "${playbookName}" - reverse every reversible action against the synthetic lab?`,
      )
    ) {
      return;
    }
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

  const canExecute = planStatus === "APPROVED" && executionStatus === "NOT_EXECUTED";
  const canRollback =
    reversible &&
    planStatus === "APPROVED" &&
    (executionStatus === "SUCCEEDED" || executionStatus === "FAILED");

  if (!canExecute && !canRollback) {
    return null;
  }

  return (
    <div className="flex flex-col gap-2">
      {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
      <div className="flex gap-2">
        {canExecute && (
          <button
            onClick={execute}
            disabled={busy}
            className="rounded bg-amber-600 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
          >
            {busy ? "EXECUTING…" : "EXECUTE APPROVED PLAN"}
          </button>
        )}
        {canRollback && (
          <button
            onClick={rollback}
            disabled={busy}
            className="rounded border border-zinc-400 px-3 py-1.5 text-xs font-medium text-zinc-700 disabled:opacity-50 dark:border-zinc-600 dark:text-zinc-300"
          >
            {busy ? "ROLLING BACK…" : "ROLLBACK"}
          </button>
        )}
      </div>
    </div>
  );
}
