import Link from "next/link";
import { ApprovalActions, ExecuteAction, RollbackAction } from "./ResponseCenterActions";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type ResponsePlan = {
  response_plan_id: string;
  incident_id: string;
  playbook_id: string;
  recommendation_source: "ai" | "analyst";
  risk_level: string;
  reversible: boolean;
  status: string;
  execution_status: string;
  created_at: string;
};

type Incident = {
  incident_id: string;
  title: string;
  severity: string;
  primary_asset_id: string | null;
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

type ViewKey = "AWAITING_APPROVAL" | "APPROVED" | "EXECUTING" | "COMPLETED" | "FAILED" | "REJECTED" | "CANCELLED";

const VIEWS: { key: ViewKey; label: string }[] = [
  { key: "AWAITING_APPROVAL", label: "AWAITING APPROVAL" },
  { key: "APPROVED", label: "APPROVED / READY" },
  { key: "EXECUTING", label: "EXECUTING" },
  { key: "COMPLETED", label: "COMPLETED" },
  { key: "FAILED", label: "FAILED / ROLLED BACK" },
  { key: "REJECTED", label: "REJECTED" },
  { key: "CANCELLED", label: "CANCELLED" },
];

function viewFor(plan: ResponsePlan): ViewKey {
  if (plan.status === "REJECTED") return "REJECTED";
  if (plan.status === "CANCELLED") return "CANCELLED";
  if (plan.status === "AWAITING_APPROVAL") return "AWAITING_APPROVAL";
  // status === APPROVED from here on - bucket by execution_status
  if (["EXECUTING", "VERIFYING", "ROLLING_BACK"].includes(plan.execution_status)) return "EXECUTING";
  if (plan.execution_status === "SUCCEEDED") return "COMPLETED";
  if (["FAILED", "ROLLED_BACK", "ROLLBACK_FAILED"].includes(plan.execution_status)) return "FAILED";
  return "APPROVED"; // NOT_EXECUTED
}

export default async function ResponseCenterPage(props: PageProps<"/response-center">) {
  const sp = await props.searchParams;
  const view = (typeof sp.view === "string" ? sp.view : "AWAITING_APPROVAL") as ViewKey;

  const allPlans = (await getJSON<ResponsePlan[]>("/api/v1/response-plans")) ?? [];
  const plans = allPlans.filter((p) => viewFor(p) === view);
  const incidents = await Promise.all(
    plans.map((p) => getJSON<Incident>(`/api/v1/incidents/${p.incident_id}`)),
  );

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-6xl flex-col gap-6 px-8 py-16">
        <div>
          <Link href="/" className="text-sm text-zinc-500 hover:underline">
            ← Mission Cyber Posture
          </Link>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
            Response Center
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Policy-evaluated response plans, human approval, and bounded execution against the
            synthetic MissionNet lab only. Approval never auto-executes - execution is always a
            separate, explicit human action.
          </p>
        </div>

        <div className="flex flex-wrap gap-2 text-sm">
          {VIEWS.map((v) => {
            const count = allPlans.filter((p) => viewFor(p) === v.key).length;
            return (
              <Link
                key={v.key}
                href={`/response-center?view=${v.key}`}
                className={`rounded border px-2 py-1 text-xs ${
                  v.key === view
                    ? "border-black bg-black text-white dark:border-white dark:bg-white dark:text-black"
                    : "border-zinc-300 text-zinc-600 hover:border-zinc-500 dark:border-zinc-700 dark:text-zinc-400"
                }`}
              >
                {v.label} ({count})
              </Link>
            );
          })}
        </div>

        {plans.length === 0 && (
          <p className="text-sm text-zinc-500">No response plans in {view.replace("_", " ")}.</p>
        )}

        {plans.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-100 text-xs uppercase text-zinc-500 dark:bg-zinc-900">
                <tr>
                  <th className="px-3 py-2">Plan</th>
                  <th className="px-3 py-2">Incident</th>
                  <th className="px-3 py-2">Severity</th>
                  <th className="px-3 py-2">Asset</th>
                  <th className="px-3 py-2">Playbook</th>
                  <th className="px-3 py-2">Source</th>
                  <th className="px-3 py-2">Mission Impact</th>
                  <th className="px-3 py-2">Approval</th>
                  <th className="px-3 py-2">Execution</th>
                  <th className="px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {plans.map((plan, i) => {
                  const incident = incidents[i];
                  return (
                    <tr
                      key={plan.response_plan_id}
                      className="border-t border-zinc-200 dark:border-zinc-800"
                    >
                      <td className="px-3 py-2 font-mono text-xs">
                        <Link
                          href={`/response-plans/${plan.response_plan_id}`}
                          className="text-blue-600 hover:underline dark:text-blue-400"
                        >
                          {plan.response_plan_id.slice(0, 13)}… (REVIEW)
                        </Link>
                      </td>
                      <td className="px-3 py-2 font-mono text-xs">
                        <Link
                          href={`/incidents/${plan.incident_id}`}
                          className="text-blue-600 hover:underline dark:text-blue-400"
                        >
                          {incident?.title ?? plan.incident_id}
                        </Link>
                      </td>
                      <td className="px-3 py-2 text-xs font-semibold uppercase">
                        {incident?.severity ?? "—"}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs">
                        {incident?.primary_asset_id ?? "—"}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs">{plan.playbook_id}</td>
                      <td className="px-3 py-2 text-xs uppercase text-zinc-500">
                        {plan.recommendation_source}
                      </td>
                      <td className="px-3 py-2 text-xs uppercase">{plan.risk_level}</td>
                      <td className="px-3 py-2 text-xs uppercase">{plan.status}</td>
                      <td className="px-3 py-2 font-mono text-xs uppercase">
                        {plan.execution_status}
                      </td>
                      <td className="px-3 py-2">
                        {view === "AWAITING_APPROVAL" && (
                          <ApprovalActions planId={plan.response_plan_id} />
                        )}
                        {view === "APPROVED" && <ExecuteAction planId={plan.response_plan_id} />}
                        {view === "COMPLETED" && plan.reversible && (
                          <RollbackAction planId={plan.response_plan_id} />
                        )}
                        {view === "FAILED" &&
                          plan.reversible &&
                          plan.execution_status === "FAILED" && (
                            <RollbackAction planId={plan.response_plan_id} />
                          )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
