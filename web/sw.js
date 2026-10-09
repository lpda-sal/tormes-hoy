// Bump CACHE_VERSION whenever app-shell files change.
const CACHE_VERSION = "tormes-hoy-v53";
const SHELL = [
  "./", "index.html", "styles.css", "app.js", "i18n.js", "data.js", "format.js", "charts.js", "vendor/chartjs/chart.min.js",
  "views/home.js", "views/weather.js", "views/uv.js", "views/river.js",
  "i18n/es.json", "manifest.webmanifest", "icons/icon.svg", "icons/icon-192.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_VERSION).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET" || new URL(request.url).origin !== location.origin) return;
  if (new URL(request.url).pathname.includes("/data/")) {
    // Data: network first, fall back to the last cached copy when offline.
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_VERSION).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => caches.match(request, { ignoreSearch: true })),
    );
    return;
  }
  // App shell: cache first.
  event.respondWith(caches.match(request).then((hit) => hit ?? fetch(request)));
});
