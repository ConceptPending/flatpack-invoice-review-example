import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-border bg-surface mt-auto">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 py-12">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold">MyApp</p>
            <p className="mt-1 text-sm text-muted max-w-xs">
              A full-stack starter application.
            </p>
          </div>

          <nav className="flex gap-6">
            <Link
              href="/items"
              className="text-sm text-muted hover:text-foreground transition-colors"
            >
              Items
            </Link>
          </nav>
        </div>

        <div className="mt-8 pt-8 border-t border-border">
          <p className="text-xs text-muted">
            &copy; {new Date().getFullYear()} MyApp. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
}
