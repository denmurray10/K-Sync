/* K-Beats service worker — minimal by design.
   Purpose: PWA installability ("Add to home screen") + gentle offline notice.
   All requests pass through to the network; nothing dynamic is cached. */
const OFFLINE_BODY = '<!doctype html><html class="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>K-Beats — Offline</title><style>body{background:#000;color:#fff;font-family:Montserrat,system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center}h1{font-weight:900;text-transform:uppercase;letter-spacing:-.02em}p{color:#94a3b8;font-size:14px}span{color:#f425c0}</style></head><body><div><h1>Signal <span>lost</span></h1><p>You are offline. K-Beats will be right here when you reconnect.</p></div></body></html>';

self.addEventListener('install', (event) => { self.skipWaiting(); });
self.addEventListener('activate', (event) => { event.waitUntil(self.clients.claim()); });

self.addEventListener('fetch', (event) => {
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() =>
        new Response(OFFLINE_BODY, { headers: { 'Content-Type': 'text/html; charset=utf-8' } })
      )
    );
  }
});
