const onlineStatus = document.getElementById("online-status");

let webSocket = null;
function onOnline() {
    onlineStatus.textContent = "Aktuell";
    onlineStatus.classList.add("online");
    onlineStatus.classList.remove("offline");
}
function onOffline() {
    onlineStatus.textContent = "Keine Verbindung zum Server";
    onlineStatus.classList.add("offline");
    onlineStatus.classList.remove("online");
}
function createWebSocket(openCallback=null) {
    webSocket = new WebSocket(
        (window.location.protocol === "http:" ? "ws:" : "wss:") + "//" +
        window.location.host + window.location.pathname + "api/wait-for-updates");

    webSocket.addEventListener("open", event => {
        console.log("WebSocket opened", event);
        onOnline();
        if (openCallback)
            openCallback();
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
            case "new_substitutions":
                window.location.reload();
                break;
            default:
                console.warn("Unknown WebSocket message type");
                break;
        }
    });
}
createWebSocket();

function updateWebSocket() {
    // Send status to server. The server checks whether the status is still up-to-date. If not, it sends a
    // message, and thus the page is reloaded.
    if (webSocket.readyState === webSocket.OPEN) {
        webSocket.send(JSON.stringify({type: "check_status", status: document.getElementById("status").textContent}));
    } else {
        createWebSocket(() => webSocket.send(JSON.stringify({type: "check_status", status: document.getElementById("status").textContent})));
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
    console.log("offline, closing WebSocket connection");
    onOffline();
    webSocket.close();
});
