const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";
const DEMO_CONTROL_URL =
  process.env.NEXT_PUBLIC_DEMO_CONTROL_URL ?? "https://sentinel-defense-ov8q.vercel.app";

type RuleCoverage = {
  rule_id: string;
  name: string;
  severity: string;
  mitre_techniques: string[];
  validating_scenarios: string[];
  validation_status: "VALIDATED" | "FAILED" | "NOT_TESTED";
  total_detections: number;
};

const SCENARIOS = [
  {
    id: "SCN-010",
    title: "Multi-Signal Compromise",
    domain: "End-to-end SOC validation",
    expected: "5 deterministic detections · 3 incidents",
    description:
      "Flagship workflow covering credential pressure, service-identity misuse, service degradation, telemetry anomalies, correlation, evidence verification, and analyst handoff.",
    runtime: "MissionNet + Sentinel",
    cloudStatus: "Cloud validated",
  },
  {
    id: "SCN-001",
    title: "Credential Pressure",
    domain: "Identity security",
    expected: "DET-001",
    description:
      "Controlled repeated-authentication-failure workflow used to validate threshold-based credential-pressure detection.",
    runtime: "MissionNet + Sentinel",
    cloudStatus: "Controlled workflow",
  },
  {
    id: "SCN-002",
    title: "Service Identity Compromise",
    domain: "Service identity",
    expected: "DET-006",
    description:
      "Revoked service identity followed by protected data access, producing deterministic service-identity misuse evidence and correlation.",
    runtime: "MissionNet + Sentinel",
    cloudStatus: "Controlled workflow",
  },
  {
    id: "SCN-003",
    title: "Critical Service Degradation",
    domain: "Mission resilience",
    expected: "DET-002",
    description:
      "Changes a mission-critical service into a degraded state and verifies evidence-backed detection and incident creation.",
    runtime: "MissionNet + Sentinel",
    cloudStatus: "Controlled workflow",
  },
  {
    id: "SCN-004",
    title: "Data Access Burst",
    domain: "Behavior analytics",
    expected: "DET-003",
    description:
      "Controlled record-access activity used to exercise behavioral threshold detection through the normal evidence pipeline.",
    runtime: "MissionNet + Sentinel",
    cloudStatus: "Controlled workflow",
  },
  {
    id: "SCN-NET-001",
    title: "Network Sensor Detection",
    domain: "Network detection engineering",
    expected: "NET-001 · NET-002 · NET-003",
    description:
      "Safe isolated traffic is captured to PCAP and analyzed by Suricata and Zeek before entering Sentinel's normal normalization, detection, correlation, and verification pipeline.",
    runtime: "Docker + Suricata + Zeek",
    cloudStatus: "Requires sensor runtime",
  },
] as const;

