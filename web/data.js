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
