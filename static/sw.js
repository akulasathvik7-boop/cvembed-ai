/**
 * CVEmbed AI — Service Worker
 * Strategy: Cache-first for static assets, Network-first for dynamic routes.
 */

const CACHE_NAME = 'cvembed-v1';

// Static assets to pre-cache on install
const STATIC_ASSETS = [
  '/',
  '/static/style.css',
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png'
];

// ── Install: pre-cache core assets ──────────────────────────────────────────
self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      // addAll is best-effort; if an icon isn't there yet it skips gracefully
      return cache.addAll(STATIC_ASSETS).catch(function (err) {
        console.warn('[SW] Pre-cache partial failure (OK if icons missing):', err);
      });
    })
  );
  self.skipWaiting();
});

// ── Activate: clean up old caches ───────────────────────────────────────────
self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys
          .filter(function (key) { return key !== CACHE_NAME; })
          .map(function (key) { return caches.delete(key); })
      );
    })
  );
  self.clients.claim();
});

// ── Fetch: Network-first for HTML/API, Cache-first for static assets ─────────
self.addEventListener('fetch', function (event) {
  const url = new URL(event.request.url);

  // Only intercept GET requests on our own origin
  if (event.request.method !== 'GET' || url.origin !== location.origin) return;

  // Static assets (CSS, JS, images) → cache-first
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then(function (cached) {
        if (cached) return cached;
        return fetch(event.request).then(function (response) {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(function (cache) {
              cache.put(event.request, clone);
            });
          }
          return response;
        });
      })
    );
    return;
  }

  // Dynamic Flask routes → network-first, fall back to cache
  event.respondWith(
    fetch(event.request)
      .then(function (response) {
        // Cache successful HTML responses for offline fallback
        if (response && response.status === 200 && event.request.headers.get('accept').includes('text/html')) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(function (cache) {
            cache.put(event.request, clone);
          });
        }
        return response;
      })
      .catch(function () {
        // Offline fallback: serve cached version if available
        return caches.match(event.request).then(function (cached) {
          return cached || caches.match('/');
        });
      })
  );
});
