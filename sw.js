/* UK Family Tour — service worker.
   App shell + images cached on install/first use; a day's audio is pre-cached
   on demand when the user starts playing that day. */
const SHELL = 'shell-v1';
const AUDIO = 'audio-v1';
const A = 'app/src/main/assets/tour';
const SHELL_URLS = [
  './', 'index.html', 'app.js', 'styles.css', 'manifest.webmanifest',
  'icons/icon-192.png', 'icons/icon-512.png',
  `${A}/manifest.json`, `${A}/images.json`,
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(SHELL_URLS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks =>
    Promise.all(ks.filter(k => k !== SHELL && k !== AUDIO).map(k => caches.delete(k)))
  ).then(() => self.clients.claim()));
});

// Pre-cache a whole day's audio when asked (fire-and-forget, best effort).
self.addEventListener('message', e => {
  const d = e.data || {};
  if (d.type === 'cacheDay' && Array.isArray(d.urls)) {
    caches.open(AUDIO).then(async cache => {
      for (const u of d.urls) {
        if (await cache.match(u)) continue;
        try { const r = await fetch(u); if (r.ok) await cache.put(u, r); } catch (_) { }
      }
    });
  }
});

self.addEventListener('fetch', e => {
  const req = e.req || e.request;
  const url = new URL(req.url);
  if (req.method !== 'GET') return;

  // SPA navigations -> app shell (works offline)
  if (req.mode === 'navigate') {
    e.respondWith(caches.match('index.html').then(r => r || fetch(req)));
    return;
  }
  // Audio: cache-first, fall back to network and store for offline replay.
  if (url.pathname.includes('/audio/') && url.pathname.endsWith('.mp3')) {
    e.respondWith((async () => {
      const cached = await caches.match(req);
      if (cached) return cached;
      try {
        const r = await fetch(req);
        if (r.ok) { const c = await caches.open(AUDIO); c.put(req, r.clone()); }
        return r;
      } catch (_) { return cached || Response.error(); }
    })());
    return;
  }
  // Everything else (shell, images, manifest): cache-first.
  e.respondWith(caches.match(req).then(r => r || fetch(req).then(resp => {
    if (resp.ok && (url.pathname.includes('/images/') || url.pathname.endsWith('.json')))
      caches.open(SHELL).then(c => c.put(req, resp.clone()));
    return resp;
  }).catch(() => r)));
});
