import Link from "next/link";
import { ResponseCenterActions } from "./ResponseCenterActions";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type ResponsePlan = {
  response_plan_id: string;
  incident_id: string;
  playbook_id: string;
  recommendation_source: "ai" | "analyst";
  risk_level: string;
  reversible: boolean;
  status: string;
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

const STATUSES = ["AWAITING_APPROVAL", "APPROVED", "REJECTED", "CANCELLED"];

export default async function ResponseCenterPage(props: PageProps<"/response-center">) {
  const sp = await props.searchParams;
  const status = typeof sp.status === "string" ? sp.status : "AWAITING_APPROVAL";

  const plans = (await getJSON<ResponsePlan[]>(`/api/v1/response-plans?status=${status}`)) ?? [];
  const incidents = await Promise.all(
    plans.map((p) => getJSON<Incident>(`/api/v1/incidents/${p.incident_id}`)),
  );

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-5xl flex-col gap-6 px-8 py-16">
        <div>
          <Link href="/" className="text-sm text-zinc-500 hover:underline">
            ← Mission Cyber Posture
          </Link>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
            Response Center
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Policy-evaluated response plans awaiting human review. Nothing here executes anything -
            approving a plan only records that a human authorized it (
            <span className="font-mono">execution_status: EXECUTION_NOT_ENABLED</span>).
          </p>
        </div>

        <div className="flex gap-2 text-sm">
          {STATUSES.map((s) => (
            <Link
              key={s}
              href={`/response-center?status=${s}`}
              className={`rounded border px-2 py-1 text-xs ${
                s === status
                  ? "border-black bg-black text-white dark:border-white dark:bg-white dark:text-black"
                  : "border-zinc-300 text-zinc-600 hover:border-zinc-500 dark:border-zinc-700 dark:text-zinc-400"
              }`}
            >
              {s}
            </Link>
          ))}
        </div>

        {plans.length === 0 && (
          <p className="text-sm text-zinc-500">No response plans with status {status}.</p>
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
                  <th className="px-3 py-2">Reversible</th>
                  <th className="px-3 py-2">Created</th>
                  {status === "AWAITING_APPROVAL" && <th className="px-3 py-2">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {plans.map((plan, i) => {
                  const incident = incidents[i];
                  return (
                    <tr key={plan.response_plan_id} className="border-t border-zinc-200 dark:border-zinc-800">
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
                      <td className="px-3 py-2 text-xs">{plan.reversible ? "yes" : "no"}</td>
                      <td className="px-3 py-2 text-xs text-zinc-500">
                        {new Date(plan.created_at).toLocaleString()}
                      </td>
                      {status === "AWAITING_APPROVAL" && (
                        <td className="px-3 py-2">
                          <ResponseCenterActions planId={plan.response_plan_id} />
                        </td>
                      )}
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
