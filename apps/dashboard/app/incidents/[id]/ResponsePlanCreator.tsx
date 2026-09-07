"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";
const ACTOR = "demo-analyst";

type Playbook = { id: string; name: string; requires_human_approval: boolean };
type ResponsePlanSummary = {
  response_plan_id: string;
  playbook_id: string;
  status: string;
  created_at: string;
};
type PolicyDecision = {
  allowed: boolean;
  reasons: string[];
  blocking_reasons: string[];
  requires_human_approval: boolean;
};

export function ResponsePlanCreator({
  incidentId,
  aiRecommendedPlaybookId,
  aiAssessmentId,
  initialEligiblePlaybooks,
  initialResponsePlans,
}: {
  incidentId: string;
  aiRecommendedPlaybookId: string | null;
  aiAssessmentId: string | null;
  initialEligiblePlaybooks: Playbook[];
  initialResponsePlans: ResponsePlanSummary[];
}) {
  const router = useRouter();
  const [selected, setSelected] = useState(
    aiRecommendedPlaybookId ?? initialEligiblePlaybooks[0]?.id ?? "",
  );
  const [decision, setDecision] = useState<PolicyDecision | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!selected) {
      return;
    }
    let cancelled = false;
    fetch(`${API_BASE}/api/v1/incidents/${incidentId}/policy-check/${selected}`, {
      cache: "no-store",
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!cancelled) setDecision(d);
      })
      .catch(() => {
        if (!cancelled) setDecision(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selected, incidentId]);

  async function createPlan() {
    setBusy(true);
    setError(null);
    try {
      const isAiRecommendation = selected === aiRecommendedPlaybookId && aiAssessmentId !== null;
      const res = await fetch(`${API_BASE}/api/v1/incidents/${incidentId}/response-plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          playbook_id: selected,
          actor: ACTOR,
          recommendation_source: isAiRecommendation ? "ai" : "analyst",
          ai_assessment_id: isAiRecommendation ? aiAssessmentId : null,
        }),
      });
      if (res.status === 422) {
        const body = await res.json();
        setError(`Policy denied: ${body.detail.blocking_reasons.join("; ")}`);
        return;
      }
      if (!res.ok) throw new Error(`${res.status}`);
      const plan = await res.json();
      router.push(`/response-plans/${plan.response_plan_id}`);
    } catch {
      setError("Failed to create response plan.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
        Response Planning
      </h2>

      {aiRecommendedPlaybookId && (
        <p className="mb-2 text-sm">
          Recommended Playbook: <span className="font-mono">{aiRecommendedPlaybookId}</span>
        </p>
      )}
      {!aiRecommendedPlaybookId && (
        <p className="mb-2 text-xs text-zinc-500">
          No AI recommendation — choose an eligible playbook manually below.
        </p>
      )}

      {initialEligiblePlaybooks.length === 0 && (
        <p className="text-xs text-zinc-500">
          No playbooks are currently eligible for this incident (see Detection Coverage / incident
          category, severity, and status above).
        </p>
      )}

      {initialEligiblePlaybooks.length > 0 && (
        <>
          <div className="mb-3 flex items-center gap-2">
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="rounded border border-zinc-300 bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            >
              {initialEligiblePlaybooks.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.id} — {p.name}
                </option>
              ))}
            </select>
            {decision && (
              <span
                className={`text-xs font-semibold ${
                  decision.allowed
                    ? "text-emerald-600 dark:text-emerald-400"
                    : "text-red-600 dark:text-red-400"
                }`}
              >
                {decision.allowed
                  ? decision.requires_human_approval
                    ? "ELIGIBLE — HUMAN APPROVAL REQUIRED"
                    : "ELIGIBLE"
                  : "NOT ELIGIBLE"}
              </span>
            )}
          </div>
          <button
            onClick={createPlan}
            disabled={busy || !decision?.allowed}
            className="rounded bg-black px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
          >
            CREATE RESPONSE PLAN
          </button>
        </>
      )}

      {error && <p className="mt-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

      {initialResponsePlans.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-xs font-semibold uppercase text-zinc-500">
            Response Plans For This Incident
          </p>
          <ul className="flex flex-col gap-1">
            {initialResponsePlans.map((p) => (
              <li key={p.response_plan_id} className="text-xs">
                <Link
                  href={`/response-plans/${p.response_plan_id}`}
                  className="font-mono text-blue-600 hover:underline dark:text-blue-400"
                >
                  {p.response_plan_id.slice(0, 13)}…
                </Link>{" "}
                {p.playbook_id} — <span className="uppercase">{p.status}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
