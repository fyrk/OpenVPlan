const a = [
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
];

const b = document.getElementsByClassName("date");
const c = document.getElementById("status-container");
let d = null;
let e = new Date();

function f1() {
    if (d == null) {
        d = document.createElement("span");
        c.appendChild(d);
    }
    const a1 = (new Date()).getTime() - e.getTime();
    const b1 = Math.floor(a1 / 60000);
    if (b1 === 0) {
        d.textContent = "Zuletzt aktualisiert: gerade eben";
    } else {
        if (b1 === 1) {
            d.textContent = "Zuletzt aktualisiert vor 1 Minute ";
        } else if (b1 < 60) {
            d.textContent = "Zuletzt aktualisiert vor " + b1 + " Minuten ";
        } else {
            const c1 = Math.floor(a1 / 3600000);
            if (c1 === 1) {
                d.textContent = "Zuletzt aktualisiert vor 1 Stunde ";
            } else if (c1 < 24) {
                d.textContent = "Zuletzt aktualisiert vor " + c1 + " Stunden ";
            } else {
                d.textContent = "Zuletzt aktualisiert: " + e.getDate() + "." + (e.getMonth() + 1) + "." + e.getFullYear() + " " + e.getHours() + ":" + e.getMinutes() + " ";
            }
        }
        const d1 = document.createElement("a");
        d1.href = "#";
        d1.textContent = "Jetzt aktualisieren";
        d1.onclick = f3;
        d.appendChild(d1);
    }
}

let f = setInterval(f1, 60000);
f1();



function f2() {
    const a2 = new Date();
    if (b.length > 0 && b[0].innerHTML === ", " + a2.getDate() + "." + (a2.getMonth() + 1) + "." + a2.getFullYear()) {
        const b2 = a2.getHours();
        const c2 = a2.getMinutes();
        for (let i of a) {
            if (i[1] < b2 || (i[1] === b2 && i[2] <= c2)) {
                [].forEach.bind(document.getElementsByClassName("lesson" + i[0]), function (p) {
                    p.classList.add("grey")
                })()
            } else {
                setTimeout(f2, new Date(a2.getFullYear(), a2.getMonth(), a2.getDate(), i[1], i[2]).getTime() - a2.getTime());
                break
            }
        }
    }
}
f2();

function f3() {
    clearInterval(f);
    d.textContent = "Aktualisiere...";
    if ((new Date).getDate() !== e.getDate()) {
        console.log("date changed");
        return;
    }
    fetch("/api/last-status")
        .then(function (p) {
            return p.text();
        }).then(function (p) {
            if (!(c.innerHTML.includes(p))) {
                window.location.reload()
            } else {
                e = new Date();
                f = setInterval(f1, 60000);
                f1();
                f2();
            }
        }).catch(function () {
            d.textContent = "Aktualisierung fehlgeschlagen ";
            const a1 = document.createElement("a");
            a1.href = "#";
            a1.textContent = "Nochmal versuchen";
            a1.onclick = f3;
            d.appendChild(a1);
        });
}
window.onfocus = f3;
