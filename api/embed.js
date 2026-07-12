// Serverless proxy for text embeddings (Vercel function), used to re-rank
// live-TMDB "similar" candidates by plot/theme instead of just genre.
//
// POST /api/embed  body: { items: [{ key, text }, ...] }  (max 20 per call)
// Response: { vectors: { [key]: number[] | null } }
//
// Vectors are cached in a Supabase (Postgres) table, shared across all
// visitors, so the second person who ever searches a given title gets an
// instant cache hit instead of burning another call against the free
// embedding quota. Table schema (create once in the Supabase SQL editor):
//   create table embeddings (key text primary key, vector jsonb not null);
//
// Set as Vercel environment variables (never commit them):
//   GEMINI_API_KEY        - Google AI Studio API key (free tier)
//   SUPABASE_URL          - e.g. https://xxxx.supabase.co
//   SUPABASE_SERVICE_KEY  - the project's service_role key (Settings > API).
//                           Server-side only, bypasses RLS - never expose it
//                           to the browser.
// Optional:
//   ALLOWED_ORIGIN  - lock the proxy to one site origin (see api/tmdb.js)

const GEMINI_URL =
  "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:batchEmbedContents";
const OUTPUT_DIMENSIONALITY = 256;
const MAX_ITEMS = 20;

function supabaseHeaders() {
  const key = process.env.SUPABASE_SERVICE_KEY;
  return { apikey: key, authorization: `Bearer ${key}`, "content-type": "application/json" };
}

// Batched lookup: one request for every key instead of one round-trip each.
async function cacheGetMany(keys) {
  const url = process.env.SUPABASE_URL;
  if (!url || !process.env.SUPABASE_SERVICE_KEY || !keys.length) return {};
  try {
    const inList = keys.map(k => encodeURIComponent(k)).join(",");
    const r = await fetch(`${url}/rest/v1/embeddings?key=in.(${inList})&select=key,vector`, {
      headers: supabaseHeaders(),
    });
    const rows = await r.json();
    const found = {};
    for (const row of Array.isArray(rows) ? rows : []) found[row.key] = row.vector;
    return found;
  } catch (e) {
    return {};
  }
}

async function cacheSetMany(entries) {
  const url = process.env.SUPABASE_URL;
  if (!url || !process.env.SUPABASE_SERVICE_KEY || !entries.length) return;
  try {
    await fetch(`${url}/rest/v1/embeddings`, {
      method: "POST",
      headers: { ...supabaseHeaders(), prefer: "resolution=merge-duplicates" },
      body: JSON.stringify(entries),
    });
  } catch (e) {
    // Cache write failure is non-fatal - vectors are still returned to the caller.
  }
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "method not allowed" });
    return;
  }

  const allowedOrigin = process.env.ALLOWED_ORIGIN;
  if (allowedOrigin) {
    const origin = (req.headers.origin || "").toString();
    const referer = (req.headers.referer || "").toString();
    if (origin !== allowedOrigin && !referer.startsWith(allowedOrigin)) {
      res.status(403).json({ error: "forbidden" });
      return;
    }
    res.setHeader("Access-Control-Allow-Origin", allowedOrigin);
  }

  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    res.status(500).json({ error: "GEMINI_API_KEY not configured on the server" });
    return;
  }

  const items = Array.isArray(req.body && req.body.items) ? req.body.items : [];
  if (!items.length || items.length > MAX_ITEMS) {
    res.status(400).json({ error: `items must be a non-empty array of at most ${MAX_ITEMS}` });
    return;
  }

  const valid = items.filter(({ key, text }) => key && text);
  const cached = await cacheGetMany(valid.map(({ key }) => key));

  const vectors = {};
  for (const { key } of items) if (!(key in vectors)) vectors[key] = null;
  const misses = [];
  for (const item of valid) {
    if (cached[item.key]) vectors[item.key] = cached[item.key];
    else misses.push(item);
  }

  if (misses.length) {
    try {
      const body = {
        requests: misses.map(({ text }) => ({
          model: "models/text-embedding-004",
          content: { parts: [{ text: text.slice(0, 2000) }] },
          outputDimensionality: OUTPUT_DIMENSIONALITY,
        })),
      };
      const upstream = await fetch(`${GEMINI_URL}?key=${apiKey}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await upstream.json();
      const embeddings = (data && data.embeddings) || [];
      const toStore = [];
      for (let i = 0; i < misses.length; i++) {
        const vec = (embeddings[i] && embeddings[i].values) || null;
        vectors[misses[i].key] = vec;
        if (vec) toStore.push({ key: misses[i].key, vector: vec });
      }
      await cacheSetMany(toStore);
    } catch (e) {
      // Leave misses as null (already defaulted above) - caller falls back gracefully.
    }
  }

  res.status(200).json({ vectors });
};
