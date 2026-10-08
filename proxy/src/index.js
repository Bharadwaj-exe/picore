// πCore Wolfram|Alpha proxy (Cloudflare Worker).
// The app calls  GET https://<worker>/query?input=...  and never sees the AppID,
// which lives in the WOLFRAM_APPID secret. Answers are cached for a day and
// each IP is rate limited, so one user can't burn the monthly API quota.

const WOLFRAM = "https://api.wolframalpha.com/v2/query";
const MAX_INPUT = 300;
const CACHE_SECONDS = 86400;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (request.method !== "GET" || url.pathname !== "/query") {
      return json({ error: "not found" }, 404);
    }
    const input = (url.searchParams.get("input") || "").trim();
    if (!input || input.length > MAX_INPUT) {
      return json({ error: "input must be 1-300 characters" }, 400);
    }

    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    if (env.LIMITER) {
      const { success } = await env.LIMITER.limit({ key: ip });
      if (!success) return json({ error: "Too many requests, slow down a little" }, 429);
    }

    // Cache by normalized input only (the AppID is never part of the cache key).
    const cacheKey = new Request(`https://picore-cache/q?input=${encodeURIComponent(input.toLowerCase())}`);
    const cache = caches.default;
    const hit = await cache.match(cacheKey);
    if (hit) return hit;

    const upstream = new URL(WOLFRAM);
    upstream.searchParams.set("appid", env.WOLFRAM_APPID);
    upstream.searchParams.set("input", input);
    upstream.searchParams.set("output", "json");

    let res;
    try {
      res = await fetch(upstream, { signal: AbortSignal.timeout(9000) });
    } catch {
      return json({ error: "Wolfram|Alpha did not respond" }, 504);
    }
    if (!res.ok) return json({ error: `Wolfram|Alpha returned ${res.status}` }, 502);

    const body = await res.text();
    const out = new Response(body, {
      headers: { "content-type": "application/json", "cache-control": `public, max-age=${CACHE_SECONDS}` },
    });
    ctx.waitUntil(cache.put(cacheKey, out.clone()));
    return out;
  },
};

function json(obj, status) {
  return new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json" } });
}
