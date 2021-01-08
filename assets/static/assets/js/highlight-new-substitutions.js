let seenSubstitutions;
let status = document.getElementById("status").textContent;
try {
    seenSubstitutions = JSON.parse(window.localStorage.getItem(substitutionPlanType + "-seen-substitutions"));
    if (seenSubstitutions["status"] !== status) {
        let currentTime = Date.now();
        for (let time of Object.keys(seenSubstitutions["seenSubstitutions"])) {
            if (time <= currentTime) {
                delete seenSubstitutions["seenSubstitutions"][time];
            }
        }
        for (let [time, substitutions] of Object.entries(seenSubstitutions["newSubstitutions"])) {
            if (time > currentTime) {
                if (time in seenSubstitutions["seenSubstitutions"]) {
                    seenSubstitutions["seenSubstitutions"][time].push(...substitutions);
                } else {
                    seenSubstitutions["seenSubstitutions"][time] = substitutions;
                }
            }
        }
        seenSubstitutions["newSubstitutions"] = {};
        seenSubstitutions["status"] = status;
    }
} catch {
}
if (!seenSubstitutions)
    seenSubstitutions = {"seenSubstitutions": {}, "newSubstitutions": {}, "status": status};

for (let substitutionsBox of document.getElementsByClassName("substitutions-box")) {
    const tableBody = substitutionsBox.querySelector(".substitutions-table tbody");
    if (tableBody) {
        const date = substitutionsBox.querySelector(".date").textContent.trim();
        let [, dd, mm, yyyy] = date.match(/(\d\d?).(\d\d?).(\d\d\d\d)/);
        const date_timestamp = Date.UTC(yyyy, mm-1, dd+1);
        if (!(date_timestamp in seenSubstitutions["seenSubstitutions"]))
            seenSubstitutions["seenSubstitutions"][date_timestamp] = [];
        if (!(date_timestamp in seenSubstitutions["newSubstitutions"]))
            seenSubstitutions["newSubstitutions"][date_timestamp] = [];
        let groupName;
        for (let row of tableBody.children) {
            let groupNameCell = row.querySelector(".group-name");
            if (groupNameCell != null) {
                groupName = groupNameCell.textContent.trim();
            }
            let subs = groupName;
            for (let td of row.children) {
                if (!td.classList.contains(".group-name")) {
                    subs += "#" + td.textContent.trim();
                }
            }
            if (!seenSubstitutions["seenSubstitutions"][date_timestamp].includes(subs)) {
                row.classList.add("new-subs");
                if (!seenSubstitutions["newSubstitutions"][date_timestamp].includes(subs))
                    seenSubstitutions["newSubstitutions"][date_timestamp].push(subs);
            }
        }
    }
}

window.localStorage.setItem(substitutionPlanType + "-seen-substitutions", JSON.stringify(seenSubstitutions));
