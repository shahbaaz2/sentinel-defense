import Link from "next/link";
import { RunView } from "./RunView";

export default async function RunPage(props: PageProps<"/runs/[id]">) {
  const { id } = await props.params;

  return (
    <div className="flex flex-1 flex-col items-center bg-black font-mono text-zinc-100">
      <main className="flex w-full max-w-4xl flex-col gap-6 px-8 py-16">
        <Link href="/" className="text-xs text-zinc-500 hover:text-cyan-400">
          ← Demo Control
        </Link>
        <RunView runId={id} />
      </main>
    </div>
  );
}
