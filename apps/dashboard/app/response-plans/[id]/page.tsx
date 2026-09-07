import Link from "next/link";
import { ResponsePlanActions } from "./ResponsePlanActions";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type ResponsePlan = {
  response_plan_id: string;
  incident_id: string;
  playbook_id: string;
  playbook_version: string;
  created_at: string;
  created_by: string;
  recommendation_source: "ai" | "analyst";
  ai_assessment_id: string | null;
  policy_bundle_version: string;
  policy_decision: string;
  policy_reasons: string[];
  risk_level: string;
  reversible: boolean;
  status: string;
  approved_by: string | null;
  approved_at: string | null;
  rejected_by: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  cancelled_by: string | null;
  cancelled_at: string | null;
  scenario_id: string | null;
  execution_status: string;
};

type Incident = {
  incident_id: string;
  title: string;
  severity: string;
  category: string;
  status: string;
  primary_asset_id: string | null;
};

type Playbook = {
  id: string;
  name: string;
  description: string;
  actions: { action_id: string; target_source: string; description: string; risk_level: string }[];
  verification: string[];
  rollback: string[];
  risk: { mission_impact: string; reversibility: string };
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

function StatusBanner({ status }: { status: string }) {
  if (status === "APPROVED") {
    return (
      <div className="rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300">
        APPROVED — EXECUTION NOT ENABLED IN PHASE 6
      </div>
    );
  }
  if (status === "REJECTED") {
    return (
      <div className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm font-semibold text-red-800 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300">
        REJECTED — no action was taken
      </div>
    );
  }
  if (status === "CANCELLED") {
    return (
      <div className="rounded border border-zinc-300 bg-zinc-100 px-3 py-2 text-sm font-semibold text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400">
        CANCELLED
      </div>
    );
  }
  return (
    <div className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
      PLANNED — NOT YET EXECUTED — AWAITING HUMAN APPROVAL
    </div>
  );
}

export default async function ResponsePlanDetailPage(props: PageProps<"/response-plans/[id]">) {
  const { id } = await props.params;
  const plan = await getJSON<ResponsePlan>(`/api/v1/response-plans/${id}`);

  if (!plan) {
    return (
      <div className="flex flex-1 flex-col items-center bg-zinc-50 p-16 font-sans dark:bg-black">
        <p className="text-sm text-red-600 dark:text-red-400">Response plan not found.</p>
      </div>
    );
  }

  const [incident, playbook] = await Promise.all([
    getJSON<Incident>(`/api/v1/incidents/${plan.incident_id}`),
    getJSON<Playbook>(`/api/v1/playbooks/${plan.playbook_id}`),
  ]);

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-4xl flex-col gap-8 px-8 py-16">
        <div>
          <Link href="/response-center" className="text-sm text-zinc-500 hover:underline">
            ← Response Center
          </Link>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-black dark:text-zinc-50">
            Response Plan: {playbook?.name ?? plan.playbook_id}
          </h1>
          <p className="mt-1 font-mono text-xs text-zinc-500">{plan.response_plan_id}</p>
        </div>

        <StatusBanner status={plan.status} />

        {/* INCIDENT CONTEXT */}
        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Incident Context
          </h2>
          {incident ? (
            <dl className="grid grid-cols-2 gap-y-2 text-sm sm:grid-cols-4">
              <dt className="text-xs text-zinc-500">Incident</dt>
              <dd className="col-span-3">
                <Link
                  href={`/incidents/${incident.incident_id}`}
                  className="text-blue-600 hover:underline dark:text-blue-400"
                >
                  {incident.title}
                </Link>
              </dd>
              <dt className="text-xs text-zinc-500">Severity</dt>
              <dd className="uppercase">{incident.severity}</dd>
              <dt className="text-xs text-zinc-500">Category</dt>
              <dd>{incident.category}</dd>
              <dt className="text-xs text-zinc-500">Asset</dt>
              <dd className="font-mono text-xs">{incident.primary_asset_id ?? "—"}</dd>
            </dl>
          ) : (
            <p className="text-sm text-zinc-500">Incident unavailable.</p>
          )}
        </section>

        {/* RECOMMENDED PLAYBOOK + WHY THIS PLAYBOOK */}
        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Recommended Playbook
          </h2>
          <p className="mb-3 font-mono text-xs text-zinc-500">
            {plan.playbook_id} v{plan.playbook_version} · recommended by{" "}
            <span className="uppercase">{plan.recommendation_source}</span>
            {plan.ai_assessment_id && (
              <>
                {" "}
                (
                <Link
                  href={`/incidents/${plan.incident_id}`}
                  className="text-blue-600 hover:underline dark:text-blue-400"
                >
                  AI assessment {plan.ai_assessment_id.slice(0, 13)}…
                </Link>
                )
              </>
            )}
          </p>
          {playbook && <p className="mb-3 text-sm">{playbook.description}</p>}

          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Why This Playbook
          </h3>
          <ul className="list-inside list-disc text-xs text-zinc-600 dark:text-zinc-400">
            {plan.policy_reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </section>

        {/* PLANNED ACTIONS */}
        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Planned Actions
          </h2>
          <p className="mb-3 text-xs text-zinc-500">
            Declarative only in this phase - nothing below has executed or will execute.
          </p>
          <ul className="flex flex-col gap-2">
            {playbook?.actions.map((a) => (
              <li
                key={a.action_id}
                className="rounded border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs">{a.action_id}</span>
                  <span className="text-[10px] uppercase text-zinc-500">{a.risk_level} risk</span>
                </div>
                <p className="text-xs text-zinc-600 dark:text-zinc-400">{a.description}</p>
                <p className="mt-1 font-mono text-[10px] text-zinc-400">
                  target: {a.target_source}
                </p>
              </li>
            ))}
          </ul>
          {playbook && playbook.verification.length > 0 && (
            <p className="mt-3 text-xs text-zinc-500">
              Verification (would confirm success): {playbook.verification.join(", ")}
            </p>
          )}
          {playbook && playbook.rollback.length > 0 && (
            <p className="mt-1 text-xs text-zinc-500">
              Rollback: {playbook.rollback.join(", ")}
            </p>
          )}
        </section>

        {/* POLICY CHECKS */}
        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Policy Checks
          </h2>
          <p className="mb-2 text-xs text-zinc-500">
            Policy bundle {plan.policy_bundle_version} · decision{" "}
            <span className="font-semibold">{plan.policy_decision}</span>
          </p>
          <ul className="list-inside list-disc text-xs text-zinc-600 dark:text-zinc-400">
            {plan.policy_reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </section>

        {/* MISSION IMPACT */}
        <section className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Mission Impact</p>
            <p className="font-semibold uppercase">{plan.risk_level}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Reversible</p>
            <p className="font-semibold">{plan.reversible ? "Yes" : "No"}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Execution Status</p>
            <p className="font-mono text-xs">{plan.execution_status}</p>
          </div>
        </section>

        {/* APPROVAL */}
        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Approval
          </h2>
          <dl className="mb-3 grid grid-cols-2 gap-y-1 text-xs sm:grid-cols-4">
            <dt className="text-zinc-500">Created by</dt>
            <dd>{plan.created_by}</dd>
            <dt className="text-zinc-500">Created at</dt>
            <dd>{new Date(plan.created_at).toLocaleString()}</dd>
            {plan.approved_by && (
              <>
                <dt className="text-zinc-500">Approved by</dt>
                <dd>{plan.approved_by}</dd>
                <dt className="text-zinc-500">Approved at</dt>
                <dd>{plan.approved_at && new Date(plan.approved_at).toLocaleString()}</dd>
              </>
            )}
            {plan.rejected_by && (
              <>
                <dt className="text-zinc-500">Rejected by</dt>
                <dd>{plan.rejected_by}</dd>
                <dt className="text-zinc-500">Reason</dt>
                <dd>{plan.rejection_reason}</dd>
              </>
            )}
            {plan.cancelled_by && (
              <>
                <dt className="text-zinc-500">Cancelled by</dt>
                <dd>{plan.cancelled_by}</dd>
              </>
            )}
          </dl>
          <ResponsePlanActions planId={plan.response_plan_id} status={plan.status} />
        </section>
      </main>
    </div>
  );
}
