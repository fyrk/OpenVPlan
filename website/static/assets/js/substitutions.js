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
                    x.classList.add("text-muted");
                }
            } else {
                setTimeout(greySubstitutions, new Date(now.getFullYear(), now.getMonth(), now.getDate(), i[1], i[2]).getTime() - now.getTime());
                break
            }
        }
    }
}

greySubstitutions();
