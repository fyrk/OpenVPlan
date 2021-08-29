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

const selection = document.getElementById("selectionInput").value;
const planId = window.location.pathname.split("/", 2)[1];

let timetables;
try {
    timetables = JSON.parse(window.localStorage.getItem(planId + "-timetables"));
    if (!timetables)
        timetables = {};
} catch {
    timetables = {};
}

const timetablesBlock = document.getElementById("timetables-block");
if (selection) {
    const substitutions = {};
    for (let substitutionsBox of document.getElementsByClassName("substitutions-box")) {
        const tableBody = substitutionsBox.querySelector(".substitutions-table tbody");
        if (tableBody) {
            const dayName = substitutionsBox.querySelector(".day-name").textContent;
            /** @type {String} */
            let groupName = null;
            let groupSubstitutions = [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}];
            function newGroupSubstitutions() {
                let groupLetterPart;
                let groupNumberPart;
                const affectedGroups = [];
                let match = groupName.match(/^(\d+)([A-Za-z]*)$/);
                if (match != null) {
                    groupNumberPart = match[1];
                    groupLetterPart = match[2].toUpperCase();
                } else {
                    groupNumberPart = "";
                    groupLetterPart = groupName.toUpperCase();
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
                    s = s.toUpperCase();
                    for (let g of affectedGroups) {
                        if (g.includes(s)) {
                            matchingSelections.push(s);
                            break;
                        }
                    }
                }
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
                    if (1 <= lesson && lesson <= 10) {
                        if (teacherName in groupSubstitutions[lesson - 1])
                            groupSubstitutions[lesson - 1][teacherName].push(row);
                        else
                            groupSubstitutions[lesson - 1][teacherName] = [row];
                    }
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
        let sUpper = s.toUpperCase();
        if (!(sUpper in timetables)) {
            timetables[sUpper] = [
                Array(10).fill(""),
                Array(10).fill(""),
                Array(10).fill(""),
                Array(10).fill(""),
                Array(10).fill("")
            ];
        }
        const timetable = timetableTemplate.content.firstElementChild.cloneNode(true);
        timetablesContainer.appendChild(timetable);
        timetable.querySelectorAll(".timetable-selection").forEach(e => e.innerText = s);
        timetable.querySelector(".share-timetable-button").addEventListener("click", () => {
            const shareTimetableBlock = timetable.querySelector(".share-timetable-block");
            if (shareTimetableBlock.hidden) {
                const linkInput = shareTimetableBlock.querySelector(".timetable-link-input");
                const copyButton = shareTimetableBlock.querySelector(".copy-timetable-link");
                let timetableStr = "";
                for (let day=0; day<5; day++) {
                    for (let lesson=0; lesson<10; lesson++) {
                        let teacher = timetables[sUpper][day][lesson];
                        if (!teacher) {
                            timetableStr += "   ";
                        } else {
                            if (teacher.length > 3) {
                                // shouldn't usually happen
                                teacher = teacher.substr(0, 3);
                            }
                            timetableStr += teacher + " ".repeat(3 - teacher.length);  // make it 3 characters long
                        }
                    }
                }
                linkInput.value = new URL("/" + planId + "/#timetable:" + sUpper + ":" + btoa(timetableStr), window.location.origin).href;
                linkInput.addEventListener("click", e => e.target.select());
                let copyTimeout = null;
                copyButton.addEventListener("click", () => {
                    function resetButton() {
                        if (copyTimeout != null)
                            clearTimeout(copyTimeout);
                        copyTimeout = setTimeout(() => {
                            copyButton.classList.remove("copied");
                            copyButton.classList.remove("copying-failed");
                            copyButton.title = "Kopieren";
                            copyTimeout = null;
                        }, 2000);
                    }

                    navigator.clipboard.writeText(linkInput.value).then(() => {
                        copyButton.classList.add("copied");
                        copyButton.title = "Kopiert!";
                        resetButton();
                        plausible("Timetable: Copy Link");
                    }).catch(() => {
                        copyButton.classList.add("copying-failed");
                        copyButton.title = "Kopieren fehlgeschlagen";
                        resetButton();
                    });
                });
                shareTimetableBlock.hidden = false;
            } else {
                shareTimetableBlock.hidden = true;
            }
        });
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
                input.id = "timetable-" + sUpper + "-" + weekday + "-" + lessonNum;
                const weekdayName = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"][weekday];
                input.setAttribute("type", "text");
                input.setAttribute("autocapitalize", "characters");
                input.setAttribute("autocomplete", "off");
                input.setAttribute("autocorrect", "off");
                input.setAttribute("spellcheck", "false");
                input.setAttribute("enterkeyhint", weekday === 4 && lessonNum === 10 ? "done" : "next");
                input.setAttribute("maxlength", "3");
                input.setAttribute("aria-label", `${lessonNum}. Stunde ${weekdayName}`);
                input.addEventListener("focus", e => e.target.select());
                input.addEventListener("input", e => {
                    // noinspection JSUnresolvedVariable
                    setRelevant(e.target, e.target.dataset.oldvalue, false);
                    // noinspection JSUnresolvedVariable
                    setRelevant(e.target);
                    // noinspection JSUnresolvedVariable
                    e.target.dataset.oldvalue = e.target.value;
                    // noinspection JSUnresolvedVariable
                    timetables[e.target.dataset.selection]
                        [parseInt(e.target.dataset.weekday)]
                        [parseInt(e.target.dataset.lesson)-1] = e.target.value.toUpperCase();
                    window.localStorage.setItem(planId + "-timetables", JSON.stringify(timetables));
                });
                input.dataset.selection = sUpper;
                // noinspection JSValidateTypes
                input.dataset.weekday = weekday;
                input.dataset.weekdayName = weekdayName;
                // noinspection JSValidateTypes
                input.dataset.lesson = lessonNum;
                let teacher = timetables[sUpper][weekday][lessonNum-1];
                if (teacher) {
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
                    if (weekday >= 5) {
                        currentInput.blur();
                        return false;
                    }
                    lesson = 1;
                }
                document.getElementById("timetable-" + currentInput.dataset.selection + "-" + weekday + "-" + lesson).focus();
                return true;
            }

            function focusNextWeekday(currentInput, direction) {
                let weekday = parseInt(currentInput.dataset.weekday);
                let lesson = parseInt(currentInput.dataset.lesson);
                weekday += direction;
                if (0 <= weekday && weekday <= 4) {
                    document.getElementById("timetable-" + currentInput.dataset.selection + "-" + weekday + "-" + lesson).focus();
                    return true;
                }
                return false;
            }

            tbody.addEventListener("keydown", e => {
                switch (e.key) {
                    case "Tab":
                    case "Enter":
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
