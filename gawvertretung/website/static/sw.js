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

self.addEventListener("push", event => {
    const data = event.data.json();
    const options = {
        icon: "favicon.ico",
        vibrate: [100, 50, 100],
        data: {
            url: new URL("/" + data["plan_type"] + "/", self.location.origin).href,
            dateOfArrival: event.data.status
        }
        /*actions: [
            {
                action: "explore", title: "Explore this new world",
                icon: "images/checkmark.png"
            },
            {
                action: "close", title: "Close",
                icon: 'images/xmark.png'
            }
        ]*/
    };
    let title;
    if (Object.keys(data["affected_groups_by_day"]).length === 1) {
        // there is only one day with new substitutions
        title = Object.keys(data["affected_groups_by_day"])[0] + ": Neue Vertretungen für " +
            Object.values(data["affected_groups_by_day"])[0].join(", ");
    } else {
        title = "Neue Vertretungen";
        let body = "";
        for (let [dayName, groups] of Object.entries(data["affected_groups_by_day"])) {
            body += dayName + ": " + groups.join(", ") + "\n";
        }
        options["body"] = body;
    }
    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

self.addEventListener("notificationclick", event => {
    event.notification.close();

    // This looks to see if the current is already open and
    // focuses if it is
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
});
