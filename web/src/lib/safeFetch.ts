/**
 * Fetch JSON with response.ok check. Returns null on any failure
 * (network error, non-2xx status, JSON parse error). Logs to console.
 */
export async function safeFetchJson<T>(input: RequestInfo, init?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(input, init);
    if (!res.ok) {
      console.warn(`[safeFetch] ${input} returned ${res.status}`);
      return null;
    }
    return (await res.json()) as T;
  } catch (e) {
    console.warn(`[safeFetch] ${input} failed:`, e);
    return null;
  }
}
