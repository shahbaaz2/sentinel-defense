const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type Assurance = {
  deployment_profile: string;
  platform: string;
  inference_location: string;
  external_ai_api: string;
  ai_analyst_status: string;
  model: string;
  model_provider: string;
  missionnet_adapter: string;
  sentinel_api: string;
  postgresql: string;
  demo_control: string;
  local_llm_runtime: string;
  rag_status: string;
  response_authority: string;
  policy_engine: string;
  human_approval: string;
  response_execution: string;
  verification: string;
  rollback: string;
  integrations: Record<string, string>;
};

type Integration = {
  adapter_id: string;
  name: string;
  version: string;
  status: "ACTIVE" | "DEGRADED" | "NOT_CONFIGURED";
  capabilities: string[];
  supported_event_categories: string[];
  last_successful_ingest_at: string | null;
  event_count: number;
};

async function getJSON<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

function statusTone(status: string) {
  const normalized = status.toUpperCase();
  if (["ACTIVE", "ONLINE", "READY", "OPERATIONAL", "NOMINAL", "ENABLED"].some((value) => normalized.includes(value))) {
    return "border-emerald-500/25 bg-emerald-500/5 text-emerald-300";
  }
  if (["DEGRADED", "OFFLINE", "UNAVAILABLE", "ERROR"].some((value) => normalized.includes(value))) {
    return "border-amber-500/25 bg-amber-500/5 text-amber-300";
  }
  return "border-slate-700 bg-[#0d1b29] text-slate-400";
}

function Node({ title, subtitle, status, technologies }: { title: string; subtitle: string; status: string; technologies: string[] }) {
  return (
    <div className="relative rounded-lg border border-slate-800 bg-[#0d1b29] p-4 shadow-[0_14px_35px_rgba(0,0,0,.12)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold text-white">{title}</p>
          <p className="mt-1 text-[9px] leading-4 text-slate-600">{subtitle}</p>
        </div>
        <span className={`rounded border px-2 py-1 font-mono text-[8px] font-semibold ${statusTone(status)}`}>{status}</span>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {technologies.map((technology) => (
          <span key={technology} className="rounded border border-slate-700 bg-[#08131e] px-2 py-1 text-[9px] font-medium text-slate-400">{technology}</span>
        ))}
      </div>
    </div>
  );
}

