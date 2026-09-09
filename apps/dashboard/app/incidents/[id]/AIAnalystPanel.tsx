"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type EvidenceRef = { event_id: string; relevance: string };
type DetectionRef = { detection_id: string; relevance: string };

type AssessmentContent = {
  classification: string;
  confidence: number;
  summary: string;
  affected_assets: string[];
  evidence_refs: EvidenceRef[];
  detection_refs: DetectionRef[];
  hypotheses: string[];
  recommended_investigation_steps: string[];
  attack_techniques: string[];
  recommended_playbook_id: string | null;
  limitations: string[];
};

type Assessment = {
  assessment_id: string;
  incident_id: string;
  created_at: string;
  model_name: string;
  model_provider: string;
  prompt_version: string;
  validation_status: "VALID" | "REJECTED_SCHEMA" | "REJECTED_HALLUCINATION" | "TIMEOUT" | "PROVIDER_ERROR";
  assessment: AssessmentContent | null;
  latency_ms: number | null;
  error: string | null;
};

type AIStatus = {
  ai_enabled: boolean;
  provider: string;
  model: string;
  status: "READY" | "LOADING" | "DEGRADED" | "DISABLED";
  last_latency_ms: number | null;
};

type ProviderDiagnostics = {
  status: "READY" | "LOADING" | "DEGRADED" | "DISABLED";
  code: string | null;
  message: string | null;
  provider: string;
  model: string;
  sentinel_core_affected: boolean;
};

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "READY" || status === "VALID"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300"
      : status === "DISABLED" || status === "LOADING"
        ? "border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400"
        : "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300";
  return <span className={`rounded border px-2 py-1 font-mono text-[10px] font-semibold ${color}`}>{status}</span>;
}

function errorCode(error: string | null): string | null {
  return error?.match(/^\[([A-Z0-9_]+)\]/)?.[1] ?? null;
}

function diagnosticTitle(code: string | null): string {
  if (code === "AI_PROVIDER_BILLING") return "AI provider balance unavailable";
  if (code === "AI_PROVIDER_AUTH") return "AI provider authentication failed";
  if (code === "AI_PROVIDER_RATE_LIMIT") return "AI provider rate limit reached";
  if (code === "AI_PROVIDER_UPSTREAM" || code === "AI_PROVIDER_NETWORK") return "AI provider temporarily unavailable";
  if (code === "AI_PROVIDER_TIMEOUT") return "AI provider request timed out";
  if (code === "AI_PROVIDER_INVALID_OUTPUT" || code === "AI_PROVIDER_INVALID_RESPONSE") return "AI provider response rejected";
  if (code === "AI_PROVIDER_CONFIG" || code === "AI_DISABLED") return "AI advisory not configured";
  return "AI advisory unavailable";
}

