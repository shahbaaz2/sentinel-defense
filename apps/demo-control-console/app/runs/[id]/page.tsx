import Link from "next/link";
import { RunView } from "./RunView";

export default async function RunPage(props: PageProps<"/runs/[id]">) {
  const { id } = await props.params;

  return (
    <div className="min-h-screen bg-[#f5f7fa] text-zinc-900">
      <div className="border-b border-zinc-200 bg-white px-5 py-3 text-xs text-zinc-500 lg:px-8">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-4">
          <Link href="/" className="font-medium text-zinc-700 hover:text-blue-700">
            ← Demo Control
          </Link>
          <span>Scenario Run Operations</span>
        </div>
      </div>
      <main className="mx-auto w-full max-w-[1500px] px-5 py-6 lg:px-8">
        <RunView runId={id} />
      </main>
    </div>
  );
}
