const dates = document.getElementsByClassName("date");
const statusContainer = document.getElementById("status-container");
let updateStatusElement = null;
let lastUpdateTime = new Date();


function showUpdateStatus() {
    if (updateStatusElement == null) {
        updateStatusElement = document.createElement("span");
        statusContainer.appendChild(updateStatusElement);
    }
    const diff = (new Date()).getTime() - lastUpdateTime.getTime();
    const diffMinutes = Math.floor(diff / 60000);
    if (diffMinutes === 0) {
        updateStatusElement.textContent = "Zuletzt aktualisiert: gerade eben";
    } else {
        if (diffMinutes === 1) {
            updateStatusElement.textContent = "Zuletzt aktualisiert vor 1 Minute ";
        } else if (diffMinutes < 60) {
            updateStatusElement.textContent = "Zuletzt aktualisiert vor " + diffMinutes + " Minuten ";
        } else {
            const diffHours = Math.floor(diff / 3600000);
            if (diffHours === 1) {
                updateStatusElement.textContent = "Zuletzt aktualisiert vor 1 Stunde ";
            } else if (diffHours < 24) {
                updateStatusElement.textContent = "Zuletzt aktualisiert vor " + diffHours + " Stunden ";
            } else {
                updateStatusElement.textContent = "Zuletzt aktualisiert: " + lastUpdateTime.getDate() + "." + (lastUpdateTime.getMonth() + 1) + "." + lastUpdateTime.getFullYear() + " " + lastUpdateTime.getHours() + ":" + lastUpdateTime.getMinutes() + " ";
            }
        }
        const d1 = document.createElement("a");
        d1.textContent = "Jetzt aktualisieren";
        d1.onclick = update;
        updateStatusElement.appendChild(d1);
    }
}

let updateInterval = setInterval(showUpdateStatus, 60000);
showUpdateStatus();


function greySubstitutions() {
    const now = new Date();
    if (dates.length > 0 && dates[0].innerHTML === ", " + now.getDate() + "." + (now.getMonth() + 1) + "." + now.getFullYear()) {
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

function update() {
    clearInterval(updateInterval);
    updateStatusElement.textContent = "Aktualisiere...";
    if ((new Date).getDate() !== lastUpdateTime.getDate()) {
        window.location.reload();
        return;
    }
    fetch("/", {
        method: "POST"
    })
        .then(function (p) {
            return p.text();
        }).then(function (p) {
            if (!(statusContainer.innerHTML.includes(p))) {
                window.location.reload()
            } else {
                lastUpdateTime = new Date();
                updateInterval = setInterval(showUpdateStatus, 60000);
                showUpdateStatus();
                greySubstitutions();
            }
        }).catch(function () {
            updateStatusElement.textContent = "Aktualisierung fehlgeschlagen ";
            const a1 = document.createElement("a");
            a1.textContent = "Nochmal versuchen";
            a1.onclick = update;
            updateStatusElement.appendChild(a1);
        });
}
window.onfocus = update;