export function AIAnalystPanel({
  incidentId,
  initialAssessment,
  initialAssessmentCount,
}: {
  incidentId: string;
  initialAssessment: Assessment | null;
  initialAssessmentCount: number;
}) {
  const [aiStatus, setAiStatus] = useState<AIStatus | null>(null);
  const [diagnostics, setDiagnostics] = useState<ProviderDiagnostics | null>(null);
  const [assessment, setAssessment] = useState<Assessment | null>(initialAssessment);
  const [assessmentCount, setAssessmentCount] = useState(initialAssessmentCount);
  const [busy, setBusy] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);

  const refreshProviderState = useCallback(async () => {
    try {
      const [statusRes, diagnosticsRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/ai/status`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/v1/ai/provider-diagnostics`, { cache: "no-store" }),
      ]);
      setAiStatus(statusRes.ok ? ((await statusRes.json()) as AIStatus) : null);
      setDiagnostics(
        diagnosticsRes.ok ? ((await diagnosticsRes.json()) as ProviderDiagnostics) : null,
      );
    } catch {
      setAiStatus(null);
      setDiagnostics(null);
    }
  }, []);

  useEffect(() => {
    void refreshProviderState();
  }, [refreshProviderState]);

  async function handleAnalyze() {
    setBusy(true);
    setRequestError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/incidents/${incidentId}/ai/analyze`, {
        method: "POST",
      });
      if (res.status === 503) {
        setRequestError("AI Analyst is disabled on this deployment. Sentinel incident data is unaffected.");
        await refreshProviderState();
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const result = (await res.json()) as Assessment;
      setAssessment(result);
      setAssessmentCount((count) => count + 1);
      await refreshProviderState();
    } catch (err) {
      setRequestError(
        `Unable to submit the advisory analysis request${err instanceof Error ? ` (${err.message})` : ""}. The deterministic incident and evidence remain available.`,
      );
    } finally {
      setBusy(false);
    }
  }

  const latestErrorCode = errorCode(assessment?.error ?? null) ?? diagnostics?.code ?? null;
  const providerProblem =
    diagnostics && diagnostics.status !== "READY"
      ? diagnostics
      : assessment && assessment.validation_status !== "VALID"
        ? {
            status: "DEGRADED" as const,
            code: latestErrorCode,
            message: assessment.error,
            provider: assessment.model_provider,
            model: assessment.model_name,
            sentinel_core_affected: false,
          }
        : null;

  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex flex-col justify-between gap-3 border-b border-zinc-200 px-5 py-4 sm:flex-row sm:items-start dark:border-zinc-800">
        <div>
          <h2 className="text-sm font-semibold text-zinc-950 dark:text-zinc-100">AI Analyst</h2>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-zinc-500">
            Evidence-grounded advisory analysis for this existing incident. AI cannot create detections,
            create incidents, approve response actions, or modify MissionNet state.
          </p>
        </div>
        {aiStatus && <StatusBadge status={aiStatus.status} />}
      </div>

      <div className="p-5">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900/60">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">Provider</p>
            <p className="mt-1 font-mono text-xs text-zinc-800 dark:text-zinc-300">{aiStatus?.provider ?? diagnostics?.provider ?? "Unavailable"}</p>
          </div>
          <div className="rounded border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900/60">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">Model</p>
            <p className="mt-1 font-mono text-xs text-zinc-800 dark:text-zinc-300">{aiStatus?.model ?? diagnostics?.model ?? "Unavailable"}</p>
          </div>
          <div className="rounded border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900/60">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">Last latency</p>
            <p className="mt-1 font-mono text-xs text-zinc-800 dark:text-zinc-300">{aiStatus?.last_latency_ms != null ? `${aiStatus.last_latency_ms} ms` : "No completed sample"}</p>
          </div>
        </div>

        {providerProblem && (
          <div className="mt-4 rounded border border-amber-300 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/20">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-amber-200 px-4 py-3 dark:border-amber-900">
              <div>
                <p className="text-xs font-semibold text-amber-950 dark:text-amber-200">{diagnosticTitle(providerProblem.code)}</p>
                <p className="mt-1 text-[11px] text-amber-800/80 dark:text-amber-300/70">External AI advisory dependency</p>
              </div>
              {providerProblem.code && <span className="rounded border border-amber-300 bg-white px-2 py-1 font-mono text-[10px] text-amber-800 dark:border-amber-800 dark:bg-zinc-950 dark:text-amber-300">{providerProblem.code}</span>}
            </div>
            <div className="px-4 py-3 text-xs leading-5 text-amber-900 dark:text-amber-200">
              <p>{providerProblem.message ?? "The configured AI provider is currently unavailable."}</p>
              {!providerProblem.sentinel_core_affected && (
                <p className="mt-2 font-semibold">Sentinel Core status: unaffected. Deterministic detections, incidents, evidence, and response controls remain available.</p>
              )}
            </div>
          </div>
        )}

        {requestError && (
          <div className="mt-4 rounded border border-red-200 bg-red-50 px-4 py-3 text-xs leading-5 text-red-800 dark:border-red-900 dark:bg-red-950/20 dark:text-red-300">
            {requestError}
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            onClick={handleAnalyze}
            disabled={busy || !aiStatus?.ai_enabled}
            className="rounded-md bg-indigo-700 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-800 disabled:cursor-not-allowed disabled:bg-zinc-300 dark:disabled:bg-zinc-800"
          >
            {busy ? "Running advisory analysis…" : "Analyze with AI"}
          </button>
          {assessmentCount > 0 && (
            <span className="text-xs text-zinc-500">
              {assessmentCount} assessment{assessmentCount === 1 ? "" : "s"} recorded
            </span>
          )}
        </div>

        {assessment && (
          <div className="mt-5 rounded border border-zinc-200 dark:border-zinc-800">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-zinc-200 bg-zinc-50 px-4 py-3 text-[10px] text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60">
              <span>{new Date(assessment.created_at).toLocaleString()}</span>
              <span className="font-mono">{assessment.model_name}</span>
              <span className="font-mono">prompt {assessment.prompt_version}</span>
              {assessment.latency_ms !== null && <span>{assessment.latency_ms} ms</span>}
              <StatusBadge status={assessment.validation_status} />
            </div>

            <div className="p-4 text-sm">
              {assessment.validation_status !== "VALID" && (
                <div className="rounded border border-red-200 bg-red-50 px-3 py-3 text-xs leading-5 text-red-800 dark:border-red-900 dark:bg-red-950/20 dark:text-red-300">
                  <p className="font-semibold">This advisory attempt was not accepted as a valid assessment.</p>
                  <p className="mt-1">{assessment.error ?? assessment.validation_status}</p>
                  <p className="mt-2 text-red-700/80 dark:text-red-300/70">The incident's deterministic evidence and security state were not changed by this failure.</p>
                </div>
              )}

              {assessment.assessment && (
                <>
                  <div className="mb-3 flex flex-wrap items-center gap-3">
                    <span className="rounded border border-indigo-200 bg-indigo-50 px-2 py-1 text-xs font-semibold uppercase text-indigo-800 dark:border-indigo-900 dark:bg-indigo-950/30 dark:text-indigo-200">
                      {assessment.assessment.classification}
                    </span>
                    <span className="text-xs text-zinc-500">confidence {(assessment.assessment.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <p className="mb-4 leading-6 text-zinc-800 dark:text-zinc-200">{assessment.assessment.summary}</p>

                  {assessment.assessment.hypotheses.length > 0 && (
                    <div className="mb-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Hypotheses</p>
                      <ul className="mt-2 list-inside list-disc space-y-1 text-xs leading-5 text-zinc-700 dark:text-zinc-300">
                        {assessment.assessment.hypotheses.map((hypothesis, index) => <li key={index}>{hypothesis}</li>)}
                      </ul>
                    </div>
                  )}

                  {assessment.assessment.recommended_investigation_steps.length > 0 && (
                    <div className="mb-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Recommended investigation steps</p>
                      <ol className="mt-2 list-inside list-decimal space-y-1 text-xs leading-5 text-zinc-700 dark:text-zinc-300">
                        {assessment.assessment.recommended_investigation_steps.map((step, index) => <li key={index}>{step}</li>)}
                      </ol>
                    </div>
                  )}

                  {assessment.assessment.evidence_refs.length > 0 && (
                    <div className="mb-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Cited evidence</p>
                      <div className="mt-2 overflow-hidden rounded border border-zinc-200 dark:border-zinc-800">
                        {assessment.assessment.evidence_refs.map((reference) => (
                          <div key={reference.event_id} className="border-b border-zinc-100 px-3 py-2 text-xs last:border-0 dark:border-zinc-800">
                            <Link href={`/events/${reference.event_id}`} className="font-mono text-blue-700 hover:underline dark:text-blue-400">{reference.event_id}</Link>
                            <span className="text-zinc-500"> — {reference.relevance}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {assessment.assessment.detection_refs.length > 0 && (
                    <div className="mb-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Cited detections</p>
                      <ul className="mt-2 space-y-1 text-xs text-zinc-700 dark:text-zinc-300">
                        {assessment.assessment.detection_refs.map((reference) => (
                          <li key={reference.detection_id}><span className="font-mono">{reference.detection_id}</span> — {reference.relevance}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {assessment.assessment.attack_techniques.length > 0 && (
                    <p className="mb-3 font-mono text-xs text-zinc-500">ATT&amp;CK candidates: {assessment.assessment.attack_techniques.join(", ")}</p>
                  )}

                  <p className="mb-3 text-xs text-zinc-500">
                    Recommended playbook: {assessment.assessment.recommended_playbook_id ?? "none"}
                  </p>

                  {assessment.assessment.limitations.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Limitations</p>
                      <ul className="mt-2 list-inside list-disc space-y-1 text-xs text-zinc-500">
                        {assessment.assessment.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}
                      </ul>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}

        {!assessment && aiStatus?.ai_enabled && !providerProblem && (
          <p className="mt-4 text-xs text-zinc-500">No advisory analysis has been run for this incident.</p>
        )}
      </div>
    </section>
  );
}
