/*
 * OpenVPlan
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

function reportError(error, event = null) {
    try {
        const name = error.name;
        const message = (event == null ? undefined : event.message) ||
            error.message;
        const description = error.description;  // non-standard Microsoft property
        const number = error.number; // non-standard Microsoft property
        const filename = (event == null ? undefined : event.filename) ||
            error.fileName;  // error.fileName is non-standard Mozilla property
        const lineno = (event == null ? undefined : event.lineno) ||
            error.lineNumber;  // error.lineNumber is non-standard Mozilla property
        const colno = (event == null ? undefined : event.colno) ||
            error.columnNumber;  // error.columnNumber is non-standard Mozilla property
        const stack = (event == null ? undefined : event.stack) ||
            error.stack;  // error.stack is non-standard Mozilla property
        const key = (name || "Generic Error") + ": " + message;
        const value = stack + " - " + filename + ":" + lineno + ":" + colno + " " + description + " " + number;
        console.log("report error", key, value);
        plausible("JavaScript Error", {
            props: { [key]: value }
        });
    } catch (e) {
        console.error("reporting error failed", e);
    }
}

window.addEventListener("error", e => reportError(e.error, e));  // e.error is experimental, according to MDN
window.addEventListener("unhandledrejection", e => reportError(e.reason));


const planId = window.location.pathname.split("/", 2)[1];
const selection = document.getElementById("selectionInput").value;

// GET TIMETABLE FROM URL
// The following is not in timetables.js so that it works even with no selection
const timetablesBlock = document.getElementById("timetables-block");
if (timetablesBlock)
    timetablesBlock.hidden = false;
if (window.location.hash.startsWith("#timetable:")) {
    try {
        let [, group, timetableStr] = window.location.hash.split(":");
        timetableStr = atob(timetableStr);
        let valid = true;
        let timetable;
        if (timetableStr.length !== 3 * 10 * 5) {  // 3 chars per lesson, 10 lessons per day, 5 days
            console.warn("Timetable in URL has wrong length:", timetableStr.length, "instead of", 3 * 10 * 5, timetableStr);
            valid = false;
        } else {
            timetable = [];
            for (let day = 0; day < 5; day++) {
                let lessons = [];
                timetable.push(lessons);
                for (let lesson = 0; lesson < 10; lesson++) {
                    let teacher = timetableStr.substr(day * 10 * 3 + lesson * 3, 3).trim();
                    lessons.push(teacher);
                }
            }
        }
        if (valid) {
            let timetables;
            try {
                timetables = JSON.parse(window.localStorage.getItem(planId + "-timetables"));
                if (!timetables)
                    timetables = {};
            } catch {
                timetables = {};
            }
            group = group.toUpperCase();
            let text = (group in timetables) ?
                ("Die aufgerufene URL enthält einen Stundenplan für " + group + ". Soll der aktuell gespeicherte Stundenplan für " + group + " durch diesen ersetzt werden?")
                : ("Die aufgerufene URL enthält einen Stundenplan für " + group + ". Diesen Stundenplan setzen?");
            if (!selection) {
                text += " Achtung: Der Stundenplan wird erst angewendet, wenn Vertretungen ausgewählt sind.";
            } else {
                let isSelected = false;
                for (let s of selection.split(", ")) {
                    if (s.toUpperCase() === group) {
                        isSelected = true;
                        break;
                    }
                }
                if (!isSelected) {
                    text += " Achtung: Der Stundenplan wird erst angewendet, wenn " + group + " auch ausgewählt ist.";
                }
            }
            if (confirm(text)) {
                timetables[group] = timetable;
                window.localStorage.setItem(planId + "-timetables", JSON.stringify(timetables));
            }
            window.location.hash = "";
            plausible("Timetable: Set From Link");
        }
    } catch (e) {
        console.error("Error while retrieving timetable from URL", e);
        reportError(e);
    }
}
