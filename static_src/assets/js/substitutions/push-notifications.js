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

const notificationsToggle = document.getElementById("notifications-toggle");

function showState(state) {
    for (let e of document.getElementsByClassName("notification-state")) {
        e.hidden = true;
    }
    document.querySelector(`.notification-state[data-n="${state}"]`).hidden = false;
}

function setPlausibleState(state) {
    localStorage.setItem(planId + "-notification-state-pa", state);
}

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

function subscribePush(registration, isActive) {
    return registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: base64UrlToUint8Array("BDu6tTwQHFlGb36-pLCzwMdgumSlyj_vqMR3I1KahllZd3v2se-LM25vhP3Yv_y0qXYx_KPOVOD2EYTaJaibzo8")
    }).then(subscription => {
        return fetch("api/subscribe-push", {
            method: "post",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({subscription: subscription.toJSON(), selection: selection, is_active: isActive})
        });
    }).then(response => {
        if (!response.ok) {
            throw Error(`Got ${response.status} from server`);
        }
        return response.json();
    }).then(data => {
        if (!data.ok) {
            throw Error("Got ok: False from server");
        }
    });
}


let notificationState;

function setNotificationState(registration, state) {
    notificationState = state;
    if (state !== "failed")
        localStorage.setItem(planId + "-notification-state", notificationState);
    setPlausibleState(state);

    notificationsToggle.checked = notificationState === "granted-and-enabled";
    notificationsToggle.disabled = notificationState === "denied";

    switch (notificationState) {
        case "granted-and-enabled":
            showState("subscribing");
            subscribePush(registration, true)
                .then(() => showState("enabled"))
                .catch(err => {
                    setNotificationState(registration, "failed");
                    reportError(err);
                });
            break;
        case "denied":
            showState("blocked");
            break;
        case "failed":
            showState("failed");
            break;
        default:
        case "default":
        case "granted-and-disabled":
            showState("disabled");
            break;
    }
}

function onNotificationsAvailable(registration) {
    document.getElementById("notifications-not-available-alert").hidden = true;
    document.getElementById("toggle-notifications-wrapper").hidden = false;

    notificationState = window.localStorage.getItem(planId + "-notification-state");

    notificationsToggle.addEventListener("change", () => {
        if (notificationsToggle.checked) {
            Notification.requestPermission()
                .then(permission => {
                    setNotificationState(registration, permission === "granted" ? "granted-and-enabled" : permission);
                });
            plausible("Push Subscription", {props: {[planId]: "Subscribe"}});
        } else {
            if (notificationState === "granted-and-enabled") {
                showState("unsubscribing");
                subscribePush(registration, false)
                    .then(() => {
                        setNotificationState(registration, "granted-and-disabled");
                    }).catch(reason => {
                        setNotificationState(registration, "failed");
                        reportError(reason);
                    });
            }
            plausible("Push Subscription", {props: {[planId]: "Unsubscribe"}})
        }
    });

    function reloadPermissionState() {
        if (!notificationState.startsWith(Notification.permission) && notificationState !== "failed") {
            console.log(notificationState + " changed to " + Notification.permission);
            // permission has been changed
            setNotificationState(registration, Notification.permission === "granted" ? "granted-and-disabled" : Notification.permission);
            return true;
        }
        return false;
    }

    if (!notificationState
        // "failed" is no longer stored in localStorage to prevent notifications from being disabled if the offline
        // page was viewed, but perhaps it's still in there from earlier versions:
        || notificationState === "failed")
        notificationState = "default";
    if (!reloadPermissionState()) {
        setNotificationState(registration, notificationState);
    }

    window.addEventListener("focus", reloadPermissionState);
}


navigator.serviceWorker.register("/sw.js").catch(e => reportError(e));

window.addEventListener("load", () => {
    if (!("serviceWorker" in navigator) || !navigator.serviceWorker) {
        setPlausibleState("unsupported (Service Worker)");
        return;
    }
    navigator.serviceWorker.ready.then(registration => {
        if (!("Notification" in window)) {
            setPlausibleState("unsupported (Notification)");
            return;
        }
        if (!("PushManager" in window)) {
            setPlausibleState("unsupported (PushManager)");
            return;
        }
        onNotificationsAvailable(registration);
    }).catch(e => reportError(e));
});
