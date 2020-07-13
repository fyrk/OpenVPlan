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

let substitutionPlanType = window.location.pathname.split(1)[1];
if (!substitutionPlanType)
    substitutionPlanType = "students"

const ws = new WebSocket(
    (window.location.protocol === "http:" ? "ws:" : "wss:") + "//" +
    window.location.host + window.location.pathname + "api/wait-for-updates");
ws.onopen = event => {
    console.log("WebSocket opened", event);
    onOnline(event);
}
ws.onclose = event => {
    console.log("WebSocket closed", event);
    onOffline(event);
}
ws.onmessage = event => {
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
const notificationsInfo_blocked = document.getElementById("notifications-info-blocked");
let swRegistration;
let isSubscribed;

function base64UrlToUint8Array(base64UrlData) {
    const padding = '='.repeat((4 - base64UrlData.length % 4) % 4);
    const base64 = (base64UrlData + padding)
        .replace(/-/g, '+')
        .replace(/_/g, '/');

    const rawData = atob(base64);
    const buffer = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        buffer[i] = rawData.charCodeAt(i);
    }

    return buffer;
}
console.log(window.location);

function onGotNotificationPermission(permission) {
    switch (permission) {
        case "granted":
            notificationsInfo_none.hidden = true;
            if (selection !== "") {
                notificationsInfo_selectionContent.textContent = selection;
                notificationsInfo_selection.hidden = false;
            } else {
                notificationsInfo_all.hidden = false;
            }
            swRegistration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: base64UrlToUint8Array("BDu6tTwQHFlGb36-pLCzwMdgumSlyj_vqMR3I1KahllZd3v2se-LM25vhP3Yv_y0qXYx_KPOVOD2EYTaJaibzo8")
            }).then(subscription => {
                console.log("Subscription", subscription);
                fetch(window.location.origin + window.location.pathname + "api/subscribe-push", {
                    method: "post",
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({subscription: subscription.toJSON(), selection: selection, is_active: true})
                })
                    .then(response => response.json())
                    .then(data => {
                        if (!data.ok) {
                            // TODO subscribing failed
                        }
                    });
            }).catch(reason => console.warn("Unable to subscribe to push", reason));
            break;
        case "denied":
            toggleNotifications.checked = false;
            toggleNotifications.disabled = true;
            notificationsInfo_none.hidden = true;
            notificationsInfo_blocked.hidden = false;
            break;
        case "default":
            toggleNotifications.checked = false;
            break;
    }
}

function onNotificationsAvailable() {
    notificationsBlock.hidden = false;
    onGotNotificationPermission(Notification.permission);
    swRegistration.pushManager.getSubscription()
        .then(subscription => {
            isSubscribed = subscription !== null;

        });
    toggleNotifications.addEventListener("change", event => {
        if (toggleNotifications.checked) {
            window.Notification.requestPermission()
                .then(permission => onGotNotificationPermission(permission));
        } else {
            notificationsInfo_all.hidden = true;
            notificationsInfo_selection.hidden = true;
            notificationsInfo_none.hidden = false;
        }
    });

    swRegistration.pushManager.getSubscription()
        .then(subscription => {
            if (subscription == null) {
                console.log("Not subscribed to push service");
            } else {
                console.log("Subscription object:", subscription);
            }
        });
}

if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.min.js")
            .then(registration => {
                swRegistration = registration;
                console.log("ServiceWorker registration successful:", registration);
                if ("PushManager" in window && "Notification" in window) {
                    onNotificationsAvailable();
                } else {
                    console.warn("PushManager and/or Notification is not supported");
                }
            }).catch(reason => console.warn("ServiceWorker registration failed:", reason))
    });
} else {
    console.warn("ServiceWorker is not supported");
}
