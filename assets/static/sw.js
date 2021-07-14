/*function reportError(error, event=null) {
    fetch("/api/report-error", {
        method: "post",
        body: new URLSearchParams({
            name: error.name,
            message: (event == null ? undefined : event.message) || error.message,
            description: error.description,  // non-standard Microsoft property
            number: error.number, // non-standard Microsoft property
            filename: (event == null ? undefined : event.filename) || error.fileName,  // error.fileName is non-standard Mozilla property
            lineno: (event == null ? undefined : event.lineno) || error.lineNumber,  // error.lineNumber is non-standard Mozilla property
            colno: (event == null ? undefined : event.colno) || error.columnNumber,  // error.columnNumber is non-standard Mozilla property
            stack: (event == null ? undefined : event.stack) || error.stack  // error.stack is non-standard Mozilla property
        })
    }).catch(reason => console.error("reporting error failed", reason))
}
self.addEventListener("error", e => reportError(e.error, e));  // e.error is experimental, according to MDN
self.addEventListener("unhandledrejection", e => reportError(e.reason));
*/ // TODO (plausible)

const CACHE = "gawvertretung-v1";

const planPaths = [
    "/students/",
    "/teachers/"
];

const assetsToCache = [
    "/assets/style/main.css",
    "/assets/style/main-dark.css",
    "/assets/style/substitutions.css",
    "/assets/style/substitutions-dark.css",
    "/assets/js/substitutions.min.js",
    "/assets/js/dark-theme.min.js",
    "/assets/js/timetables.min.js",
    //"/assets/img/python-powered.min.svg", // caching <object src="..."> doesn't work: https://stackoverflow.com/questions/56854918/how-to-interact-with-an-svg-asset-in-an-offline-progressive-web-app
    //"/assets/img/about.min.svg",
    //"/assets/style/about.css",
    "/favicon-32x32.png",
    "/android-chrome-192x192.png"
];

self.addEventListener("install", event => {
    event.waitUntil(
        caches.open(CACHE).then(cache =>
            Promise.all([
                // assetsToCache are added to the cache as soon as they're requested by the page
                // this way, url params for cache busting can be changed in HTML and don't need to be saved in assetsToCache
                //cache.addAll(assetsToCache),
                Promise.all(
                    // for plans, save a response in cache that is not redirected
                    planPaths.map(url => fetch(url+"?all&sw").then(r => cache.put(url, r)))
                )
            ])
        )
    );
});

self.addEventListener("activate", event => {
    event.waitUntil(
        caches.open(CACHE).then(cache => {
            cache.keys().then(keys =>
                Promise.all(
                    keys.map(request => {
                        const url = new URL(request.url);
                        if (!(assetsToCache.includes(url.pathname) || planPaths.includes(url.pathname))) {
                            console.log("cache: delete old", request);
                            return cache.delete(request);
                        }
                    })
                )
            )
        })
    )
})

// from https://serviceworke.rs/strategy-network-or-cache_service-worker_doc.html (MIT license)
self.addEventListener("fetch", event => {
    const url = new URL(event.request.url);
    console.log("requested", event.request.url, url.pathname);
    if (url.pathname === "/") {
        event.respondWith(Response.redirect("/students/"))
    } else if (planPaths.includes(url.pathname)) {
        // network-then-cache because plans need to be up-to-date
        event.respondWith(
            new Promise((fulfill, reject) => {
                // currently, using a timeout might not display the most recent substitutions
                // more work is needed, especially with WebSocket connection in updates.js
                /*const timeout = setTimeout(() => {
                    console.log("timeout", url.pathname);
                    reject();
                }, 1000);*/
                console.log("fetching", event.request);
                fetch(event.request).then(response => {
                    //clearTimeout(timeout);
                    console.log("fetch successful", event.request.url);
                    fulfill(response.clone());
                    // save this version of the plan in cache
                    caches.open(CACHE).then(cache => cache.put(url.pathname, response));
                }, reject);
            }).catch(() =>
                caches.open(CACHE).then(cache =>
                    cache.match(url.pathname, {ignoreSearch: true}).then(matching => {
                        if (matching)
                            return matching
                        else {
                            console.log("no match for", event.request);
                            return Promise.reject("no-match");
                        }
                    })
                )
            )
        );
    } else if (assetsToCache.includes(url.pathname)) {
        // cache-then-network (and if network fails, use outdated item from cache)
        // update cache if url params are different (cache busting)
        event.respondWith(
            new Promise(resolve =>
                // check whether the exact requested URL (including params for cache busting!) exists
                caches.open(CACHE).then(cache => cache.match(event.request).then(response => {
                    if (response) {
                        // an up-to-date item is in the cache
                        console.log("cache has up-to-date response for", event.request.url);
                        resolve(response);
                        return;
                    }
                    fetch(event.request).then(async response => {
                        console.log("cache is missing up-to-date response, fetching for", event.request.url);
                        resolve(response.clone());

                        // delete all items in the cache that have the same pathname - they're outdated because they
                        // haven't got the same cache busting parameter
                        await cache.delete(event.request, {ignoreSearch: true, ignoreVary: true}).then(value => console.log("deleted", value, event.request.url));

                        console.log("putting in cache:", event.request.url);
                        // save this new up-to-date version in the cache
                        await cache.put(event.request, response);
                    }).catch(() => {
                        // fetch didn't work, must fall back to an outdated version from cache
                        resolve(cache.match(event.request, {ignoreSearch: true, ignoreVary: true}));
                    })
                }))
            )
        )
        /*new Promise((fulfill, reject) => {
                // currently, using a timeout might not display the most recent substitutions
                // more work is needed, especially with WebSocket connection in updates.js
                /*const timeout = setTimeout(() => {
                    console.log("timeout", url.pathname);
                    reject();
                }, 1000);* /
                console.log("fetching", event.request);
                fetch(event.request).then(response => {
                    //clearTimeout(timeout);
                    console.log("fetch successful", event.request.url);
                    fulfill(response.clone());
                    if ((url.pathname !== "/students/" && url.pathname !== "/teachers/") || url.search !== "") {
                        console.log("saving response in cache", event.request.url);
                        caches.open(CACHE).then(cache => cache.put(new Request(url.pathname), response))
                    } else {
                        console.log("not saving in cache", event.request.url);
                    }
                }, reject);
            }).catch(() => caches.open(CACHE)
                .then(cache => cache.match(event.request, {ignoreSearch: true})
                    .then(matching => {
                        if (matching)
                            return matching
                        else {
                            console.log("no match for", event.request);
                            return Promise.reject("no-match");
                        }
                    }))));*/
    } else {
        console.log("not using SW for request");
    }
});

