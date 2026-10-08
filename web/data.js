// Data files are published next to the app, in data/.
const DATA_BASE = "data/";
const cache = new Map();

/** Load data/<name>.json. Resolves to null when the file does not exist. */
export async function loadData(name, { optional = false } = {}) {
  if (cache.has(name)) return cache.get(name);
  const promise = fetch(`${DATA_BASE}${name}.json`, { cache: "no-cache" }).then(
    (res) => {
      if (res.ok) return res.json();
      if (optional && res.status === 404) return null;
      throw new Error(`${name}: HTTP ${res.status}`);
    },
  );
  cache.set(name, promise);
  promise.catch(() => cache.delete(name));
  return promise;
}

/** Forget cached files (e.g. when the app returns to the foreground). */
export function clearDataCache() {
  cache.clear();
}

export async function loadSunTimes(location, date) {
  const params = new URLSearchParams({
    lat: location.lat, lng: location.lon, date, tz: location.timezone,
  });
  const key = `sun-times:${params}`;
  if (cache.has(key)) return cache.get(key);
  const valid = (data) => data?.date === date && [
    "civil_twilight_begin", "sunrise", "sunset", "civil_twilight_end",
  ].every((field) => data[field] === null || (
    typeof data[field] === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(data[field])
    && Number.isFinite(Date.parse(data[field]))
  ));
  const promise = (async () => {
    try {
      const saved = JSON.parse(localStorage.getItem("sun-times"));
      if (saved?.key === key && valid(saved.data)) return saved.data;
    } catch {}
    const response = await fetch(`https://api.sunrise-sunset.org/v2?${params}`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) throw new Error(`Sunrise-Sunset: HTTP ${response.status}`);
    const data = await response.json();
    if (!valid(data)) throw new Error("Sunrise-Sunset: invalid solar times");
    try {
      localStorage.setItem("sun-times", JSON.stringify({ key, data }));
    } catch {}
    return data;
  })();
  cache.set(key, promise);
  promise.catch(() => cache.delete(key));
  return promise;
}
