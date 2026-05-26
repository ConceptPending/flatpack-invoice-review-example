"use client";

export default function AdminError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  console.error("Admin error:", error);

  return (
    <div className="flex flex-col items-center justify-center py-24">
      <h1 className="text-xl font-semibold tracking-tight mb-2">
        Admin Error
      </h1>
      <p className="text-sm text-muted mb-4">
        An unexpected error occurred. Please try again.
      </p>
      <button
        onClick={reset}
        className="rounded-full bg-accent px-6 py-2 text-sm font-semibold text-white hover:bg-accent-bright transition-colors"
      >
        Try again
      </button>
    </div>
  );
}
