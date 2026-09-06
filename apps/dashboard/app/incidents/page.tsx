import Link from "next/link";
import { IncidentsLive } from "./IncidentsLive";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type Incident = {
  incident_id: string;
  title: string;
  severity: string;
  status: string;
  category: string;
  primary_asset_id: string | null;
  assigned_to: string | null;
  detection_ids: string[];
  first_seen: string;
};

async function getIncidents(): Promise<Incident[] | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/incidents`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as Incident[];
  } catch {
    return null;
  }
}

export default async function IncidentsPage() {
  const incidents = await getIncidents();

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-5xl flex-col gap-6 px-8 py-16">
        <div>
          <Link href="/" className="text-sm text-zinc-500 hover:underline">
            ← Mission Cyber Posture
          </Link>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
            Live Incidents
          </h1>
        </div>

        <IncidentsLive initialIncidents={incidents} />
      </main>
    </div>
  );
}
