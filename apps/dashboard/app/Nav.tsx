import Link from "next/link";

const SECTIONS = [
  { href: "/", label: "Overview" },
  { href: "/incidents", label: "Incidents" },
  { href: "/assets", label: "Assets" },
  { href: "/detection-coverage", label: "Detection Coverage" },
  { href: "/events", label: "Event Explorer" },
  { href: "/audit", label: "Audit / Provenance" },
  { href: "/assurance", label: "System Assurance" },
];

export function Nav() {
  return (
    <nav className="w-full border-b border-zinc-200 bg-white/80 backdrop-blur dark:border-zinc-800 dark:bg-black/80">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-8 py-3">
        <Link href="/" className="text-sm font-semibold tracking-tight text-black dark:text-zinc-50">
          SENTINEL
        </Link>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-zinc-500">
          {SECTIONS.slice(1).map((s) => (
            <Link key={s.href} href={s.href} className="hover:text-black dark:hover:text-zinc-50">
              {s.label}
            </Link>
          ))}
        </div>
        <div className="ml-auto flex gap-3 text-xs text-zinc-400">
          <a
            href="http://127.0.0.1:3100"
            target="_blank"
            rel="noreferrer"
            className="rounded border border-zinc-200 px-2 py-1 hover:border-zinc-400 dark:border-zinc-800"
          >
            MissionNet (external)
          </a>
          <a
            href="http://127.0.0.1:3200"
            target="_blank"
            rel="noreferrer"
            className="rounded border border-zinc-200 px-2 py-1 hover:border-zinc-400 dark:border-zinc-800"
          >
            Demo Control (external)
          </a>
        </div>
      </div>
    </nav>
  );
}
