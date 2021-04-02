document.getElementById("themes-block").appendChild(document.getElementById("themes-block-template").content);

const html = document.documentElement;
const systemDefaultRadio = document.getElementById("themes-system-default");
const lightRadio = document.getElementById("themes-light");
const darkRadio = document.getElementById("themes-dark");
function applyThemeSetting(setting) {
    localStorage.setItem("theme", setting);
    switch (setting) {
        case "system-default":
            html.classList.remove("light", "dark");
            break;
        case "light":
            html.classList.add("light");
            html.classList.remove("dark");
            break;
        case "dark":
            html.classList.add("dark");
            html.classList.remove("light");
            break;
    }
}
switch (localStorage.getItem("theme")) {
    case "light":
        lightRadio.checked = true;
        break;
    case "dark":
        darkRadio.checked = true;
}
systemDefaultRadio.addEventListener("change", () => applyThemeSetting("system-default"));
lightRadio.addEventListener("change", () => applyThemeSetting("light"));
darkRadio.addEventListener("change", () => applyThemeSetting("dark"));
