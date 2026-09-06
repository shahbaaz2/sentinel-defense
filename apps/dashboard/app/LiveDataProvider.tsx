"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";

export type LiveIncidentSummary = {
  incident_id: string;
  title: string;
  severity: string;
  status: string;
  primary_asset_id: string | null;
  first_seen: string;
  detection_count: number;
};

export type LiveSnapshot = {
  metrics: {
    protected_assets: number;
    normalized_events: number;
    active_detections: number;
    open_incidents: number;
    last_ingestion_at: string | null;
  };
  missionnet_reachable: boolean;
  recent_incidents: LiveIncidentSummary[];
};

type LiveDataContextValue = {
  snapshot: LiveSnapshot | null;
  connected: boolean;
};

const LiveDataContext = createContext<LiveDataContextValue>({ snapshot: null, connected: false });

/**
 * One shared EventSource for the whole app (Phase 4: "avoid polling every page independently").
 * EventSource reconnects on its own when a tab wakes up or a connection drops - no custom retry
 * logic needed for that part; we only track `connected` for the UI's own status indicator.
 */
export function LiveDataProvider({ children }: { children: React.ReactNode }) {
  const [snapshot, setSnapshot] = useState<LiveSnapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const source = new EventSource(`${API_BASE}/api/v1/stream`);
    sourceRef.current = source;

    source.addEventListener("snapshot", (event) => {
      try {
        setSnapshot(JSON.parse((event as MessageEvent).data));
        setConnected(true);
      } catch {
        // Malformed snapshot - skip this tick, keep the previous one displayed.
      }
    });
    source.onerror = () => setConnected(false);
    source.onopen = () => setConnected(true);

    return () => {
      source.close();
    };
  }, []);

  return (
    <LiveDataContext.Provider value={{ snapshot, connected }}>{children}</LiveDataContext.Provider>
  );
}

export function useLiveData() {
  return useContext(LiveDataContext);
}