export default async function ArchitecturePage() {
  const [assurance, integrations] = await Promise.all([
    getJSON<Assurance>("/api/v1/system/assurance"),
    getJSON<Integration[]>("/api/v1/integrations"),
  ]);

  return (
    <main className="min-h-screen">
      <header className="border-b border-slate-800 bg-[#091521]/90 px-5 py-4 backdrop-blur lg:px-7">
        <div className="mx-auto w-full max-w-[1680px]">
          <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-[0.14em] text-slate-600">
            <span>Security Operations</span><span>/</span><span className="text-slate-400">Platform Architecture</span>
          </div>
          <div className="mt-2 flex flex-col justify-between gap-4 xl:flex-row xl:items-end">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-white">Sentinel Technology & Control Topology</h1>
              <p className="mt-2 max-w-4xl text-xs leading-5 text-slate-400">
                Employer-facing architecture view of how synthetic protected-system activity becomes evidence, deterministic security findings, incident investigations, advisory AI output, bounded response actions, and verified recovery.
              </p>
            </div>
            <span className="rounded border border-slate-700 bg-[#0d1b29] px-3 py-2 font-mono text-[9px] text-slate-500">Runtime state + supported integration boundary</span>
          </div>
        </div>
      </header>

      <div className="mx-auto w-full max-w-[1680px] space-y-5 p-5 lg:p-7">
        <section className="soc-panel rounded-lg p-5">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div><p className="soc-kicker">End-to-end data path</p><h2 className="mt-1 text-sm font-semibold text-white">Security Control Plane</h2></div>
            <span className="rounded border border-emerald-500/20 bg-emerald-500/5 px-2 py-1 text-[9px] font-semibold text-emerald-300">Deterministic core</span>
          </div>

          <div className="grid gap-3 xl:grid-cols-7">
            <Node title="Protected Environment" subtitle="Source application state and controlled lab activity." status={assurance?.missionnet_adapter ?? "UNKNOWN"} technologies={["MissionNet", "FastAPI", "PostgreSQL"]} />
            <Node title="Telemetry & Sensors" subtitle="Application and network evidence enters through vendor-neutral adapters." status="ADAPTER BOUNDARY" technologies={["MissionNet", "Suricata", "Zeek", "Wazuh", "Falco"]} />
            <Node title="Normalization" subtitle="Source events are normalized into a stable security-event contract." status="DETERMINISTIC" technologies={["Pydantic", "Python", "Schema contracts"]} />
            <Node title="Detection" subtitle="Rules establish findings without relying on an LLM." status="DETERMINISTIC" technologies={["Rule engine", "MITRE ATT&CK", "Evidence refs"]} />
            <Node title="Correlation" subtitle="Detections are grouped into incidents using fixed security logic." status="DETERMINISTIC" technologies={["Correlation engine", "PostgreSQL", "SQLAlchemy"]} />
            <Node title="AI Advisory" subtitle="Second-opinion analysis is evidence-grounded and non-authoritative." status={assurance?.ai_analyst_status ?? "UNKNOWN"} technologies={[assurance?.model_provider ?? "DeepSeek", assurance?.model ?? "AI model", "RAG", "KEV"]} />
            <Node title="Response & Recovery" subtitle="Human-approved actions execute through bounded policy with verification and rollback." status={assurance?.response_execution ?? "UNKNOWN"} technologies={["Policy Engine", "Human Approval", "Verification", "Rollback"]} />
          </div>

          <div className="mt-3 hidden grid-cols-7 gap-3 xl:grid">
            {Array.from({ length: 6 }).map((_, index) => <div key={index} className="relative col-span-1 h-5"><div className="absolute left-[55%] right-[-55%] top-2 h-px bg-gradient-to-r from-sky-500/60 to-slate-700" /><span className="absolute right-[-58%] top-[3px] text-[10px] text-sky-500">›</span></div>)}
          </div>
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,.75fr)]">
          <div className="soc-panel rounded-lg">
            <div className="border-b border-slate-800 px-5 py-4"><p className="soc-kicker">Runtime technology fabric</p><h2 className="mt-1 text-sm font-semibold text-white">Application & Cloud Stack</h2></div>
            <div className="grid gap-px bg-slate-800 md:grid-cols-2">
              {[
                ["Experience", ["Next.js 16", "React 19", "TypeScript", "Tailwind CSS 4", "Server Components", "SSE live updates"]],
                ["API & Services", ["Python", "FastAPI", "Uvicorn", "Pydantic", "httpx", "Async workflows"]],
                ["Persistence", ["PostgreSQL", "SQLAlchemy", "asyncpg", "Alembic", "Evidence provenance"]],
                ["Cloud Delivery", ["Vercel", "Render", "GitHub", "Environment-scoped configuration", "Health checks"]],
                ["Detection Engineering", ["Deterministic rules", "Correlation", "MITRE ATT&CK", "Scenario validation", "Replay idempotency"]],
                ["AI & Knowledge", [assurance?.model_provider ?? "DeepSeek", assurance?.model ?? "Configured model", "RAG", "KEV context", "Runbooks", "Schema-validated output"]],
              ].map(([label, rawItems]) => {
                const items = rawItems as string[];
                return (
                  <div key={label as string} className="bg-[#0d1b29] p-5">
                    <p className="soc-kicker">{label as string}</p>
                    <div className="mt-3 flex flex-wrap gap-1.5">{items.map((item) => <span key={item} className="rounded border border-slate-700 bg-[#08131e] px-2 py-1 text-[9px] text-slate-400">{item}</span>)}</div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="soc-panel rounded-lg">
            <div className="border-b border-slate-800 px-5 py-4"><p className="soc-kicker">Authority model</p><h2 className="mt-1 text-sm font-semibold text-white">Trust Boundaries</h2></div>
            <div className="space-y-3 p-5">
              {[
                ["Security truth", "Deterministic rules + persisted evidence", "emerald"],
                ["Incident creation", "Deterministic correlation", "emerald"],
                ["AI role", "Advisory analysis only", "amber"],
                ["Response authority", assurance?.response_authority ?? "Human controlled", "sky"],
                ["Policy engine", assurance?.policy_engine ?? "Unknown", "sky"],
                ["Human approval", assurance?.human_approval ?? "Required", "sky"],
                ["Verification", assurance?.verification ?? "Unknown", "emerald"],
                ["Rollback", assurance?.rollback ?? "Unknown", "emerald"],
              ].map(([label, value, tone]) => (
                <div key={label as string} className="flex items-center justify-between gap-4 rounded border border-slate-800 bg-[#0d1b29] px-3 py-3">
                  <span className="text-[10px] text-slate-500">{label as string}</span>
                  <span className={`text-right font-mono text-[9px] font-semibold ${tone === "emerald" ? "text-emerald-300" : tone === "amber" ? "text-amber-300" : "text-sky-300"}`}>{value as string}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="soc-panel rounded-lg">
          <div className="flex flex-col justify-between gap-3 border-b border-slate-800 px-5 py-4 sm:flex-row sm:items-center">
            <div><p className="soc-kicker">Enterprise ecosystem</p><h2 className="mt-1 text-sm font-semibold text-white">Integration Adapter Registry</h2><p className="mt-1 text-[10px] text-slate-600">Status reflects the API integration registry. Supported does not mean enabled in this cloud deployment.</p></div>
            <span className="rounded border border-slate-700 bg-[#0d1b29] px-2 py-1 font-mono text-[9px] text-slate-500">{integrations?.length ?? 0} adapters returned</span>
          </div>
          <div className="grid gap-3 p-5 md:grid-cols-2 xl:grid-cols-3">
            {(integrations ?? []).map((integration) => (
              <div key={integration.adapter_id} className="rounded border border-slate-800 bg-[#0d1b29] p-4">
                <div className="flex items-start justify-between gap-3"><div><p className="text-[11px] font-semibold text-white">{integration.name}</p><p className="mt-1 font-mono text-[8px] text-slate-600">{integration.adapter_id} · v{integration.version}</p></div><span className={`rounded border px-2 py-1 text-[8px] font-semibold ${statusTone(integration.status)}`}>{integration.status}</span></div>
                <div className="mt-3 flex flex-wrap gap-1.5">{integration.capabilities.map((capability) => <span key={capability} className="rounded border border-slate-700 px-2 py-1 text-[8px] text-slate-500">{capability}</span>)}</div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-[9px]"><div><p className="text-slate-600">Events</p><p className="mt-1 font-mono text-slate-300">{integration.event_count.toLocaleString()}</p></div><div><p className="text-slate-600">Last ingest</p><p className="mt-1 font-mono text-slate-300">{integration.last_successful_ingest_at ? new Date(integration.last_successful_ingest_at).toLocaleString() : "none"}</p></div></div>
              </div>
            ))}
            {(!integrations || integrations.length === 0) && <p className="text-[10px] text-slate-600">Integration registry is currently unavailable.</p>}
          </div>
        </section>
      </div>
    </main>
  );
}
