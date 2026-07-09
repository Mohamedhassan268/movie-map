// Serverless proxy for the TMDB API (Vercel function).
//
// Keeps the TMDB credential server-side: the browser calls
//   /api/tmdb?endpoint=<whitelisted path>&<passthrough params>
// and this function injects the key from an environment variable and forwards
// the request to https://api.themoviedb.org/3/<endpoint>.
//
// Set ONE of these as a Vercel environment variable (never commit it):
//   TMDB_READ_TOKEN  - the v4 "API Read Access Token" (sent as a Bearer header)
//   TMDB_API_KEY     - the v3 API key (sent as an api_key query param)

const TMDB_BASE = "https://api.themoviedb.org/3";

// Only these endpoints are allowed, so this can't be used as an open proxy.
const ALLOWED = /^(search\/multi|genre\/(movie|tv)\/list|(movie|tv)\/\d+(\/(recommendations|similar))?)$/;

// Query params the frontend is allowed to pass through.
const PASS_PARAMS = ["query", "page", "append_to_response", "language"];

module.exports = async function handler(req, res) {
  const endpoint = (req.query.endpoint || "").toString();
  if (!ALLOWED.test(endpoint)) {
    res.status(400).json({ error: "endpoint not allowed" });
    return;
  }

  const readToken = process.env.TMDB_READ_TOKEN;
  const apiKey = process.env.TMDB_API_KEY;
  if (!readToken && !apiKey) {
    res.status(500).json({ error: "TMDB credential not configured on the server" });
    return;
  }

  const url = new URL(`${TMDB_BASE}/${endpoint}`);
  for (const p of PASS_PARAMS) {
    if (req.query[p] != null) url.searchParams.set(p, req.query[p].toString());
  }

  const headers = { accept: "application/json" };
  if (readToken) {
    headers.authorization = `Bearer ${readToken}`;
  } else {
    url.searchParams.set("api_key", apiKey);
  }

  try {
    const upstream = await fetch(url, { headers });
    const body = await upstream.json();
    // Short cache: TMDB data is stable; keeps repeat recenters snappy.
    res.setHeader("Cache-Control", "s-maxage=3600, stale-while-revalidate");
    res.status(upstream.status).json(body);
  } catch (err) {
    res.status(502).json({ error: "upstream request failed" });
  }
}
