/*function reportError(error, event=null) {
    fetch("/api/report-error", {
        method: "post",
        body: new URLSearchParams({
            name: error.name,
            message: (event == null ? undefined : event.message) || error.message,
            description: error.description,  // non-standard Microsoft property
            number: error.number, // non-standard Microsoft property
            filename: (event == null ? undefined : event.filename) || error.fileName,  // error.fileName is non-standard Mozilla property
            lineno: (event == null ? undefined : event.lineno) || error.lineNumber,  // error.lineNumber is non-standard Mozilla property
            colno: (event == null ? undefined : event.colno) || error.columnNumber,  // error.columnNumber is non-standard Mozilla property
            stack: (event == null ? undefined : event.stack) || error.stack  // error.stack is non-standard Mozilla property
        })
    }).catch(reason => console.error("reporting error failed", reason))
}
window.addEventListener("error", e => reportError(e.error, e));  // e.error is experimental, according to MDN
window.addEventListener("unhandledrejection", e => reportError(e.reason));
*/ // TODO (plausible)


const substitutionPlanType = window.location.pathname.split("/", 2)[1];
const selection = document.getElementById("selectionInput").value;

// GET TIMETABLE FROM URL
// The following is not in timetables.js so that it works even with no selection
if (window.location.hash.startsWith("#timetable:")) {
    try {
        let [, group, timetableStr] = window.location.hash.split(":");
        timetableStr = atob(timetableStr);
        let valid = true;
        let timetable;
        if (timetableStr.length !== 3*10*5) {  // 3 chars per lesson, 10 lessons per day, 5 days
            console.warn("Timetable in URL has wrong length:", timetableStr.length, "instead of", 3*10*5, timetableStr);
            valid = false;
        } else {
            timetable = [];
            for (let day = 0; day < 5; day++) {
                let lessons = [];
                timetable.push(lessons);
                for (let lesson = 0; lesson < 10; lesson++) {
                    let teacher = timetableStr.substr(day*10*3+lesson*3, 3).trim();
                    if (teacher === "")
                        teacher = null;
                    lessons.push(teacher);
                }
            }
        }
        if (valid) {
            let timetables;
            try {
                timetables = JSON.parse(window.localStorage.getItem(substitutionPlanType + "-timetables"));
                if (!timetables)
                    timetables = {};
            } catch {
                timetables = {};
            }
            group = group.toUpperCase();
            let text = (group in timetables) ?
                ("Die aufgerufenen URL enthält einen Stundenplan für " + group + ". Soll der aktuell gesetzte Stundenplan für " + group + " durch diesen ersetzt werden?")
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
                window.localStorage.setItem(substitutionPlanType + "-timetables", JSON.stringify(timetables));
            }
            window.location.hash = "";
        }
    } catch (e) {
        console.error("Error while retrieving timetable from URL", e);
        reportError(e);
    }
}
