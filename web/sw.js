const CACHE_NAME = 'hotspot-share-v2.0.7';
const STATIC_ASSETS = [
  '/',
  '/style.css?v=2.0.7',
  '/app.js?v=2.0.7',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    }).catch(() => {})
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Always bypass cache for API routes, uploads, downloads, and websockets
  if (
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/upload') ||
    url.pathname.startsWith('/download') ||
    url.pathname.startsWith('/zip') ||
    url.pathname.startsWith('/raw') ||
    event.request.method !== 'GET'
  ) {
    return;
  }

  // Network-First with Cache Fallback for all UI assets
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
