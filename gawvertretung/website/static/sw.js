self.addEventListener("activate", event => {
    event.waitUntil(() => {
        /*self.idb.open("settings", 1, upgradeDB => {
            const storage = upgradeDB.createObjectStore("settings", {
                keyPath: "key"
            });
            storage.put({key: "hasEnabledPushNotifications", value: false});
        })*/
    });
})

self.addEventListener("fetch", function(event) {});

self.addEventListener("push", event => {
    const data = event.data.json();

    // convert status ("dd.mm.yyyy hh:MM") to milliseconds
    let timestamp;
    try {
        let [, dd, mm, yyyy, hh, MM] = data.status.match(/(\d\d).(\d\d).(\d\d\d\d) (\d\d):(\d\d)/);
        timestamp = Date.UTC(yyyy, mm, dd, hh, MM);
    } catch (e) {
        console.error(e);
        timestamp = null;
    }

    let title;
    let body;
    if (Object.keys(data["affected_groups_by_day"]).length === 1) {
        // there is only one day with new substitutions
        title = Object.keys(data["affected_groups_by_day"])[0] + ": Neue Vertretungen";
        body = Object.values(data["affected_groups_by_day"])[0].join(", ");
    } else {
        title = "Neue Vertretungen";
        body = "";
        for (let [dayName, groups] of Object.entries(data["affected_groups_by_day"])) {
            body += dayName + ": " + groups.join(", ") + "\n";
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
            url: new URL("/" + data["plan_type"] + "/", self.location.origin).href
        }
    };

    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

self.addEventListener("notificationclick", event => {
    event.notification.close();

    // open website
    event.waitUntil(self.clients.matchAll({
        type: "window"
    }).then(function (clientList) {
        for (let client of clientList) {
            if (client.url.split("?")[0] === event.notification.data.url && "focus" in client)
                return client.focus();
        }
        if (self.clients.openWindow)
            return self.clients.openWindow(event.notification.data.url).then(windowClient => windowClient.focus());
    }));

    // close all notifications
    self.registration.getNotifications().then(notifications => {
        notifications.forEach(n => n.close());
    });
});
