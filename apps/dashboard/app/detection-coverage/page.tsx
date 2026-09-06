import Link from "next/link";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type RuleCoverage = {
  rule_id: string;
  name: string;
  version: string;
  enabled: boolean;
  severity: string;
  category: string;
  description: string;
  event_categories: string[];
  mitre_techniques: string[];
  validating_scenarios: string[];
  validation_status: "VALIDATED" | "FAILED" | "NOT_TESTED";
  last_triggered: string | null;
  total_detections: number;
};

async function getCoverage(): Promise<RuleCoverage[] | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/detection-coverage`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as RuleCoverage[];
  } catch {
    return null;
  }
}

const STATUS_STYLE: Record<string, string> = {
  VALIDATED: "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400",
  FAILED: "bg-red-500/20 text-red-700 dark:text-red-400",
  NOT_TESTED: "bg-zinc-500/20 text-zinc-600 dark:text-zinc-400",
};

export default async function DetectionCoveragePage() {
  const coverage = await getCoverage();

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-5xl flex-col gap-6 px-8 py-16">
        <div>
          <Link href="/" className="text-sm text-zinc-500 hover:underline">
            ← Mission Cyber Posture
          </Link>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
            Detection Coverage
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Every rule Sentinel actually ships, and whether a Demo Control scenario has ever
            genuinely triggered and validated it. No fabricated percentages - a rule is either
            validated by a real run, failed by one, or not yet tested.
          </p>
        </div>

        {coverage === null && (
          <p className="text-sm text-red-600 dark:text-red-400">Sentinel API unreachable.</p>
        )}
        {coverage !== null && (
          <div className="flex flex-col gap-4">
            {coverage.map((rule) => (
              <div
                key={rule.rule_id}
                className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm text-zinc-500">
                      {rule.rule_id} v{rule.version}
                    </span>
                    <span className="font-medium">{rule.name}</span>
                    <span className="rounded bg-zinc-500/10 px-1.5 py-0.5 text-[10px] uppercase text-zinc-500">
                      {rule.severity}
                    </span>
                    {!rule.enabled && (
                      <span className="rounded bg-red-500/10 px-1.5 py-0.5 text-[10px] uppercase text-red-500">
                        disabled
                      </span>
                    )}
                  </div>
                  <span
                    className={`rounded px-2 py-1 text-xs font-semibold ${STATUS_STYLE[rule.validation_status]}`}
                  >
                    {rule.validation_status.replace("_", " ")}
                  </span>
                </div>
                <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">{rule.description}</p>
                <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-xs text-zinc-500 sm:grid-cols-4">
                  <span>Category: {rule.category}</span>
                  <span>Event categories: {rule.event_categories.join(", ") || "—"}</span>
                  <span>ATT&CK: {rule.mitre_techniques.join(", ") || "none"}</span>
                  <span>Total detections: {rule.total_detections}</span>
                  <span>
                    Last triggered:{" "}
                    {rule.last_triggered ? new Date(rule.last_triggered).toLocaleString() : "never"}
                  </span>
                  <span>
                    Validating scenarios: {rule.validating_scenarios.join(", ") || "none"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
