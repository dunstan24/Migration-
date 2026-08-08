/**
 * fetchWithRetry — fetch with automatic retry on BOTH network errors AND 5xx responses.
 *
 * Why 5xx retries? At startup the backend takes ~30s-3min to load ML models and
 * initialise Chroma RAG. During that window uvicorn may drop connections or return
 * 500/502/503. Retrying with exponential back-off lets the request self-heal once
 * the server is ready instead of surfacing a hard error to the user.
 *
 * @param {string}  url
 * @param {object}  options   - fetch options (method, headers, body …)
 * @param {number}  retries   - total attempts (default 5)
 * @param {number}  backoff   - base delay ms (doubles each attempt, default 800ms)
 */
export async function fetchWithRetry(
  url,
  options = {},
  retries = 3,
  backoff = 400,
) {
  let lastErr;
  let targetUrl = url;

  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(targetUrl, options);

      // Success — return parsed JSON
      if (res.ok) return await res.json();

      // 4xx errors are definitive (bad request / auth) — don't retry
      if (res.status >= 400 && res.status < 500) {
        throw new Error(`API error: ${res.status} ${res.statusText}`);
      }

      // 5xx — server not ready yet, treat as retryable
      lastErr = new Error(`API error: ${res.status} ${res.statusText}`);
    } catch (err) {
      lastErr = err;
      if (err.message && /^API error: 4\d\d/.test(err.message)) throw err;
    }

    // Fallback: If external backend fails, convert http://... URL to relative /api/... path
    if (i === 0 && targetUrl.startsWith("http")) {
      try {
        const u = new URL(targetUrl);
        if (u.pathname.startsWith("/api")) {
          targetUrl = u.pathname + u.search;
        }
      } catch {
        // ignore url parse error
      }
    }

    if (i < retries - 1) {
      const delay = backoff * Math.pow(2, i);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  // Final fallback to relative mock endpoint if absolute URL failed
  if (targetUrl.startsWith("http")) {
    try {
      const u = new URL(targetUrl);
      const relativeUrl = u.pathname + u.search;
      const res = await fetch(relativeUrl, options);
      if (res.ok) return await res.json();
    } catch {
      // ignore
    }
  }

  throw lastErr;
}

/**
 * waitForBackend — polls /health until the server responds 200.
 * Call this before making any data requests at startup.
 *
 * @param {number} timeoutMs   - give up after this many ms  (default 3 min)
 * @param {number} intervalMs  - polling interval             (default 2 s)
 * @returns {Promise<boolean>} true = ready, false = timed out
 */
export async function waitForBackend(timeoutMs = 180_000, intervalMs = 2_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch("/api/data/health", { method: "GET" });
      if (res.ok) return true;
    } catch {
      // still not up — keep polling
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return false; // timed out — let callers decide what to show
}

