/*self.addEventListener("activate", event => {
    event.waitUntil(() => {
        self.idb.open("settings", 1, upgradeDB => {
            const storage = upgradeDB.createObjectStore("settings", {
                keyPath: "key"
            });
            storage.put({key: "hasEnabledPushNotifications", value: false});
        })
    });
})*/

function reportError(error, event=null) {
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
            stack: (event == null ? undefined : event.stack) || error.stack,  // error.stack is non-standard Mozilla property
            user_agent: navigator.userAgent
        })
    })
}

self.addEventListener("error", e => {
    reportError(e.error, e);  // e.error is experimental, according to MDN
});

self.addEventListener("unhandledrejection", e => {
    console.log("unhandledrejection", e);
    reportError(e.reason);
});

self.addEventListener("fetch", () => {});

self.addEventListener("push", async (event) => {
    const data = event.data.json();

    let timestamp = data["timestamp"];
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
                if (n.data.plan_id === plan_id) {
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
                icon: "favicon.ico",
                badge: "favicon-96-monochrome.png",
                lang: "de",
                timestamp: timestamp,
                vibrate: [300, 100, 400],
                data: {
                    plan_id: plan_id,
                    url: new URL("/" + plan_id + "/", self.location.origin).href,
                    affected_groups_by_day: affectedGroups
                }
            };

            self.registration.showNotification(title, options)
        })
    );
});

self.addEventListener("notificationclick", event => {
    event.notification.close();

    // open website
    event.waitUntil(self.clients.matchAll({
        type: "window"
    }).then(function (clientList) {
        for (let client of clientList) {
            const url = new URL(client.url);
            console.log(event.notification.data.url, url.origin+url.pathname);
            if (url.origin+url.pathname === event.notification.data.url && "focus" in client)
                return client.focus();
        }
        if (self.clients.openWindow)
            return self.clients.openWindow(event.notification.data.url).then(windowClient => windowClient.focus());
    }));

    // close all notifications
    self.registration.getNotifications().then(notifications => {
        notifications.forEach(n => {
            if (event.notification.data.plan_id === n.data.plan_id)
                n.close()
        });
    });
});
