"use client";
/**
 * DataCacheContext
 * Global in-memory cache for all API responses.
 */
import {
  createContext,
  useContext,
  useRef,
  useCallback,
  ReactNode,
} from "react";
import { fetchWithRetry } from "./fetchWithRetry";

const API =
  typeof window !== "undefined"
    ? ""
    : process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type CacheEntry = {
  data: any;
  fetchedAt: number;
  status: "ok" | "error";
};

type InFlight = Promise<any>;

type CacheContextValue = {
  get: (url: string, ttlMs?: number) => Promise<any>;
  prefetch: (url: string) => void;
  peek: (url: string) => CacheEntry | null;
  bust: (url: string) => void;
  isCached: (url: string) => boolean;
};

const DataCacheContext = createContext<CacheContextValue | null>(null);

const DEFAULT_TTL = 5 * 60 * 1000;

export function DataCacheProvider({ children }: { children: ReactNode }) {
  const cache = useRef<Map<string, CacheEntry>>(new Map());
  const inFlight = useRef<Map<string, InFlight>>(new Map());

  const get = useCallback(
    async (url: string, ttlMs = DEFAULT_TTL): Promise<any> => {
      const fullUrl = url.startsWith("http") ? url : `${API}${url}`;
      const now = Date.now();

      // Return from cache if fresh
      const cached = cache.current.get(fullUrl);
      if (cached && now - cached.fetchedAt < ttlMs) {
        return cached.data;
      }

      // Deduplicate in-flight requests
      if (inFlight.current.has(fullUrl)) {
        return inFlight.current.get(fullUrl);
      }

      // New fetch with retry logic (fetchWithRetry already handles 5xx + network retries)
      const promise = fetchWithRetry(fullUrl)
        .then((data) => {
          cache.current.set(fullUrl, {
            data,
            fetchedAt: Date.now(),
            status: "ok",
          });
          inFlight.current.delete(fullUrl);
          return data;
        })
        .catch((err) => {
          // Store error state so repeated calls don't re-fetch a known-bad URL immediately
          cache.current.set(fullUrl, {
            data: null,
            fetchedAt: Date.now() - DEFAULT_TTL + 15_000, // retry after 15s
            status: "error",
          });
          inFlight.current.delete(fullUrl);
          throw err;
        });

      inFlight.current.set(fullUrl, promise);
      return promise;
    },
    [],
  );

  const prefetch = useCallback(
    (url: string) => {
      if (typeof window === "undefined") return;
      const fullUrl = url.startsWith("http") ? url : `${API}${url}`;
      if (!cache.current.has(fullUrl) && !inFlight.current.has(fullUrl)) {
        get(fullUrl).catch(() => {});
      }
    },
    [get],
  );

  const peek = useCallback((url: string): CacheEntry | null => {
    const fullUrl = url.startsWith("http") ? url : `${API}${url}`;
    return cache.current.get(fullUrl) ?? null;
  }, []);

  const bust = useCallback((url: string) => {
    const fullUrl = url.startsWith("http") ? url : `${API}${url}`;
    cache.current.delete(fullUrl);
  }, []);

  const isCached = useCallback((url: string): boolean => {
    const fullUrl = url.startsWith("http") ? url : `${API}${url}`;
    const entry = cache.current.get(fullUrl);
    if (!entry) return false;
    return Date.now() - entry.fetchedAt < DEFAULT_TTL;
  }, []);

  return (
    <DataCacheContext.Provider value={{ get, prefetch, peek, bust, isCached }}>
      {children}
    </DataCacheContext.Provider>
  );
}

export function useDataCache(): CacheContextValue {
  const ctx = useContext(DataCacheContext);
  if (!ctx)
    throw new Error("useDataCache must be used inside DataCacheProvider");
  return ctx;
}

export default DataCacheContext;
