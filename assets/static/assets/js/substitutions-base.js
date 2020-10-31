window.addEventListener("error", e => {
    const error = {type: Object.getPrototypeOf(e.error).name};
    Object.getOwnPropertyNames(e.error).forEach(p => error[p] = e.error[p]);
    fetch("/api/report-error", {
        method: "post",
        body: new URLSearchParams({message: e.message, filename: e.filename, lineno: e.lineno, colno: e.colno, error: JSON.stringify(error)})
    })
});

const substitutionPlanType = window.location.pathname.split("/", 2)[1];
const selection = document.getElementById("selectionInput").value;
