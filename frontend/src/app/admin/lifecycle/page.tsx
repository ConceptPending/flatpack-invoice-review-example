"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { StatusPill } from "@/components/ui/StatusPill";
import {
  getAvailableActions,
  getBatchLifecycle,
  getBatches,
  getLifecycleEvents,
} from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type {
  AvailableActions,
  Batch,
  LifecycleEvent,
  LifecycleSpec,
} from "@/lib/lifecycle-types";

// A read-only viewer + case simulator for the batch review lifecycle: the
// policy in force (version + digest), what's available to you right now and
// why, and the append-only event history.
export default function LifecycleViewerPage() {
  const [spec, setSpec] = useState<LifecycleSpec | null>(null);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [actions, setActions] = useState<AvailableActions | null>(null);
  const [events, setEvents] = useState<LifecycleEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getBatchLifecycle().then(setSpec).catch((e) => setError(errorMessage(e, "Failed to load policy")));
    getBatches().then(setBatches).catch((e) => setError(errorMessage(e, "Failed to load batches")));
  }, []);

  useEffect(() => {
    if (!selected) return;
    getAvailableActions(selected).then(setActions).catch((e) => setError(errorMessage(e, "Failed to simulate")));
    getLifecycleEvents(selected).then(setEvents).catch((e) => setError(errorMessage(e, "Failed to load history")));
  }, [selected]);

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Lifecycle</h1>
        {spec && (
          <p className="text-sm text-muted mt-1">
            {spec.title} — policy <strong>v{spec.version}</strong>{" "}
            <code className="text-xs">{spec.digest.slice(0, 12)}…</code>
          </p>
        )}
      </div>

      <ErrorBanner error={error} onDismiss={() => setError(null)} />

      {/* The policy: transitions + the rules that gate them. */}
      {spec && (
        <Card className="p-5">
          <h2 className="font-medium mb-3">Policy</h2>
          <table className="w-full text-sm">
            <thead className="text-muted text-left">
              <tr>
                <th className="pb-2">Action</th>
                <th className="pb-2">From → To</th>
                <th className="pb-2">Who</th>
                <th className="pb-2">Condition</th>
              </tr>
            </thead>
            <tbody>
              {spec.transitions.map((t) => (
                <tr key={t.name} className="border-t border-border">
                  <td className="py-2 font-medium">{t.name}</td>
                  <td className="py-2">{t.from.join(", ")} → {t.to}</td>
                  <td className="py-2">{t.roles.join(", ") || "—"}</td>
                  <td className="py-2 text-muted">{t.guard_text ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {spec.invariants.length > 0 && (
            <ul className="mt-4 text-sm text-muted list-disc pl-5 space-y-1">
              {spec.invariants.map((i) => (
                <li key={i.name}>
                  <strong>{i.name}</strong>: <code className="text-xs">{i.text}</code>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {/* Pick a batch to simulate against. */}
      <Card className="p-5">
        <h2 className="font-medium mb-3">Batches</h2>
        {batches.length === 0 ? (
          <p className="text-sm text-muted">No batches uploaded yet.</p>
        ) : (
          <div className="space-y-1">
            {batches.map((b) => (
              <button
                key={b.id}
                onClick={() => setSelected(b.id)}
                className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors ${
                  selected === b.id
                    ? "bg-surface-elevated"
                    : "hover:bg-surface-elevated"
                }`}
              >
                <span className="truncate">{b.source_filename}</span>
                <StatusPill status={b.status} />
              </button>
            ))}
          </div>
        )}
      </Card>

      {/* The case simulator: what's allowed for you now, and why. */}
      {actions && (
        <Card className="p-5">
          <h2 className="font-medium mb-1">Available to you now</h2>
          <p className="text-xs text-muted mb-3">
            status <strong>{actions.status}</strong> · entity v{actions.version} ·
            policy v{actions.spec_version}
          </p>
          <ul className="space-y-2 text-sm">
            {actions.actions.map((a) => (
              <li key={a.action} className="flex items-start gap-2">
                <span className={a.allowed ? "text-green-400" : "text-red-400"}>
                  {a.allowed ? "✓" : "✗"}
                </span>
                <span>
                  <strong>{a.action}</strong> → {a.to}
                  {!a.allowed && (
                    <span className="text-muted"> — {a.reason}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* The append-only audit trail. */}
      {selected && (
        <Card className="p-5">
          <h2 className="font-medium mb-3">History</h2>
          {events.length === 0 ? (
            <p className="text-sm text-muted">No lifecycle events yet.</p>
          ) : (
            <ol className="space-y-3 text-sm">
              {events.map((ev) => (
                <li key={ev.id} className="border-t border-border pt-3">
                  <div>
                    <strong>{ev.action}</strong>: {ev.previous_state} →{" "}
                    {ev.new_state} by{" "}
                    <code className="text-xs">{ev.actor_id ?? "system"}</code>{" "}
                    as [{ev.actor_roles.join(", ")}]
                  </div>
                  <div className="text-xs text-muted mt-0.5">
                    {new Date(ev.occurred_at).toLocaleString()} · policy v
                    {ev.spec_version} {ev.spec_digest.slice(0, 12)}…
                  </div>
                  <ul className="mt-1 text-xs text-muted space-y-0.5">
                    {[...ev.guard_results, ...ev.invariant_results].map((r, idx) => (
                      <li key={idx}>
                        {r.result ? "✓" : "✗"} {r.control_id}{" "}
                        <span className="opacity-70">
                          ({Object.entries(r.inputs)
                            .map(([k, v]) => `${k}=${String(v)}`)
                            .join(", ")})
                        </span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          )}
        </Card>
      )}
    </div>
  );
}
