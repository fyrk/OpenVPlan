// ==================
// GREY SUBSTITUTIONS
try {
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
} catch (e) {
    console.error(e);
}
let substitutionPlanType = window.location.pathname.split("/", 2)[1];


// ============
// PUSH NOTIFICATIONS

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
                        console.error("Push subscription failed", data);
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

function setNotificationsInfo(state, registration) {
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
        } else {
            if (notificationState === "granted-and-enabled") {
                setNotificationsInfo("granted-and-disabled", registration);
            }
        }
    });

    function reloadPermissionState() {
        if (!notificationState.startsWith(Notification.permission)) {
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
    if (notificationState == null)
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
                if (!("Notification" in window)) {
                    console.warn("Notification is not supported");
                    return;
                }
                if (!("localStorage" in window)) {
                    console.warn("localStorage is not supported");
                    return;
                }
                if (!("PushManager" in window)) {
                    console.warn("PushManager is not supported");
                    return;
                }
                onNotificationsAvailable(registration);
            });
        navigator.serviceWorker.register("/sw.min.js")
            .then(registration => {
                console.log("ServiceWorker registration successful:", registration);
            }).catch(reason => console.warn("ServiceWorker registration failed:", reason))
    });
} else {
    console.warn("serviceWorker is not supported");
}


// =================
// WEBSOCKET UPDATES

try {
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
} catch (e) {
    console.error(e);
}


// =================
// TIMETABLES

const selection = document.getElementById("selectionInput").value;