async function getCoverage(): Promise<RuleCoverage[]> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/detection-coverage`, { cache: "no-store" });
    if (!response.ok) return [];
    return (await response.json()) as RuleCoverage[];
  } catch {
    return [];
  }
}

function badgeTone(status: string) {
  if (status === "VALIDATED") return "border-emerald-500/25 bg-emerald-500/5 text-emerald-300";
  if (status === "FAILED") return "border-red-500/25 bg-red-500/5 text-red-300";
  return "border-slate-700 bg-[#0d1b29] text-slate-400";
}

export default async function ScenariosPage() {
  const coverage = await getCoverage();

  return (
    <main className="min-h-screen">
      <header className="border-b border-slate-800 bg-[#091521]/90 px-5 py-4 backdrop-blur lg:px-7">
        <div className="mx-auto w-full max-w-[1680px]">
          <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-[0.14em] text-slate-600">
            <span>Security Operations</span><span>/</span><span className="text-slate-400">Scenario Validation</span>
          </div>
          <div className="mt-2 flex flex-col justify-between gap-4 xl:flex-row xl:items-end">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-white">Controlled Validation Library</h1>
              <p className="mt-2 max-w-4xl text-xs leading-5 text-slate-400">
                Repeatable defensive workflows that exercise Sentinel through real application state, telemetry, deterministic detections, incident correlation, evidence verification, and analyst handoff. Validation state is derived from the platform rather than invented for presentation.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="rounded border border-slate-700 bg-[#0d1b29] px-3 py-2 font-mono text-[9px] text-slate-500">6 scenario definitions</span>
              <a href={`${DEMO_CONTROL_URL.replace(/\/$/, "")}/live-demo`} target="_blank" rel="noreferrer" className="rounded bg-sky-500 px-3 py-2 text-[10px] font-bold text-slate-950 hover:bg-sky-400">Open scenario console ↗</a>
            </div>
          </div>
        </div>
      </header>

      <div className="mx-auto w-full max-w-[1680px] space-y-5 p-5 lg:p-7">
        <section className="grid gap-4 xl:grid-cols-2 2xl:grid-cols-3">
          {SCENARIOS.map((scenario) => {
            const rules = coverage.filter((rule) => rule.validating_scenarios.includes(scenario.id));
            const techniques = [...new Set(rules.flatMap((rule) => rule.mitre_techniques))];
            const validated = rules.filter((rule) => rule.validation_status === "VALIDATED").length;
            const scenarioHref = scenario.id === "SCN-NET-001"
              ? `${DEMO_CONTROL_URL.replace(/\/$/, "")}/live-demo/network`
              : `${DEMO_CONTROL_URL.replace(/\/$/, "")}/live-demo/scenarios/${scenario.id}`;

            return (
              <article key={scenario.id} className="soc-panel overflow-hidden rounded-lg">
                <div className="flex items-start justify-between gap-4 border-b border-slate-800 bg-[#0d1b29] px-5 py-4">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[10px] font-bold text-sky-300">{scenario.id}</span>
                      <span className="rounded border border-slate-700 px-2 py-0.5 text-[8px] uppercase tracking-wider text-slate-500">{scenario.domain}</span>
                    </div>
                    <h2 className="mt-2 text-sm font-semibold text-white">{scenario.title}</h2>
                  </div>
                  <span className="rounded border border-slate-700 bg-[#08131e] px-2 py-1 text-[9px] text-slate-400">{scenario.cloudStatus}</span>
                </div>

                <div className="space-y-4 p-5">
                  <p className="text-[11px] leading-5 text-slate-400">{scenario.description}</p>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="rounded border border-slate-800 bg-[#0d1b29] p-3">
                      <p className="soc-kicker">Expected security result</p>
                      <p className="mt-2 text-[10px] font-semibold leading-4 text-slate-200">{scenario.expected}</p>
                    </div>
                    <div className="rounded border border-slate-800 bg-[#0d1b29] p-3">
                      <p className="soc-kicker">Execution fabric</p>
                      <p className="mt-2 text-[10px] font-semibold leading-4 text-slate-200">{scenario.runtime}</p>
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between gap-3">
                      <p className="soc-kicker">Detection validation</p>
                      <span className="font-mono text-[9px] text-slate-500">{validated}/{rules.length || 0} validated rules</span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {rules.length > 0 ? rules.map((rule) => (
                        <span key={rule.rule_id} className={`rounded border px-2 py-1 font-mono text-[9px] ${badgeTone(rule.validation_status)}`} title={rule.name}>
                          {rule.rule_id} · {rule.validation_status}
                        </span>
                      )) : <span className="text-[10px] text-slate-600">No live coverage record returned for this scenario.</span>}
                    </div>
                  </div>

                  <div>
                    <p className="soc-kicker">MITRE ATT&amp;CK context</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {techniques.length > 0 ? techniques.map((technique) => (
                        <span key={technique} className="rounded border border-violet-500/20 bg-violet-500/5 px-2 py-1 font-mono text-[9px] text-violet-300">{technique}</span>
                      )) : <span className="text-[10px] text-slate-600">Technique mapping appears when validated rules expose ATT&amp;CK metadata.</span>}
                    </div>
                  </div>

                  <a href={scenarioHref} target="_blank" rel="noreferrer" className="flex items-center justify-between rounded border border-sky-500/25 bg-sky-500/5 px-3 py-2.5 text-[10px] font-semibold text-sky-300 transition hover:border-sky-400/50 hover:bg-sky-500/10">
                    <span>Open enterprise scenario workspace</span><span>↗</span>
                  </a>
                </div>
              </article>
            );
          })}
        </section>

        <section className="soc-panel rounded-lg p-5">
          <p className="soc-kicker">Control boundary</p>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            <div className="rounded border border-slate-800 bg-[#0d1b29] p-4"><p className="text-[10px] font-semibold text-emerald-300">DETECTION</p><p className="mt-2 text-[10px] leading-4 text-slate-500">Deterministic rules establish whether security findings exist.</p></div>
            <div className="rounded border border-slate-800 bg-[#0d1b29] p-4"><p className="text-[10px] font-semibold text-amber-300">AI ADVISORY</p><p className="mt-2 text-[10px] leading-4 text-slate-500">AI interprets existing evidence only; it does not create detections or incidents.</p></div>
            <div className="rounded border border-slate-800 bg-[#0d1b29] p-4"><p className="text-[10px] font-semibold text-sky-300">RESPONSE</p><p className="mt-2 text-[10px] leading-4 text-slate-500">Supported response actions remain bounded, auditable, and human-approved.</p></div>
          </div>
        </section>
      </div>
    </main>
  );
}
