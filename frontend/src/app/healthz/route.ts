// Liveness probe target. Static 200; deliberately doesn't load any data so
// it stays cheap and the container can be marked healthy as soon as the
// Node server is up.
export function GET() {
  return new Response("ok", {
    status: 200,
    headers: { "content-type": "text/plain" },
  });
}
