import { AIAdvisoryWorkspace } from "./AIAdvisoryWorkspace";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type Incident = {
  incident_id: string;
  title: string;
  severity: string;
  status: string;
  category: string;
  primary_asset_id: string | null;
  detection_ids: string[];
  first_seen: string;
};

type AIStatus = {
  ai_enabled: boolean;
  provider: string;
  model: string;
  status: string;
  external_ai_api?: string;
  last_latency_ms: number | null;
};

type Diagnostics = {
  status: string;
  code: string | null;
  message: string | null;
  provider: string;
  model: string;
  sentinel_core_affected: boolean;
};

type Assessment = {
  assessment_id: string;
  incident_id: string;
  created_at: string;
  model_name: string;
  model_provider: string;
  prompt_version: string;
  validation_status: string;
  assessment: {
    classification: string;
    confidence: number;
    summary: string;
    affected_assets: string[];
    evidence_refs: { event_id: string; relevance: string }[];
    detection_refs: { detection_id: string; relevance: string }[];
    hypotheses: string[];
    recommended_investigation_steps: string[];
    attack_techniques: string[];
    recommended_playbook_id: string | null;
    limitations: string[];
  } | null;
  latency_ms: number | null;
  error: string | null;
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

export default async function AIAdvisoryPage() {
  const [status, diagnostics, incidentsResponse] = await Promise.all([
    getJSON<AIStatus>("/api/v1/ai/status"),
    getJSON<Diagnostics>("/api/v1/ai/provider-diagnostics"),
    getJSON<Incident[]>("/api/v1/incidents?limit=50"),
  ]);

  const incidents = (incidentsResponse ?? []).slice(0, 20);
  const latest = await Promise.all(
    incidents.map(async (incident) => [
      incident.incident_id,
      await getJSON<Assessment>(`/api/v1/incidents/${incident.incident_id}/ai/assessment`),
    ] as const),
  );
  const initialAssessments = Object.fromEntries(latest) as Record<string, Assessment | null>;

  return (
    <main className="min-h-screen">
      <header className="border-b border-slate-800 bg-[#091521]/90 px-5 py-4 backdrop-blur lg:px-7">
        <div className="mx-auto w-full max-w-[1680px]">
          <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-[0.14em] text-slate-600">
            <span>Security Operations</span><span>/</span><span>Investigations</span><span>/</span><span className="text-slate-400">AI Advisory</span>
          </div>
          <div className="mt-2 flex flex-col justify-between gap-4 xl:flex-row xl:items-end">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-2xl font-semibold tracking-tight text-white">AI Advisory Workspace</h1>
                <span className="rounded border border-amber-500/25 bg-amber-500/5 px-2 py-1 text-[9px] font-bold uppercase tracking-wider text-amber-300">Non-authoritative analysis</span>
              </div>
              <p className="mt-2 max-w-4xl text-xs leading-5 text-slate-400">
                Evidence-grounded second-opinion analysis over incidents that already exist. Sentinel's deterministic rule and correlation engines remain the source of security truth; AI cannot create findings or execute response actions.
              </p>
            </div>
            <div className="rounded border border-slate-700 bg-[#0d1b29] px-3 py-2 font-mono text-[9px] text-slate-500">
              Provider diagnostics + incident analysis + ATT&amp;CK context
            </div>
          </div>
        </div>
      </header>

      <div className="mx-auto w-full max-w-[1680px] p-5 lg:p-7">
        <AIAdvisoryWorkspace
          incidents={incidents}
          initialStatus={status}
          initialDiagnostics={diagnostics}
          initialAssessments={initialAssessments}
        />
      </div>
    </main>
  );
}
