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
