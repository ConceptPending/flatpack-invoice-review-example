import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import Link from "next/link";

export default function HomePage() {
  return (
    <>
      <Header />
      <main className="flex-1">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 py-24 text-center">
          <h1 className="text-4xl font-semibold tracking-tight mb-4">
            Welcome to MyApp
          </h1>
          <p className="text-lg text-muted max-w-xl mx-auto mb-8">
            A production-ready full-stack starter with FastAPI, Next.js, and PostgreSQL.
          </p>
          <div className="flex gap-4 justify-center">
            <Link
              href="/items"
              className="inline-flex items-center justify-center rounded-full bg-accent text-white font-semibold px-6 py-3 text-sm hover:bg-accent-bright transition-colors"
            >
              View Items
            </Link>
            <Link
              href="/admin"
              className="inline-flex items-center justify-center rounded-full border border-border text-foreground font-semibold px-6 py-3 text-sm hover:bg-surface-elevated transition-colors"
            >
              Admin Panel
            </Link>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
