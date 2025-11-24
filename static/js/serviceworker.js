const CACHE_NAME = 'FlashAI-cache-v2';
const urlsToCache = [
  '/',  // home
  '/offline/',
  '/static/css/bootstrap.min.css',
  '/static/js/bootstrap.bundle.min.js',
  '/static/img/icon-192.png',
  '/static/img/icon-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('Caching files...');
      return Promise.all(
        urlsToCache.map(url =>
          fetch(url)
            .then(response => {
              if (!response.ok) throw new Error(`Request failed for ${url}`);
              return cache.put(url, response);
            })
            .catch(err => console.warn('Skipping file:', url, err))
        )
      );
    })
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request).then(response => {
      return response || caches.match('/offline/');
    }))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
    ))
  );
});
