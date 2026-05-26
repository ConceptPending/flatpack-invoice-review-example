type Status = "draft" | "scheduled" | "published" | "running" | "completed" | "failed" | "active" | "inactive";

const statusStyles: Record<string, string> = {
  published: "pill-active",
  completed: "pill-active",
  active: "pill-active",
  draft: "pill-pending",
  inactive: "pill-pending",
  scheduled: "pill-warning",
  running: "pill-warning",
  failed: "pill-error",
};

export function StatusPill({ status }: { status: Status | string }) {
  const style = statusStyles[status] || "pill-pending";
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${style}`}
    >
      {status}
    </span>
  );
}
