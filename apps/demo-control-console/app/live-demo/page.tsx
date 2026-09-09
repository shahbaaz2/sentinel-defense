import Link from "next/link";
import { EnterpriseSecurityConsole } from "./EnterpriseSecurityConsole";

export default function LiveDemoPage() {
  return (
    <>
      <div className="border-b border-slate-800 bg-[#071019] px-5 py-3 text-xs text-slate-500 lg:px-8">
        <div className="mx-auto flex max-w-[1700px] items-center justify-between gap-4">
          <Link href="/" className="font-medium text-slate-300 hover:text-sky-300">
            ← Demo Control
          </Link>
          <span>Controlled Scenario Validation</span>
        </div>
      </div>
      <EnterpriseSecurityConsole />
    </>
  );
}
