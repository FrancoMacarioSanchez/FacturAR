// Este código hace que la PWA sea instalable. 
// En una etapa avanzada, acá podés agregar caché para funcionar sin conexión.
const CACHE_NAME = 'corex-pwa-v1';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('fetch', (event) => {
    // Modo red primero (Network First)
    event.respondWith(
        fetch(event.request).catch(() => caches.match(event.request))
    );
});