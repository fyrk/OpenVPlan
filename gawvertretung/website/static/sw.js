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
            url: "/" + data.plan_type + "/",
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
    event.waitUntil(
        self.clients.matchAll({type: "window"})
            .then(clientsArray => {
                const hasWindow = clientsArray.some(windowClient => {
                    if (windowClient.url === event.notification.data.url) {
                        windowClient.focus()
                        return true;
                    }
                    return false;
                });
                if (!hasWindow) {
                    self.clients.openWindow(event.notification.data.url).then(windowClient => windowClient ? windowClient.focus() : null);
                }
            })
    );
})
