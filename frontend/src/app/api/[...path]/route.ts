// Runtime proxy for /api/* → the backend service.
//
// Previously this was a `rewrites()` entry in next.config.ts. That works,
// but Next.js bakes the destination URL into the build output at `next build`
// time — meaning the same Docker image can't serve multiple environments
// (different API_URL per env requires a different image per env).
//
// A Route Handler reads `process.env.API_URL` at request time, so one image
// runs unchanged across dev / staging / prod with only the env var changing.
//
// What this handler does:
// - Catches every method on /api/* (GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD)
// - Forwards the request to API_URL + the same path + query
// - Preserves request headers (including Cookie, X-CSRF-Token, etc.)
// - Preserves response headers (including Set-Cookie for auth + csrf cookies)
// - Streams the response body back to the client
//
// Cookies pass through naturally because Headers preserves them in both
// directions. Verified end-to-end via the CSRF tests + live deploy.

import type { NextRequest } from "next/server";

const API_URL = process.env.API_URL || "http://localhost:8001";

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const target = new URL(`${API_URL}/api/${path.join("/")}`);
  target.search = request.nextUrl.search;

  const headers = new Headers(request.headers);
  // Drop hop-by-hop headers that fetch will set itself.
  headers.delete("host");
  headers.delete("content-length");

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  const upstream = await fetch(target, init);

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: upstream.headers,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
export const HEAD = proxy;
