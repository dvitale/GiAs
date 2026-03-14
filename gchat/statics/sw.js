// REQ: [PG-03] Service Worker - cache-first static, network-first API
// REQ: [PG-06] Versioned cache for updates
const CACHE_VERSION = 'gias-v1';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const BASE_PATH = '/gias/webchat';

// Asset statici da pre-cachare
const PRECACHE_URLS = [
  `${BASE_PATH}/`,
  `${BASE_PATH}/offline.html`,
  `${BASE_PATH}/static/css/style.css`,
  `${BASE_PATH}/static/js/chat.js`,
  `${BASE_PATH}/static/img/gias.png`,
  `${BASE_PATH}/static/img/logo-reg.png`,
  `${BASE_PATH}/manifest.webmanifest`
];

// REQ: [PG-03] Install: pre-cache asset statici
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

// REQ: [PG-06] Activate: rimuovi vecchie cache
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== STATIC_CACHE)
          .map((name) => caches.delete(name))
      );
    }).then(() => self.clients.claim())
  );
});

// REQ: [PG-03] Fetch strategy
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Network-first per API e navigazione POST
  if (event.request.method !== 'GET' ||
      url.pathname.includes('/chat') ||
      url.pathname.includes('/api/') ||
      url.pathname.includes('/stream')) {
    event.respondWith(
      fetch(event.request).catch(() => {
        // REQ: [PG-04] Fallback offline per navigazione
        if (event.request.mode === 'navigate') {
          return caches.match(`${BASE_PATH}/offline.html`);
        }
        return new Response('Offline', { status: 503 });
      })
    );
    return;
  }

  // Cache-first per asset statici
  if (url.pathname.startsWith(`${BASE_PATH}/static/`) ||
      url.pathname.endsWith('.webmanifest')) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(STATIC_CACHE).then((cache) => cache.put(event.request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // REQ: [PG-04] Network-first per navigazione, fallback offline
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match(`${BASE_PATH}/offline.html`);
      })
    );
    return;
  }

  // Default: network con fallback cache
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
