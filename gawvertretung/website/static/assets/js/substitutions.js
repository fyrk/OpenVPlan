// ==================
// GREY SUBSTITUTIONS

const dates = document.getElementsByClassName("date");

function greySubstitutions() {
    const now = new Date();
    if (dates.length > 0 && dates[0].innerHTML === now.getDate() + "." + (now.getMonth() + 1) + "." + now.getFullYear()) {
        const b2 = now.getHours();
        const c2 = now.getMinutes();
        for (let i of [
            ["1", 8, 35],
            ["2", 9, 25],
            ["3", 10, 30],
            ["4", 11, 15],
            ["5", 12, 20],
            ["6", 13, 10],
            ["7", 14, 35],
            ["8", 15, 25],
            ["9", 16, 20],
            ["10", 17, 5]
        ]) {
            if (i[1] < b2 || (i[1] === b2 && i[2] <= c2)) {
                for (let x of document.getElementsByClassName("lesson" + i[0])) {
                    x.classList.add("grey");
                }
            } else {
                setTimeout(greySubstitutions, new Date(now.getFullYear(), now.getMonth(), now.getDate(), i[1], i[2]).getTime() - now.getTime());
                break
            }
        }
    }
}

greySubstitutions();


// =================
// WEBSOCKET UPDATES

let type = window.location.pathname.split(1)[1];
if (!type)
    type = "students"
const socket = new WebSocket("ws://localhost:8080/api/" + type + "/wait-for-update");

socket.onopen = event => {
    console.log("WebSocket opened", event);
    onOnline(event);
}
socket.onclose = event => {
    console.log("WebSocket closed", event);
    onOffline(event);
}
socket.onmessage = event => {
    const msg = JSON.parse(event.data);
    console.log("WebSocket message", msg);
    window.location.reload();
}

const onlineStatus = document.getElementById("online-status");
function onOnline(event) {
    onlineStatus.textContent = "Aktuell";
    onlineStatus.classList.add("online");
    onlineStatus.classList.remove("offline");
}
function onOffline(event) {
    onlineStatus.textContent = "Keine Verbindung zum Server";
    onlineStatus.classList.add("offline");
    onlineStatus.classList.remove("online");
}


// ============
// PUSH NOTIFICATIONS

const selection = document.getElementById("selectionInput").value;

const notificationsBlock = document.getElementById("notifications-block");
const toggleNotifications = document.getElementById("toggle-notifications");
const notificationsInfo_none = document.getElementById("notifications-info-none");
const notificationsInfo_all = document.getElementById("notifications-info-all");
const notificationsInfo_selection = document.getElementById("notifications-info-selection");
const notificationsInfo_selectionContent = document.getElementById("notifications-info-selection-content");
let swRegistration;
let isSubscribed;

function onNotificationsDenied() {
    toggleNotifications.disabled = true;
    notificationsInfo.textContent = "Du hast Benachrichtigungen vom Vertretungsplan blockiert.";
    notificationsInfo.classList.add("text-danger");
}

function onNotificationsAvailable() {
    notificationsBlock.hidden = false;
    if ("Notification" in window) {
        switch (Notification.permission) {
            case "denied":
                onNotificationsDenied();
                break;
        }
    }
    swRegistration.pushManager.getSubscription()
        .then(subscription => {
            isSubscribed = subscription !== null;

        });
    toggleNotifications.addEventListener("change", event => {
        if (toggleNotifications.checked) {
            window.Notification.requestPermission()
                .then(permission => {
                    switch (permission) {
                        case "denied":
                            toggleNotifications.checked = false;
                            onNotificationsDenied();
                            break;
                        case "default":
                            toggleNotifications.checked = false;
                            break;
                        case "granted":
                            notificationsInfo_none.hidden = true;
                            if (selection !== "") {
                                notificationsInfo_selectionContent.textContent = selection;
                                notificationsInfo_selection.hidden = false;
                            } else {
                                notificationsInfo_all.hidden = false;
                            }
                            break;
                    }
                });
        } else {
            notificationsInfo_all.hidden = true;
            notificationsInfo_selection.hidden = true;
            notificationsInfo_none.hidden = false;
        }
    });
}

if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.min.js")
            .then(registration => {
                swRegistration = registration;
                console.log("ServiceWorker registration successful:", registration);
                if ("PushManager" in window) {
                    onNotificationsAvailable();
                } else {
                    console.warn("PushManager is not supported");
                }
            })
            .catch(reason => console.warn("ServiceWorker registration failed:", reason))
    });
} else {
    console.warn("ServiceWorker is not supported");
}
