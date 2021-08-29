/*
 * GaW-Vertretungsplan
 * Copyright (C) 2019-2021  Florian Rädiker
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published
 * by the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

const toggleNotifications = document.getElementById("toggle-notifications");
const notificationsInfo = document.getElementById("notifications-info");
const notificationsInfo_none = document.getElementById("notifications-info-none");
const notificationsInfo_all = document.getElementById("notifications-info-all");
const notificationsInfo_selection = document.getElementById("notifications-info-selection");
const notificationsInfo_blocked = document.getElementById("notifications-info-blocked");
const notificationsInfo_failed = document.getElementById("notifications-info-failed");

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

function subscribePush(isActive, registration) {
    return new Promise((resolve, reject) => {
        registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: base64UrlToUint8Array("BDu6tTwQHFlGb36-pLCzwMdgumSlyj_vqMR3I1KahllZd3v2se-LM25vhP3Yv_y0qXYx_KPOVOD2EYTaJaibzo8")
        }).then(subscription => {
            console.log("Got push subscription:", subscription, isActive ? "(active)" : "(not active)");
            return fetch(window.location.origin + window.location.pathname + "api/subscribe-push", {
                method: "post",
                "headers": {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({subscription: subscription.toJSON(), selection: selection, is_active: isActive})
            });
        }).then(response => response.json()
        ).then(data => {
            if (data.ok) {
                console.log("Push subscription successful");
                resolve();
            } else {
                console.error("Push subscription failed", data);
                reject();
            }
        }).catch(reason => {
            console.error("Push subscription failed", reason);
            reject(reason);
        });
    });
}


let notificationState;

function setNotificationsInfo(state, registration) {
    console.log("Setting notification-state to", state);
    notificationState = state;
    if (state !== "failed")
        localStorage.setItem(substitutionPlanType + "-notification-state", notificationState);
    localStorage.setItem(substitutionPlanType + "-notification-state-all", notificationState);  // for Plausible with "failed", see plausible.js
    switch (notificationState) {
        case "granted-and-enabled":
            toggleNotifications.checked = true;
            toggleNotifications.disabled = false;
            if (selection !== "") {
                notificationsInfo.innerHTML = notificationsInfo_selection.innerHTML;
            } else {
                notificationsInfo.innerHTML = notificationsInfo_all.innerHTML;
            }
            subscribePush(true, registration)
                .catch(reason => {
                    console.error("Push subscription failed", reason);
                    setNotificationsInfo("failed", registration);
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
            subscribePush(false, registration)
                .catch(reason => {
                    console.error("Push subscription failed", reason);
                    setNotificationsInfo("failed", registration);
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

function onNotificationsAvailable(registration) {
    document.getElementById("notifications-not-available-alert").hidden = true;
    document.getElementById("toggle-notifications-wrapper").hidden = false;
    toggleNotifications.addEventListener("change", () => {
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
                    setNotificationsInfo(notificationState, registration);
                });
            plausible("Push Subscription", {props: {[substitutionPlanType]: "Subscribe"}})
        } else {
            if (notificationState === "granted-and-enabled") {
                setNotificationsInfo("granted-and-disabled", registration);
            }
            plausible("Push Subscription", {props: {[substitutionPlanType]: "Unsubscribe"}})
        }
    });

    function reloadPermissionState() {
        if (!notificationState.startsWith(Notification.permission) && notificationState !== "failed") {
            console.log(notificationState + " changed to " + Notification.permission);
            // permission has been changed
            if (Notification.permission === "granted") {
                setNotificationsInfo("granted-and-disabled", registration);
            } else {
                setNotificationsInfo(Notification.permission, registration);
            }
            return true;
        }
        return false;
    }
    window.addEventListener("focus", reloadPermissionState);

    notificationState = window.localStorage.getItem(substitutionPlanType + "-notification-state");
    if (notificationState == null
        // "failed" is no longer stored in localStorage to prevent notifications from being disabled if the offline
        // page was viewed, but perhaps it's still in there from earlier versions:
        || notificationState === "failed")
        notificationState = "default";
    if (!reloadPermissionState()) {
        setNotificationsInfo(notificationState, registration);
    }
}

if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
        navigator.serviceWorker.ready
            .then(registration => {
                console.log("ServiceWorker is active:", registration.active);
                if ("Notification" in window && "localStorage" in window && "PushManager" in window) {
                    onNotificationsAvailable(registration);
                } else {
                    console.warn("Push Notifications are not supported");
                    localStorage.setItem(substitutionPlanType + "-notification-state-all", "unsupported");  // for Plausible
                }
            });
        navigator.serviceWorker.register("/sw.js")
            .then(registration => {
                console.log("ServiceWorker registration successful:", registration);
            }).catch(reason => console.warn("ServiceWorker registration failed:", reason))
    });
} else {
    console.warn("Service Worker is not supported");
    localStorage.setItem(substitutionPlanType + "-notification-state-all", "unsupported");  // for Plausible
}
