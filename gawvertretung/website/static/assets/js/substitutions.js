if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.min.js")
        .then((registration) => {
            console.log("Service worker registration succeeded:", registration);
                if ("PushManager" in window) {
                    window.Notification.requestPermission()
                        .then(permission => {
                                // value of permission can be 'granted', 'default', 'denied'

                            if(permission !== 'granted'){
                                throw new Error("Permission not granted for Notification:", permission);
                            }
                        });
                }
        })
        .catch(reason => console.log("Service worker registration failed:", reason));
}

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

let type = window.location.pathname.split(1)[1];
if (!type)
    type = "students"
const socket = new WebSocket("ws://localhost:8080/api/" + type + "/wait-for-update");

socket.onopen = event => {
    console.log("WebSocket open", event);
    onOnline(event);
}
socket.onclose = event => {
    console.log("WebSocket close", event);
    onOffline(event);
}
socket.onmessage = event => {
    const msg = JSON.parse(event.data);
    console.log("onmessage", msg);
    console.log("hello");
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

window.ononline = onOnline;
window.onoffline = onOffline;
