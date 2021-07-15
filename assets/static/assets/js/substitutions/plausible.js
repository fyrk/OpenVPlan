// send features to Plausible
try {
    let theme = localStorage.getItem("theme");
    if (theme === "system-default" || !theme)
        theme = "system-" + ((window.matchMedia &&
            window.matchMedia("(prefers-color-scheme: dark)").matches)
            ? "dark"
            : "light");

    plausible("Features - " + substitutionPlanType, {
        props: {
            Selection: selection ? (selection.match(/,/g) || []).length + 1 : 0,
            Notifications: localStorage.getItem(substitutionPlanType + "-notification-state-all"),
            Theme: theme,
            Timetables: null,  // TODO
        }
    })
} catch (e) {
    console.error(e);
}
