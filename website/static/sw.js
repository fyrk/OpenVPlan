/*self.addEventListener("install", event => {
    if (caches) {
        event.waitUntil(
            caches.open("gawvertretung").then(async cache => {
                for (let uri of [
                    "/",
                    "/teachers",
                    "/about",
                    "/privacy",
                    "/assets/img/about.svg",
                    "/assets/img/python-powered.svg",
                    "/assets/img/bootstrap/bookmark.svg",
                    "/assets/img/bootstrap/box-arrow-up-right.svg",
                    "/assets/style/main.css",
                    "/assets/js/substitutions.min.js",
                    "/manifest.json",
                ]) {
                    try {
                        await cache.add(uri);
                    } catch (e) {
                        console.error(e);
                    }
                }
            })
        );
    } else {
        console.error("no cache available");
    }
});

self.addEventListener("fetch", event => {
    console.log(event.request.url);
    event.respondWith(
        caches.match(event.request).then(response => {
            try {
                return fetch(event.request);
            } catch (e) {
                return response;
            }
        })
    );
});*/

self.addEventListener('push', event => {
    event.waitUntil(
        self.registration.showNotification('ServiceWorker Cookbook', {
            body: 'Alea iacta est',
        })
    );
});
