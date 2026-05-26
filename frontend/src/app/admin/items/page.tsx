"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { StatusPill } from "@/components/ui/StatusPill";
import { getItems, createItem, updateItem, deleteItem } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { Item } from "@/lib/types";

export default function AdminItemsPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    getItems()
      .then(setItems)
      .catch((err) => setError(errorMessage(err, "Failed to load items")));

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createItem({ name, description: description || undefined });
      setName("");
      setDescription("");
      setModalOpen(false);
      load();
    } catch (err) {
      setError(errorMessage(err, "Failed to create item"));
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(item: Item) {
    try {
      await updateItem(item.id, { is_active: !item.is_active });
      load();
    } catch (err) {
      setError(errorMessage(err, "Failed to update item"));
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this item?")) return;
    try {
      await deleteItem(id);
      load();
    } catch (err) {
      setError(errorMessage(err, "Failed to delete item"));
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Items</h1>
        <Button onClick={() => setModalOpen(true)}>New Item</Button>
      </div>

      <ErrorBanner error={error} onDismiss={() => setError(null)} />

      <Card>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted">
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Description</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-b border-border last:border-0">
                <td className="px-4 py-3 font-medium">{item.name}</td>
                <td className="px-4 py-3 text-muted">{item.description || "—"}</td>
                <td className="px-4 py-3">
                  <StatusPill status={item.is_active ? "active" : "inactive"} />
                </td>
                <td className="px-4 py-3 text-right space-x-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleActive(item)}
                  >
                    {item.is_active ? "Deactivate" : "Activate"}
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => handleDelete(item.id)}
                  >
                    Delete
                  </Button>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-muted">
                  No items yet. Create one to get started.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="New Item">
        <form onSubmit={handleCreate} className="space-y-4">
          <Input
            id="item-name"
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <Input
            id="item-description"
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              type="button"
              onClick={() => setModalOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Creating..." : "Create"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
