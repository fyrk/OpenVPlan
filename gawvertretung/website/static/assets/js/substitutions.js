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
                // noinspection JSCheckFunctionSignatures
                setTimeout(greySubstitutions, new Date(now.getFullYear(), now.getMonth(), now.getDate(), i[1], i[2]).getTime() - now.getTime());
                break
            }
        }
    }
}

greySubstitutions();


// =================
// WEBSOCKET UPDATES

let substitutionPlanType = window.location.pathname.split("/", 2)[1];
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

const toggleNotifications = document.getElementById("toggle-notifications");
const notificationsInfo = document.getElementById("notifications-info");
const notificationsInfo_none = document.getElementById("notifications-info-none");
const notificationsInfo_all = document.getElementById("notifications-info-all");
const notificationsInfo_selection = document.getElementById("notifications-info-selection");
const notificationsInfo_blocked = document.getElementById("notifications-info-blocked");
const notificationsInfo_failed = document.getElementById("notifications-info-failed");
let swRegistration;

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

function subscribePush(isActive) {
    return new Promise((resolve, reject) => {
            swRegistration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: base64UrlToUint8Array("BDu6tTwQHFlGb36-pLCzwMdgumSlyj_vqMR3I1KahllZd3v2se-LM25vhP3Yv_y0qXYx_KPOVOD2EYTaJaibzo8")
        }).then(subscription => {
            console.log("Got push subscription:", subscription, isActive ? "(active)" : "(not active)");
            fetch(window.location.origin + window.location.pathname + "api/subscribe-push", {
                method: "post",
                "headers": {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({subscription: subscription.toJSON(), selection: selection, is_active: isActive})
            })
                .then(response => response.json())
                .then(data => {
                    if (data.ok) {
                        console.log("Push subscription successful");
                        resolve();
                    } else {
                        console.error("Push subscription failed");
                        reject();
                    }
                });
        }).catch(reason => {
            console.error("Push subscription failed", reason);
            reject(reason);
        });
    });
}


let notificationState;

function setNotificationsInfo(state) {
    console.log("Setting notification-state to", state);
    notificationState = state;
    window.localStorage.setItem(substitutionPlanType + "-notification-state", notificationState);
    switch (notificationState) {
        case "granted-and-enabled":
            toggleNotifications.checked = true;
            toggleNotifications.disabled = false;
            if (selection !== "") {
                notificationsInfo.innerHTML = notificationsInfo_selection.innerHTML.replace("{selection}", selection);
            } else {
                notificationsInfo.innerHTML = notificationsInfo_all.innerHTML;
            }
            subscribePush(true)
                .catch(reason => {
                    setNotificationsInfo("failed");
                });
            break;
        case "denied":
            toggleNotifications.checked = false;
            toggleNotifications.disabled = true;
            notificationsInfo.innerHTML = notificationsInfo_blocked.innerHTML;
            break;
        case "failed":
            toggleNotifications.checked = false;
            toggleNotifications.disabled = true;
            notificationsInfo.innerHTML = notificationsInfo_failed.innerHTML;
            break;
        case "granted-and-disabled":
            subscribePush(false)
                .catch(reason => {
                        setNotificationsInfo("failed");
                    });
            toggleNotifications.checked = false;
            toggleNotifications.disabled = false;
            notificationsInfo.innerHTML = notificationsInfo_none.innerHTML;
            break;
        default:
        case "default":
            toggleNotifications.checked = false;
            toggleNotifications.disabled = false;
            notificationsInfo.innerHTML = notificationsInfo_none.innerHTML;
            break;
    }
}

function onNotificationsAvailable() {
    document.getElementById("notifications-block").hidden = false;
    toggleNotifications.addEventListener("change", event => {
        if (toggleNotifications.checked) {
            window.Notification.requestPermission()
                .then(permission => {
                    switch (permission) {
                        case "granted":
                            notificationState = "granted-and-enabled";
                            break;
                        default:
                            notificationState = permission;
                    }
                    setNotificationsInfo(notificationState);
                });
        } else {
            if (notificationState === "granted-and-enabled") {
                setNotificationsInfo("granted-and-disabled");
            }
        }
    });
    function reloadPermissionState() {
        if (!notificationState.startsWith(Notification.permission)) {
            // permission has been changed
            if (Notification.permission === "granted") {
                setNotificationsInfo("granted-and-disabled");
            } else {
                setNotificationsInfo(Notification.permission);
            }
            return true;
        }
        return false;
    }
    window.addEventListener("focus", reloadPermissionState);

    notificationState = window.localStorage.getItem(substitutionPlanType + "-notification-state");
    if (!reloadPermissionState()) {
        if (notificationState != null) {
            setNotificationsInfo(notificationState);
        } else {
            setNotificationsInfo("default");
        }
    }
}

if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.min.js")
            .then(registration => {
                swRegistration = registration;
                console.log("ServiceWorker registration successful:", registration);
                if (!("Notification" in window)) {
                    console.warn("Notification is not supported");
                    return;
                }
                if (!("localStorage" in window)) {
                    console.warn("localStorage is not supported");
                    return;
                }
                onNotificationsAvailable();
            }).catch(reason => console.warn("ServiceWorker registration failed:", reason))
    });
} else {
    console.warn("serviceWorker is not supported");
}