try {
    let timetables;
    try {
        timetables = JSON.parse(window.localStorage.getItem(substitutionPlanType + "-timetables"));
        if (!timetables)
            timetables = {};
    } catch (SyntaxError) {
        timetables = {};
    }

    const timetablesBlock = document.getElementById("timetables-block");
    if (timetablesBlock != null && selection) {
        const substitutions = {};
        for (let substitutionsBox of document.getElementsByClassName("substitutions-box")) {
            const tableBody = substitutionsBox.querySelector(".substitutions-table tbody");
            if (tableBody) {
                const dayName = substitutionsBox.querySelector(".day-name").textContent;
                let groupName = null;
                let groupSubstitutions = [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}];
                function newGroupSubstitutions() {
                    let groupLetterPart;
                    let groupNumberPart;
                    const affectedGroups = [];
                    let match = groupName.match(/^(\d+)([A-Za-z]*)$/);
                    if (match != null) {
                        groupNumberPart = match[1];
                        groupLetterPart = match[2];
                    } else {
                        groupNumberPart = "";
                        groupLetterPart = groupName;
                    }
                    if (groupNumberPart !== "") {
                        if (groupLetterPart !== "") {
                            for (let letter of groupLetterPart) {
                                affectedGroups.push(groupNumberPart + letter);
                            }
                        } else {
                            affectedGroups.push(groupNumberPart);
                        }
                    } else {
                        affectedGroups.push(groupLetterPart);
                    }
                    let matchingSelections = [];
                    for (let s of selection.split(", ")) {
                        for (let g of affectedGroups) {
                            if (g.includes(s)) {
                                matchingSelections.push(s);
                                break;
                            }
                        }
                    }
                    console.log(groupName, affectedGroups, matchingSelections);
                    for (let s of matchingSelections) {
                        if (!(s in substitutions)) {
                            substitutions[s] = {};
                        }
                        if (dayName in substitutions[s]) {
                            for (let l = 0; l<10; l++) {
                                substitutions[s][dayName][l] = Object.assign(substitutions[s][dayName][l], groupSubstitutions[l]);
                            }
                        } else {
                            substitutions[s][dayName] = groupSubstitutions;
                        }
                    }
                }
                for (let row of tableBody.children) {
                    let groupNameCell = row.querySelector(".group-name");
                    let teacherName;
                    let lessonString;
                    if (groupNameCell != null) {
                        if (groupName != null)
                            newGroupSubstitutions();
                        groupSubstitutions = [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}];
                        groupName = groupNameCell.textContent;
                        teacherName = row.children[1].textContent.toUpperCase();
                        lessonString = row.children[3].textContent;
                    } else {
                        teacherName = row.children[0].textContent.toUpperCase();
                        lessonString = row.children[2].textContent;
                    }
                    for (let lesson of lessonString.match(/(\d+)/g)) {
                        lesson = parseInt(lesson);
                        if (teacherName in groupSubstitutions[lesson-1])
                            groupSubstitutions[lesson-1][teacherName].push(row);
                        else
                            groupSubstitutions[lesson-1][teacherName] = [row];
                    }
                }
                if (groupName != null)
                    newGroupSubstitutions();
            }
        }
        console.log(substitutions);

        const timetablesBlockTemplate = document.getElementById("timetables-block-template");
        const timetableTemplate = document.getElementById("timetable-template");
        timetablesBlock.appendChild(timetablesBlockTemplate.content);
        const timetablesContainer = document.getElementById("timetables-container");
        function setRelevant(input, value = null, markRelevant = true) {
            if (!value)
                value = input.value;
            let selection = input.dataset.selection;
            if (selection in substitutions) {
                let s = substitutions[selection];
                let weekdayName = input.dataset.weekdayName;
                if (weekdayName in s) {
                    let teacher = value.toUpperCase();
                    s = s[weekdayName][input.dataset.lesson-1];
                    if (teacher in s) {
                        for (let row of s[teacher]) {
                            if (markRelevant)
                                row.classList.add("is-relevant");
                            else
                                row.classList.remove("is-relevant");
                        }
                    }
                }
            }
        }
        for (let s of selection.split(", ")) {
            if (!(s in timetables)) {
                timetables[s] = [
                    [null, null, null, null, null, null, null, null, null, null],
                    [null, null, null, null, null, null, null, null, null, null],
                    [null, null, null, null, null, null, null, null, null, null],
                    [null, null, null, null, null, null, null, null, null, null],
                    [null, null, null, null, null, null, null, null, null, null],
                ];
            }
            const timetable = timetableTemplate.content.firstElementChild.cloneNode(true);
            timetablesContainer.appendChild(timetable);
            timetable.querySelector(".timetable-selection").innerText = s;
            const tbody = timetable.querySelector("tbody");
            for (let lessonNum = 1; lessonNum < 11; lessonNum++) {
                const row = document.createElement("tr");
                tbody.appendChild(row);
                const th = document.createElement("th");
                row.appendChild(th);
                th.innerText = lessonNum + ".";
                for (let weekday = 0; weekday < 5; weekday++) {
                    const cell = document.createElement("td");
                    row.appendChild(cell);
                    const input = document.createElement("input");
                    cell.appendChild(input);
                    input.classList.add("form-control", "form-control-sm");
                    input.id = s + "-" + weekday + "-" + lessonNum;
                    const weekdayName = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"][weekday];
                    input.setAttribute("type", "text");
                    input.setAttribute("maxlength", "3");
                    input.setAttribute("aria-label", `${lessonNum}. Stunde ${weekdayName}`);
                    input.addEventListener("focus", e => e.target.select());
                    input.addEventListener("input", e => {
                        // noinspection JSUnresolvedVariable
                        setRelevant(e.target, e.target.dataset.oldvalue, false);
                        // noinspection JSUnresolvedVariable
                        setRelevant(e.target);
                        // noinspection JSUnresolvedVariable
                        timetables[e.target.dataset.selection]
                            [parseInt(e.target.dataset.weekday)]
                            [parseInt(e.target.dataset.lesson)-1] = e.target.value.toUpperCase();
                        window.localStorage.setItem(substitutionPlanType + "-timetables", JSON.stringify(timetables));
                    });
                    input.dataset.selection = s;
                    input.dataset.weekday = weekday;
                    input.dataset.weekdayName = weekdayName;
                    input.dataset.lesson = lessonNum;
                    let teacher = timetables[s][weekday][lessonNum-1];
                    if (teacher != null) {
                        input.value = teacher;
                        input.dataset.oldvalue = teacher;
                        setRelevant(input);
                    } else {
                        input.dataset.oldvalue = "";
                    }
                }

                function focusNextLesson(currentInput, direction) {
                    let weekday = parseInt(currentInput.dataset.weekday);
                    let lesson = parseInt(currentInput.dataset.lesson);
                    lesson += direction;
                    if (lesson < 1) {
                        weekday--;
                        if (weekday < 0)
                            return false;
                        lesson = 10;
                    } else if (lesson > 10) {
                        weekday++;
                        if (weekday >= 5)
                            return false;
                        lesson = 1;
                    }
                    document.getElementById(currentInput.dataset.selection + "-" + weekday + "-" + lesson).focus();
                    return true;
                }

                function focusNextWeekday(currentInput, direction) {
                    let weekday = parseInt(currentInput.dataset.weekday);
                    let lesson = parseInt(currentInput.dataset.lesson);
                    weekday += direction;
                    if (0 <= weekday && weekday <= 4) {
                        document.getElementById(currentInput.dataset.selection + "-" + weekday + "-" + lesson).focus();
                        return true;
                    }
                    return false;
                }

                tbody.addEventListener("keydown", e => {
                    switch (e.key) {
                        case "Tab":
                            if (focusNextLesson(e.target, e.shiftKey ? -1 : 1))
                                e.preventDefault();
                            break;
                        case "ArrowDown":
                            if (focusNextLesson(e.target, 1))
                                e.preventDefault();
                            break;
                        case "ArrowUp":
                            if (focusNextLesson(e.target, -1))
                                e.preventDefault();
                            break;
                        case "ArrowLeft":
                            // noinspection JSUnresolvedVariable
                            if (e.target.selectionStart === 0 &&
                                (e.target.selectionEnd === 1 || e.target.selectionEnd === 0))
                                if (focusNextWeekday(e.target, -1))
                                    e.preventDefault();
                            break;
                        case "ArrowRight":
                            // noinspection JSUnresolvedVariable
                            if (e.target.selectionStart === e.target.selectionEnd)
                                if (focusNextWeekday(e.target, 1))
                                    e.preventDefault();
                            break;
                    }
                });
                tbody.addEventListener("input", e => {
                    // noinspection JSUnresolvedVariable
                    if (e.target.value.length >= e.target.maxLength) {
                        focusNextLesson(e.target, 1);
                    }
                });
            }
        }
    }
} catch (e) {
    console.error(e);
}
