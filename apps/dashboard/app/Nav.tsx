"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

const DEMO_CONTROL_URL =
  process.env.NEXT_PUBLIC_DEMO_CONTROL_URL ?? "https://sentinel-defense-ov8q.vercel.app";

const SECTIONS = [
  { href: "/", label: "Security Posture", icon: "▦" },
  { href: "/incidents", label: "Investigations", icon: "◎" },
  { href: "/ai-advisory", label: "AI Advisory", icon: "✦" },
  { href: "/events", label: "Event Explorer", icon: "≋" },
  { href: "/assets", label: "Asset Intelligence", icon: "◇" },
  { href: "/detection-coverage", label: "Detection Coverage", icon: "⌁" },
  { href: "/scenarios", label: "Scenario Validation", icon: "◈" },
  { href: "/architecture", label: "Architecture", icon: "⌘" },
  { href: "/data-sources", label: "Data Sources", icon: "⇄" },
  { href: "/response-center", label: "Response Center", icon: "✓" },
  { href: "/audit", label: "Audit & Provenance", icon: "◫" },
  { href: "/assurance", label: "System Assurance", icon: "◉" },
];

const SCENARIO_COMMANDS = [
  ["SCN-010", "Multi-Signal Compromise"],
  ["SCN-001", "Credential Pressure"],
  ["SCN-002", "Service Identity Compromise"],
  ["SCN-003", "Critical Service Degradation"],
  ["SCN-004", "Data Access Burst"],
] as const;

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const [launcherOpen, setLauncherOpen] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    function handleKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setLauncherOpen((open) => !open);
      }
      if (event.key === "Escape") setLauncherOpen(false);
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  const commands = useMemo(() => {
    const navigation = SECTIONS.map((section) => ({
      id: `nav-${section.href}`,
      label: section.label,
      detail: "Open Sentinel workspace",
      action: () => router.push(section.href),
    }));
    const scenarios = SCENARIO_COMMANDS.map(([id, title]) => ({
      id: `scenario-${id}`,
      label: `${id} · ${title}`,
      detail: "Open enterprise scenario console",
      action: () => window.open(`${DEMO_CONTROL_URL.replace(/\/$/, "")}/live-demo/scenarios/${id}`, "_blank", "noopener,noreferrer"),
    }));
    const network = {
      id: "scenario-network",
      label: "SCN-NET-001 · Network Sensor Detection",
      detail: "Open Suricata + Zeek sensor workspace",
      action: () => window.open(`${DEMO_CONTROL_URL.replace(/\/$/, "")}/live-demo/network`, "_blank", "noopener,noreferrer"),
    };
    const all = [...navigation, ...scenarios, network];
    const normalized = query.trim().toLowerCase();
    if (!normalized) return all;
    return all.filter((command) => `${command.label} ${command.detail}`.toLowerCase().includes(normalized));
  }, [query, router]);

  function execute(action: () => void) {
    setLauncherOpen(false);
    setQuery("");
    action();
  }

  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[246px] border-r border-slate-800 bg-[#08131e] lg:flex lg:flex-col">
        <div className="border-b border-slate-800 px-5 py-5">
          <Link href="/" className="block">
            <div className="flex items-center gap-3">
              <div className="grid h-9 w-9 place-items-center rounded-md border border-sky-500/30 bg-sky-500/10 font-mono text-sm font-bold text-sky-300">S</div>
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-sky-400">Sentinel</p>
                <p className="mt-0.5 text-sm font-semibold text-white">Enterprise Security</p>
              </div>
            </div>
          </Link>
          <div className="mt-4 flex items-center gap-2 rounded border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-emerald-300">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />Security operations online
          </div>
          <button onClick={() => setLauncherOpen(true)} className="mt-3 flex w-full items-center justify-between rounded border border-slate-700 bg-[#0d1b29] px-3 py-2 text-left text-[10px] text-slate-500 transition hover:border-sky-500/30 hover:text-slate-300">
            <span>Search workspaces & scenarios</span><span className="rounded border border-slate-700 px-1.5 py-0.5 font-mono text-[8px]">⌘K</span>
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          <p className="px-3 pb-2 text-[9px] font-bold uppercase tracking-[0.18em] text-slate-600">Operations</p>
          {SECTIONS.map((section) => {
            const active = isActive(pathname, section.href);
            return (
              <Link key={section.href} href={section.href} className={`mb-1 flex items-center gap-3 rounded-md px-3 py-2.5 text-[12px] transition ${active ? "border border-sky-500/20 bg-sky-500/10 font-semibold text-sky-200" : "border border-transparent text-slate-400 hover:bg-slate-800/60 hover:text-slate-100"}`}>
                <span className={`w-4 text-center font-mono text-sm ${active ? "text-sky-400" : "text-slate-600"}`}>{section.icon}</span><span>{section.label}</span>
              </Link>
            );
          })}

          <p className="mt-6 px-3 pb-2 text-[9px] font-bold uppercase tracking-[0.18em] text-slate-600">Controlled validation</p>
          <a href={`${DEMO_CONTROL_URL.replace(/\/$/, "")}/live-demo#SCN-010`} target="_blank" rel="noreferrer" className="flex items-center justify-between rounded-md border border-slate-700 bg-[#0d1b29] px-3 py-3 text-[11px] text-slate-300 transition hover:border-sky-500/40 hover:text-white">
            <span><span className="block font-semibold">Scenario Console</span><span className="mt-1 block text-[9px] text-slate-500">SCN-001 → SCN-010</span></span><span className="text-sky-400">↗</span>
          </a>
        </nav>

        <div className="border-t border-slate-800 p-4">
          <div className="grid grid-cols-2 gap-2 text-center">
            <div className="rounded border border-slate-800 bg-[#0b1723] p-2"><p className="text-[9px] uppercase text-slate-600">Detection</p><p className="mt-1 text-[10px] font-semibold text-emerald-300">Deterministic</p></div>
            <Link href="/ai-advisory" className="rounded border border-amber-500/20 bg-amber-500/5 p-2 transition hover:border-amber-400/40"><p className="text-[9px] uppercase text-slate-600">AI</p><p className="mt-1 text-[10px] font-semibold text-amber-300">Open advisory</p></Link>
          </div>
          <p className="mt-3 text-[9px] leading-4 text-slate-600">Synthetic defensive environment · human authority retained for response actions.</p>
        </div>
      </aside>

      <div className="sticky top-0 z-40 flex items-center justify-between border-b border-slate-800 bg-[#08131e]/95 px-4 py-3 backdrop-blur lg:hidden">
        <Link href="/" className="text-xs font-bold uppercase tracking-[0.2em] text-sky-400">Sentinel</Link>
        <div className="flex items-center gap-2">
          <button onClick={() => setLauncherOpen(true)} className="rounded border border-slate-700 bg-[#0d1b29] px-3 py-1.5 text-[10px] font-semibold text-slate-300">Search</button>
          <Link href="/ai-advisory" className="rounded border border-amber-500/25 bg-amber-500/5 px-3 py-1.5 text-[10px] font-semibold text-amber-200">AI</Link>
          <a href={`${DEMO_CONTROL_URL.replace(/\/$/, "")}/live-demo#SCN-010`} target="_blank" rel="noreferrer" className="rounded border border-sky-500/30 bg-sky-500/10 px-3 py-1.5 text-[10px] font-semibold text-sky-200">Scenario ↗</a>
        </div>
      </div>

      {launcherOpen && (
        <div className="fixed inset-0 z-[100] flex items-start justify-center bg-black/65 px-4 pt-[12vh] backdrop-blur-sm" onMouseDown={() => setLauncherOpen(false)}>
          <div className="w-full max-w-2xl overflow-hidden rounded-xl border border-slate-700 bg-[#0a1621] shadow-[0_30px_90px_rgba(0,0,0,.55)]" onMouseDown={(event) => event.stopPropagation()}>
            <div className="flex items-center gap-3 border-b border-slate-800 px-4 py-3">
              <span className="text-sky-400">⌕</span>
              <input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search Sentinel workspaces, investigations, scenarios…" className="w-full border-0 bg-transparent text-sm text-white outline-none placeholder:text-slate-600" />
              <span className="rounded border border-slate-700 px-2 py-1 font-mono text-[8px] text-slate-500">ESC</span>
            </div>
            <div className="max-h-[52vh] overflow-y-auto p-2">
              {commands.length > 0 ? commands.map((command) => (
                <button key={command.id} onClick={() => execute(command.action)} className="flex w-full items-center justify-between gap-4 rounded-lg px-3 py-3 text-left transition hover:bg-sky-500/10">
                  <div><p className="text-[11px] font-semibold text-slate-200">{command.label}</p><p className="mt-1 text-[9px] text-slate-600">{command.detail}</p></div><span className="text-[10px] text-sky-400">→</span>
                </button>
              )) : <p className="px-3 py-8 text-center text-[10px] text-slate-600">No matching Sentinel command.</p>}
            </div>
            <div className="border-t border-slate-800 px-4 py-2 text-[8px] uppercase tracking-wider text-slate-700">Enterprise command launcher · navigation only · no security state is modified</div>
          </div>
        </div>
      )}
    </>
  );
}
