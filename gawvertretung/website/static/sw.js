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
    let title;
    if (event.data)
        title = "Neue Vertretungen für " + event.data.text();
    else
        title = "Neue Vertretungen";
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
                    if (windowClient.url === e.notification.data.url) {
                        windowClient.focus()
                        return true;
                    }
                    return false;
                });
                if (!hasWindow) {
                    self.clients.openWindow(e.notification.data.url).then(windowClient => windowClient ? windowClient.focus() : null);
                }
            })
    );
})
