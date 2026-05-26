"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { getItems } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { Item } from "@/lib/types";

export default function AdminDashboard() {
  const [items, setItems] = useState<Item[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getItems()
      .then(setItems)
      .catch((err) => setError(errorMessage(err, "Failed to load items")));
  }, []);

  const active = items.filter((i) => i.is_active).length;
  const inactive = items.filter((i) => !i.is_active).length;

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight mb-6">
        Dashboard
      </h1>

      <ErrorBanner error={error} onDismiss={() => setError(null)} />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <Card className="p-5">
          <p className="text-sm text-muted">Total Items</p>
          <p className="mt-1 text-3xl font-semibold">{items.length}</p>
        </Card>
        <Card className="p-5">
          <p className="text-sm text-muted">Active</p>
          <p className="mt-1 text-3xl font-semibold">{active}</p>
        </Card>
        <Card className="p-5">
          <p className="text-sm text-muted">Inactive</p>
          <p className="mt-1 text-3xl font-semibold">{inactive}</p>
        </Card>
      </div>

      <Card className="p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Recent Items</h2>
          <Link href="/admin/items" className="text-xs text-accent hover:underline">
            View all
          </Link>
        </div>
        <div className="space-y-3">
          {items.slice(0, 5).map((item) => (
            <div key={item.id} className="flex items-center justify-between border-b border-border pb-2 last:border-0">
              <div>
                <p className="text-sm font-medium">{item.name}</p>
                <p className="text-xs text-muted mt-0.5">
                  {item.is_active ? "Active" : "Inactive"}
                </p>
              </div>
            </div>
          ))}
          {items.length === 0 && (
            <p className="text-sm text-muted">No items yet.</p>
          )}
        </div>
      </Card>
    </div>
  );
}
