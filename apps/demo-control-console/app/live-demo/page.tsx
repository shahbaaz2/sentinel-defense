import Link from "next/link";
import { SplunkSecurityDashboard } from "./SplunkSecurityDashboard";

const SENTINEL_DASHBOARD =
  process.env.NEXT_PUBLIC_SENTINEL_DASHBOARD_URL ?? "https://sentinel-defense-g6id.vercel.app";

export default function LiveDemoPage() {
  return (
    <>
      <div className="border-b border-[#263442] bg-[#050a0f] px-4 py-2 text-[10px] text-slate-600 lg:px-6">
        <div className="mx-auto flex max-w-[1900px] items-center justify-between gap-4">
          <Link href="/" className="font-medium text-slate-400 hover:text-cyan-300">← Demo Control</Link>
          <div className="flex items-center gap-2 sm:gap-4">
            <span className="hidden lg:inline">Controlled Scenario Validation · Synthetic Defensive Environment</span>
            <a
              href={`${SENTINEL_DASHBOARD.replace(/\/$/, "")}/ai-advisory`}
              target="_blank"
              rel="noreferrer"
              className="rounded border border-amber-500/25 bg-amber-500/5 px-2.5 py-1 font-semibold text-amber-300 hover:border-amber-400/50 hover:text-amber-200"
            >
              AI Advisory ↗
            </a>
            <Link href="/live-demo/network" className="rounded border border-slate-700 bg-[#0d1b29] px-2.5 py-1 font-semibold text-sky-300 hover:border-sky-500/40 hover:text-sky-200">Network Sensor Lab →</Link>
          </div>
        </div>
      </div>
      <SplunkSecurityDashboard />
    </>
  );
}
