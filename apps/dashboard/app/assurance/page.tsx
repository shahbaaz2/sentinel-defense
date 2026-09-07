import Link from "next/link";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type Assurance = {
  deployment_profile: string;
  platform: string;
  inference_location: string;
  external_ai_api: string;
  ai_analyst_status: string;
  internet_required_for_core_demo: string;
  model: string;
  model_provider: string;
  knowledge_bundle: string;
  policy_bundle: string;
  synthetic_only: boolean;
  missionnet_adapter: string;
  sentinel_api: string;
  postgresql: string;
  demo_control: string;
  local_llm_runtime: string;
  rag_status: string;
  response_authority: string;
  response_planning: string;
  policy_engine: string;
  human_approval: string;
  response_execution: string;
  autonomous_response: string;
  integrations: Record<string, string>;
};

async function getAssurance(): Promise<Assurance | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/system/assurance`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as Assurance;
  } catch {
    return null;
  }
}

function Row({ label, value }: { label: string; value: string }) {
  const ok = [
    "ONLINE",
    "ACTIVE",
    "DISABLED",
    "OPERATIONAL",
    "READY",
    "NONE",
    "ENABLED",
    "DISABLED - NEXT PHASE",
  ].includes(value);
  const warn = value === "OFFLINE" || value === "DEGRADED";
  return (
    <div className="flex items-center justify-between border-t border-zinc-200 py-2 text-sm first:border-t-0 dark:border-zinc-800">
      <span className="text-zinc-600 dark:text-zinc-400">{label}</span>
      <span
        className={`font-mono text-xs ${
          ok ? "text-emerald-600 dark:text-emerald-400" : warn ? "text-red-600 dark:text-red-400" : ""
        }`}
      >
        {value}
      </span>
    </div>
  );
}

export default async function AssurancePage() {
  const assurance = await getAssurance();

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-3xl flex-col gap-6 px-8 py-16">
        <div>
          <Link href="/" className="text-sm text-zinc-500 hover:underline">
            ← Mission Cyber Posture
          </Link>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
            System Assurance
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            How this prototype is actually deployed - every field below reflects a real check, not
            an assertion. Mapping to controls is not certification; nothing here claims DoD/CMMC/
            FedRAMP approval or classified-ready status.
          </p>
        </div>

        {assurance === null && (
          <p className="text-sm text-red-600 dark:text-red-400">Sentinel API unreachable.</p>
        )}
        {assurance !== null && (
          <>
            <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
              <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-zinc-500">
                Deployment
              </h2>
              <Row label="Deployment Profile" value={assurance.deployment_profile} />
              <Row label="Platform" value={assurance.platform} />
              <Row label="Inference Location" value={assurance.inference_location} />
              <Row label="External AI API" value={assurance.external_ai_api} />
              <Row label="AI Analyst" value={assurance.ai_analyst_status} />
              <Row label="Local LLM Runtime" value={assurance.local_llm_runtime} />
              <Row label="RAG" value={assurance.rag_status} />
              <Row label="Response Authority" value={assurance.response_authority} />
              <Row
                label="Internet Required for Core Demo"
                value={assurance.internet_required_for_core_demo}
              />
              <Row label="Synthetic Only" value={String(assurance.synthetic_only).toUpperCase()} />
            </section>

            <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
              <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-zinc-500">
                Response Planning &amp; Policy
              </h2>
              <Row label="Response Planning" value={assurance.response_planning} />
              <Row label="Policy Engine" value={assurance.policy_engine} />
              <Row label="Human Approval" value={assurance.human_approval} />
              <Row label="Response Execution" value={assurance.response_execution} />
              <Row label="Autonomous Response" value={assurance.autonomous_response} />
            </section>

            <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
              <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-zinc-500">
                Model &amp; Knowledge
              </h2>
              <Row label="Model" value={assurance.model} />
              <Row label="Model Provider" value={assurance.model_provider} />
              <Row label="Knowledge Bundle" value={assurance.knowledge_bundle} />
              <Row label="Policy Bundle" value={assurance.policy_bundle} />
            </section>

            <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
              <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-zinc-500">
                Component Health
              </h2>
              <Row label="MissionNet Adapter" value={assurance.missionnet_adapter} />
              <Row label="Sentinel API" value={assurance.sentinel_api} />
              <Row label="PostgreSQL" value={assurance.postgresql} />
              <Row label="Demo Control" value={assurance.demo_control} />
            </section>

            <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
              <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-zinc-500">
                SIEM / Sensor Integrations
              </h2>
              {Object.entries(assurance.integrations).map(([name, status]) => (
                <Row key={name} label={name} value={status} />
              ))}
            </section>
          </>
        )}
      </main>
    </div>
  );
}
