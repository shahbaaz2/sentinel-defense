import Link from "next/link";
import { LiveAttackReplay } from "./LiveAttackReplay";

export default function LiveDemoPage() {
  return (
    <>
      <div className="bg-[#020406] px-5 pt-5 font-mono text-xs text-zinc-600 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <Link href="/" className="hover:text-cyan-400">
            ← Demo Control
          </Link>
        </div>
      </div>
      <LiveAttackReplay />
    </>
  );
}
