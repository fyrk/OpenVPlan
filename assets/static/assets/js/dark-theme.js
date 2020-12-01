const darkThemeBlock = document.getElementById("dark-theme-block");
const darkThemeBlockTemplate = document.getElementById("dark-theme-block-template");
darkThemeBlock.appendChild(darkThemeBlockTemplate.content);
const systemDefaultRadio = document.getElementById("dark-theme-system-default");
const lightRadio = document.getElementById("dark-theme-light");
const darkRadio = document.getElementById("dark-theme-dark");
function applyThemeSetting(setting) {
    localStorage.setItem("dark-theme", setting);
    switch (setting) {
        case "system-default":
            for (let s of document.getElementsByClassName("dark-stylesheet"))
                s.setAttribute("media", "(prefers-color-scheme: dark)");
            document.querySelector('meta[name="color-scheme"]').setAttribute("content", "light dark");
            break;
        case "light":
            for (let s of document.getElementsByClassName("dark-stylesheet"))
                s.setAttribute("media","none");
            document.querySelector('meta[name="color-scheme"]').setAttribute("content","light");
            break;
        case "dark":
            for (let s of document.getElementsByClassName("dark-stylesheet"))
                s.removeAttribute("media");
            document.querySelector('meta[name="color-scheme"]').setAttribute("content", "dark")
            break;
    }
}
switch (localStorage.getItem("dark-theme")) {
    case "light":
        lightRadio.checked = true;
        break;
    case "dark":
        darkRadio.checked = true;
}
systemDefaultRadio.addEventListener("change", () => applyThemeSetting("system-default"));
lightRadio.addEventListener("change", () => applyThemeSetting("light"));
darkRadio.addEventListener("change", () => applyThemeSetting("dark"));
if (localStorage.getItem("has-seen-dark-theme-news") !== "true") {
    const main = document.getElementById("main");
    main.insertBefore(document.getElementById("template-news-dark-theme").content, main.firstElementChild);
    document.getElementById("news-dark-theme-close").addEventListener("click", () => {
        document.getElementById("news-dark-theme").remove();
        localStorage.setItem("has-seen-dark-theme-news", "true");
    })
}
