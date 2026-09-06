import Link from "next/link";

const API_BASE = process.env.SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

type Asset = {
  id: string;
  external_asset_id: string;
  name: string;
  asset_type: string;
  environment: string;
  criticality: number;
  status: string;
  last_seen_at: string;
};

async function getAssets(params: URLSearchParams): Promise<Asset[] | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/assets?${params.toString()}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as Asset[];
  } catch {
    return null;
  }
}

export default async function AssetsPage(props: PageProps<"/assets">) {
  const searchParams = await props.searchParams;
  const criticality = typeof searchParams.criticality === "string" ? searchParams.criticality : "";
  const status = typeof searchParams.status === "string" ? searchParams.status : "";
  const assetType = typeof searchParams.asset_type === "string" ? searchParams.asset_type : "";

  const params = new URLSearchParams();
  if (criticality) params.set("criticality", criticality);
  if (status) params.set("status", status);
  if (assetType) params.set("asset_type", assetType);

  const assets = await getAssets(params);

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-5xl flex-col gap-6 px-8 py-16">
        <div>
          <Link href="/" className="text-sm text-zinc-500 hover:underline">
            ← Mission Cyber Posture
          </Link>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
            Asset Inventory
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Sentinel&apos;s own synced view of protected MissionNet assets - not a live MissionNet
            query. See{" "}
            <a href="http://127.0.0.1:3100" target="_blank" rel="noreferrer" className="underline">
              MissionNet Operations Console
            </a>{" "}
            for the source of truth.
          </p>
        </div>

        <form className="flex flex-wrap gap-3 text-sm" method="get">
          <select
            name="criticality"
            defaultValue={criticality}
            className="rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          >
            <option value="">All criticality</option>
            {[5, 4, 3, 2, 1].map((c) => (
              <option key={c} value={c}>
                Criticality {c}
              </option>
            ))}
          </select>
          <select
            name="status"
            defaultValue={status}
            className="rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          >
            <option value="">All statuses</option>
            <option value="nominal">Nominal</option>
            <option value="degraded">Degraded</option>
            <option value="quarantined">Quarantined</option>
          </select>
          <select
            name="asset_type"
            defaultValue={assetType}
            className="rounded border border-zinc-300 bg-white px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          >
            <option value="">All types</option>
            <option value="service">Service</option>
            <option value="frontend">Frontend</option>
            <option value="edge-device">Edge device</option>
          </select>
          <button
            type="submit"
            className="rounded bg-black px-3 py-1 text-white dark:bg-white dark:text-black"
          >
            Filter
          </button>
          {(criticality || status || assetType) && (
            <Link href="/assets" className="self-center text-xs text-zinc-500 hover:underline">
              Clear filters
            </Link>
          )}
        </form>

        {assets === null && (
          <p className="text-sm text-red-600 dark:text-red-400">Sentinel API unreachable.</p>
        )}
        {assets !== null && assets.length === 0 && (
          <p className="text-sm text-zinc-500">
            No assets match these filters. Run <code>make ingest-once</code> if the inventory is
            empty.
          </p>
        )}
        {assets !== null && assets.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-100 text-xs uppercase text-zinc-500 dark:bg-zinc-900">
                <tr>
                  <th className="px-3 py-2">Asset ID</th>
                  <th className="px-3 py-2">Name</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Criticality</th>
                  <th className="px-3 py-2">Environment</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Last Seen</th>
                </tr>
              </thead>
              <tbody>
                {assets.map((asset) => (
                  <tr key={asset.id} className="border-t border-zinc-200 dark:border-zinc-800">
                    <td className="px-3 py-2">
                      <Link
                        href={`/assets/${encodeURIComponent(asset.id)}`}
                        className="font-mono text-xs text-blue-600 hover:underline dark:text-blue-400"
                      >
                        {asset.external_asset_id}
                      </Link>
                    </td>
                    <td className="px-3 py-2">{asset.name}</td>
                    <td className="px-3 py-2 text-xs">{asset.asset_type}</td>
                    <td className="px-3 py-2">{asset.criticality}</td>
                    <td className="px-3 py-2 text-xs">{asset.environment}</td>
                    <td className="px-3 py-2">
                      <span
                        className={`inline-block h-2 w-2 rounded-full mr-2 ${
                          asset.status === "nominal" ? "bg-emerald-500" : "bg-amber-500"
                        }`}
                      />
                      {asset.status}
                    </td>
                    <td className="px-3 py-2 text-xs">
                      {new Date(asset.last_seen_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
