import Link from "next/link";
import { AIAnalystPanel } from "./AIAnalystPanel";
import { IncidentWorkflowPanel } from "./IncidentWorkflowPanel";
import { ResponsePlanCreator } from "./ResponsePlanCreator";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type Detection = {
  detection_id: string;
  rule_id: string;
  rule_name: string;
  rule_version: string;
  severity: string;
  evidence_summary: string;
  mitre_techniques: string[];
  event_ids: string[];
};

type Note = { note_id: string; author: string; body: string; created_at: string };

type AIAssessment = {
  assessment_id: string;
  incident_id: string;
  created_at: string;
  model_name: string;
  model_provider: string;
  prompt_version: string;
  validation_status: "VALID" | "REJECTED_SCHEMA" | "REJECTED_HALLUCINATION" | "TIMEOUT" | "PROVIDER_ERROR";
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

type IncidentDetail = {
  incident_id: string;
  title: string;
  severity: string;
  status: string;
  category: string;
  summary: string;
  primary_asset_id: string | null;
  scenario_id: string | null;
  assigned_to: string | null;
  disposition: string | null;
  resolved_at: string | null;
  mitre_techniques: string[];
  first_seen: string;
  last_seen: string;
  created_at: string;
  updated_at: string;
  detections: Detection[];
  detection_ids: string[];
  event_ids: string[];
  notes: Note[];
};

type Playbook = { id: string; name: string; requires_human_approval: boolean };
type ResponsePlanSummary = {
  response_plan_id: string;
  playbook_id: string;
  status: string;
  execution_status: string;
  created_at: string;
};

type NormalizedEvent = {
  event_id: string;
  timestamp: string;
  source: string;
  source_event_id: string;
  event_category: string;
  event_type: string;
  severity: string;
  asset_id: string | null;
  user_id: string | null;
  summary: string;
  raw_event_ref: string;
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

function correlationExplanation(incident: IncidentDetail): string {
  if (incident.detections.length <= 1) {
    return "A single detection was sufficient to open this incident - no correlation with other detections was needed.";
  }
  const basis = incident.primary_asset_id ? "the same asset" : "the same identity";
  return (
    `${incident.detections.length} detections were correlated because they share ${basis} ` +
    `and occurred within the deterministic correlation window (see docs/incident-correlation.md). ` +
    `This is a fixed rule, not a judgment call.`
  );
}

export default async function IncidentDetailPage(props: PageProps<"/incidents/[id]">) {
  const { id } = await props.params;
  const incident = await getJSON<IncidentDetail>(`/api/v1/incidents/${id}`);

  if (!incident) {
    return (
      <div className="flex flex-1 flex-col items-center bg-zinc-50 p-16 font-sans dark:bg-black">
        <p className="text-sm text-red-600 dark:text-red-400">Incident not found.</p>
      </div>
    );
  }

  const events = await Promise.all(
    incident.event_ids.map((eventId) => getJSON<NormalizedEvent>(`/api/v1/events/${eventId}`)),
  );
  const latestAssessment = await getJSON<AIAssessment>(
    `/api/v1/incidents/${incident.incident_id}/ai/assessment`,
  );
  const assessmentHistory = await getJSON<AIAssessment[]>(
    `/api/v1/incidents/${incident.incident_id}/ai/assessments`,
  );
  const eligiblePlaybooks =
    (await getJSON<Playbook[]>(`/api/v1/incidents/${incident.incident_id}/eligible-playbooks`)) ??
    [];
  const responsePlans =
    (await getJSON<ResponsePlanSummary[]>(
      `/api/v1/incidents/${incident.incident_id}/response-plans`,
    )) ?? [];
  const aiRecommendedPlaybookId =
    latestAssessment?.validation_status === "VALID"
      ? (latestAssessment.assessment?.recommended_playbook_id ?? null)
      : null;

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-4xl flex-col gap-8 px-8 py-16">
        <div>
          <Link href="/incidents" className="text-sm text-zinc-500 hover:underline">
            ← Live Incidents
          </Link>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-black dark:text-zinc-50">
            {incident.title}
          </h1>
          <p className="mt-1 font-mono text-xs text-zinc-500">{incident.incident_id}</p>
        </div>

        {/* A. INCIDENT SUMMARY */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Severity</p>
            <p className="font-semibold uppercase">{incident.severity}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Status</p>
            <p className="font-semibold uppercase">{incident.status}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Primary Asset</p>
            <p className="font-mono text-sm">{incident.primary_asset_id ?? "—"}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Detections / Evidence</p>
            <p className="font-semibold">
              {incident.detection_ids.length} / {incident.event_ids.length}
            </p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">First Seen</p>
            <p className="text-sm">{new Date(incident.first_seen).toLocaleString()}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Last Seen</p>
            <p className="text-sm">{new Date(incident.last_seen).toLocaleString()}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Assigned Analyst</p>
            <p className="text-sm">{incident.assigned_to ?? "unassigned"}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Disposition</p>
            <p className="text-sm">{incident.disposition ?? "undetermined"}</p>
          </div>
        </div>

        {/* B. OBSERVED EVIDENCE */}
        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Observed Evidence
          </h2>
          <p className="mb-3 text-xs text-zinc-500">
            Facts from Sentinel&apos;s ingest pipeline — never interpreted, only recorded.
          </p>
          <ul className="flex flex-col gap-2">
            {events.map(
              (event) =>
                event && (
                  <li
                    key={event.event_id}
                    className="rounded border border-zinc-200 px-3 py-2 text-xs dark:border-zinc-800"
                  >
                    <div>
                      <span className="font-mono text-zinc-500">
                        {new Date(event.timestamp).toLocaleString()}
                      </span>{" "}
                      <span className="font-medium">{event.event_type}</span> (
                      {event.event_category}, {event.severity}) — {event.summary}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] text-zinc-400">
                      <span>source: {event.source}</span>
                      <span>asset: {event.asset_id ?? "—"}</span>
                      <span>user: {event.user_id ?? "—"}</span>
                      <Link
                        href={`/events/${event.event_id}`}
                        className="text-blue-600 hover:underline dark:text-blue-400"
                      >
                        source_event_id: {event.source_event_id} → view raw provenance
                      </Link>
                    </div>
                  </li>
                ),
            )}
          </ul>
        </section>

        {/* C. DETERMINISTIC DETECTIONS */}
        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Deterministic Detections
          </h2>
          <p className="mb-3 text-xs text-zinc-500">
            Rule-based matches — no AI involved in creating any of these.
          </p>
          <ul className="flex flex-col gap-3">
            {incident.detections.map((d) => (
              <li
                key={d.detection_id}
                className="rounded border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-zinc-500">
                    {d.rule_id} v{d.rule_version}
                  </span>
                  <span className="text-xs font-semibold uppercase">{d.severity}</span>
                </div>
                <p className="font-medium">{d.rule_name}</p>
                <p className="text-xs text-zinc-600 dark:text-zinc-400">{d.evidence_summary}</p>
                <p className="mt-1 font-mono text-[10px] text-zinc-400">
                  matching events: {d.event_ids.join(", ")}
                </p>
                {d.mitre_techniques.length > 0 && (
                  <p className="mt-1 font-mono text-xs text-zinc-500">
                    ATT&CK: {d.mitre_techniques.join(", ")}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </section>

        {/* D. CORRELATION */}
        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Incident Correlation
          </h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">{correlationExplanation(incident)}</p>
        </section>

        {/* E. AI ANALYST */}
        <AIAnalystPanel
          incidentId={incident.incident_id}
          initialAssessment={latestAssessment}
          initialAssessmentCount={assessmentHistory?.length ?? 0}
        />

        {/* RESPONSE PLANNING (Phase 6) */}
        <ResponsePlanCreator
          incidentId={incident.incident_id}
          aiRecommendedPlaybookId={aiRecommendedPlaybookId}
          aiAssessmentId={latestAssessment?.assessment_id ?? null}
          initialEligiblePlaybooks={eligiblePlaybooks}
          initialResponsePlans={responsePlans}
        />

        {/* F. ANALYST WORKFLOW */}
        <IncidentWorkflowPanel
          incidentId={incident.incident_id}
          initialStatus={incident.status}
          initialAssignedTo={incident.assigned_to}
          initialDisposition={incident.disposition}
          initialNotes={incident.notes}
        />

        {/* G. PROVENANCE */}
        <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Provenance
          </h2>
          <dl className="grid grid-cols-1 gap-y-2 text-xs sm:grid-cols-2">
            <dt className="text-zinc-500">Source event IDs</dt>
            <dd className="font-mono">{incident.event_ids.join(", ") || "—"}</dd>
            <dt className="text-zinc-500">Detection IDs</dt>
            <dd className="font-mono">{incident.detection_ids.join(", ") || "—"}</dd>
            <dt className="text-zinc-500">Rule version(s)</dt>
            <dd className="font-mono">
              {[...new Set(incident.detections.map((d) => `${d.rule_id}@${d.rule_version}`))].join(
                ", ",
              ) || "—"}
            </dd>
            <dt className="text-zinc-500">Scenario / Run provenance</dt>
            <dd className="font-mono">{incident.scenario_id ?? "not scenario-attributed"}</dd>
            <dt className="text-zinc-500">Created</dt>
            <dd className="font-mono">{new Date(incident.created_at).toLocaleString()}</dd>
            <dt className="text-zinc-500">Last updated</dt>
            <dd className="font-mono">{new Date(incident.updated_at).toLocaleString()}</dd>
          </dl>
          <p className="mt-3 text-xs text-zinc-500">
            Full audit trail:{" "}
            <Link
              href={`/audit?entity_id=${incident.incident_id}`}
              className="text-blue-600 hover:underline dark:text-blue-400"
            >
              view in Audit / Provenance →
            </Link>
          </p>
        </section>
      </main>
    </div>
  );
}
