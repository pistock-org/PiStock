// PiStock — service worker minimal
// Stratégie : cache uniquement les assets statiques connus (model-viewer
// et l'icône), pas les requêtes API ni les pages HTML.
// Permet à l'app de se charger même offline si les assets sont déjà
// dans le cache.

const CACHE_NAME = 'pistock-v1';
const STATIC_ASSETS = [
    '/static/model-viewer.min.js',
    '/static/icon.svg',
    '/static/manifest.json'
];

self.addEventListener('install', (event) => {
    // Pré-cache des assets statiques au moment de l'installation.
    // skipWaiting() = active immédiatement la nouvelle version du SW
    // (pas d'attente que tous les onglets ouverts soient fermés).
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.addAll(STATIC_ASSETS))
            .then(() => self.skipWaiting())
            .catch((err) => console.warn('SW install error:', err))
    );
});

self.addEventListener('activate', (event) => {
    // Prend le contrôle de tous les clients (onglets) immédiatement,
    // et purge les anciens caches d'une version précédente.
    event.waitUntil(
        caches.keys().then((names) =>
            Promise.all(
                names.filter((n) => n !== CACHE_NAME)
                     .map((n) => caches.delete(n))
            )
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    // On ne sert depuis le cache QUE pour les assets connus.
    // Pour tout le reste (API, pages, uploads), on laisse passer
    // normalement (network-first, pas de cache).
    const isStaticAsset = STATIC_ASSETS.some((path) =>
        url.pathname === path
    );
    if (!isStaticAsset) {
        return; // pas d'interception
    }
    event.respondWith(
        caches.match(event.request).then((cached) => {
            if (cached) return cached;
            // Pas en cache : fetch normal puis met en cache pour la suite
            return fetch(event.request).then((response) => {
                if (response && response.status === 200) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME)
                          .then((cache) => cache.put(event.request, clone));
                }
                return response;
            });
        })
    );
});
