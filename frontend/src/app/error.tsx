"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background">
      <h1 className="text-2xl font-semibold tracking-tight mb-2">
        Something went wrong
      </h1>
      <p className="text-sm text-muted mb-6">
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
