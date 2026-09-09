import Link from "next/link";
import { SplunkSecurityDashboard } from "./SplunkSecurityDashboard";

export default function LiveDemoPage() {
  return (
    <>
      <div className="border-b border-[#263442] bg-[#050a0f] px-4 py-2 text-[10px] text-slate-600 lg:px-6">
        <div className="mx-auto flex max-w-[1900px] items-center justify-between gap-4">
          <Link href="/" className="font-medium text-slate-400 hover:text-cyan-300">
            ← Demo Control
          </Link>
          <span>Controlled Scenario Validation · Synthetic Defensive Environment</span>
        </div>
      </div>
      <SplunkSecurityDashboard />
    </>
  );
}
