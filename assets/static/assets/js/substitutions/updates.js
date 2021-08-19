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

const onlineStatus = document.getElementById("online-status");

let webSocket = null;

function onOnline() {
    onlineStatus.textContent = "Aktuell";
    onlineStatus.classList.add("online");
    onlineStatus.classList.remove("offline", "updating");
}
function onOffline() {
    onlineStatus.textContent = "Offline";
    onlineStatus.classList.add("offline");
    onlineStatus.classList.remove("online", "updating");
}
function onUpdating() {
    onlineStatus.textContent = "Aktualisiere...";
    onlineStatus.classList.add("updating");
    onlineStatus.classList.remove("online", "offline");
}
function createWebSocket(openCallback=null) {
    webSocket = new WebSocket(
        (window.location.protocol === "http:" ? "ws:" : "wss:") + "//" +
        window.location.host + window.location.pathname + "api/wait-for-updates");

    webSocket.addEventListener("open", event => {
        console.log("WebSocket opened", event);
        onOnline();
        if (openCallback)
            openCallback(event.target);
    });
    webSocket.addEventListener("close", event => {
        console.log("WebSocket closed", event);
        onOffline();
    });
    webSocket.addEventListener("message", event => {
        const msg = JSON.parse(event.data);
        console.log("WebSocket message", msg);
        switch (msg.type) {
            /*case "heartbeat":
                clearTimeout(disconnectTimeout);
                break;*/
            case "status":
                let status = msg.status;
                if (status) {
                    if (status === document.getElementById("status").textContent)
                        onOnline();
                    else
                        window.location.reload();
                }
                break;
            default:
                console.warn("Unknown WebSocket message type", msg.type);
                break;
        }
    });
}
createWebSocket();

function updateWebSocket() {
    onUpdating();
    // Request current status from server
    if (webSocket.readyState === webSocket.OPEN) {
        webSocket.send(JSON.stringify({type: "get_status"}));
    } else {
        createWebSocket(ws => ws.send(JSON.stringify({type: "get_status"})));
    }
}

window.addEventListener("focus", () => {
    console.log("focus, checking for new substitutions");
    updateWebSocket();
});
window.addEventListener("online", () => {
    console.log("online, checking for new substitutions");
    updateWebSocket();
});
window.addEventListener("offline", () => {
    console.log("offline");
    onOffline();
});
