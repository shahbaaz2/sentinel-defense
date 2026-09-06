"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_SENTINEL_API_BASE_URL ?? "http://127.0.0.1:8080";
const ACTOR = "demo-analyst";

const STATUSES = ["OPEN", "INVESTIGATING", "MONITORING", "RESOLVED", "DISMISSED"];
const DISPOSITIONS = [
  "",
  "TRUE_POSITIVE",
  "BENIGN_TRUE_POSITIVE",
  "FALSE_POSITIVE",
  "TEST_SCENARIO",
  "UNDETERMINED",
];

type Note = { note_id: string; author: string; body: string; created_at: string };

export function IncidentWorkflowPanel({
  incidentId,
  initialStatus,
  initialAssignedTo,
  initialDisposition,
  initialNotes,
}: {
  incidentId: string;
  initialStatus: string;
  initialAssignedTo: string | null;
  initialDisposition: string | null;
  initialNotes: Note[];
}) {
  const router = useRouter();
  const [status, setStatus] = useState(initialStatus);
  const [assignedTo, setAssignedTo] = useState(initialAssignedTo ?? "");
  const [disposition, setDisposition] = useState(initialDisposition ?? "");
  const [noteBody, setNoteBody] = useState("");
  const [notes, setNotes] = useState(initialNotes);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStatusChange(newStatus: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/incidents/${incidentId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus, actor: ACTOR }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      setStatus(newStatus);
      router.refresh();
    } catch {
      setError("Failed to update status.");
    } finally {
      setBusy(false);
    }
  }

  async function handleAssign() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/incidents/${incidentId}/assignment`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assigned_to: assignedTo || null, actor: ACTOR }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      router.refresh();
    } catch {
      setError("Failed to update assignment.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDispositionChange(newDisposition: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/incidents/${incidentId}/disposition`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ disposition: newDisposition, actor: ACTOR }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      setDisposition(newDisposition);
      router.refresh();
    } catch {
      setError("Failed to update disposition.");
    } finally {
      setBusy(false);
    }
  }

  async function handleAddNote() {
    if (!noteBody.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/incidents/${incidentId}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ author: ACTOR, body: noteBody }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const note = await res.json();
      setNotes([...notes, note]);
      setNoteBody("");
      router.refresh();
    } catch {
      setError("Failed to add note.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
        Analyst Workflow
      </h2>
      {error && <p className="mb-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div>
          <label className="block text-xs text-zinc-500" htmlFor="status-select">
            Status
          </label>
          <select
            id="status-select"
            value={status}
            disabled={busy}
            onChange={(e) => handleStatusChange(e.target.value)}
            className="mt-1 w-full rounded border border-zinc-300 bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs text-zinc-500" htmlFor="assignee-input">
            Assigned Analyst
          </label>
          <div className="mt-1 flex gap-2">
            <input
              id="assignee-input"
              value={assignedTo}
              onChange={(e) => setAssignedTo(e.target.value)}
              placeholder="unassigned"
              className="w-full rounded border border-zinc-300 bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            />
            <button
              onClick={handleAssign}
              disabled={busy}
              className="rounded border border-zinc-300 px-2 py-1.5 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
            >
              Save
            </button>
          </div>
        </div>

        <div>
          <label className="block text-xs text-zinc-500" htmlFor="disposition-select">
            Disposition
          </label>
          <select
            id="disposition-select"
            value={disposition}
            disabled={busy}
            onChange={(e) => handleDispositionChange(e.target.value)}
            className="mt-1 w-full rounded border border-zinc-300 bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          >
            {DISPOSITIONS.map((d) => (
              <option key={d} value={d}>
                {d || "— none —"}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-4">
        <p className="mb-2 text-xs text-zinc-500">Analyst Notes</p>
        <ul className="mb-3 flex flex-col gap-2">
          {notes.length === 0 && <li className="text-xs text-zinc-500">No notes yet.</li>}
          {notes.map((n) => (
            <li
              key={n.note_id}
              className="rounded border border-zinc-200 px-3 py-2 text-xs dark:border-zinc-800"
            >
              <span className="font-medium">{n.author}</span>{" "}
              <span className="text-zinc-500">
                {new Date(n.created_at).toLocaleString()}
              </span>
              <p className="mt-1">{n.body}</p>
            </li>
          ))}
        </ul>
        <div className="flex gap-2">
          <textarea
            value={noteBody}
            onChange={(e) => setNoteBody(e.target.value)}
            placeholder="Add an analyst note…"
            rows={2}
            className="w-full rounded border border-zinc-300 bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
          <button
            onClick={handleAddNote}
            disabled={busy || !noteBody.trim()}
            className="self-start rounded bg-black px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
          >
            Add Note
          </button>
        </div>
      </div>
    </section>
  );
}
