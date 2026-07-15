/* UK Family Tour — service worker.
   App shell + images cached on install/first use; a day's audio is pre-cached
   on demand when the user starts playing that day.
   Shell is served stale-while-revalidate so deploys reach installed phones. */
const VERSION = 'v2';
const SHELL = `shell-${VERSION}`;
const AUDIO = 'audio-v1'; // survives shell version bumps: audio never changes
const A = 'app/src/main/assets/tour';
const SHELL_URLS = [
  './', 'index.html', 'app.js', 'styles.css', 'manifest.webmanifest',
  'icons/icon-192.png', 'icons/icon-512.png',
  `${A}/manifest.json`, `${A}/images.json`,
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL)
    // cache: 'reload' bypasses the HTTP cache so a deploy can't install stale files
    .then(c => c.addAll(SHELL_URLS.map(u => new Request(u, { cache: 'reload' }))))
    .then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks =>
    Promise.all(ks.filter(k => k !== SHELL && k !== AUDIO).map(k => caches.delete(k)))
  ).then(() => self.clients.claim()));
});

// Pre-cache a whole day's audio when asked, reporting progress to all clients.
self.addEventListener('message', e => {
  const d = e.data || {};
  if (d.type === 'cacheDay' && Array.isArray(d.urls)) {
    e.waitUntil ? e.waitUntil(cacheUrls(d.urls, d.day)) : cacheUrls(d.urls, d.day);
  }
});
async function cacheUrls(urls, day) {
  const cache = await caches.open(AUDIO);
  let done = 0, failed = 0;
  for (const u of urls) {
    if (await cache.match(u)) { done++; }
    else {
      try {
        const r = await fetch(u, { cache: 'no-store' });
        if (r.ok && r.status === 200) { await cache.put(u, r.clone()); done++; }
        else failed++;
      } catch (_) { failed++; }
    }
    broadcast({ type: 'dayProgress', day, done, failed, total: urls.length });
  }
}
function broadcast(msg) {
  self.clients.matchAll({ includeUncontrolled: true })
    .then(cs => cs.forEach(c => c.postMessage(msg)));
}

/* Audio must honor Range requests: iOS Safari's media stack asks for byte
   ranges and rejects mismatched answers, and cache.put() throws on 206s.
   So we always fetch + cache the FULL file keyed by bare URL, then slice
   ranges out of the cached body ourselves. */
async function serveAudio(req) {
  const url = req.url.split('#')[0];
  const cache = await caches.open(AUDIO);
  let full = await cache.match(url);
  if (!full) {
    let r;
    try { r = await fetch(url, { cache: 'no-store' }); } catch (_) { return Response.error(); }
    if (!r.ok || r.status !== 200) return r; // pass odd responses through, never cache
    await cache.put(url, r.clone());
    full = r;
  }
  const range = req.headers.get('range');
  const m = range && /bytes=(\d+)-(\d*)/.exec(range);
  if (!m) return full;
  const buf = await full.arrayBuffer();
  const start = Number(m[1]);
  const end = m[2] ? Math.min(Number(m[2]), buf.byteLength - 1) : buf.byteLength - 1;
  if (start >= buf.byteLength) return new Response(null, { status: 416 });
  return new Response(buf.slice(start, end + 1), {
    status: 206,
    headers: {
      'Content-Type': full.headers.get('Content-Type') || 'audio/mpeg',
      'Content-Range': `bytes ${start}-${end}/${buf.byteLength}`,
      'Content-Length': String(end - start + 1),
      'Accept-Ranges': 'bytes',
    },
  });
}

self.addEventListener('fetch', e => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== 'GET') return;

  // SPA navigations -> app shell (works offline)
  if (req.mode === 'navigate') {
    e.respondWith(caches.match('index.html').then(r => r || fetch(req)));
    return;
  }
  if (url.pathname.includes('/audio/') && url.pathname.endsWith('.mp3')) {
    e.respondWith(serveAudio(req));
    return;
  }
  // Everything else (shell, images, manifest): stale-while-revalidate, so an
  // app.js deploy reaches phones on their next launch even if sw.js is unchanged.
  e.respondWith(caches.match(req).then(cached => {
    const fresh = fetch(req).then(resp => {
      if (resp.ok) caches.open(SHELL).then(c => c.put(req, resp.clone()));
      return resp;
    }).catch(() => cached);
    return cached || fresh;
  }));
});
