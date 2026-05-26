import { API_BASE } from "@/lib/server-config";
import { Card } from "@/components/ui/Card";
import { StatusPill } from "@/components/ui/StatusPill";
import type { Item } from "@/lib/types";

async function getItems(): Promise<Item[]> {
  try {
    const res = await fetch(`${API_BASE}/api/public/items`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export const revalidate = 60;

export default async function ItemsPage() {
  const items = await getItems();

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 py-12">
      <h1 className="text-2xl font-semibold tracking-tight mb-6">Items</h1>

      {items.length === 0 ? (
        <p className="text-muted">No items yet.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <Card key={item.id} className="p-5">
              <div className="flex items-start justify-between mb-2">
                <h2 className="font-semibold">{item.name}</h2>
                <StatusPill status={item.is_active ? "active" : "inactive"} />
              </div>
              {item.description && (
                <p className="text-sm text-muted">{item.description}</p>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