self.addEventListener("push", async (event) => {
    const data = event.data.json();

    //let timestamp = data["timestamp"];
    let plan_id = data["plan_id"];

    // merge all affected groups of previous notifications with the same plan id that are still open
    let affectedGroups = data["affected_groups_by_day"];
    console.log("affectedGroups", affectedGroups);
    for (let day of Object.values(affectedGroups)) {
        day["groups"] = new Set(day["groups"]);
    }
    let currentTimestamp = Date.now()/1000;  // current UTC timestamp in seconds
    event.waitUntil(
        self.registration.getNotifications().then(notifications => {
            for (let n of notifications) {
                if (n.data && n.data.plan_id === plan_id) {
                    for (let [expiryTime, day] of Object.entries(n.data.affected_groups_by_day)) {
                        console.log("expiryTime, currentTimestamp:", expiryTime, currentTimestamp);
                        if (expiryTime > currentTimestamp) {
                            console.log("add", day["groups"]);
                            if (expiryTime in affectedGroups) {
                                console.log("already in affectedGroups");
                                day["groups"].forEach(g => affectedGroups[expiryTime]["groups"].add(g));
                            }
                            else {
                                console.log("new day", day);
                                affectedGroups[expiryTime] = day;
                            }
                        }
                    }
                    n.close();
                }
            }
            for (let day of Object.values(affectedGroups)) {
                day["groups"] = Array.from(day["groups"]);
            }

            let title;
            let body;

            if (Object.keys(affectedGroups).length === 1) {
                // there is only one day with new substitutions
                let day = Object.values(affectedGroups)[0];
                title = day["name"] + ": Neue Vertretungen";
                body = day["groups"].join(", ");
            } else {
                title = "Neue Vertretungen";
                body = "";
                for (let day of Object.values(affectedGroups)) {
                    body += day["name"] + ": " + day["groups"].join(", ") + "\n";
                }
            }

            const options = {
                body: body,
                icon: "android-chrome-512x512.png",
                badge: "monochrome-96x96.png",
                lang: "de",
                //timestamp: timestamp,
                vibrate: [300, 100, 400],
                data: {
                    plan_id: plan_id,
                    url: new URL("/" + plan_id + "/", self.location.origin).href,
                    affected_groups_by_day: affectedGroups,
                    notification_id: data.notification_id
                }
            };

            self.registration.showNotification(title, options)

            // TODO (plausible): Send notification received event
        })
    );
});

self.addEventListener("notificationclick", event => {
    event.notification.close();

    // open website
    event.waitUntil(Promise.all([
        self.clients.matchAll({
            type: "window"
        }).then(function (clientList) {
            for (let client of clientList) {
                const url = new URL(client.url);
                console.log(event.notification.data.url, url.origin + url.pathname);
                if (url.origin + url.pathname === event.notification.data.url && "focus" in client)
                    return client.focus();
            }
            if (self.clients.openWindow)
                return self.clients.openWindow(event.notification.data.url);
        }),

        // close all notifications
        self.registration.getNotifications().then(notifications => {
            notifications.forEach(n => {
                if (n.data != null && n.data.plan_id === event.notification.data.plan_id)
                    n.close()
            });
        }),

        // TODO (plausible): Send notification clicked event

    ]));
});
