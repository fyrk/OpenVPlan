function reportError(error, event=null) {
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
            stack: (event == null ? undefined : event.stack) || error.stack,  // error.stack is non-standard Mozilla property
            user_agent: navigator.userAgent
        })
    })
}

window.addEventListener("error", e => {
    reportError(e.error, e);  // e.error is experimental, according to MDN
});

window.addEventListener("unhandledrejection", e => {
    console.log("unhandledrejection", e);
    reportError(e.reason);
});

const substitutionPlanType = window.location.pathname.split("/", 2)[1];
const selection = document.getElementById("selectionInput").value;
