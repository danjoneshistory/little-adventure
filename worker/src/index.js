// Saves the scavenger hunt's progress and photos.
// Every request must carry the hunt key (X-Hunt-Key header), which matches the HUNT_KEY secret.
//
//   GET    /state          -> saved progress ({} if none)
//   PUT    /state          -> merge new progress in (progress only ever grows)
//   DELETE /state          -> wipe progress and photos
//   GET    /photo/<id>     -> photo as a data: URL
//   PUT    /photo/<id>     -> save a photo (data: URL text)

const ORIGINS = [
  "https://danjoneshistory.github.io",
  "http://127.0.0.1:8765",
  "http://localhost:8765",
];
const MAX_PHOTO = 4 * 1024 * 1024;   // 4 MB of text per photo

export default {
  async fetch(req, env) {
    const origin = req.headers.get("Origin") || "";
    const cors = {
      "Access-Control-Allow-Origin": ORIGINS.includes(origin) ? origin : ORIGINS[0],
      "Access-Control-Allow-Methods": "GET, PUT, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, X-Hunt-Key",
      "Access-Control-Max-Age": "86400",
      "Vary": "Origin",
    };
    const reply = (body, status = 200, type = "application/json") =>
      new Response(typeof body === "string" ? body : JSON.stringify(body),
        { status, headers: { ...cors, "Content-Type": type, "Cache-Control": "no-store" } });

    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (!env.HUNT_KEY || !(await sameKey(req.headers.get("X-Hunt-Key") || "", env.HUNT_KEY)))
      return reply({ error: "wrong key" }, 401);

    const path = new URL(req.url).pathname;

    if (path === "/state") {
      if (req.method === "GET") return reply((await env.HUNT.get("state", "json")) || {});
      if (req.method === "PUT") {
        let incoming;
        try { incoming = await req.json(); } catch { return reply({ error: "bad json" }, 400); }
        if (!incoming || typeof incoming !== "object") return reply({ error: "bad state" }, 400);
        const merged = mergeState((await env.HUNT.get("state", "json")) || {}, incoming);
        merged.updated = Date.now();
        await env.HUNT.put("state", JSON.stringify(merged));
        return reply(merged);
      }
      if (req.method === "DELETE") {
        const list = await env.HUNT.list({ prefix: "photo:" });
        await Promise.all([env.HUNT.delete("state"), ...list.keys.map(k => env.HUNT.delete(k.name))]);
        return reply({ ok: true });
      }
    }

    const m = path.match(/^\/photo\/([A-Za-z0-9_-]{1,40})$/);
    if (m) {
      const key = "photo:" + m[1];
      if (req.method === "GET") {
        const data = await env.HUNT.get(key);
        return data ? reply(data, 200, "text/plain") : reply({ error: "no photo" }, 404);
      }
      if (req.method === "PUT") {
        const data = await req.text();
        if (!data.startsWith("data:image/") || data.length > MAX_PHOTO) return reply({ error: "bad photo" }, 400);
        await env.HUNT.put(key, data);
        return reply({ ok: true });
      }
    }

    return reply({ error: "not found" }, 404);
  },
};

// Progress only grows: lists are combined and anything done stays done.
function mergeState(a, b) {
  const list = k => [...new Set([...(Array.isArray(a[k]) ? a[k] : []), ...(Array.isArray(b[k]) ? b[k] : [])])];
  const steps = {};
  for (const src of [a.steps, b.steps]) {
    if (!src || typeof src !== "object") continue;
    for (const [key, done] of Object.entries(src)) {
      if (!done || typeof done !== "object") continue;
      steps[key] = steps[key] || {};
      for (const [step, v] of Object.entries(done)) if (v) steps[key][step] = true;
    }
  }
  return {
    arrived: list("arrived"), solved: list("solved"),
    spotArrived: list("spotArrived"), spotSolved: list("spotSolved"),
    finalSolved: !!(a.finalSolved || b.finalSolved), steps,
  };
}

async function sameKey(given, real) {
  const enc = new TextEncoder();
  const [x, y] = await Promise.all([crypto.subtle.digest("SHA-256", enc.encode(given)), crypto.subtle.digest("SHA-256", enc.encode(real))]);
  return crypto.subtle.timingSafeEqual(x, y);
}
