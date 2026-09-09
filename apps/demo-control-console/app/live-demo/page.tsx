import Link from "next/link";
import { LiveAttackReplay } from "./LiveAttackReplay";

export default function LiveDemoPage() {
  return (
    <>
      <div className="border-b border-zinc-200 bg-white px-5 py-3 text-xs text-zinc-500 lg:px-8">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-4">
          <Link href="/" className="font-medium text-zinc-700 hover:text-blue-700">
            ← Demo Control
          </Link>
          <span>Controlled Scenario Validation</span>
        </div>
      </div>
      <LiveAttackReplay />
    </>
  );
}
