// Network-first: always tries for the latest version, falls back to the last saved copy when offline.
const C='kwhh-v1';
self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(C).then(c=>c.addAll(['./','./music.json','./icon-192.png'])).catch(()=>{}))});
self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(e.request.method!=='GET'||u.origin!==location.origin)return;
const key=u.origin+u.pathname;
e.respondWith(fetch(e.request).then(r=>{if(r.ok){const cp=r.clone();caches.open(C).then(c=>c.put(key,cp))}return r}).catch(()=>caches.match(key).then(r=>r||caches.match(u.origin+u.pathname.replace(/[^/]*$/,'')))))});
