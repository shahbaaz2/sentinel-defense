import Link from "next/link";
import { NetworkSensorConsole } from "./NetworkSensorConsole";

export default function NetworkSensorPage() {
  return (
    <>
      <div className="border-b border-slate-800 bg-[#071019] px-5 py-3 text-xs text-slate-500 lg:px-8">
        <div className="mx-auto flex max-w-[1700px] items-center justify-between gap-4">
          <Link href="/live-demo#SCN-010" className="font-medium text-slate-300 hover:text-sky-300">← Scenario Console</Link>
          <span>Controlled Network Sensor Validation</span>
        </div>
      </div>
      <NetworkSensorConsole />
    </>
  );
}
