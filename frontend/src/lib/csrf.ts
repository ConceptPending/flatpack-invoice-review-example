// Read the CSRF token cookie set by the backend on login (and via
// GET /api/auth/csrf). Returned to callers so they can echo it as
// `X-CSRF-Token` on write requests — `fetchAPI` in `api.ts` does this
// automatically.
export function getCSRFToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|; )csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}
