self.addEventListener("activate", event => {
    event.waitUntil(() => {
        idb.open("settings", 1, upgradeDB => {
            const storage = upgradeDB.createObjectStore("settings", {
                keyPath: "key"
            });
            storage.put({key: "hasEnabledPushNotifications", value: false});
        })
    });
})

self.addEventListener("push", event => {
    const options = {
        icon: "favicon.ico",
        vibrate: [100, 50, 100],
        data: {
            dateOfArrival: Date.now(),
            primaryKey: "2"
        },
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
    if (event.data)
        options.body = "Neue Vertretungen für " + event.data.text();
    event.waitUntil(
        self.registration.showNotification("Neue Vertretungen", options)
    );
});

self.addEventListener("notificationclick", event => {
    const notification = event.notification;
    const primaryKey = notification.data.primaryKey;
    const action = e.action;
    switch (event.action) {
        case "close":
            break;
        default:
            clients.openWindow("https://gawvertretung.florian-raediker.de");
    }
    event.notification.close();
})
