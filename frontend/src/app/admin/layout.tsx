"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

const NAV_ITEMS = [
  { href: "/admin", label: "Dashboard" },
  { href: "/admin/items", label: "Items" },
];

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const isAuth = useRequireAuth();

  if (pathname === "/admin/login") {
    return <>{children}</>;
  }

  if (!isAuth) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-muted text-sm">Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex h-screen">
      <aside className="w-56 shrink-0 border-r border-border bg-surface flex flex-col">
        <div className="p-4 border-b border-border">
          <Link href="/admin" className="text-lg font-semibold">
            MyApp
          </Link>
          <p className="text-xs text-muted mt-1.5">Admin</p>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive =
              item.href === "/admin"
                ? pathname === "/admin"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-surface-elevated text-foreground font-medium"
                    : "text-muted hover:text-foreground hover:bg-surface-elevated"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="p-3 border-t border-border">
          <Link
            href="/"
            className="block px-3 py-2 rounded-lg text-sm text-muted hover:text-foreground hover:bg-surface-elevated transition-colors"
          >
            View site
          </Link>
          <button
            onClick={async () => {
              try {
                await logout();
              } finally {
                window.location.href = "/admin/login";
              }
            }}
            className="block w-full text-left px-3 py-2 rounded-lg text-sm text-muted hover:text-foreground hover:bg-surface-elevated transition-colors"
          >
            Logout
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="p-6 md:p-8">{children}</div>
      </main>
    </div>
  );
}
