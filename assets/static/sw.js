
// the following is inspired by code from (https://github.com/plausible/analytics/blob/0089add5944177bd2352510236a09157dc9d16bf/tracker/src/plausible.js, MIT license)
// the original code isn't designed to be used with SWs
//var plausible_ignore = window.localStorage.plausible_ignore;  // TODO: localStorage is not supported by SW
function plausible(eventName, options) {
    const payload = {
        n: eventName,
        u: self.location.toString(),
        d: "gawvertretung.florian-raediker.de",
        r: null,
        //w: 0
    }
    if (options && options.meta) {
        payload.m = JSON.stringify(options.meta)
    }
    if (options && options.props) {
        payload.p = JSON.stringify(options.props)
    }
    return fetch("https://plausible.io/api/event", {
        method: "POST",
        headers: {"Content-Type": "text/plain"},
        body: JSON.stringify(payload)
    }).catch(reason => console.error("reporting error failed", reason))
}

function reportError(error, event = null) {
    console.error("reporting error", error, event);
    try {
        let name = error.name;
        let message = (event == null ? undefined : event.message) ||
            error.message;
        let description = error.description;  // non-standard Microsoft property
        let number = error.number; // non-standard Microsoft property
        let filename = (event == null ? undefined : event.filename) ||
            error.fileName;  // error.fileName is non-standard Mozilla property
        let lineno = (event == null ? undefined : event.lineno) ||
            error.lineNumber;  // error.lineNumber is non-standard Mozilla property
        let colno = (event == null ? undefined : event.colno) ||
            error.columnNumber;  // error.columnNumber is non-standard Mozilla property
        let stack = (event == null ? undefined : event.stack) ||
            error.stack;  // error.stack is non-standard Mozilla property
        plausible("JavaScript Error (Service Worker)", {
            props: {
                [(name || "Generic Error") + ": " + message]: stack + " - " + filename + ":" + lineno + ":" + colno +
                " " + description + " " + number
            }
        });
    } catch (e) {
        console.error("reporting error failed", e);
    }
}

self.addEventListener("error", e => reportError(e.error, e));  // e.error is experimental, according to MDN
self.addEventListener("unhandledrejection", e => reportError(e.reason));


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
    "/assets/ferien/script.min.js",
    "/assets/ferien/style.css",
    //"/assets/img/python-powered.min.svg", // caching <object src="..."> doesn't work: https://stackoverflow.com/questions/56854918/how-to-interact-with-an-svg-asset-in-an-offline-progressive-web-app
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
    if (!event.data) {
        event.waitUntil(Promise.all([
                self.registration.showNotification("Neue Benachrichtigung", {
                    icon: "android-chrome-512x512.png",
                    badge: "monochrome-96x96.png",
                    lang: "de"
                }),
                plausible("Notification", {props: {other: "Received, but without Payload"}})
            ])
        );
        return;
    }
    const data = event.data.json();

    if (data.type === "generic_message") {
        event.waitUntil(
            self.registration.showNotification(data.title, {
                body: data.body || "",
                icon: "android-chrome-512x512.png",
                badge: "monochrome-96x96.png",
                lang: "de",
                data: {
                    type: "generic_message"
                }
            })
        );
    } else {
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
                        type: "subs_update",
                        plan_id: plan_id,
                        url: new URL("/" + plan_id + "/?source=Notification", self.location.origin).href,
                        affected_groups_by_day: affectedGroups,
                    }
                };

                self.registration.showNotification(title, options)

                plausible("Notification", {props: {[plan_id]: "Received"}})
            })
        );
    }
});

self.addEventListener("notificationclick", event => {
    event.notification.close();

    if (event.notification.data.type === "subs_update") {
        // open website
        event.waitUntil(Promise.all([
            self.clients.matchAll().then(function(clientList) {
                const notificationURL = new URL(event.notification.data.url);
                for (let client of clientList) {
                    const url = new URL(client.url);
                    if (url.origin + url.pathname === notificationURL.origin + notificationURL.pathname && "focus" in
                        client)
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

            plausible("Notification", {props: {[event.notification.data.plan_id]: "Clicked"}})
        ]));
    }
});
